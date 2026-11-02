import os
import sys
import json
import time
import shutil
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime, timezone

POC_DIR = Path(r"C:\dev\harness-engineering\.poc\antigravity-flash-001")
TASKS_TEMPLATE_DIR = POC_DIR / "tasks_template"
ORACLE_DIR = POC_DIR / "oracle"
HARNESS_ASSETS_DIR = POC_DIR / "harness_assets"
RUNS_DIR = POC_DIR / "runs"
EVIDENCIAS_DIR = POC_DIR / "EVIDENCIAS"
CSV_PATH = POC_DIR / "RESULTADOS.csv"
CLI_BRAIN_DIR = Path(os.path.expanduser(r"~\.gemini\antigravity-cli\brain"))

MODEL = "gemini-3.8-flash-low"
EFFORT = "low"
ENV_VERSION = "Antigravity CLI 1.4.10 / Gemini 3.8 Flash"

PROMPTS = {
    "T1": (
        "You are tasked with fixing a bug in src/semver_parser.py.\n"
        "First run the existing tests in tests/test_initial.py using python -m pytest tests/test_initial.py to observe the failure.\n"
        "Diagnose and fix the bug in src/semver_parser.py so that all semantic version comparisons, including prerelease versions, follow the SemVer 2.0.0 specification (e.g. 1.0.0 > 1.0.0-alpha, 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-beta).\n"
        "Ensure all tests in tests/test_initial.py pass and no regressions are introduced."
    ),
    "T2": (
        "You are tasked with implementing the Circuit Breaker pattern in src/circuit_breaker.py.\n"
        "Inspect the requirements and class skeleton in src/circuit_breaker.py.\n"
        "Run python -m pytest tests/test_initial.py to see the initial status.\n"
        "Implement the state machine (CLOSED, OPEN, HALF_OPEN) and the call() and reset() methods according to the specifications in the docstring.\n"
        "Ensure all tests pass and handle edge cases cleanly."
    ),
    "T3": (
        "You are tasked with refactoring src/order_calculator.py.\n"
        "Currently, calculate_order is a monolithic function. All tests in tests/test_initial.py currently pass.\n"
        "Refactor src/order_calculator.py by extracting modular helper classes: DiscountPolicy, TaxCalculator, and ShippingCalculator.\n"
        "The public function calculate_order(order_data, config) must be preserved with identical behavior.\n"
        "Ensure that existing tests in tests/test_initial.py continue to pass and new unit tests are added for the extracted classes."
    ),
}

ORACLE_TESTS = {
    "T1": ORACLE_DIR / "test_t1_acceptance.py",
    "T2": ORACLE_DIR / "test_t2_acceptance.py",
    "T3": ORACLE_DIR / "test_t3_acceptance.py",
}

def compute_dir_hash(directory: Path) -> str:
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        for f in sorted(files):
            if f.endswith((".pyc", ".TAG", ".lock")) or "__pycache__" in root or ".pytest_cache" in root:
                continue
            fpath = Path(root) / f
            hasher.update(f.encode("utf-8"))
            try:
                hasher.update(fpath.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()

def setup_run_workspace(run_id: str, task_id: str, condition: str) -> Path:
    run_dir = RUNS_DIR / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True, exist_ok=True)

    # Copy pristine task template
    template_dir = TASKS_TEMPLATE_DIR / task_id
    for item in template_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, run_dir / item.name)
        else:
            shutil.copy2(item, run_dir / item.name)

    # Clean any stray caches
    for p in run_dir.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    for p in run_dir.rglob(".pytest_cache"):
        shutil.rmtree(p, ignore_errors=True)

    # Condition specific harness files
    if condition in ("B", "C"):
        # Copy AGENTS.md
        shutil.copy2(HARNESS_ASSETS_DIR / "AGENTS.md", run_dir / "AGENTS.md")

    if condition == "C":
        # Copy .agents
        shutil.copytree(HARNESS_ASSETS_DIR / ".agents", run_dir / ".agents")

    return run_dir

