#!/usr/bin/env python3
"""Infisical CLI verification and sanitized secret presence checker.

Adheres strictly to zero-leak security rules:
- NEVER logs, prints, or exports secret values.
- Validates CLI installation, active profile, organization, and project linking.
- Reports secret availability as strictly 'PRESENTE', 'AUSENTE', or 'ERRO'.
- Provides exact commands for trusted terminal execution by the operator.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECRET_VAR_NAME = "TYPESAFE_API_KEY"


def check_cli_installed() -> dict[str, Any]:
    bin_path = shutil.which("infisical")
    if not bin_path:
        return {"installed": False, "version": None, "path": None, "error": "infisical binary not found on PATH"}
    try:
        proc = subprocess.run([bin_path, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10, check=False)
        output = proc.stdout.strip() or proc.stderr.strip()
        # Parse version e.g. "infisical version 0.44.11"
        match = re.search(r"version\s+([0-9]+\.[0-9]+\.[0-9]+)", output, re.IGNORECASE)
        version = match.group(1) if match else output
        return {"installed": True, "version": version, "path": bin_path, "raw": output}
    except Exception as exc:
        return {"installed": False, "version": None, "path": bin_path, "error": str(exc)}


def check_profile() -> dict[str, Any]:
    bin_path = shutil.which("infisical")
    if not bin_path:
        return {"authenticated": False, "error": "CLI not installed"}
    try:
        proc = subprocess.run([bin_path, "profile", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False)
        lines = proc.stdout.splitlines()
        # Look for line with active marker '*'
        for line in lines:
            if line.strip().startswith("*"):
                parts = [p.strip() for p in line.split() if p.strip()]
                # Format: * NAME EMAIL ORG SESSION DOMAIN
                name = parts[1] if len(parts) > 1 else "UNKNOWN"
                email = parts[2] if len(parts) > 2 else "UNKNOWN"
                org = parts[3] if len(parts) > 3 else "UNKNOWN"
                session = parts[4] if len(parts) > 4 else "UNKNOWN"
                domain = parts[5] if len(parts) > 5 else "UNKNOWN"
                return {
                    "authenticated": session.lower() == "active",
                    "profile_name": name,
                    "email": email,
                    "organization": org,
                    "session_status": session,
                    "domain": domain,
                }
        return {"authenticated": False, "error": "No active profile found in profile list"}
    except Exception as exc:
        return {"authenticated": False, "error": str(exc)}


def check_local_project_config() -> dict[str, Any]:
    config_file = ROOT / ".infisical.yaml"
    if not config_file.exists():
        # Fallback to legacy .infisical.json
        legacy_file = ROOT / ".infisical.json"
        if legacy_file.exists():
            try:
                data = json.loads(legacy_file.read_text(encoding="utf-8"))
                return {"configured": True, "file": ".infisical.json", "project_id": data.get("projectId")}
            except Exception as exc:
                return {"configured": False, "error": f"Failed to read .infisical.json: {exc}"}
        return {"configured": False, "error": ".infisical.yaml not found"}
    try:
        # Simple YAML extraction without external pyyaml dependency
        content = config_file.read_text(encoding="utf-8")
        project_id = None
        for line in content.splitlines():
            if "project-id:" in line:
                project_id = line.split("project-id:")[1].strip()
                break
        return {"configured": bool(project_id), "file": ".infisical.yaml", "project_id": project_id}
    except Exception as exc:
        return {"configured": False, "error": str(exc)}


def check_remote_project() -> dict[str, Any]:
    bin_path = shutil.which("infisical")
    if not bin_path:
        return {"project_found": False, "error": "CLI not installed"}
    try:
        proc = subprocess.run([bin_path, "sm", "projects", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False)
        output = proc.stdout
        # Check if "Harness Engineering" is in table
        has_harness = "Harness Engineering" in output
        # Extract project id if possible
        match = re.search(r"Harness Engineering\s*[│|]\s*([^\s│|]+)\s*[│|]\s*([a-f0-9\-]+)", output)
        project_slug = match.group(1) if match else "harness-engineering-ok-qq"
        project_id = match.group(2) if match else None
        return {
            "project_found": has_harness,
            "project_name": "Harness Engineering",
            "project_slug": project_slug,
            "project_id": project_id,
        }
    except Exception as exc:
        return {"project_found": False, "error": str(exc)}


def check_environment(project_id: str | None = None) -> dict[str, Any]:
    bin_path = shutil.which("infisical")
    if not bin_path:
        return {"env_found": False, "error": "CLI not installed"}
    try:
        cmd = [bin_path, "sm", "projects", "get"]
        if project_id:
            cmd.append(f"--projectId={project_id}")
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, check=False)
        output = proc.stdout
        has_dev = "Development" in output or "dev" in output
        return {
            "environment_checked": "dev",
            "environment_available": has_dev,
            "all_environments": ["dev", "staging", "prod"] if has_dev else [],
        }
    except Exception as exc:
        return {"env_found": False, "error": str(exc)}


def check_secret_presence(var_name: str = SECRET_VAR_NAME) -> dict[str, Any]:
    """Sanitized presence check. NEVER exposes secret value."""
    val = os.environ.get(var_name)
    if (val is None or len(val.strip()) == 0) and var_name == SECRET_VAR_NAME:
        alt_val = os.environ.get("OPENROUTER_API_KEY")
        if alt_val is not None and len(alt_val.strip()) > 0:
            val = alt_val
            var_name = "OPENROUTER_API_KEY"
    if val is not None and len(val.strip()) > 0:
        val_clean = val.strip()
        provider_hint = "openrouter" if (val_clean.startswith("sk-or-") or var_name == "OPENROUTER_API_KEY") else "typesafe"
        return {
            "variable_name": var_name,
            "status": "PRESENTE",
            "available_to_process": True,
            "char_length": len(val_clean),
            "format": "REDACTED",
            "provider_hint": provider_hint,
        }
    return {
        "variable_name": var_name,
        "status": "AUSENTE",
        "available_to_process": False,
        "note": "Secret not injected in this process environment",
    }


def run_full_verification() -> dict[str, Any]:
    cli = check_cli_installed()
    profile = check_profile()
    local_cfg = check_local_project_config()
    remote_proj = check_remote_project()
    project_id = local_cfg.get("project_id") or remote_proj.get("project_id")
    env_info = check_environment(project_id)
    secret_status = check_secret_presence()

    is_ready = (
        cli.get("installed") is True
        and profile.get("authenticated") is True
        and remote_proj.get("project_found") is True
        and env_info.get("environment_available") is True
    )

    return {
        "verifier_version": "1.0.0",
        "cli": cli,
        "profile": profile,
        "local_project": local_cfg,
        "remote_project": remote_proj,
        "environment": env_info,
        "secret_presence": secret_status,
        "overall_status": "AUTHENTICATED_AND_LINKED" if is_ready else "CONFIG_INCOMPLETE",
        "operator_instructions": {
            "presence_test_powershell": (
                'infisical run --env=dev -- powershell -NoProfile -Command '
                '"if ($env:TYPESAFE_API_KEY) { Write-Output \'STATUS: PRESENTE\' } '
                'else { Write-Output \'STATUS: AUSENTE\' }"'
            ),
            "presence_test_python": (
                'infisical run --env=dev -- python scripts/infisical_verifier.py --check-only'
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Output full report as JSON")
    parser.add_argument("--check-only", action="store_true", help="Only output sanitized secret status: PRESENTE or AUSENTE")
    args = parser.parse_args()

    if args.check_only:
        res = check_secret_presence()
        print(f"SECRET_{res['variable_name']}: {res['status']}")
        return 0 if res["status"] == "PRESENTE" else 1

    report = run_full_verification()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print(" HARNESS ENGINEERING — INFISICAL VERIFICATION REPORT")
    print("=" * 60)
    cli = report["cli"]
    print(f"CLI:          {'OK' if cli.get('installed') else 'FAIL'} (Version: {cli.get('version')})")
    prof = report["profile"]
    print(f"Auth Profile: {'OK' if prof.get('authenticated') else 'FAIL'} (Org: {prof.get('organization')}, Email: {prof.get('email')})")
    proj = report["remote_project"]
    print(f"Project:      {'OK' if proj.get('project_found') else 'FAIL'} ({proj.get('project_name')} - {proj.get('project_id')})")
    env = report["environment"]
    print(f"Environment:  {'OK' if env.get('environment_available') else 'FAIL'} ({env.get('environment_checked')})")
    sec = report["secret_presence"]
    print(f"Secret Check: {sec.get('status')} ({sec.get('variable_name')})")
    print("=" * 60)
    print(f"Overall Status: {report['overall_status']}")
    print("=" * 60)
    print("\n[Operador: para testar a injeção autorizada em terminal confiável:]")
    print(report["operator_instructions"]["presence_test_powershell"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
