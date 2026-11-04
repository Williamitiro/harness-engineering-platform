#!/usr/bin/env python3
"""Benchmark R2 (piloto): o mesmo agente Codex com e sem o kit, em tarefas reais da plataforma.

Pré-registro em benchmarks/r2/tasks.json. Cada execução usa uma cópia descartável, sem histórico, com um único
commit local; os testes ocultos ficam fora da cópia e só entram na verificação, numa segunda cópia.
Mede o que a telemetria nativa do `codex exec --json` dá; o que não foi observado é null, nunca 0.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import harnessctl  # noqa: E402

SPEC = ROOT / "benchmarks" / "r2" / "tasks.json"
PLATFORM = Path(os.environ.get("HE_R2_PLATFORM", r"C:\dev\plataforma-metalurgica"))
WORK = Path(os.environ.get("HE_R2_WORK", r"C:\Users\itiro\AppData\Local\Temp\hxb"))  # curto: limite de caminho
USER_SKILLS = Path.home() / ".agents" / "skills"
IGNORED = ("__pycache__/", ".pytest_cache/", ".agents/")
SKILL_READ = re.compile(r"skills[\\/]+([A-Za-z0-9_-]+)[\\/]+SKILL\.md")


def load_spec() -> dict:
    return json.loads(SPEC.read_text(encoding="utf-8"))


# --- telemetria --------------------------------------------------------------------------------------------------

def parse_events(lines: list[str]) -> dict:
    """Resumo do JSONL do `codex exec --json`. Uso ausente fica null; linhas que não são JSON são contadas."""
    usage_keys = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
    usage = None
    commands, messages, bad, turns = [], [], 0, 0
    for raw in lines:
        try:
            event = json.loads(raw)
        except ValueError:
            bad += 1
            continue
        kind = event.get("type")
        if kind == "turn.completed":
            turns += 1
            got = event.get("usage") or {}
            if usage is None:
                usage = {k: None for k in usage_keys}
            for key in usage_keys:
                if isinstance(got.get(key), int):
                    usage[key] = (usage[key] or 0) + got[key]
        elif kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "command_execution":
                commands.append(str(item.get("command", "")))
            elif item.get("type") == "agent_message":
                messages.append(str(item.get("text", "")))
    return {"usage": usage, "turns": turns, "commands": commands, "command_count": len(commands),
            "final_message": messages[-1] if messages else None, "non_json_lines": bad}


def skills_read(commands: list[str]) -> list[str]:
    return sorted({m.group(1) for c in commands for m in SKILL_READ.finditer(c)})


def leak_hits(commands: list[str], forbidden: list[str], allowed: list[str]) -> list[str]:
    """Comandos que citam um caminho proibido. Trechos permitidos (o Python da plataforma, a própria cópia) saem antes."""
    def norm(text: str) -> str:
        return text.lower().replace("\\", "/")
    hits = []
    for command in commands:
        low = norm(command)
        for ok in allowed:
            low = low.replace(norm(ok), "")
        if any(norm(f).rstrip("/") in low for f in forbidden):
            hits.append(command[:300])
    return hits


def classify_numstat(text: str) -> dict:
    """`git diff --numstat` → arquivos e linhas, separando testes do resto. Binário conta arquivo, não linha."""
    files = {"code": [], "tests": []}
    lines = {"code": 0, "tests": 0}
    for row in text.splitlines():
        parts = row.split("\t")
        if len(parts) != 3:
            continue
        added, removed, path = parts
        path = path.replace("\\", "/")
        if path.startswith(IGNORED) or "/__pycache__/" in path:
            continue
        group = "tests" if path.startswith("tests/") or "/tests/" in path else "code"
        files[group].append(path)
        if added.isdigit() and removed.isdigit():
            lines[group] += int(added) + int(removed)
    return {"files": files, "changed_lines": lines,
            "changed_files_total": len(files["code"]) + len(files["tests"])}


# --- cópias --------------------------------------------------------------------------------------------------------

def git(ws: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "user.name=bench", "-c", "user.email=bench@local",
                           *args], cwd=ws, capture_output=True, text=True, encoding="utf-8", check=check)


def snapshot(base: str) -> Path:
    target = WORK / "snap" / base[:10]
    if (target / ".done").exists():
        return target
    if target.exists():
        shutil.rmtree(target)
    data = subprocess.run(["git", "archive", "--format=tar", base], cwd=PLATFORM, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        tar.extractall(target, filter="data")
    (target / ".done").write_text(base, encoding="utf-8")
    return target


def prepare(spec: dict, task: str, arm: str, run_id: str) -> Path:
    ws = WORK / "r" / run_id
    if ws.exists():
        raise SystemExit(f"{ws} já existe; use outro --rep")
    shutil.copytree(snapshot(spec["tasks"][task]["base_commit"]), ws, ignore=shutil.ignore_patterns(".done"))
    if spec["arms"][arm]["kit"]:
        for name, rel in spec["kit_skills"].items():
            shutil.copytree(ROOT / rel, ws / ".agents" / "skills" / name)
        rules = (ROOT / "benchmarks" / "r2" / "kit_rules.md").read_bytes()
        with open(ws / "AGENTS.md", "ab") as out:
            out.write(rules)
    git(ws, "init", "-q")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "base")
    return ws


def disabled_skills_config(spec: dict) -> str:
    entries = []
    for name in spec["isolation"]["user_skills_disabled_in_all_arms"]:
        path = (USER_SKILLS / name / "SKILL.md").as_posix()
        entries.append(f'{{path="{path}",enabled=false}}')
    return "skills.config=[" + ",".join(entries) + "]"


def skill_list(ws: Path, config: str) -> list[str]:
    real = subprocess.Popen

    def popen(args, *a, **k):  # mesmo app-server do harnessctl, com a configuração e a pasta da execução
        k["cwd"] = str(ws)
        return real(list(args) + ["-c", config], *a, **k)

    harnessctl.subprocess.Popen = popen
    try:
        original = harnessctl.tempfile.TemporaryDirectory

        class Here:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return str(ws)

            def __exit__(self, *exc):
                return False

        harnessctl.tempfile.TemporaryDirectory = Here
        result = harnessctl.codex_skill_listing()
    finally:
        harnessctl.subprocess.Popen = real
        harnessctl.tempfile.TemporaryDirectory = original
    return sorted({s.get("name") for d in result.get("data", []) for s in d.get("skills", []) if s.get("enabled", True)})


# --- verificação ---------------------------------------------------------------------------------------------------

def pytest(ws: Path, spec: dict, args: list[str], tag: str) -> dict:
    (WORK / "t").mkdir(parents=True, exist_ok=True)  # o pytest cria a pasta, não a mãe dela
    proc = subprocess.run([spec["python"], "-m", "pytest", "-q", "-p", "no:cacheprovider",
                           "--basetemp", str(WORK / "t" / tag), *args],
                          cwd=ws, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    tail = [l for l in proc.stdout.splitlines() if l.strip()][-1:] or [""]
    return {"returncode": proc.returncode, "summary": tail[0][:200]}


def hidden_names(text: str) -> list[str]:
    return re.findall(r"^def (test_\w+)", text, flags=re.M)


def verify(spec: dict, task: str, ws: Path, run_id: str) -> dict:
    info = spec["tasks"][task]
    if "hidden_tests" not in info:
        return {"accepted": None}
    vdir = WORK / "v" / run_id
    if vdir.exists():
        shutil.rmtree(vdir)
    shutil.copytree(ws, vdir, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    hidden = (ROOT / info["hidden_tests"]["append"]).read_text(encoding="utf-8")
    target = vdir / info["hidden_tests"]["file"]
    with open(target, "a", encoding="utf-8", newline="\n") as out:
        out.write("\n\n" + hidden)
    names = hidden_names(hidden)
    only = pytest(vdir, spec, [info["hidden_tests"]["file"], "-k", " or ".join(names)], run_id + "h")
    full = pytest(vdir, spec, [info["hidden_tests"]["file"]], run_id + "f")
    return {"hidden": only, "file": full, "accepted": only["returncode"] == 0 and full["returncode"] == 0}


# --- execução ------------------------------------------------------------------------------------------------------

def run(task: str, arm: str, rep: int, dry: bool = False) -> dict:
    spec = load_spec()
    run_id = f"{task}{arm}{rep}"
    out = WORK / "results" / f"{run_id}.json"
    if out.exists():
        raise SystemExit(f"{out} já existe")
    ws = prepare(spec, task, arm, run_id)
    config = disabled_skills_config(spec)
    arm_spec = spec["arms"][arm]
    listed = skill_list(ws, config)
    prompt = spec["tasks"][task]["prompt"] + spec["prompt_suffix"]
    exe = shutil.which("codex")
    cmd = [exe, "exec", "--json", "--ephemeral", "--approve-for-me", "--skip-git-repo-check", "-C", str(ws),
           "-m", arm_spec["model"], "-c", f"model_reasoning_effort={arm_spec['effort']}", "-c", config, prompt]
    record = {"run_id": run_id, "task": task, "arm": arm, "rep": rep, "model": arm_spec["model"],
              "effort": arm_spec["effort"], "kit": arm_spec["kit"], "skills_listed": listed,
              "codex_version": subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()}
    if dry:
        return record
    events_path = WORK / "results" / f"{run_id}.events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with open(events_path, "w", encoding="utf-8") as sink:
        proc = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=sink, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", timeout=3600)
    record["wall_seconds"] = round(time.monotonic() - start, 1)
    record["exit_code"] = proc.returncode
    parsed = parse_events(events_path.read_text(encoding="utf-8", errors="replace").splitlines())
    record.update({k: parsed[k] for k in ("usage", "turns", "command_count", "final_message", "non_json_lines")})
    record["skills_read"] = skills_read(parsed["commands"])
    record["leaks"] = leak_hits(parsed["commands"],
                                forbidden=[str(PLATFORM), r"C:\dev\harness-engineering", str(WORK)],
                                allowed=[spec["python"], str(ws)])
    git(ws, "add", "-A")
    record["diff"] = classify_numstat(git(ws, "diff", "--cached", "--numstat", "HEAD").stdout)
    diff_text = git(ws, "diff", "--cached", "HEAD", "--", ".", ":(exclude).agents").stdout
    record["reuse_signal"] = ("modelo_solidcraft" in diff_text and "desenvolvimentos(" in diff_text) if task == "T2" else None
    record["verify"] = verify(spec, task, ws, run_id)
    if task == "T3":
        record["verify"]["accepted"] = record["diff"]["changed_files_total"] == 0
    record["valid"] = not record["leaks"] and record["exit_code"] == 0
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def calibrate(task: str) -> dict:
    """Na base, os testes ocultos têm de falhar e o resto do arquivo de teste tem de passar."""
    spec = load_spec()
    info = spec["tasks"][task]
    base = snapshot(info["base_commit"])
    before = pytest(base, spec, [info["hidden_tests"]["file"]], task + "cal0")
    result = verify(spec, task, base, task + "cal")
    return {"task": task, "file_at_base": before, "with_hidden": result,
            "valid_task": before["returncode"] == 0 and result["hidden"]["returncode"] != 0}


def mean(values: list) -> float | None:
    seen = [v for v in values if isinstance(v, (int, float))]
    return round(sum(seen) / len(seen), 1) if seen else None


def aggregate(records: list[dict]) -> dict:
    """Por tarefa e braço. Média só do que foi observado; sem observação, null."""
    out: dict = {}
    for r in records:
        cell = out.setdefault(r["task"], {}).setdefault(r["arm"], {"runs": [], "invalid": []})
        (cell["runs"] if r.get("valid") else cell["invalid"]).append(r)
    for task in out.values():
        for arm, cell in task.items():
            runs = cell.pop("runs")
            cell["invalid"] = [r["run_id"] for r in cell["invalid"]]
            usage = [r.get("usage") or {} for r in runs]
            fresh = [u["input_tokens"] - (u.get("cached_input_tokens") or 0)
                     if isinstance(u.get("input_tokens"), int) else None for u in usage]
            skills: dict = {}
            for r in runs:
                for s in r.get("skills_read") or []:
                    skills[s] = skills.get(s, 0) + 1
            cell.update({
                "n": len(runs),
                "accepted": sum(1 for r in runs if r["verify"].get("accepted") is True),
                "input_tokens": mean([u.get("input_tokens") for u in usage]),
                "uncached_input_tokens": mean(fresh),
                "cached_input_tokens": mean([u.get("cached_input_tokens") for u in usage]),
                "output_tokens": mean([u.get("output_tokens") for u in usage]),
                "commands": mean([r.get("command_count") for r in runs]),
                "wall_seconds": mean([r.get("wall_seconds") for r in runs]),
                "code_lines_changed": mean([r["diff"]["changed_lines"]["code"] for r in runs]),
                "test_lines_changed": mean([r["diff"]["changed_lines"]["tests"] for r in runs]),
                "code_files_changed": mean([len(r["diff"]["files"]["code"]) for r in runs]),
                "reuse": (sum(1 for r in runs if r.get("reuse_signal")) if runs and runs[0]["task"] == "T2" else None),
                "skills_read": skills,
                "run_ids": [r["run_id"] for r in runs]})
    return out


def report() -> dict:
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((WORK / "results").glob("*.json"))
               if not p.name.endswith(".events.jsonl")]
    return {"spec": load_spec()["id"], "cells": aggregate(records)}


def summary(record: dict) -> str:
    u = record.get("usage") or {}
    return (f"{record['run_id']}: aceite={record['verify'].get('accepted')} valido={record.get('valid')} "
            f"in={u.get('input_tokens')} cache={u.get('cached_input_tokens')} out={u.get('output_tokens')} "
            f"cmds={record.get('command_count')} t={record.get('wall_seconds')}s "
            f"diff={record['diff']['changed_lines']} skills={record.get('skills_read')} reuso={record.get('reuse_signal')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--task", required=True)
    r.add_argument("--arm", required=True)
    r.add_argument("--rep", type=int, required=True)
    r.add_argument("--dry", action="store_true")
    sub.add_parser("report")
    c = sub.add_parser("calibrate")
    c.add_argument("--task", required=True)
    args = parser.parse_args(argv)
    if args.command == "report":
        print(json.dumps(report(), indent=2, ensure_ascii=False))
        return 0
    if args.command == "calibrate":
        print(json.dumps(calibrate(args.task), indent=2, ensure_ascii=False))
        return 0
    record = run(args.task, args.arm, args.rep, args.dry)
    print(summary(record) if not args.dry else json.dumps(record, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