def run_oracle_tests(run_dir: Path, oracle_test_path: Path):
    cmd = [sys.executable, "-m", "pytest", str(oracle_test_path), "-v", "--tb=short"]
    res = subprocess.run(cmd, cwd=str(run_dir), capture_output=True, text=True)
    out = res.stdout + "\n" + res.stderr

    accepted = 0
    passed = 0
    failed = 0

    # Parse pytest output
    # E.g. "5 passed in 0.05s" or "2 failed, 3 passed in 0.06s"
    for line in out.splitlines():
        if "collected " in line and " items" in line:
            try:
                accepted = int(line.split("collected ")[1].split(" items")[0])
            except Exception:
                pass
        if line.startswith("===") and " in " in line:
            # summary line
            parts = line.strip("=").strip().split(",")
            for p in parts:
                p = p.strip()
                if "passed" in p and "in " not in p:
                    try:
                        passed = int(p.split()[0])
                    except Exception:
                        pass
                elif "failed" in p and "in " not in p:
                    try:
                        failed = int(p.split()[0])
                    except Exception:
                        pass
                elif "passed in " in p:
                    try:
                        passed = int(p.split()[0])
                    except Exception:
                        pass
                elif "failed in " in p:
                    try:
                        failed = int(p.split()[0])
                    except Exception:
                        pass

    if accepted == 0 and (passed + failed > 0):
        accepted = passed + failed

    success = (res.returncode == 0 and failed == 0 and passed == accepted and accepted > 0)
    return {
        "returncode": res.returncode,
        "output": out,
        "accepted": accepted,
        "passed": passed,
        "failed": failed,
        "success": success
    }

def analyze_transcript(transcript_path: Path):
    tool_calls = []
    skill_discovery = False
    skill_invocation = False
    skill_execution = False

    if not transcript_path.exists():
        return tool_calls, skill_discovery, skill_invocation, skill_execution

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    step = json.loads(line)
                except Exception:
                    continue

                content = step.get("content", "")
                if isinstance(content, str):
                    if "tdd-workflow" in content or "verification-loop" in content:
                        skill_discovery = True

                tcalls = step.get("tool_calls", [])
                if isinstance(tcalls, list):
                    for tc in tcalls:
                        name = tc.get("name", "")
                        tool_calls.append(name)
                        args = str(tc.get("args", ""))
                        if "tdd-workflow" in args or "verification-loop" in args:
                            skill_invocation = True
                            skill_execution = True
                        if "setup-package-manager.js" in args:
                            skill_execution = True

                # Also check if agent read SKILL.md
                if step.get("type") == "PLANNER_RESPONSE":
                    for tc in tcalls:
                        args = tc.get("args", {})
                        p = str(args.get("Path", ""))
                        if "tdd-workflow" in p or "verification-loop" in p:
                            skill_invocation = True
                            skill_execution = True
    except Exception as e:
        print(f"Error parsing transcript {transcript_path}: {e}")

    return tool_calls, skill_discovery, skill_invocation, skill_execution

