#!/usr/bin/env python3
"""Standardized, verifiable evaluation runner for native runtimes (Codex and Claude Code).

Operates within disposable sandboxes below .poc/, enforcing Gates G0 to G3:
- G0: Identity and pinned ECC manifest integrity
- G1: Containment and isolation verification (sentinels/canaries)
- G2: Progressive skill activation (Levels 1 to 5)
- G3: Independent external QA evaluation (frozen oracle outside sandbox)

Supports Conditions A (native), B (project contract), and C (contract + ECC skills).
Does NOT implement an agent runtime; executes native official CLIs only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import harnessctl


class EvalError(RuntimeError):
    pass


def find_codex_binary() -> str | None:
    # 1. Vendor binary bundled in npm package (avoids PowerShell execution policy blocks on Windows)
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        vendor_exe = (
            Path(appdata)
            / "npm"
            / "node_modules"
            / "@openai"
            / "codex"
            / "node_modules"
            / "@openai"
            / "codex-win32-x64"
            / "vendor"
            / "x86_64-pc-windows-msvc"
            / "bin"
            / "codex.exe"
        )
        if vendor_exe.is_file():
            return str(vendor_exe)
    # 2. Standard PATH lookups
    for name in ("codex.cmd", "codex.exe", "codex"):
        found = shutil.which(name)
        if found:
            return found
    return None


def find_claude_binary() -> str | None:
    for name in ("claude.exe", "claude.cmd", "claude"):
        found = shutil.which(name)
        if found:
            return found
    return None


def check_client_auth(client: str, binary: str) -> tuple[bool, str]:
    if client == "codex":
        try:
            res = subprocess.run(
                [binary, "doctor", "--summary"],
                capture_output=True, encoding="utf-8", errors="replace", check=False, timeout=15,
            )
            out = (res.stdout or "") + (res.stderr or "")
            if "auth is configured" in out or "stored ChatGPT tokens" in out or "chatgpt" in out.lower():
                return True, "Codex authenticated"
            return False, "Codex unauthenticated or doctor check failed"
        except Exception as exc:
            return False, f"Codex doctor probe failed: {exc}"
    elif client == "claude":
        try:
            res = subprocess.run(
                [binary, "doctor"],
                capture_output=True, encoding="utf-8", errors="replace", check=False, timeout=15,
            )
            out = (res.stdout or "") + (res.stderr or "")
            if "Not logged in" in out or "no usable credentials" in out:
                return False, "Not logged in · Please run /login"
            if res.returncode == 0:
                return True, "Claude Code authenticated"
            return False, out.strip() or "Claude Code doctor failed"
        except Exception as exc:
            return False, f"Claude doctor probe failed: {exc}"
    return False, f"Unknown client {client}"


def assert_eval_target(target: Path) -> None:
    """Refuse deletion, traversal, symlinks and non-disposable workspaces.

    This is filesystem hygiene, NOT a security sandbox for executing an LLM.
    """
    base = (ROOT / ".poc").resolve()
    candidate = target.absolute()
    harnessctl.assert_no_symlink(candidate)
    resolved = candidate.resolve(strict=False)
    if resolved == base or base not in resolved.parents:
        raise EvalError("target must be a child of this repository's .poc directory")
    if candidate.exists() and not candidate.is_dir():
        raise EvalError("target is not a directory")
    if candidate.exists() and any(candidate.iterdir()):
        raise EvalError("target is not empty; manual review/cleanup required")


def setup_sandbox(
    target: Path,
    task_dir: Path,
    client: str,
    condition: str,
    source: Path | None,
    manifest: dict,
) -> dict:
    # No rmtree: never erase experiments or files without a separate review.
    assert_eval_target(target)
    target.mkdir(parents=True, exist_ok=True)
    harnessctl.check_sandbox(target)

    task_spec = task_dir / "specification.md"
    if not task_spec.is_file():
        raise EvalError(f"Task specification not found: {task_spec}")
    shutil.copy2(task_spec, target / "TASK.md")

    contract_file = ROOT / "templates" / ("AGENTS.md" if client == "codex" else "CLAUDE.md")
    if condition in ("B", "C"):
        if not contract_file.is_file():
            raise EvalError(f"Contract template missing: {contract_file}")
        shutil.copy2(contract_file, target / contract_file.name)

    skills_meta = {"installed": False, "verified": False}
    if condition == "C":
        if source is None or not source.is_dir():
            raise EvalError("ECC source required for condition C")
        plan_res = harnessctl.plan(source, target, client, manifest)
        harnessctl.install(plan_res, target)
        rec, paths = harnessctl.record_and_paths(target, manifest=manifest)
        skills_meta = {
            "installed": True,
            "verified": len(paths) == 2,
            "adapter": rec["adapter"],
            "ecc_commit": rec["ecc_commit"],
        }
    return skills_meta


def run_oracle(oracle_path: Path, target: Path) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(target)
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(oracle_path)],
        capture_output=True, encoding="utf-8", errors="replace", check=False, env=env, timeout=30,
    )
    elapsed = round(time.monotonic() - start, 3)
    out = (proc.stdout or "") + (proc.stderr or "")
    tests_run = 0
    passed = 0
    for line in out.splitlines():
        if line.startswith("Ran ") and (" test in " in line or " tests in " in line):
            try:
                parts = line.split()
                tests_run = int(parts[1])
            except (ValueError, IndexError):
                pass
    if proc.returncode == 0:
        passed = tests_run
    return {
        "status": "PASS" if proc.returncode == 0 and tests_run > 0 else "FAIL",
        "returncode": proc.returncode,
        "tests_total": tests_run,
        "tests_passed": passed,
        "duration_seconds": elapsed,
        "output": out,
    }


def analyze_trajectory(events: list[dict], client: str) -> dict:
    """Conservative evidence classifier, never a tool router or an LLM judge.

    Count only completed command executions with exit codes. A skill name in an
    agent response, failed command or generic test run is not invocation/TDD.
    """
    import re

    records = []
    for item in events:
        if item.get("type") != "item.completed":
            continue
        cmd = item.get("item", {})
        if cmd.get("type") != "command_execution" or cmd.get("status") != "completed":
            continue
        exit_code = cmd.get("exit_code")
        if type(exit_code) is not int:
            continue
        records.append({
            "command": str(cmd.get("command", "")),
            "output": str(cmd.get("aggregated_output", "")),
            "exit_code": exit_code,
        })

    successful = [r for r in records if r["exit_code"] == 0]
    successful_reads = set()
    for r in successful:
        cmd = r["command"].replace("\\", "/").lower()
        output = r["output"].lower()
        if not re.search(r"get-content|\bcat\b|\btype\b|\bsed\b", cmd):
            continue
        for skill in harnessctl.ALLOWED:
            if f"{skill}/skill.md" in cmd and (
                f"name: {skill}" in output or f"# {skill}" in output
            ):
                successful_reads.add(skill)

    test_pattern = re.compile(r"(?:python(?:3)?\s+-m\s+)?(?:pytest|unittest)\b", re.I)
    tests = [(i, r) for i, r in enumerate(records) if test_pattern.search(r["command"])]
    red_green = any(
        first["exit_code"] != 0 and second["exit_code"] == 0 and i < j
        for i, first in tests for j, second in tests
    )
    # Require separate commands with successful exit codes. Shell statements
    # chained in one command cannot establish every sub-step succeeded.
    verified_names = (
        "mypy", "ruff", "coverage",
    )
    verified = all(
        any(k in r["command"].lower() and r["exit_code"] == 0 for r in records)
        for k in verified_names
    )
    return {
        "discovered": bool(successful_reads),
        "invoked": len(successful_reads) == len(harnessctl.ALLOWED),
        "procedure_executed": len(successful_reads) == len(harnessctl.ALLOWED)
                              and red_green and verified,
        "red_green_observed": red_green,
        "verification_commands_observed": verified,
        "skill_bodies_read": sorted(successful_reads),
        "commands_count": len(records),
        "commands": [r["command"] for r in records],
    }


def execute_eval(
    client: str,
    task_dir: Path,
    condition: str,
    source: Path | None,
    target: Path,
    manifest: dict,
    dry_run: bool = False,
    timeout_seconds: int = 180,
    live_authorized: bool = False,
) -> dict:
    experiment_id = f"eval-{client}-{condition}-{task_dir.name}"
    start_time = time.monotonic()

    if not dry_run and not live_authorized:
        return {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "client": client,
            "task_id": task_dir.name,
            "condition": condition,
            "isolation_verified": False,
            "acceptance": {"status": "NOT_RUN", "tests_passed": None, "tests_total": None},
            "skills": {"discovered": False, "invoked": False, "procedure_executed": False},
            "metrics": {"duration_seconds": 0, "input_tokens": None, "output_tokens": None, "cost_usd": None},
            "verdict": "BLOCKED",
            "reason": "Live execution disabled by default. Requires external OS isolation and --live-in-preisolated-environment.",
        }

    # Gate G1: Setup external canary
    poc_root = ROOT / ".poc"
    poc_root.mkdir(exist_ok=True)
    canary = poc_root / "canary_sentinel.txt"
    canary_token = hashlib.sha256(b"harness-canary-secret").hexdigest()
    canary.write_text(canary_token, encoding="utf-8")

    skills_meta = setup_sandbox(target, task_dir, client, condition, source, manifest)

    # Offline dry-run must not require installation, login or model API access.
    if dry_run:
        oracle_res = run_oracle(task_dir / "oracle.py", target)
        elapsed = round(time.monotonic() - start_time, 3)
        return {
            "schema_version": 1, "experiment_id": experiment_id, "client": client,
            "client_version": "NOT_PROBED_OFFLINE", "task_id": task_dir.name,
            "condition": condition, "isolation_verified": False,
            "canary_intact": canary.read_text(encoding="utf-8") == canary_token,
            "skills": {"discovered": False, "invoked": False, "procedure_executed": False},
            "acceptance": {"status": oracle_res["status"], "tests_passed": oracle_res["tests_passed"],
                           "tests_total": oracle_res["tests_total"]},
            "metrics": {"duration_seconds": elapsed, "input_tokens": None,
                        "output_tokens": None, "cost_usd": None},
            "evidence": {"transcript": None, "oracle_log": oracle_res["output"], "diff": None},
            "verdict": "PREPARED", "skills_meta": skills_meta,
            "note": "No model called; canary intact does NOT prove OS/network isolation",
        }

    binary = find_codex_binary() if client == "codex" else find_claude_binary()
    if not binary:
        return {
            "schema_version": 1, "experiment_id": experiment_id, "client": client,
            "client_version": "NOT_INSTALLED", "task_id": task_dir.name,
            "condition": condition, "isolation_verified": False,
            "skills": {"discovered": False, "invoked": False, "procedure_executed": False},
            "acceptance": {"status": "BLOCKED", "tests_passed": 0, "tests_total": 0},
            "metrics": {"duration_seconds": 0, "input_tokens": None,
                        "output_tokens": None, "cost_usd": None},
            "verdict": "BLOCKED", "reason": f"Binary for {client} not found on system PATH",
        }
    auth_ok, auth_msg = check_client_auth(client, binary)
    if not auth_ok:
        return {
            "schema_version": 1, "experiment_id": experiment_id, "client": client,
            "client_version": binary, "task_id": task_dir.name,
            "condition": condition, "isolation_verified": False,
            "skills": {"discovered": False, "invoked": False, "procedure_executed": False},
            "acceptance": {"status": "BLOCKED", "tests_passed": 0, "tests_total": 0},
            "metrics": {"duration_seconds": 0, "input_tokens": None,
                        "output_tokens": None, "cost_usd": None},
            "verdict": "BLOCKED", "reason": auth_msg,
        }

    # Live execution with native runtime
    prompt = (
        "Read TASK.md and implement the requested functionality completely. "
        "Adhere to all workspace guidelines, test your implementation, and verify it before finishing."
    )

    events: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    proc_stdout = ""
    proc_stderr = ""

    if client == "codex":
        cmd = [
            binary,
            "exec",
            "--cd", str(target),
            "--skip-git-repo-check",
            "--ephemeral",
            "--json",
            prompt,
        ]
        try:
            res = subprocess.run(
                cmd,
                input="",
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            proc_stdout = res.stdout or ""
            proc_stderr = res.stderr or ""
            for line in proc_stdout.splitlines():
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        parsed = json.loads(line)
                        events.append(parsed)
                        if parsed.get("type") == "turn.completed":
                            usage = parsed.get("usage", {})
                            input_tokens += usage.get("input_tokens", 0)
                            output_tokens += usage.get("output_tokens", 0)
                    except json.JSONDecodeError:
                        pass
        except subprocess.TimeoutExpired:
            proc_stderr += f"\nTimeout expired after {timeout_seconds}s"
    elif client == "claude":
        cmd = [
            binary,
            "-p", prompt,
            "--output-format", "json",
        ]
        try:
            res = subprocess.run(
                cmd,
                cwd=str(target),
                input="",
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
            proc_stdout = res.stdout or ""
            proc_stderr = res.stderr or ""
            try:
                events = [json.loads(proc_stdout)]
            except json.JSONDecodeError:
                pass
        except subprocess.TimeoutExpired:
            proc_stderr += f"\nTimeout expired after {timeout_seconds}s"

    elapsed = round(time.monotonic() - start_time, 3)

    # Gate G1 verification
    canary_intact = canary.is_file() and canary.read_text(encoding="utf-8") == canary_token

    # Gate G2 analysis (Levels 1 to 4)
    traj = analyze_trajectory(events, client)
    skill_eval = {
        "discovered": traj["discovered"],
        "invoked": traj["invoked"],
        "procedure_executed": traj["procedure_executed"],
    }

    # Gate G3: Independent Oracle Evaluation (Level 5)
    oracle_res = run_oracle(task_dir / "oracle.py", target)

    # Diff analysis
    diff_output = ""
    for file_path in target.rglob("*.py"):
        diff_output += f"--- {file_path.name} ---\n{file_path.read_text(encoding='utf-8', errors='ignore')}\n\n"

    # An externally granted live exception is not itself evidence of isolation.
    verdict = "PROVISIONAL" if oracle_res["status"] == "PASS" and canary_intact else "FAIL"

    return {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "client": client,
        "client_version": binary,
        "task_id": task_dir.name,
        "condition": condition,
        "isolation_verified": False,
        "canary_intact": canary_intact,
        "skills": skill_eval,
        "acceptance": {
            "status": oracle_res["status"],
            "tests_passed": oracle_res["tests_passed"],
            "tests_total": oracle_res["tests_total"],
        },
        "metrics": {
            "duration_seconds": elapsed,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": None,
        },
        "evidence": {
            "transcript": proc_stdout[:4000],
            "oracle_log": oracle_res["output"],
            "diff": diff_output[:4000],
        },
        "verdict": verdict,
        "commands": traj.get("commands", []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=("codex", "claude"), default="codex")
    parser.add_argument("--condition", choices=("A", "B", "C"), default="C")
    parser.add_argument("--task", type=Path,
                        default=ROOT / "benchmarks" / "tasks" / "ratelimit")
    parser.add_argument("--source", type=Path, default=ROOT / ".poc" / "ecc-pinned")
    parser.add_argument("--target", type=Path, default=None)
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "config" / "approved_skills.json")
    parser.add_argument("--dry-run", action="store_true", help="dry-run without calling native LLM")
    parser.add_argument("--live-in-preisolated-environment", action="store_true",
                        help="explicit opt-in after OS/container isolation is independently proven; never marks G1 PASS")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    manifest = harnessctl.read_manifest(args.manifest)
    target = args.target
    if target is None:
        target = ROOT / ".poc" / f"eval-{args.client}-{args.condition}-{args.task.name}"

    source = args.source if args.condition == "C" else None
    result = execute_eval(
        client=args.client,
        task_dir=args.task,
        condition=args.condition,
        source=source,
        target=target,
        manifest=manifest,
        dry_run=args.dry_run,
        timeout_seconds=args.timeout,
        live_authorized=args.live_in_preisolated_environment,
    )

    out_json = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out_json, encoding="utf-8")
    print(out_json)
    return 0 if result["verdict"] in ("PASS", "PREPARED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
