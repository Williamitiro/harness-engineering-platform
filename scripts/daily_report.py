#!/usr/bin/env python3
"""Relatório diário de funcionamento do Harness, lido das sessões locais do Claude Code e do Codex.

Responde, por sessão do dia: em que repositório, se ele tem o Harness, quais skills o agente usou,
se rodou testes (falhou e depois passou? o último passou?), tokens e erros. Só contagens e nomes:
nenhum texto de conversa, comando ou saída entra no relatório.

**Não é benchmark.** Mostra o que os agentes fizeram, não se a qualidade melhorou; para isso existe o R2
(SPEC §6). Ausente é null, nunca 0.

Fontes (somente leitura):
- Claude Code: ~/.claude/projects/<projeto>/<sessão>.jsonl (eventos assistant/user, tool_use/tool_result,
  usage por mensagem da API, deduplicado pelo id da mensagem).
- Codex: ~/.codex/sessions/AAAA/MM/DD/rollout-*.jsonl (session_meta, turn_context, item_completed com
  CommandExecution e exit_code, token_count com o total acumulado da sessão).

Uso:
  python scripts/daily_report.py                 # hoje, em Markdown
  python scripts/daily_report.py --date 2026-11-07 --json
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

EVIDENCE = "OPERATIONAL_LOG_ONLY_NOT_A_BENCHMARK"
SKILL_PATH = re.compile(r"skills/([A-Za-z0-9_.:-]+)/skill\.md", re.I)
TEST_CMD = re.compile(
    r"\b(pytest|unittest|(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+test|vitest|jest|go\s+test|cargo\s+test|"
    r"dotnet\s+test|mvn\s+test|gradle\w*\s+test)\b", re.I)
SHELL_TOOLS = {"Bash", "PowerShell"}


# --- utilidades -----------------------------------------------------------------------------------------------

def local_date(ts: Any) -> dt.date | None:
    if not isinstance(ts, str):
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        return None


def events(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                yield event


def touched_since(path: Path, day: dt.date) -> bool:
    try:
        return dt.datetime.fromtimestamp(path.stat().st_mtime).date() >= day
    except OSError:
        return False


def repo_of(cwd: Any) -> tuple[str | None, bool]:
    """(nome do repositório Git que contém cwd, tem .harness/manifest.json?). Sem Git: (None, False)."""
    if not isinstance(cwd, str) or not cwd:
        return None, False
    if cwd.startswith("file:///"):
        cwd = cwd[len("file:///"):]
    path = Path(cwd)
    if not path.is_absolute():  # relativo seria resolvido contra a pasta de quem roda o relatório
        return None, False
    for candidate in (path, *path.parents):
        git = candidate / ".git"
        try:
            if not git.exists():
                continue
            name = candidate.name
            if git.is_file():  # cópia de trabalho (git worktree): "gitdir: <repo>/.git/worktrees/<cópia>"
                text = git.read_text(encoding="utf-8", errors="replace").strip().replace("\\", "/")
                marker = "/.git/worktrees/"
                if text.startswith("gitdir:") and marker in text:
                    name = Path(text[len("gitdir:"):].strip().split(marker)[0]).name
            # o Harness vale para o que está na cópia aberta, não no checkout principal
            return name, (candidate / ".harness" / "manifest.json").is_file()
        except OSError:
            return None, False
    return None, False


def skills_in(text: str) -> set[str]:
    return {m.group(1) for m in SKILL_PATH.finditer(text.replace("\\", "/"))}


def test_summary(results: list[bool]) -> dict:
    """results: True/False por execução de teste, em ordem."""
    red_green = any(not a and b for i, a in enumerate(results) for b in results[i + 1:])
    return {"runs": len(results), "failed": results.count(False), "red_then_green": red_green,
            "last_passed": results[-1] if results else None}


def new_session(client: str, path: Path) -> dict:
    return {"client": client, "session_id": None, "file": path.name, "client_version": None, "cwd": None,
            "repo": None, "harness_attached": False, "models": [], "skills_used": [],
            "tests": test_summary([]), "tokens": None, "errors": None}


# --- Claude Code ----------------------------------------------------------------------------------------------

def claude_session(path: Path, day: dt.date) -> dict | None:
    s = new_session("claude", path)
    seen_today = False
    pending: dict[str, dict] = {}
    tests: list[bool] = []
    skills: set[str] = set()
    models: list[str] = []
    usage_by_msg: dict[str, dict] = {}
    api_errors = tool_errors = 0
    for e in events(path):
        if local_date(e.get("timestamp")) != day:
            continue
        seen_today = True
        s["session_id"] = s["session_id"] or e.get("sessionId")
        s["cwd"] = e.get("cwd") or s["cwd"]
        s["client_version"] = e.get("version") or s["client_version"]
        msg = e.get("message") if isinstance(e.get("message"), dict) else {}
        if e.get("type") == "assistant":
            if e.get("isApiErrorMessage"):
                api_errors += 1
            model = msg.get("model")
            if isinstance(model, str) and model not in models and not model.startswith("<"):
                models.append(model)
            if isinstance(msg.get("usage"), dict) and msg.get("id"):
                usage_by_msg[msg["id"]] = msg["usage"]
            for block in msg.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name, inp = block.get("name"), block.get("input") if isinstance(block.get("input"), dict) else {}
                if name == "Skill" and isinstance(inp.get("skill"), str):
                    skills.add(inp["skill"])
                elif name == "Read":
                    skills |= skills_in(str(inp.get("file_path", "")))
                elif name in SHELL_TOOLS:
                    cmd = str(inp.get("command", ""))
                    skills |= skills_in(cmd)
                    if TEST_CMD.search(cmd) and block.get("id"):
                        pending[block["id"]] = {"test": True}
        elif e.get("type") == "user":
            for block in msg.get("content") if isinstance(msg.get("content"), list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    if block.get("is_error"):
                        tool_errors += 1
                    if pending.pop(block.get("tool_use_id"), None):
                        tests.append(not block.get("is_error"))
    if not seen_today:
        return None
    s["repo"], s["harness_attached"] = repo_of(s["cwd"])
    s["models"], s["skills_used"], s["tests"] = models, sorted(skills), test_summary(tests)
    if usage_by_msg:
        def total(key: str) -> int:
            return sum(u.get(key) or 0 for u in usage_by_msg.values() if isinstance(u.get(key) or 0, int))
        cached = total("cache_read_input_tokens")
        s["tokens"] = {"input_tokens": total("input_tokens") + cached + total("cache_creation_input_tokens"),
                       "cached_input_tokens": cached, "output_tokens": total("output_tokens"),
                       "reasoning_output_tokens": None}
    s["errors"] = {"api_errors": api_errors, "tool_errors": tool_errors, "aborted_turns": None}
    return s


# --- Codex ----------------------------------------------------------------------------------------------------

def _command_text(item: dict) -> str:
    parsed = item.get("parsed_cmd")
    if isinstance(parsed, list):
        cmds = [str(p.get("cmd", "")) for p in parsed if isinstance(p, dict)]
        if any(cmds):
            return " ; ".join(cmds)
    cmd = item.get("command")
    return " ".join(map(str, cmd)) if isinstance(cmd, list) else str(cmd or "")


def codex_session(path: Path, day: dt.date) -> dict | None:
    s = new_session("codex", path)
    seen_today = False
    tests: list[bool] = []
    skills: set[str] = set()
    models: list[str] = []
    before: dict | None = None
    last_today: dict | None = None
    aborted = task_errors = tool_errors = 0
    for e in events(path):
        typ = e.get("type")
        p = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        when = local_date(e.get("timestamp"))
        if typ == "session_meta":
            s["session_id"] = p.get("id") or p.get("session_id")
            s["client_version"] = p.get("cli_version")
            s["cwd"] = p.get("cwd") or s["cwd"]
        if typ == "event_msg" and p.get("type") == "token_count":
            total = (p.get("info") or {}).get("total_token_usage")
            if isinstance(total, dict):
                if when is not None and when < day:
                    before = total
                elif when == day:
                    last_today = total
        if when != day:
            continue
        seen_today = True
        if typ == "turn_context":
            s["cwd"] = p.get("cwd") or s["cwd"]
            model = p.get("model")
            if isinstance(model, str) and model not in models:
                models.append(model)
        elif typ == "event_msg":
            kind = p.get("type")
            if kind == "turn_aborted":
                aborted += 1
            elif kind == "task_complete" and p.get("error"):
                task_errors += 1
            elif kind == "item_completed":
                item = p.get("item") if isinstance(p.get("item"), dict) else {}
                if item.get("type") in ("CommandExecution", "command_execution"):
                    text = _command_text(item)
                    skills |= skills_in(text)
                    try:
                        code = int(item.get("exit_code"))
                    except (TypeError, ValueError):
                        code = None
                    if code not in (0, None):
                        tool_errors += 1
                    if code is not None and TEST_CMD.search(text):
                        tests.append(code == 0)
    if not seen_today:
        return None
    s["repo"], s["harness_attached"] = repo_of(s["cwd"])
    s["models"], s["skills_used"], s["tests"] = models, sorted(skills), test_summary(tests)
    if last_today is not None:  # total acumulado: o dia é o último do dia menos o último de antes
        def delta(key: str) -> int | None:
            end = last_today.get(key)
            if not isinstance(end, int):
                return None
            start = (before or {}).get(key)
            return end - (start if isinstance(start, int) else 0)
        s["tokens"] = {k: delta(k) for k in
                       ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")}
    s["errors"] = {"api_errors": task_errors, "tool_errors": tool_errors, "aborted_turns": aborted}
    return s


# --- relatório ------------------------------------------------------------------------------------------------

def build_report(day: dt.date, claude_root: Path | None = None, codex_root: Path | None = None) -> dict:
    claude_root = claude_root or Path.home() / ".claude" / "projects"
    codex_root = codex_root or Path.home() / ".codex" / "sessions"
    sessions: list[dict] = []
    for path in sorted(claude_root.glob("*/*.jsonl")) if claude_root.is_dir() else []:
        if touched_since(path, day) and (s := claude_session(path, day)):
            sessions.append(s)
    for path in sorted(codex_root.rglob("rollout-*.jsonl")) if codex_root.is_dir() else []:
        if touched_since(path, day) and (s := codex_session(path, day)):
            sessions.append(s)
    for s in sessions:
        s.pop("cwd", None)  # caminho completo fica fora do relatório; o nome do repositório basta

    n = len(sessions)

    def share(count: int) -> float | None:
        return round(count / n, 3) if n else None

    with_skill = sum(1 for s in sessions if s["skills_used"])
    with_tests = sum(1 for s in sessions if s["tests"]["runs"])
    skill_counts = collections.Counter(k for s in sessions for k in s["skills_used"])
    return {
        "date": day.isoformat(),
        "evidence_level": EVIDENCE,
        "summary": {
            "sessions": n,
            "by_client": dict(collections.Counter(s["client"] for s in sessions)),
            "sessions_in_harness_repos": sum(1 for s in sessions if s["harness_attached"]),
            "sessions_with_skill_use": with_skill,
            "share_with_skill_use": share(with_skill),
            "skill_counts": dict(skill_counts.most_common()),
            "sessions_with_tests": with_tests,
            "share_with_tests": share(with_tests),
            "sessions_red_then_green": sum(1 for s in sessions if s["tests"]["red_then_green"]),
            "sessions_last_test_failed": sum(1 for s in sessions if s["tests"]["last_passed"] is False),
        },
        "sessions": sessions,
        "limits": [
            "Mostra comportamento observado nos registros locais, não ganho de qualidade (isso é o benchmark R2).",
            "Skill 'usada' = invocada pela ferramenta Skill ou SKILL.md lido; não prova que o procedimento foi seguido.",
            "Teste = comando reconhecido (pytest, npm test...); suítes com outro nome não são contadas.",
            "Tokens do Claude somam as mensagens da API do dia; os do Codex são a diferença do total acumulado.",
        ],
    }


def _fmt(value: Any) -> str:
    return "—" if value is None else str(value)


def render_markdown(rep: dict) -> str:
    sm = rep["summary"]
    pct = lambda v: "—" if v is None else f"{v:.0%}"  # noqa: E731
    lines = [
        f"# Relatório diário do Harness — {rep['date']}",
        "",
        "> Relatório de funcionamento: o que os agentes fizeram hoje. **Não é benchmark** e não diz se a "
        "qualidade melhorou.",
        "",
        f"- Sessões: **{sm['sessions']}** ({', '.join(f'{k}: {v}' for k, v in sm['by_client'].items()) or '—'})",
        f"- Em repositórios com o Harness: **{sm['sessions_in_harness_repos']}**",
        f"- Com uso de skill: **{sm['sessions_with_skill_use']}** ({pct(sm['share_with_skill_use'])})"
        + (f" — {', '.join(f'{k} ×{v}' for k, v in sm['skill_counts'].items())}" if sm["skill_counts"] else ""),
        f"- Com testes: **{sm['sessions_with_tests']}** ({pct(sm['share_with_tests'])}); "
        f"falhou e depois passou: {sm['sessions_red_then_green']}; terminou com teste falhando: "
        f"{sm['sessions_last_test_failed']}",
        "",
    ]
    if rep["sessions"]:
        lines += ["| Agente | Repositório | Harness | Skills | Testes (rodadas/falhas) | Vermelho→verde | "
                  "Último teste | Tokens entrada / saída | Erros |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for s in sorted(rep["sessions"], key=lambda x: (x["repo"] or "~", x["client"])):
            t, tok, err = s["tests"], s["tokens"] or {}, s["errors"] or {}
            last = {True: "passou", False: "**falhou**", None: "—"}[t["last_passed"]]
            errs = ", ".join(f"{k}={v}" for k, v in err.items() if v)
            lines.append(
                f"| {s['client']} | {_fmt(s['repo'])} | {'sim' if s['harness_attached'] else 'não'} | "
                f"{', '.join(s['skills_used']) or '—'} | {t['runs']}/{t['failed']} | "
                f"{'sim' if t['red_then_green'] else '—'} | {last} | "
                f"{_fmt(tok.get('input_tokens'))} / {_fmt(tok.get('output_tokens'))} | {errs or '—'} |")
        lines.append("")
    lines += ["**Limites**", ""] + [f"- {x}" for x in rep["limits"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", type=dt.date.fromisoformat, default=dt.date.today(),
                        help="dia (AAAA-MM-DD, fuso local); padrão: hoje")
    parser.add_argument("--json", action="store_true", help="saída JSON em vez de Markdown")
    parser.add_argument("--output", type=Path, help="gravar também neste arquivo")
    parser.add_argument("--claude-root", type=Path, help="padrão: ~/.claude/projects")
    parser.add_argument("--codex-root", type=Path, help="padrão: ~/.codex/sessions")
    args = parser.parse_args(argv)
    rep = build_report(args.date, args.claude_root, args.codex_root)
    text = json.dumps(rep, indent=2, ensure_ascii=False) if args.json else render_markdown(rep)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
