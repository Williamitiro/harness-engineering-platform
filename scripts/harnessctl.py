#!/usr/bin/env python3
"""Offline, allowlisted ECC skill lifecycle for disposable A1 sandboxes.

No network, installer, model call, or production write. Python 3.12+ stdlib only.
Discovery/invocation/runtime execution are intentionally NOT claimed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SUPPORTED = {"codex": ".agents/skills", "claude": ".claude/skills"}
STATE = ".harness-install-record.json"
ALLOWED = {"tdd-workflow", "verification-loop"}


class GateError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("ecc"), dict):
        raise GateError("invalid manifest")
    ecc = data["ecc"]
    if not isinstance(ecc.get("commit"), str) or len(ecc["commit"]) != 40:
        raise GateError("ECC commit must be a full 40-character SHA")
    skills = ecc.get("skills")
    if not isinstance(skills, dict) or set(skills) != ALLOWED:
        raise GateError("manifest must allowlist exactly the two pilot skills")
    for name, expected in skills.items():
        if not isinstance(expected, str) or len(expected) != 64:
            raise GateError(f"invalid checksum for {name}")
        try:
            int(expected, 16)
        except ValueError as exc:
            raise GateError(f"non-hex checksum for {name}") from exc
    return data


def assert_no_symlink(path: Path) -> None:
    p = path.absolute()
    for part in (p, *p.parents):
        if part.is_symlink():
            raise GateError(f"symlink path refused: {part}")


def cleanup_empty_parents(start_dir: Path, stop_at: Path) -> None:
    current = start_dir
    while current != stop_at and current != current.parent:
        if current.is_dir() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent
        else:
            break


def check_sandbox(target: Path) -> None:
    if not target.is_dir() or ".poc" not in target.parts:
        raise GateError("destination must be an existing directory below .poc/")
    assert_no_symlink(target)
    git_dir = target / ".git"
    if git_dir.exists() or git_dir.is_symlink():
        raise GateError("destination may not be a Git checkout")
    state_file = target / STATE
    if state_file.exists() and state_file.is_symlink():
        raise GateError("state symlink refused")


def check_source(source: Path, manifest: dict) -> list[dict]:
    if not source.is_dir():
        raise GateError("ECC source checkout not found")
    assert_no_symlink(source)
    probe = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--verify", "HEAD"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if probe.returncode != 0 or probe.stdout.strip().lower() != manifest["ecc"]["commit"].lower():
        raise GateError("ECC source HEAD differs from the pinned commit")
    status_probe = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain"],
        capture_output=True, text=True, check=False, timeout=10,
    )
    if status_probe.returncode != 0 or status_probe.stdout.strip():
        raise GateError("ECC source worktree has uncommitted modifications or untracked files")
    # Never trust Git HEAD alone: the worktree can contain modified/untracked files.
    result = []
    for name, expected in sorted(manifest["ecc"]["skills"].items()):
        source_file = source / "skills" / name / "SKILL.md"
        if not source_file.is_file() or source_file.is_symlink():
            raise GateError(f"source skill missing or linked: {name}")
        raw = source_file.read_bytes()
        if digest(raw) != expected.lower():
            raise GateError(f"upstream skill hash mismatch: {name}")
        result.append({"name": name, "sha256": expected.lower(), "source": str(source_file)})
    return result


def plan(source: Path, target: Path, adapter: str, manifest: dict) -> dict:
    check_sandbox(target)
    if adapter not in SUPPORTED:
        raise GateError("adapter must be 'codex' or 'claude'")
    skills = check_source(source, manifest)
    if (target / STATE).exists():
        raise GateError("previous installation state exists; verify or remove first")
    changes = []
    for skill in skills:
        dst = target / SUPPORTED[adapter] / skill["name"] / "SKILL.md"
        assert_no_symlink(dst)
        if dst.exists() or dst.parent.exists():
            raise GateError(f"collision detected: {dst}")
        changes.append({
            "name": skill["name"], "source": skill["source"],
            "destination": str(dst), "sha256": skill["sha256"],
        })
    return {
        "status": "PLANNED_NOT_INSTALLED",
        "adapter": adapter,
        "pinned_ecc_commit": manifest["ecc"]["commit"],
        "target": str(target),
        "changes": changes,
        "runtime_discovery": "NOT_RUN",
        "runtime_invocation": "NOT_RUN",
        "runtime_execution": "NOT_RUN",
    }


def install(result: dict, target: Path) -> None:
    # Recheck all collisions and source bytes before the first write.
    check_sandbox(target)
    if (target / STATE).exists():
        raise GateError("state already exists")
    validated: list[tuple[Path, bytes]] = []
    for change in result["changes"]:
        src, dst = Path(change["source"]), Path(change["destination"])
        assert_no_symlink(dst)
        if dst.exists() or dst.parent.exists():
            raise GateError(f"collision detected: {dst}")
        raw = src.read_bytes()
        if digest(raw) != change["sha256"]:
            raise GateError("source changed since plan")
        validated.append((dst, raw))
    created: list[Path] = []
    try:
        for dst, raw in validated:
            dst.parent.mkdir(parents=True, exist_ok=False)
            with dst.open("xb") as handle:
                handle.write(raw)
            created.append(dst)
        record = {
            "schema_version": 1,
            "adapter": result["adapter"],
            "ecc_commit": result["pinned_ecc_commit"],
            "files": [
                {"path": str(dst.relative_to(target)).replace(os.sep, "/"),
                 "sha256": digest(raw)}
                for dst, raw in validated
            ],
            "runtime_status": "NOT_RUN",
        }
        with (target / STATE).open("x", encoding="utf-8") as handle:
            json.dump(record, handle, indent=2)
            handle.write("\n")
    except Exception:
        for dst in reversed(created):
            if dst.exists():
                dst.unlink()
            cleanup_empty_parents(dst.parent, target)
        if (target / STATE).exists():
            (target / STATE).unlink()
        raise


def record_and_paths(target: Path, manifest: dict | None = None) -> tuple[dict, list[Path]]:
    check_sandbox(target)
    path = target / STATE
    if not path.is_file() or path.is_symlink():
        raise GateError("installation record missing")
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("schema_version") != 1 or record.get("adapter") not in SUPPORTED:
        raise GateError("unsupported installation record")
    if manifest is not None:
        if record.get("ecc_commit", "").lower() != manifest["ecc"]["commit"].lower():
            raise GateError("installation record commit differs from manifest")
    files = record.get("files")
    if not isinstance(files, list) or len(files) != 2:
        raise GateError("installation record must contain exactly two files")
    names = set()
    destinations = []
    for item in files:
        if not isinstance(item, dict):
            raise GateError("invalid file entry")
        rel = item.get("path", "")
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts or "\\" in rel:
            raise GateError("unsafe relative path in installation record")
        expected_name = rel_path.parent.name
        if expected_name not in ALLOWED or rel_path.name != "SKILL.md":
            raise GateError("unexpected destination in installation record")
        if rel_path.as_posix() != f"{SUPPORTED[record['adapter']]}/{expected_name}/SKILL.md":
            raise GateError("destination not in allowlisted skill directory")
        if expected_name in names:
            raise GateError("duplicate skill entry")
        names.add(expected_name)
        dst = target / rel_path
        assert_no_symlink(dst)
        sha = item.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            raise GateError("invalid sha256 in installation record")
        if manifest is not None and sha.lower() != manifest["ecc"]["skills"].get(expected_name, "").lower():
            raise GateError(f"installation record hash does not match manifest for {expected_name}")
        if not dst.is_file() or digest(dst.read_bytes()) != sha.lower():
            raise GateError(f"managed file missing or modified: {dst}")
        destinations.append(dst)
    if names != ALLOWED:
        raise GateError("missing allowlisted skill")
    return record, destinations


def remove(target: Path, manifest: dict | None = None) -> None:
    _, paths = record_and_paths(target, manifest=manifest)  # No partial removal on a mismatch.
    for dst in paths:
        dst.unlink()
        cleanup_empty_parents(dst.parent, target)
    (target / STATE).unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "install", "verify", "remove"))
    parser.add_argument("--source", type=Path, help="pre-fetched ECC Git checkout at pinned commit")
    parser.add_argument("--target", type=Path, required=True, help="existing disposable .poc/ directory")
    parser.add_argument("--adapter", choices=tuple(SUPPORTED), default="codex")
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).resolve().parents[1] / "config" / "approved_skills.json")
    parser.add_argument("--apply", action="store_true", help="explicit opt-in for writes")
    args = parser.parse_args(argv)
    try:
        assert_no_symlink(args.target)
        target = args.target.resolve(strict=True)
        assert_no_symlink(target)
        manifest = read_manifest(args.manifest) if args.manifest.exists() else None
        if args.action in ("plan", "install"):
            if args.source is None:
                raise GateError("--source required for plan/install")
            assert_no_symlink(args.source)
            source = args.source.resolve(strict=True)
            assert_no_symlink(source)
            if manifest is None:
                raise GateError("manifest file missing")
            spec = plan(source, target, args.adapter, manifest)
            if args.action == "install":
                if not args.apply:
                    raise GateError("install needs --apply")
                install(spec, target)
                spec["status"] = "FILES_INSTALLED_RUNTIME_NOT_VERIFIED"
            print(json.dumps(spec, indent=2))
        elif args.action == "verify":
            rec, paths = record_and_paths(target, manifest=manifest)
            print(json.dumps({"status": "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED",
                              "adapter": rec["adapter"], "verified_files": len(paths)}, indent=2))
        else:
            if not args.apply:
                raise GateError("remove needs --apply")
            remove(target, manifest=manifest)
            print(json.dumps({"status": "REMOVED_EXACT_OWNED_FILES"}))
        return 0
    except (GateError, FileNotFoundError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
