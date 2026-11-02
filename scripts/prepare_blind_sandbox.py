#!/usr/bin/env python3
"""Prepares an isolated, blind sandbox directory for empirical benchmarking.

Ensures absolute blindness and zero test contamination:
1. Copies ONLY blind task files (benchmarks/jev/tasks/*.jsonl) to the target sandbox.
2. Strictly refuses and excludes any golden holdout ground truth (golden_*.jsonl).
3. Excludes all .git history, commits, and logs to prevent historical extraction.
4. Optionally packages runner scripts and policies without test solutions.
5. Emits a verifiable SHA-256 manifest of all exported artifacts.
6. Generates a Containerfile and run script with negative canary checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

class SandboxError(RuntimeError):
    pass

def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def verify_file_is_blind(path: Path) -> None:
    """Verifies that a tasks file contains no expected answers or contamination."""
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SandboxError(f"File {path.name} line {line_no} invalid JSON: {exc}")
        
        # Check forbidden ground truth keys
        for forbidden in ("expected_label", "expected", "golden_label", "ground_truth"):
            if forbidden in item:
                raise SandboxError(
                    f"Contamination detected in {path.name} line {line_no}! "
                    f"Forbidden key '{forbidden}' found in blind task."
                )

def prepare_blind_sandbox(
    tasks_source: Path,
    target_dir: Path,
    include_runner: bool = True,
    clean_target: bool = False,
) -> dict[str, Any]:
    if clean_target:
        raise SandboxError("--clean disabled: destructive sandbox cleanup is not permitted")
    if not tasks_source.exists():
        raise SandboxError(f"Tasks source not found: {tasks_source}")
    if tasks_source.is_symlink():
        raise SandboxError("Symlink task source refused")
    # Temporary output must be OUTSIDE the Git checkout, within the OS temp
    # directory; never copy material into an agent-accessible repo descendant.
    temp_root = Path(tempfile.gettempdir()).resolve()
    requested = target_dir.absolute()
    for ancestor in (requested, *requested.parents):
        if ancestor.is_symlink():
            raise SandboxError("Symlink in destination path refused")
    target_dir = requested.resolve(strict=False)
    if target_dir == temp_root or temp_root not in target_dir.parents:
        raise SandboxError("Output must be a child of the OS temporary directory")
    if target_dir == ROOT or ROOT in target_dir.parents or target_dir in ROOT.parents:
        raise SandboxError("Output cannot be in or above this Git checkout")
    if target_dir.exists() and (not target_dir.is_dir() or any(target_dir.iterdir())):
        raise SandboxError("Output directory must be absent or empty; never overwrite existing files")
    target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copy tasks
    target_tasks_dir = target_dir / "tasks"
    target_tasks_dir.mkdir(parents=True, exist_ok=True)
    
    copied_files: list[Path] = []
    
    if tasks_source.is_file():
        verify_file_is_blind(tasks_source)
        dest = target_tasks_dir / tasks_source.name
        shutil.copy2(tasks_source, dest)
        copied_files.append(dest)
    elif tasks_source.is_dir():
        for task_file in sorted(tasks_source.glob("*.jsonl")):
            if task_file.is_symlink():
                raise SandboxError("Symlink task input refused")
            if "golden" in task_file.name or "truth" in task_file.name:
                continue # Skip any ground truth accidentally in folder
            verify_file_is_blind(task_file)
            dest = target_tasks_dir / task_file.name
            shutil.copy2(task_file, dest)
            copied_files.append(dest)
            
    if not copied_files:
        raise SandboxError(f"No valid blind task files found in {tasks_source}")
        
    # 2. Optionally copy scripts and policies (strictly without ground truth)
    if include_runner:
        target_scripts_dir = target_dir / "scripts"
        target_scripts_dir.mkdir(parents=True, exist_ok=True)
        
        for script_name in ("jev_collector.py", "jev_adapter.py", "native_baseline.py", "canary_probes.py"):
            src_script = ROOT / "scripts" / script_name
            if src_script.is_file():
                dest = target_scripts_dir / script_name
                shutil.copy2(src_script, dest)
                copied_files.append(dest)
                
        target_config_dir = target_dir / "config"
        target_config_dir.mkdir(parents=True, exist_ok=True)
        for policy_file in sorted((ROOT / "config").glob("jev_*_policy.json")):
            dest = target_config_dir / policy_file.name
            shutil.copy2(policy_file, dest)
            copied_files.append(dest)
            
        mcp_src = ROOT / "config" / "mcp"
        if mcp_src.is_dir():
            target_mcp_dir = target_config_dir / "mcp"
            target_mcp_dir.mkdir(parents=True, exist_ok=True)
            for mcp_file in sorted(mcp_src.glob("*.json")):
                dest = target_mcp_dir / mcp_file.name
                shutil.copy2(mcp_file, dest)
                copied_files.append(dest)

    # 3. Security audit of the generated target
    for root_dir, dirs, files in os.walk(target_dir):
        if ".git" in dirs:
            raise SandboxError("CRITICAL: .git directory found inside blind sandbox!")
        for fname in files:
            lower = fname.lower()
            if "golden" in lower or "truth" in lower:
                raise SandboxError(f"CRITICAL: Ground truth file '{fname}' leaked into blind sandbox!")

    # 4. Generate manifest
    manifest_items = {}
    for fpath in copied_files:
        rel = fpath.relative_to(target_dir).as_posix()
        manifest_items[rel] = {
            "size_bytes": fpath.stat().st_size,
            "sha256": compute_sha256(fpath),
        }
        
    manifest_path = target_dir / "sandbox_manifest.json"
    manifest_doc = {
        "sandbox_version": "1.0.0",
        "description": "Blind sandbox workspace for empirical benchmark execution",
        "blindness_verified": True,
        "ground_truth_excluded": True,
        "git_history_excluded": True,
        "environment_isolated": False,
        "G1_verified": False,
        "warning": "File scan only; not a sandbox or proof of host access restrictions",
        "files": manifest_items,
    }
    manifest_path.write_text(json.dumps(manifest_doc, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # 5. Generate container recipe and negative canary verification script
    containerfile_path = target_dir / "Containerfile"
    containerfile_path.write_text(
        "# Container descartável para execução cega e isolada (Gate G1)\n"
        "FROM node:20-alpine\n"
        "RUN apk add --no-cache python3 bash\n"
        "WORKDIR /workspace\n"
        "COPY . /workspace\n"
        "USER node\n"
        "ENV NODE_ENV=production\n"
        'ENTRYPOINT ["python3", "scripts/jev_collector.py"]\n',
        encoding="utf-8"
    )
    
    canary_script_path = target_dir / "verify_negative_canaries.sh"
    canary_script_path.write_text(
        "#!/bin/sh\n"
        "# Provas negativas de contenção: confirma que segredos do host são inacessíveis\n"
        "FAILED=0\n"
        'for canary in "/root/.ssh" "/home/node/.ssh" "/root/.aws" "/mnt/c"; do\n'
        '  if [ -e "$canary" ]; then\n'
        '    echo "[CANARY FAIL] Host leak detected: $canary exists inside container!" >&2\n'
        "    FAILED=1\n"
        "  else\n"
        '    echo "[CANARY PASS] $canary is inaccessible (OK)"\n'
        "  fi\n"
        "done\n"
        "exit $FAILED\n",
        encoding="utf-8"
    )
    
    run_script_path = target_dir / "run_isolated_podman.sh"
    run_script_path.write_text(
        "#!/bin/sh\n"
        "# Offline container preflight ONLY. Does not validate G1 by itself.\n"
        "set -eu\n"
        'cd "$(dirname "$0")"\n'
        'podman build --network=none --pull=never -t harness-jev-preflight .\n'
        "podman run --rm --network none --read-only --cap-drop=ALL \\\n"
        "  --security-opt=no-new-privileges \\\n"
        "  --entrypoint /bin/sh harness-jev-preflight \\\n"
        "  /workspace/verify_negative_canaries.sh\n",
        encoding="utf-8"
    )

    bwrap_script_path = target_dir / "run_isolated_bwrap.sh"
    bwrap_script_path.write_text(
        "#!/bin/bash\n"
        "# Offline isolated execution via bubblewrap (WSL2 / Linux container sandbox)\n"
        "set -eu\n"
        'WORKDIR="$(cd "$(dirname "$0")" && pwd)"\n'
        "bwrap \\\n"
        "  --ro-bind /usr /usr \\\n"
        "  --ro-bind /lib /lib \\\n"
        "  --ro-bind /lib64 /lib64 \\\n"
        "  --proc /proc \\\n"
        "  --dev /dev \\\n"
        '  --bind "$WORKDIR" /workspace \\\n'
        "  --unshare-all \\\n"
        "  --chdir /workspace \\\n"
        '  python3 scripts/canary_probes.py\n',
        encoding="utf-8"
    )

    return {
        "status": "SANDBOX_PREPARED",
        "target_directory": str(target_dir),
        "tasks_copied": len(list(target_tasks_dir.glob("*.jsonl"))),
        "manifest_path": str(manifest_path),
        "blindness_verified": True,
        "files_count": len([p for p in target_dir.rglob("*") if p.is_file()]),
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks" / "jev" / "tasks",
                        help="Path to tasks file or directory")
    parser.add_argument("--target-dir", type=Path, required=True,
                        help="Target directory for the isolated blind sandbox")
    parser.add_argument("--no-runner", action="store_true",
                        help="Do not copy collector scripts or policies")
    parser.add_argument("--clean", action="store_true",
                        help="Clean target directory before preparing")
    
    args = parser.parse_args()
    try:
        summary = prepare_blind_sandbox(
            tasks_source=args.tasks,
            target_dir=args.target_dir,
            include_runner=not args.no_runner,
            clean_target=args.clean,
        )
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except SandboxError as exc:
        print(json.dumps({"status": "FAILED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
