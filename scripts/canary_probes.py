#!/usr/bin/env python3
"""Objective negative canary probes for G1 isolation verification.

Tests for absence of unauthorized access:
1. Filesystem containment: Host home, personal credentials (~/.ssh, ~/.aws, ~/.infisical).
2. Git isolation: Absence of repository .git/ and historical commit inspection.
3. Blindness isolation: Complete absence of golden holdout ground truth (golden_*.jsonl).
4. Network containment: Outbound network egress restriction.

A container or sandbox is ONLY homologated if ALL negative probes report BLOCKED_OK.
If ANY probe detects host access, it flags LEAKED and the gate fails closed (FAIL_CLOSED).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
from typing import Any


def check_host_credentials() -> dict[str, Any]:
    """Negative check: host credentials must NOT be accessible in the sandbox."""
    home = Path.home()
    probes = [
        home / ".ssh",
        home / ".aws",
        home / ".azure",
        home / ".infisical",
        Path("/root/.ssh"),
        Path("/root/.aws"),
        Path("/mnt/c/Users"),
    ]
    leaks = []
    for p in probes:
        try:
            if p.exists():
                leaks.append(str(p))
        except (PermissionError, OSError):
            continue

    passed = len(leaks) == 0
    return {
        "probe": "host_credentials",
        "status": "BLOCKED_OK" if passed else "LEAKED",
        "passed": passed,
        "detail": f"Tested {len(probes)} paths; {len(leaks)} accessible",
        "leaks": leaks,
    }


def check_git_isolation() -> dict[str, Any]:
    """Negative check: parent .git directory must NOT be accessible."""
    cwd = Path.cwd().resolve()
    git_found = []
    # Check cwd and all parents
    for path in (cwd, *cwd.parents):
        git_dir = path / ".git"
        try:
            if git_dir.exists():
                git_found.append(str(git_dir))
        except (PermissionError, OSError):
            continue

    passed = len(git_found) == 0
    return {
        "probe": "git_isolation",
        "status": "BLOCKED_OK" if passed else "LEAKED",
        "passed": passed,
        "detail": f"Checked {len(cwd.parents) + 1} parent directories for .git/",
        "leaks": git_found,
    }


def check_ground_truth_isolation() -> dict[str, Any]:
    """Negative check: holdout ground truth (golden_*.jsonl) must NOT be accessible."""
    cwd = Path.cwd().resolve()
    leaks = []
    # Check known ground truth locations or files with golden / truth in name
    for path in (cwd, *cwd.parents):
        gt_dir = path / "benchmarks" / "jev" / "ground_truth"
        try:
            if gt_dir.is_dir():
                leaks.append(str(gt_dir))
        except (PermissionError, OSError):
            continue
    # Check current tree for golden files
    try:
        for p in cwd.glob("**/golden_*.jsonl"):
            leaks.append(str(p))
    except (PermissionError, OSError):
        pass

    passed = len(leaks) == 0
    return {
        "probe": "ground_truth_isolation",
        "status": "BLOCKED_OK" if passed else "LEAKED",
        "passed": passed,
        "detail": f"Ground truth search; {len(leaks)} files/directories found",
        "leaks": leaks,
    }


def check_network_egress(timeout_s: float = 1.0) -> dict[str, Any]:
    """Check outbound network connectivity. In fully offline sandbox, egress is blocked."""
    target_ip = "8.8.8.8"
    target_port = 53
    is_blocked = False
    reason = "Connected successfully (network accessible)"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout_s)
        s.connect((target_ip, target_port))
        s.close()
    except (socket.timeout, OSError) as exc:
        is_blocked = True
        reason = f"Outbound socket blocked: {type(exc).__name__}"

    return {
        "probe": "network_containment",
        "status": "BLOCKED_OK" if is_blocked else "NETWORK_ACCESSIBLE",
        "passed": is_blocked,
        "detail": reason,
    }


def run_all_canaries() -> dict[str, Any]:
    cred = check_host_credentials()
    git = check_git_isolation()
    gt = check_ground_truth_isolation()
    net = check_network_egress()

    probes = [cred, git, gt, net]
    # For filesystem and confidentiality isolation: credentials, git, and ground truth MUST pass
    fs_isolated = cred["passed"] and git["passed"] and gt["passed"]
    fully_contained = fs_isolated and net["passed"]

    return {
        "canary_suite_version": "1.0.0",
        "filesystem_isolated": fs_isolated,
        "network_isolated": net["passed"],
        "all_canaries_passed": fully_contained,
        "isolation_verdict": "G1_VERIFIED" if fully_contained else "G1_BLOCKED_LEAKS_DETECTED",
        "probes": {
            "credentials": cred,
            "git": git,
            "ground_truth": gt,
            "network": net,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    results = run_all_canaries()
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0 if results["all_canaries_passed"] else 1

    print("=" * 60)
    print(" G1 ISOLATION NEGATIVE CANARY PROBES")
    print("=" * 60)
    for name, p in results["probes"].items():
        status_text = "PASS (BLOCKED)" if p["passed"] else "FAIL (LEAKED)"
        print(f"[{status_text:15s}] {name:22s}: {p['detail']}")
        if p.get("leaks"):
            for leak in p["leaks"][:3]:
                print(f"   -> Exposed: {leak}")
    print("=" * 60)
    print(f"Verdict: {results['isolation_verdict']}")
    print("=" * 60)
    return 0 if results["all_canaries_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
