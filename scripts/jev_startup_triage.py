#!/usr/bin/env python3
"""Free, keyless Windows Node/Jev MCP startup comparison; no model calls.

Exactly two possible environment profiles, in one bounded invocation:
  MINIMAL: same non-secret keys the live paired executor currently passes
  WINDOWS_OS: MINIMAL plus a small allowlist of OS-required paths
No credential is read, inherited, forwarded, saved or displayed. A successful
handshake is local readiness only, not OpenRouter connectivity or G1 proof.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.jev_adapter import JevAdapterError, JevMcpClient
from scripts.jev_live_smoke import verify_package

NODE_MINIMAL_KEYS = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP", "TMPDIR")
NODE_WINDOWS_KEYS = ("SystemDrive", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                     "HOMEDRIVE", "HOMEPATH", "PROGRAMDATA", "ProgramFiles")
JEV_ENTRY = (Path(tempfile.gettempdir()) / "harness-jev-smoke-050"
             / "node_modules" / "@french-castle" / "jev-code" / "dist" / "cli.js")


def clean_runtime_env(parent: dict[str, str], windows_os: bool = False) -> dict[str, str]:
    """Fixed allowlist. Does NOT include Infisical, provider or agent credentials."""
    keys = NODE_MINIMAL_KEYS + (NODE_WINDOWS_KEYS if windows_os else ())
    env = {k: parent[k] for k in keys if k in parent}
    env.update({"NODE_ENV": "production", "JEV_CODE_PROVIDER": "openrouter",
                "JEV_CODE_MAX_RETRIES": "0", "JEV_CODE_TIMEOUT_MS": "30000"})
    return env


def stderr_category(data: bytes) -> list[str]:
    """Parse only fixed categories. Never retain or emit raw stderr."""
    low = data[:16384].lower()
    result = set()
    for name, indicators in (
        ("NODE_ASSERTION_OR_ABORT", (b"assertion failed", b"sigabrt", b"abort()")),
        ("NODE_FATAL_RUNTIME", (b"fatal error", b"uv_fatal_error", b"uv_loop")),
        ("NODE_OUT_OF_MEMORY", (b"heap out of memory", b"allocation failed")),
        ("NODE_MODULE_MISSING", (b"err_module_not_found", b"cannot find module")),
        ("NODE_SYNTAX_ERROR", (b"syntaxerror", b"unexpected token")),
        ("PROCESS_ACCESS_DENIED", (b"eacces", b"access is denied")),
        ("PROCESS_FILE_MISSING", (b"enoent", b"no such file")),
    ):
        if any(term in low for term in indicators):
            result.add(name)
    return sorted(result)


def check_node(node: str, env: dict[str, str]) -> dict:
    try:
        run = subprocess.run(
            [node, "-e", "process.stdout.write('HE_NODE_READY ' + process.version)"],
            cwd=None, env=env, capture_output=True, timeout=8, check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "FAIL", "code": "NODE_TIMEOUT"}
    except OSError:
        return {"status": "FAIL", "code": "NODE_SPAWN_FAILED"}
    match = re.fullmatch(rb"HE_NODE_READY (v\d+\.\d+\.\d+)", run.stdout)
    ok = run.returncode == 0 and match is not None
    return {"status": "PASS" if ok else "FAIL",
            "node_version": match.group(1).decode("ascii") if match else None,
            "code": "NODE_READY" if ok else "NODE_STARTUP_FAILED",
            "exit_code": run.returncode,
            "stderr_categories": stderr_category(run.stderr)}


def check_mcp(node: str, entry: Path, env: dict[str, str]) -> dict:
    client = JevMcpClient([node, str(entry), "mcp"], env, entry.parent.parent)
    try:
        with client:
            diag = client.startup_diagnostic()
        return {"status": "PASS", "code": "MCP_INITIALIZED",
                "diagnostic": diag}
    except JevAdapterError as exc:
        return {"status": "FAIL", "code": exc.diagnostic_code,
                "diagnostic": client.startup_diagnostic()}
    except (OSError, ValueError):
        return {"status": "FAIL", "code": "MCP_LOCAL_ERROR",
                "diagnostic": client.startup_diagnostic()}


def main() -> int:
    if os.name != "nt":
        print(json.dumps({"status": "BLOCKED", "code": "WINDOWS_ONLY"}))
        return 2
    try:
        entry = verify_package(JEV_ENTRY)
        minimal = clean_runtime_env(dict(os.environ))
        node = shutil.which("node", path=minimal.get("PATH"))
        if not node:
            raise RuntimeError("NODE_NOT_FOUND")
    except (ValueError, OSError, RuntimeError):
        print(json.dumps({"status": "BLOCKED", "code": "PACKAGE_OR_NODE_MISSING"}))
        return 2

    # No keys have been copied. Upstream creates provider client only upon tools/call.
    steps = {}
    steps["node_minimal"] = check_node(node, minimal)
    if steps["node_minimal"]["status"] == "PASS":
        steps["mcp_minimal"] = check_mcp(node, entry, minimal)
    if steps.get("mcp_minimal", {}).get("status") == "PASS":
        verdict = "MINIMAL_ENV_MCP_READY_WITHOUT_CREDENTIALS"
    else:
        operational = clean_runtime_env(dict(os.environ), windows_os=True)
        steps["node_windows_os"] = check_node(node, operational)
        if steps["node_windows_os"]["status"] == "PASS":
            steps["mcp_windows_os"] = check_mcp(node, entry, operational)
        verdict = ("WINDOWS_ENV_DEPENDENCY_CONFIRMED"
                   if steps.get("mcp_windows_os", {}).get("status") == "PASS"
                   else "MCP_OR_NODE_FAILURE_STILL_PRESENT")
    print(json.dumps({"status": verdict, "paid_calls": 0,
                      "provider_tools_called": 0, "secrets_forwarded": False,
                      "steps": steps}, sort_keys=True, indent=2))
    return 0 if verdict in ("MINIMAL_ENV_MCP_READY_WITHOUT_CREDENTIALS",
                            "WINDOWS_ENV_DEPENDENCY_CONFIRMED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
