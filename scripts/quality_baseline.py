#!/usr/bin/env python3
"""Linha de base de qualidade e custo por PR, a partir do que já existe: PRs do GitHub e logs locais dos agentes.

Qualidade = defeitos confirmados pela revisão independente depois do merge (linhas da tabela de um PR de achados
que citam o PR de origem). PR fora de qualquer revisão fica com achados null, nunca 0.
Custo = tokens dos logs do Claude Code (~/.claude/projects) e do Codex (~/.codex/sessions) cujo branch é o do PR.
Só leitura. A saída guarda números, branch e modelo; nenhum título ou corpo de PR.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from r2_bench import classify_numstat  # noqa: E402

FINDINGS_TITLE = re.compile(r"achad", re.I)
PR_REF = re.compile(r"#(\d+)")
RANGE = re.compile(r"PRs?\s+(\d+)\s*[–-]\s*(\d+)")
LIST = re.compile(r"PRs?\s+((?:\d+\s*,\s*)+\d+)")
MODEL_LINE = re.compile(r"Modelo\s*/\s*esfor[cç]o\s*:\s*\**\s*([^\n]+)", re.I)
FIELDS = "number,title,body,headRefName,mergedAt,mergeCommit"


# --- PRs ------------------------------------------------------------------------------------------------------------

def table_rows(body: str) -> list[str]:
    """Linhas de dados de tabelas markdown (sem cabeçalho nem separador)."""
    rows, header_seen = [], False
    for line in body.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            header_seen = False
            continue
        if re.fullmatch(r"\|[\s:|-]+\|?", s):
            continue
        if not header_seen:
            header_seen = True
            continue
        rows.append(s)
    return rows


def reviewed_set(text: str) -> set[int]:
    """PRs que uma revisão cobriu, pelas faixas ("PRs 219–243") e listas ("PRs 220, 226") do título/corpo."""
    got: set[int] = set()
    for a, b in RANGE.findall(text):
        got.update(range(int(a), int(b) + 1))
    for group in LIST.findall(text):
        got.update(int(n) for n in re.findall(r"\d+", group))
    return got


def parse_findings_pr(pr: dict) -> dict | None:
    """Achados atribuídos por PR de origem. None se o PR não é de achados."""
    title, body, number = pr.get("title") or "", pr.get("body") or "", pr["number"]
    if not FINDINGS_TITLE.search(title) or title.lower().startswith("docs"):
        return None
    per_origin: Counter = Counter()
    unattributed = 0
    for row in table_rows(body):
        refs = [int(n) for n in PR_REF.findall(row) if int(n) < number]
        if refs:
            per_origin[refs[0]] += 1
        else:
            unattributed += 1
    reviewed = reviewed_set(title + "\n" + body.split("\n\n")[0]) | set(per_origin)
    reviewed |= {int(n) for n in PR_REF.findall(title) if int(n) < number}
    return {"pr": number, "per_origin": dict(per_origin), "unattributed_rows": unattributed,
            "reviewed": sorted(reviewed)}


def model_from_body(body: str) -> str | None:
    m = MODEL_LINE.search(body or "")
    return m.group(1).strip().rstrip(".")[:80] if m else None


def diff_size(files: list[dict]) -> dict:
    docs, rest = 0, []
    for f in files or []:
        path = (f.get("path") or "").replace("\\", "/")
        n = int(f.get("additions") or 0) + int(f.get("deletions") or 0)
        if path.startswith("docs/") or path.endswith(".md"):
            docs += n
        else:
            rest.append(f"{f.get('additions', 0)}\t{f.get('deletions', 0)}\t{path}")
    c = classify_numstat("\n".join(rest))["changed_lines"]
    return {"code": c["code"], "tests": c["tests"], "docs": docs}


# --- logs dos agentes ------------------------------------------------------------------------------------------------

def claude_usage(paths: list[Path]) -> dict[str, dict]:
    """Por branch: tokens das mensagens do assistente (deduplicadas por id), modelos e sessões."""
    out: dict[str, dict] = defaultdict(lambda: {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0,
                                                "models": Counter(), "sessions": set()})
    seen: set[str] = set()
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for raw in lines:
            if '"usage"' not in raw:
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            msg, branch = e.get("message") or {}, e.get("gitBranch")
            usage = msg.get("usage")
            if not branch or not isinstance(usage, dict):
                continue
            key = f"{msg.get('id')}:{e.get('requestId')}"
            if key in seen:
                continue
            seen.add(key)
            row = out[branch]
            row["input"] += int(usage.get("input_tokens") or 0)
            row["cache_write"] += int(usage.get("cache_creation_input_tokens") or 0)
            row["cache_read"] += int(usage.get("cache_read_input_tokens") or 0)
            row["output"] += int(usage.get("output_tokens") or 0)
            if msg.get("model"):
                row["models"][msg["model"]] += 1
            row["sessions"].add(e.get("sessionId") or path.stem)
    return out


def codex_usage(paths: list[Path]) -> dict[str, dict]:
    """Por branch: último total de tokens de cada sessão do Codex, modelo e esforço."""
    out: dict[str, dict] = defaultdict(lambda: {"input": 0, "cached": 0, "output": 0, "models": Counter(),
                                                "sessions": set()})
    for path in paths:
        branch, total, model = None, None, None
        try:
            with path.open(encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    if '"session_meta"' in raw[:200] and branch is None:
                        try:
                            branch = ((json.loads(raw).get("payload") or {}).get("git") or {}).get("branch")
                        except ValueError:
                            pass
                    elif '"turn_context"' in raw[:200] and model is None:
                        try:
                            p = json.loads(raw).get("payload") or {}
                            eff = ((p.get("collaboration_mode") or {}).get("settings") or {}).get("reasoning_effort")
                            model = f"{p.get('model')}/{eff}" if eff else p.get("model")
                        except ValueError:
                            pass
                    elif '"token_count"' in raw:
                        try:
                            info = (json.loads(raw).get("payload") or {}).get("info") or {}
                            total = info.get("total_token_usage") or total
                        except ValueError:
                            pass
        except OSError:
            continue
        if not branch or not total:
            continue
        row = out[branch]
        row["input"] += int(total.get("input_tokens") or 0)
        row["cached"] += int(total.get("cached_input_tokens") or 0)
        row["output"] += int(total.get("output_tokens") or 0)
        if model:
            row["models"][model] += 1
        row["sessions"].add(path.stem)
    return out


# --- montagem -------------------------------------------------------------------------------------------------------

def build(prs: list[dict], claude: dict, codex: dict) -> dict:
    findings = [f for f in (parse_findings_pr(p) for p in prs) if f]
    # Só conta revisão com achados em tabela; sem tabela não há contagem, e o PR revisado fica null (não 0).
    reviewed = {n for f in findings if f["per_origin"] for n in f["reviewed"]}
    uncounted = sorted(f["pr"] for f in findings if not f["per_origin"])
    found: Counter = Counter()
    for f in findings:
        found.update(f["per_origin"])
    finding_prs = {f["pr"] for f in findings}
    records = []
    for pr in sorted(prs, key=lambda p: p["number"]):
        n, branch = pr["number"], pr.get("headRefName")
        cl, cx = claude.get(branch), codex.get(branch)
        records.append({
            "pr": n, "merged_at": pr.get("mergedAt"), "branch": branch,
            "is_findings_fix": n in finding_prs,
            "reviewed": n in reviewed,
            "findings": found.get(n, 0) if n in reviewed else None,
            "declared_model": model_from_body(pr.get("body") or ""),
            "lines": diff_size(pr.get("files") or []),
            "claude": None if not cl else {k: cl[k] for k in ("input", "cache_write", "cache_read", "output")}
            | {"models": dict(cl["models"]), "sessions": len(cl["sessions"])},
            "codex": None if not cx else {k: cx[k] for k in ("input", "cached", "output")}
            | {"models": dict(cx["models"]), "sessions": len(cx["sessions"])},
        })
    summary = summarize(records)
    summary["findings_prs_without_table"] = uncounted
    return {"records": records, "findings_prs": findings, "summary": summary}


def median(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.median(vals) if vals else None


def summarize(records: list[dict]) -> dict:
    work = [r for r in records if not r["is_findings_fix"]]
    rev = [r for r in work if r["reviewed"]]
    rev_code = [r for r in rev if r["lines"]["code"] > 0]
    with_claude = [r for r in work if r["claude"]]
    by_model: dict[str, list] = defaultdict(list)
    for r in rev:
        if r["claude"]:
            top = max(r["claude"]["models"], key=r["claude"]["models"].get) if r["claude"]["models"] else None
            by_model[top or "desconhecido"].append(r)
    return {
        "prs_total": len(records), "prs_work": len(work), "prs_findings_fix": len(records) - len(work),
        "reviewed": len(rev),
        "reviewed_with_findings": sum(1 for r in rev if r["findings"]),
        "findings_total": sum(r["findings"] for r in rev),
        "findings_per_reviewed_pr": round(sum(r["findings"] for r in rev) / len(rev), 2) if rev else None,
        "reviewed_with_code": len(rev_code),
        "findings_per_reviewed_code_pr": round(sum(r["findings"] for r in rev_code) / len(rev_code), 2)
        if rev_code else None,
        "token_coverage": {"claude": len(with_claude), "codex": sum(1 for r in work if r["codex"]),
                           "of": len(work)},
        "median_claude_output_per_pr": median([r["claude"]["output"] for r in with_claude]),
        "median_claude_input_uncached_per_pr": median([r["claude"]["input"] + r["claude"]["cache_write"]
                                                       for r in with_claude]),
        "median_code_lines_per_pr": median([r["lines"]["code"] for r in work]),
        "reviewed_by_main_claude_model": {m: {"prs": len(rs), "findings": sum(r["findings"] for r in rs)}
                                          for m, rs in sorted(by_model.items())},
    }


def fetch_prs(repo_dir: Path, limit: int) -> list[dict]:
    """Metadados pelo gh; arquivos e linhas pelo git local (diff do commit de merge contra o primeiro pai),
    porque `gh pr list --json files` estoura em históricos grandes."""
    out = subprocess.run(["gh", "pr", "list", "--state", "merged", "--limit", str(limit), "--json", FIELDS],
                         cwd=repo_dir, capture_output=True, text=True, encoding="utf-8", check=True)
    prs = json.loads(out.stdout)
    for pr in prs:
        oid = (pr.pop("mergeCommit", None) or {}).get("oid")
        pr["files"] = None
        if oid:
            git = subprocess.run(["git", "diff", "--numstat", f"{oid}^1", oid], cwd=repo_dir, capture_output=True,
                                 text=True, encoding="utf-8")
            if git.returncode == 0:
                pr["files"] = [{"additions": int(a) if a.isdigit() else 0, "deletions": int(d) if d.isdigit() else 0,
                                "path": p} for a, d, p in (r.split("\t", 2) for r in git.stdout.splitlines()
                                                           if r.count("\t") >= 2)]
    return prs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=r"C:\dev\plataforma-metalurgica")
    ap.add_argument("--project-glob", default="*plataforma-metalurgica*",
                    help="pastas de ~/.claude/projects deste repositório")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    prs = fetch_prs(Path(a.repo), a.limit)
    claude_files = [p for d in (Path.home() / ".claude" / "projects").glob(a.project_glob) for p in d.rglob("*.jsonl")]
    codex_files = list((Path.home() / ".codex" / "sessions").rglob("rollout-*.jsonl"))
    result = build(prs, claude_usage(claude_files), codex_usage(codex_files))
    result["inputs"] = {"repo": a.repo, "prs": len(prs), "claude_logs": len(claude_files), "codex_logs": len(codex_files)}
    text = json.dumps(result, ensure_ascii=False, indent=1)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
