#!/usr/bin/env python3
"""One-call real Jev/TypeSafe smoke test, NOT an isolated benchmark.

Run only from a trusted operator terminal via Infisical.  This test launches
no coding agent, uses a fixed public prompt, and never stores API credentials,
raw MCP output, or the provider response body.  A successful call proves
provider connectivity, not G1 sandbox containment or model quality.

Usage: python scripts/jev_live_smoke.py --package-entry PATH --execute-one-call
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jev_adapter import JevMcpClient

PACKAGE_NAME = "@french-castle/jev-code"
PACKAGE_VERSION = "0.5.0"
SAMPLE_QUESTION = "Implement automated unit tests for a small Python function."
SAMPLE_CLASSES = ["software-development", "project-documentation"]


class SmokePreflightError(RuntimeError):
    """Safe preflight error; messages contain no credential values."""


def verify_package(entry: Path) -> Path:
    """Require the exact published version and entry, prepared without secrets."""
    path = entry.expanduser().absolute()
    if not path.is_file() or path.is_symlink() or path.name != "cli.js" or path.parent.name != "dist":
        raise SmokePreflightError("Expected installed dist/cli.js file from pinned jev-code package")
    pkg = path.parent.parent
    manifest = pkg / "package.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise SmokePreflightError("Installed jev-code package manifest missing")
    try:
        obj = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SmokePreflightError("Invalid installed jev-code package manifest") from exc
    if obj.get("name") != PACKAGE_NAME or obj.get("version") != PACKAGE_VERSION:
        raise SmokePreflightError("Unexpected jev-code package name or version")
    return path


def isolated_child_env(parent: dict[str, str]) -> dict[str, str]:
    """Minimize inherited environment: key plus Node/Windows OS necessities.

    This is NOT OS filesystem/network containment. Never feed this environment
    to an untrusted coding agent. In particular, don't copy arbitrary API keys.
    """
    key = parent.get("TYPESAFE_API_KEY", "")
    if not key.strip():
        raise SmokePreflightError("TYPESAFE_API_KEY absent from this process; no call attempted")
    env = {"TYPESAFE_API_KEY": key, "NODE_ENV": "production"}
    for name in ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR"):
        if name in parent:
            env[name] = parent[name]
    return env


def run_one_call(entry: Path, parent_env: dict[str, str] | None = None) -> dict[str, Any]:
    """Exactly one advisory MCP classify call, no agent execution or writes."""
    source = os.environ if parent_env is None else parent_env
    env = isolated_child_env(source)
    cli = verify_package(entry)
    node = shutil.which("node", path=env.get("PATH"))
    if node is None:
        raise SmokePreflightError("Node.js missing from PATH")
    # The package was installed BEFORE invoking Infisical; no npx/npm download
    # is run in this secret-bearing process.  Do not print the MCP raw output.
    with JevMcpClient(command=[node, str(cli), "mcp"], env=env, cwd=cli.parent.parent) as client:
        result = client.classify(SAMPLE_QUESTION, SAMPLE_CLASSES, timeout_s=30.0)
    # Provider-controlled strings are never copied verbatim into logs.
    model = result.get("model")
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/@-]{1,120}", model):
        model = "REDACTED"
    return {
        "status": "PROVIDER_RESPONSE_OBSERVED",
        "scope": "ONE_CALL_SMOKE_ONLY_NOT_A_BENCHMARK",
        "upstream": PACKAGE_NAME,
        "upstream_version": PACKAGE_VERSION,
        "task_kind": "fixed_public_prompt",
        "label": result.get("label"),
        "decision_status": result.get("execution_status"),
        "model": model,
        "latency_ms": result.get("latency_ms"),
        "tokens_in": result.get("tokens_in"),
        "tokens_out": result.get("tokens_out"),
        "cost_usd": None,
        "model_quality_proven": False,
        "G1_verified": False,
        "benchmark_evidence": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-entry", type=Path, required=True)
    parser.add_argument("--execute-one-call", action="store_true",
                        help="Explicitly authorize exactly one potentially billable API call")
    args = parser.parse_args()
    if not args.execute_one_call:
        print("BLOCKED_AUTHORIZATION: add --execute-one-call", file=sys.stderr)
        return 2
    try:
        result = run_one_call(args.package_entry)
    except Exception as exc:
        # Never reflect provider errors, HTTP bodies, stack traces or credentials
        # to logs. Local debugging should use a separate, explicitly redacted tool.
        print(f"SMOKE_FAILED: {type(exc).__name__}; no provider body logged", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