def execute_run(run_id: str, task_id: str, condition: str):
    print(f"\n==================================================")
    print(f"Starting {run_id} (Task: {task_id}, Condition: {condition})")
    print(f"==================================================")

    evidence_run_dir = EVIDENCIAS_DIR / run_id
    evidence_run_dir.mkdir(parents=True, exist_ok=True)

    run_dir = setup_run_workspace(run_id, task_id, condition)
    initial_hash = compute_dir_hash(run_dir)
    print(f"Initial workspace hash: {initial_hash}")

    prompt = PROMPTS[task_id]
    cmd = [
        "agy", "-p", prompt,
        "--model", MODEL,
        "--effort", EFFORT,
        "--dangerously-skip-permissions",
        "--output-format", "json"
    ]

    start_time = time.time()
    iso_start = datetime.now(timezone.utc).isoformat()
    print(f"Executing agy at {iso_start}...")

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=180
        )
        stdout_raw = proc.stdout
        stderr_raw = proc.stderr
        exit_code = proc.returncode
    except subprocess.TimeoutExpired:
        print("Run TIMED OUT after 180s")
        stdout_raw = "{}"
        stderr_raw = "TimeoutExpired"
        exit_code = -1

    duration_wall = round(time.time() - start_time, 2)
    print(f"agy finished in {duration_wall}s with exit code {exit_code}")

    # Parse JSON output from agy
    conversation_id = "N/A"
    status = "ERROR" if exit_code != 0 else "UNKNOWN"
    duration_reported = duration_wall
    input_tokens = "N/A"
    output_tokens = "N/A"
    total_tokens = "N/A"

    try:
        data = json.loads(stdout_raw.strip())
        conversation_id = data.get("conversation_id", "N/A")
        status = data.get("status", status)
        duration_reported = data.get("duration_seconds", duration_wall)
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", "N/A")
        output_tokens = usage.get("output_tokens", "N/A")
        total_tokens = usage.get("total_tokens", "N/A")
    except Exception as e:
        print(f"Could not parse agy JSON stdout: {e}")
        # Save raw stdout
        (evidence_run_dir / "stdout_raw.txt").write_text(stdout_raw, encoding="utf-8")

    (evidence_run_dir / "stdout_agy.json").write_text(stdout_raw, encoding="utf-8")
    if stderr_raw:
        (evidence_run_dir / "stderr_agy.txt").write_text(stderr_raw, encoding="utf-8")

    # Locate transcript
    tool_calls = []
    skill_discovery = False
    skill_invocation = False
    skill_execution = False

    if conversation_id != "N/A":
        trans_source = CLI_BRAIN_DIR / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
        trans_full_source = CLI_BRAIN_DIR / conversation_id / ".system_generated" / "logs" / "transcript_full.jsonl"
        if trans_source.exists():
            shutil.copy2(trans_source, evidence_run_dir / "transcript.jsonl")
        if trans_full_source.exists():
            shutil.copy2(trans_full_source, evidence_run_dir / "transcript_full.jsonl")

        tool_calls, skill_discovery, skill_invocation, skill_execution = analyze_transcript(evidence_run_dir / "transcript.jsonl")

    print(f"Tool calls recorded: {len(tool_calls)} {tool_calls}")
    print(f"Skills discovered: {skill_discovery}, invoked: {skill_invocation}, executed: {skill_execution}")

    # Run independent oracle acceptance tests
    print("Running independent oracle acceptance tests...")
    oracle_res = run_oracle_tests(run_dir, ORACLE_TESTS[task_id])
    (evidence_run_dir / "acceptance_test.log").write_text(oracle_res["output"], encoding="utf-8")
    print(f"Acceptance result: {oracle_res['passed']}/{oracle_res['accepted']} passed (Success: {oracle_res['success']})")

    # Diff of src/
    diff_cmd = ["git", "diff", "--no-index", str(TASKS_TEMPLATE_DIR / task_id / "src"), str(run_dir / "src")]
    diff_proc = subprocess.run(diff_cmd, capture_output=True, text=True)
    (evidence_run_dir / "diff.patch").write_text(diff_proc.stdout, encoding="utf-8")

    # Summary record
    run_status = "COMPROVADO" if oracle_res["success"] else "FALHOU"

    record = {
        "run_id": run_id,
        "task_id": task_id,
        "condition": condition,
        "model": MODEL,
        "effort": EFFORT,
        "environment_version": ENV_VERSION,
        "initial_hash": initial_hash,
        "accepted_tests": oracle_res["accepted"],
        "passed_tests": oracle_res["passed"],
        "failed_tests": oracle_res["failed"],
        "success": "TRUE" if oracle_res["success"] else "FALSE",
        "duration_seconds": duration_reported,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "reported_cost": "$0.00 (Subscription)",
        "tool_calls": len(tool_calls),
        "skill_discovery": "TRUE" if skill_discovery else "FALSE",
        "skill_invocation": "TRUE" if skill_invocation else "FALSE",
        "skill_execution": "TRUE" if skill_execution else "FALSE",
        "evidence_path": str(evidence_run_dir.relative_to(POC_DIR)),
        "status": run_status
    }

    (evidence_run_dir / "summary.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record

def main():
    header = [
        "run_id", "task_id", "condition", "model", "effort", "environment_version",
        "initial_hash", "accepted_tests", "passed_tests", "failed_tests", "success",
        "duration_seconds", "input_tokens", "output_tokens", "total_tokens", "reported_cost",
        "tool_calls", "skill_discovery", "skill_invocation", "skill_execution",
        "evidence_path", "status"
    ]

    records = []
    
    # 9 experimental runs:
    # T1: A -> B -> C
    # T2: A -> B -> C
    # T3: A -> B -> C
    matrix = [
        ("run_t1_condA", "T1", "A"),
        ("run_t1_condB", "T1", "B"),
        ("run_t1_condC", "T1", "C"),
        ("run_t2_condA", "T2", "A"),
        ("run_t2_condB", "T2", "B"),
        ("run_t2_condC", "T2", "C"),
        ("run_t3_condA", "T3", "A"),
        ("run_t3_condB", "T3", "B"),
        ("run_t3_condC", "T3", "C"),
    ]

    for run_id, task_id, cond in matrix:
        rec = execute_run(run_id, task_id, cond)
        records.append(rec)

    # Write CSV
    with open(CSV_PATH, "w", encoding="utf-8") as f:
        f.write(",".join(header) + "\n")
        for r in records:
            row = [str(r.get(h, "N/A")) for h in header]
            f.write(",".join(row) + "\n")

    print(f"\n==================================================")
    print(f"All 9 experimental runs completed! Results saved to {CSV_PATH}")
    print(f"==================================================")

if __name__ == "__main__":
    main()
