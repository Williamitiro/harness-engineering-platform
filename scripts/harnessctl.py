#!/usr/bin/env python3
"""Offline ECC lifecycle for .poc/ and read-only Codex project inspection.

No network, installer, model call, or production write. Python 3.12+ stdlib only.
Discovery/invocation/runtime execution are intentionally NOT claimed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import stat
import subprocess
import sys
import tempfile
import threading

SUPPORTED = {"codex": ".agents/skills", "claude": ".claude/skills"}
STATE = ".harness-install-record.json"
ALLOWED = {"tdd-workflow", "verification-loop"}
ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = ".harness/manifest.json"
# Byte-identical upstream copy shipped with the Harness (HE-R1-01); default source.
VENDORED = ROOT / "vendor" / "ecc"
BUNDLE_FILES = {"LICENSE", "SOURCE.json", *(f"skills/{name}/SKILL.md" for name in ALLOWED)}


class GateError(RuntimeError):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_probe(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Local metadata only; disable filter commands for status without changing config."""
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATHEXT"}}
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false",
               "-c", "core.hooksPath=/dev/null", "-C", str(repo)]
    if args and args[0] == "status":
        # Reading configuration names cannot invoke clean/process filters. Never
        # read/print their command values; override all drivers in this child only.
        filters = subprocess.run(
            [*command, "config", "--null", "--name-only", "--get-regexp", r"^filter\..*\.(clean|process)$"],
            capture_output=True, text=True, timeout=10, env=env, check=False)
        if filters.returncode not in (0, 1):
            raise GateError("Git filter configuration could not be inspected")
        drivers = {key.rsplit(".", 1)[0] for key in filters.stdout.split("\0") if key}
        for driver in sorted(drivers):
            for setting, value in (("clean", ""), ("process", ""), ("required", "false")):
                command.extend(["-c", f"{driver}.{setting}={value}"])
    return subprocess.run(
        [*command, *args], capture_output=True, text=True, timeout=10, env=env, check=False)


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
        # Windows junctions are not symlinks; refuse every reparse point too.
        try:
            attrs = getattr(part.lstat(), "st_file_attributes", 0)
        except (FileNotFoundError, NotADirectoryError):
            continue
        if attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise GateError(f"reparse path refused: {part}")


def cleanup_empty_parents(start_dir: Path, stop_at: Path) -> None:
    current = start_dir
    while current != stop_at and current != current.parent:
        if current.is_dir() and not any(current.iterdir()):
            current.rmdir()
            current = current.parent
        else:
            break


def check_sandbox(target: Path) -> None:
    if not target.is_dir():
        raise GateError("destination must be an existing directory")
    assert_no_symlink(target)
    base = (Path(__file__).resolve().parents[1] / ".poc").resolve()
    resolved = target.absolute().resolve(strict=False)
    if resolved == base or base not in resolved.parents:
        raise GateError("destination must be a child of THIS repository's .poc/")
    git_dir = target / ".git"
    if git_dir.exists() or git_dir.is_symlink():
        raise GateError("destination may not be a Git checkout")
    state_file = target / STATE
    if state_file.exists() and state_file.is_symlink():
        raise GateError("state symlink refused")


def check_source(source: Path, manifest: dict) -> list[dict]:
    """Accept a pinned ECC Git checkout or exactly this repository's bundled copy."""
    if not source.is_dir():
        raise GateError("ECC source checkout not found")
    assert_no_symlink(source)
    git_marker = source / ".git"
    if git_marker.exists() or git_marker.is_symlink():
        return check_git_source(source, manifest)
    if source.absolute().resolve() != VENDORED.absolute().resolve():
        raise GateError("ECC source must be the pinned Git checkout or the bundled vendor/ecc copy")
    return check_bundled_source(source, manifest)


def check_bundled_source(source: Path, manifest: dict) -> list[dict]:
    present = set()
    for path in source.rglob("*"):
        assert_no_symlink(path)
        if path.is_file():
            present.add(path.relative_to(source).as_posix())
        elif not path.is_dir():
            raise GateError("special file in bundled source refused")
    if present != BUNDLE_FILES:
        raise GateError("bundled source file list differs from the approved package")
    try:
        record = json.loads((source / "SOURCE.json").read_text(encoding="utf-8"))
    except ValueError as exc:
        raise GateError("bundled SOURCE.json is not valid JSON") from exc
    if str(record.get("commit", "")).lower() != manifest["ecc"]["commit"].lower():
        raise GateError("bundled source commit differs from the pinned commit")
    return hashed_skills(source, manifest)


def check_git_source(source: Path, manifest: dict) -> list[dict]:
    probe = git_probe(source, "rev-parse", "--verify", "HEAD")
    if probe.returncode != 0 or probe.stdout.strip().lower() != manifest["ecc"]["commit"].lower():
        raise GateError("ECC source HEAD differs from the pinned commit")
    status_probe = git_probe(source, "status", "--porcelain", "--ignore-submodules=all")
    if status_probe.returncode != 0 or status_probe.stdout.strip():
        raise GateError("ECC source worktree has uncommitted modifications or untracked files")
    # Never trust Git HEAD alone: the worktree can contain modified/untracked files.
    return hashed_skills(source, manifest)


def hashed_skills(source: Path, manifest: dict) -> list[dict]:
    result = []
    for name, expected in sorted(manifest["ecc"]["skills"].items()):
        source_file = source / "skills" / name / "SKILL.md"
        assert_no_symlink(source_file)
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


def inspect_project(repo: Path, client: str, preserve_contract: bool = False) -> dict:
    """Inspect only fixed integration paths, never target file contents or Git config.

    A .git marker is structural evidence only, including worktree gitfiles. Do
    not invoke Git, a client, hooks, or read the gitfile to resolve another path.
    No ownership or runtime compatibility is inferred from existing files.
    """
    if client != "codex":
        raise GateError("project inspection supports only codex")
    if ".." in repo.parts:
        raise GateError("--repo must not contain parent traversal")
    # Accept the explicit --repo . documented by SPEC §2.1. Do not resolve
    # links here: the existing ancestor checks must see and refuse them.
    repo = repo.absolute()
    assert_no_symlink(repo)
    if not repo.is_dir():
        raise GateError("--repo must be an existing repository directory")
    marker = repo / ".git"
    assert_no_symlink(marker)
    if not (marker.is_dir() or marker.is_file()):
        raise GateError("--repo must contain a .git directory or worktree marker")
    if preserve_contract and not (repo / "AGENTS.md").is_file():
        raise GateError("--preserve-contract requires an existing regular AGENTS.md")

    destinations = ([] if preserve_contract else ["AGENTS.md"]) + [*[
        f"{SUPPORTED[client]}/{name}/SKILL.md" for name in sorted(ALLOWED)
    ], ".harness/manifest.json"]
    # Conservatively block third-party skill directories and prior state. No
    # recursive inventory, existing-file hashes, content reads or ownership claims.
    watched = ["AGENTS.md", ".agents", SUPPORTED[client], ".harness", STATE]
    watched += [f"{SUPPORTED[client]}/{name}" for name in sorted(ALLOWED)]
    watched += destinations
    blockers = []
    for rel in dict.fromkeys(watched):
        path = repo / rel
        try:
            assert_no_symlink(path)
            exists = path.exists()
            if preserve_contract and rel == "AGENTS.md" and path.is_file():
                continue  # Existing project rules are neither read nor owned.
            container = rel in (".agents", SUPPORTED[client])
            # An empty native skills directory is compatible; any pre-existing
            # skill requires an explicit compatibility decision by the operator.
            collision = exists and (not container or not path.is_dir() or (
                rel == SUPPORTED[client] and next(path.iterdir(), None) is not None))
            if collision:
                blockers.append({"path": rel, "status": "BLOCKED_COLLISION"})
        except (GateError, OSError):
            blockers.append({"path": rel, "status": "BLOCKED_PATH"})

    changes = []
    for rel in destinations:
        affecting = [b["status"] for b in blockers
                     if rel == b["path"] or rel.startswith(b["path"] + "/")]
        action = ("BLOCKED_PATH" if "BLOCKED_PATH" in affecting else
                  "BLOCKED_COLLISION" if affecting else "WOULD_CREATE")
        changes.append({"path": rel, "action": action})
    return {
        "status": ("BLOCKED_PATH" if any(b["status"] == "BLOCKED_PATH" for b in blockers)
                   else "BLOCKED_COLLISION" if blockers else "COMPATIBLE_NOT_RUNTIME_VERIFIED"),
        "repo": str(repo), "client": client, "read_only": True,
        "contract_policy": "preserve-existing" if preserve_contract else "create-new",
        "compatibility": {"repository": "GIT_MARKER_ONLY", "client_layout": SUPPORTED[client],
                          "client_runtime": "NOT_PROBED", "ownership": "NOT_CLAIMED"},
        "changes": changes, "blockers": blockers,
        "source_validation": "NOT_RUN", "runtime_discovery": "NOT_RUN",
        "runtime_invocation": "NOT_RUN", "runtime_execution": "NOT_RUN",
    }


def project_root(repo: Path) -> Path:
    """Validate a real Git root for lifecycle operations, without running hooks."""
    inspect_project(repo, "codex")  # structural/path validation, no content reads
    repo = repo.absolute()
    result = git_probe(repo, "rev-parse", "--show-toplevel")
    if result.returncode or Path(result.stdout.strip()).resolve() != repo.resolve():
        raise GateError("--repo must be the root of a valid Git worktree")
    status = git_probe(repo, "status", "--porcelain", "--untracked-files=no", "--ignore-submodules=all")
    if status.returncode:
        raise GateError("Git status could not be inspected")
    return repo


def owned_bytes(path: Path, limit: int = 262144) -> bytes:
    assert_no_symlink(path)
    try:
        info = path.stat()
    except (FileNotFoundError, NotADirectoryError) as exc:
        raise GateError("managed file missing") from exc
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
        raise GateError("managed file must be regular, bounded and not hardlinked")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise GateError("managed file exceeds size limit")
    return data


def project_hashes(manifest: dict, preserve_contract: bool = False) -> dict[str, str]:
    contract = {} if preserve_contract else {"AGENTS.md": digest(owned_bytes(ROOT / "templates/AGENTS.md"))}
    return {**contract, **{
        f"{SUPPORTED['codex']}/{name}/SKILL.md": sha.lower()
        for name, sha in sorted(manifest["ecc"]["skills"].items())}}


def package_dirs(files: list[str]) -> set[str]:
    return {p.as_posix() for rel in files for p in Path(rel).parents if p != Path(".")}


def validate_record(repo: Path, state: str, expected: dict[str, str], kind: str) -> dict:
    record = json.loads(owned_bytes(repo / state))
    if not isinstance(record, dict) or record.get("schema_version") != 1 or record.get("kind") != kind:
        raise GateError("unsupported ownership record")
    entries = record.get("files")
    if not isinstance(entries, list) or len(entries) != len(expected):
        raise GateError("ownership file list differs from the approved package")
    found = {}
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise GateError("invalid ownership entry")
        rel = item["path"]
        if rel not in expected or rel in found or item.get("sha256") != expected[rel]:
            raise GateError("ownership path or hash differs from the approved package")
        found[rel] = item["sha256"]
    directories = record.get("created_dirs")
    allowed_dirs = package_dirs([*expected, state])
    if (not isinstance(directories, list) or any(not isinstance(d, str) or d not in allowed_dirs for d in directories)
            or len(set(directories)) != len(directories)):
        raise GateError("unsafe directory ownership")
    # Validate the complete record before opening any of its target files.
    for rel, sha in found.items():
        if digest(owned_bytes(repo / rel)) != sha:
            raise GateError(f"managed file missing or modified: {rel}")
    for rel in directories:
        assert_no_symlink(repo / rel)
    return record


def write_package(repo: Path, files: dict[str, bytes], state: str, record: dict) -> dict:
    """Exclusive creation; rollback only files/directories created by this call."""
    dirs = sorted(package_dirs([*files, state]), key=lambda p: (len(Path(p).parts), p))
    for rel in [*dirs, *files, state]:
        assert_no_symlink(repo / rel)
    if any((repo / rel).exists() for rel in [*files, state]):
        raise GateError("BLOCKED_COLLISION: destination already exists")
    record["created_dirs"] = [rel for rel in dirs if not (repo / rel).exists()]
    record["files"] = [{"path": rel, "sha256": digest(raw)} for rel, raw in files.items()]
    payloads = {**files, state: (json.dumps(record, indent=2) + "\n").encode("utf-8")}
    created, made_dirs = [], []
    try:
        for rel in record["created_dirs"]:
            path = repo / rel
            assert_no_symlink(path)
            path.mkdir()
            made_dirs.append(path)
        for rel, raw in payloads.items():
            path = repo / rel
            assert_no_symlink(path)
            with path.open("xb") as handle:
                created.append(path)
                handle.write(raw)
    except Exception:
        for path in reversed(created):
            path.unlink()
        for path in reversed(made_dirs):
            path.rmdir()
        raise
    return record


def remove_package(repo: Path, state: str, record: dict) -> None:
    # Keep originals in memory until all removals succeed. Never touch unowned files.
    state_bytes = owned_bytes(repo / state)
    if json.loads(state_bytes) != record:
        raise GateError("ownership record changed since verification")
    originals = {}
    for item in record["files"]:
        raw = owned_bytes(repo / item["path"])
        if digest(raw) != item["sha256"]:
            raise GateError("managed file changed since verification")
        originals[item["path"]] = raw
    originals[state] = state_bytes
    deleted, removed_dirs = [], []
    try:
        for rel in originals:
            path = repo / rel
            assert_no_symlink(path)
            if owned_bytes(path) != originals[rel]:
                raise GateError("managed file changed during removal")
            path.unlink()
            deleted.append(rel)
        for rel in sorted(record["created_dirs"], key=lambda p: (len(Path(p).parts), p), reverse=True):
            path = repo / rel
            assert_no_symlink(path)
            if path.is_dir() and next(path.iterdir(), None) is None:
                path.rmdir()
                removed_dirs.append(rel)
    except Exception:
        # Directory cleanup is part of the transaction. Rebuild only directories
        # actually removed by this call, parents first, then restore exclusive files.
        for rel in sorted(removed_dirs, key=lambda p: (len(Path(p).parts), p)):
            path = repo / rel
            assert_no_symlink(path)
            path.mkdir()
        for rel in deleted:
            with (repo / rel).open("xb") as handle:
                handle.write(originals[rel])
        raise


def verify_project(repo: Path, manifest: dict) -> dict:
    repo = project_root(repo)
    initial = json.loads(owned_bytes(repo / PROJECT_STATE))
    if not isinstance(initial, dict) or initial.get("contract_policy", "create-new") not in ("create-new", "preserve-existing"):
        raise GateError("unsupported project contract policy")
    policy = initial.get("contract_policy", "create-new")
    record = validate_record(repo, PROJECT_STATE,
                             project_hashes(manifest, preserve_contract=policy == "preserve-existing"), "harness-project")
    if record.get("contract_policy", "create-new") != policy:
        raise GateError("ownership contract policy changed during verification")
    notice = record.get("license_notice")
    if (record.get("client") != "codex" or record.get("ecc_commit") != manifest["ecc"]["commit"]
            or not isinstance(notice, str) or digest(notice.encode("utf-8")) != manifest["ecc"].get("license_sha256")):
        raise GateError("ownership pin, client or license differs from approved package")
    return record


def attach_project(repo: Path, source: Path, manifest: dict, preserve_contract: bool = False) -> dict:
    repo = project_root(repo)
    if (repo / PROJECT_STATE).exists():
        record = verify_project(repo, manifest)
        if (record.get("contract_policy", "create-new") == "preserve-existing") != preserve_contract:
            raise GateError("installed contract policy differs; verify or remove before changing modes")
        return {"status": "ALREADY_ATTACHED", "runtime_execution": "NOT_RUN"}
    inspection = inspect_project(repo, "codex", preserve_contract=preserve_contract)
    if inspection["blockers"]:
        raise GateError(f"{inspection['status']}: review project-plan; no files overwritten")
    skills = check_source(source.absolute(), manifest)
    notice = owned_bytes(source / "LICENSE")
    if digest(notice) != manifest["ecc"].get("license_sha256"):
        raise GateError("ECC license differs from approved hash")
    files = {} if preserve_contract else {"AGENTS.md": owned_bytes(ROOT / "templates/AGENTS.md")}
    for skill in skills:
        raw = owned_bytes(Path(skill["source"]))
        if digest(raw) != skill["sha256"]:
            raise GateError("source changed since validation")
        files[f"{SUPPORTED['codex']}/{skill['name']}/SKILL.md"] = raw
    # Recheck paths and collisions after source verification and before writing.
    if inspect_project(repo, "codex", preserve_contract=preserve_contract)["blockers"]:
        raise GateError("project changed since inspection")
    record = {"schema_version": 1, "kind": "harness-project", "client": "codex",
              "contract_policy": "preserve-existing" if preserve_contract else "create-new",
              "ecc_commit": manifest["ecc"]["commit"], "license_notice": notice.decode("utf-8"),
              "runtime_execution": "NOT_RUN"}
    write_package(repo, files, PROJECT_STATE, record)
    return {"status": "FILES_INSTALLED_RUNTIME_NOT_VERIFIED", "runtime_execution": "NOT_RUN"}


def remove_project(repo: Path, manifest: dict, apply: bool = True) -> dict:
    repo = project_root(repo)
    if not (repo / PROJECT_STATE).exists():
        # Do not treat linked or conflicting state paths as an absent installation.
        assert_no_symlink(repo / PROJECT_STATE)
        return {"status": "ALREADY_REMOVED"}
    record = verify_project(repo, manifest)
    if not apply:
        return {"status": "PLANNED_NOT_REMOVED", "files": [x["path"] for x in record["files"]]}
    remove_package(repo, PROJECT_STATE, record)
    return {"status": "REMOVED_EXACT_OWNED_FILES"}


# --- Repository layer, package 2 (HE-R1-03): project rules only, no generic skills ---
# Rules files belong to the project. The Harness creates them from templates when
# absent, never reads or rewrites existing ones, and on removal deletes only files
# it created that are still byte-identical to the approved template.

REPO_RULES = {"AGENTS.md": ROOT / "templates/repo/AGENTS.md", "CLAUDE.md": ROOT / "templates/repo/CLAUDE.md"}


def check_repo_path(repo: Path) -> Path:
    if ".." in repo.parts:
        raise GateError("--repo must not contain parent traversal")
    repo = repo.absolute()
    assert_no_symlink(repo)
    if not repo.is_dir():
        raise GateError("--repo must be an existing repository directory")
    marker = repo / ".git"
    assert_no_symlink(marker)
    if not (marker.is_dir() or marker.is_file()):
        raise GateError("--repo must contain a .git directory or worktree marker")
    return repo


def read_repo_record(repo: Path) -> dict:
    record = json.loads(owned_bytes(repo / PROJECT_STATE))
    if not isinstance(record, dict) or record.get("kind") != "harness-project":
        raise GateError("unsupported project ownership record")
    return record


def repo_inspect(repo: Path) -> dict:
    """Read-only: path metadata only. Never opens project files except the Harness record."""
    repo = check_repo_path(repo)
    blockers, changes = [], []
    for rel in (".harness", PROJECT_STATE, STATE):
        try:
            assert_no_symlink(repo / rel)
        except GateError:
            blockers.append({"path": rel, "status": "BLOCKED_PATH"})
    installed = None
    if not blockers:
        if (repo / STATE).exists():
            blockers.append({"path": STATE, "status": "BLOCKED_COLLISION"})
        if (repo / PROJECT_STATE).is_file():
            try:  # the Harness's own record is the only file this inspection opens
                installed = read_repo_record(repo).get("package", 1)
            except (GateError, ValueError):
                blockers.append({"path": PROJECT_STATE, "status": "BLOCKED_COLLISION"})
        elif (repo / ".harness").exists():
            blockers.append({"path": ".harness", "status": "BLOCKED_COLLISION"})
    for name in REPO_RULES:
        path = repo / name
        try:
            assert_no_symlink(path)
        except GateError:
            blockers.append({"path": name, "status": "BLOCKED_PATH"})
            changes.append({"path": name, "action": "BLOCKED_PATH"})
            continue
        if not path.exists():
            changes.append({"path": name, "action": "WOULD_CREATE"})
        elif path.is_file():
            changes.append({"path": name, "action": "PRESERVE_CHECK_IMPORT" if name == "CLAUDE.md" else "PRESERVE"})
        else:
            blockers.append({"path": name, "status": "BLOCKED_COLLISION"})
            changes.append({"path": name, "action": "BLOCKED_COLLISION"})
    if installed is None:
        changes.append({"path": PROJECT_STATE, "action": "WOULD_CREATE"})
    case = "NEW_REPO" if all(p.name == ".git" for p in repo.iterdir()) else "EXISTING_REPO"
    if any(b["status"] == "BLOCKED_PATH" for b in blockers):
        status = "BLOCKED_PATH"
    elif blockers:
        status = "BLOCKED_COLLISION"
    elif installed == 2:
        status = "ATTACHED"
    elif installed is not None:
        status = "LEGACY_ATTACHED"
    else:
        status = "COMPATIBLE_NOT_RUNTIME_VERIFIED"
    return {"status": status, "case": case, "repo": str(repo), "read_only": True, "package": 2,
            "compatibility": {"repository": "GIT_MARKER_ONLY", "client_runtime": "NOT_PROBED",
                              "ownership": "NOT_CLAIMED"},
            "changes": changes if installed is None else [], "blockers": blockers,
            "note": "CLAUDE.md existente: confira se contém a linha @AGENTS.md (o Harness não lê nem altera)."
                    if any(c["action"] == "PRESERVE_CHECK_IMPORT" for c in changes) else None,
            "runtime_discovery": "NOT_RUN"}


def validate_repo_record(record: dict) -> None:
    files, preserved, dirs = record.get("files"), record.get("preserved"), record.get("created_dirs")
    if (record.get("package") != 2 or not isinstance(files, list) or not isinstance(preserved, list)
            or not isinstance(dirs, list) or any(d not in (".harness",) for d in dirs)):
        raise GateError("invalid package 2 ownership record")
    paths = []
    for item in files:
        if (not isinstance(item, dict) or item.get("path") not in REPO_RULES
                or not isinstance(item.get("sha256"), str) or len(item["sha256"]) != 64):
            raise GateError("ownership record lists a path outside the repository package")
        paths.append(item["path"])
    if (len(set(paths)) != len(paths) or any(p not in REPO_RULES for p in preserved)
            or set(paths) & set(preserved)):
        raise GateError("ownership record paths are duplicated or inconsistent")


def created_file_state(repo: Path, item: dict) -> str:
    path = repo / item["path"]
    assert_no_symlink(path)
    if not path.exists():
        return "MISSING"
    try:
        current = digest(owned_bytes(path))
    except GateError:
        return "EDITED_BY_PROJECT"  # e.g. grew past the size bound; never owned again
    template = digest(owned_bytes(REPO_RULES[item["path"]]))
    return "UNCHANGED" if current == item["sha256"] == template else "EDITED_BY_PROJECT"


def repo_attach(repo: Path) -> dict:
    repo = project_root(repo)
    inspection = repo_inspect(repo)
    if inspection["status"] == "ATTACHED":
        repo_verify(repo)
        return {"status": "ALREADY_ATTACHED", "package": 2, "runtime_execution": "NOT_RUN"}
    if inspection["status"] == "LEGACY_ATTACHED":
        return {"status": "LEGACY_ATTACHED", "package": 1,
                "migration": "project-remove --apply e depois project-attach --apply (pacote 2 sem cópia de skills)"}
    if inspection["blockers"]:
        raise GateError(f"{inspection['status']}: review project-plan; no files written")
    actions = {c["path"]: c["action"] for c in inspection["changes"]}
    files = {name: owned_bytes(template) for name, template in REPO_RULES.items() if actions[name] == "WOULD_CREATE"}
    preserved = [name for name in REPO_RULES if actions[name].startswith("PRESERVE")]
    if repo_inspect(repo)["changes"] != inspection["changes"]:
        raise GateError("project changed since inspection")
    write_package(repo, files, PROJECT_STATE, {
        "schema_version": 1, "kind": "harness-project", "package": 2,
        "preserved": preserved, "runtime_execution": "NOT_RUN"})
    return {"status": "FILES_INSTALLED_RUNTIME_NOT_VERIFIED", "package": 2, "case": inspection["case"],
            "created": sorted(files), "preserved": preserved, "note": inspection["note"],
            "runtime_execution": "NOT_RUN"}


def repo_verify(repo: Path) -> dict:
    repo = project_root(repo)
    record = read_repo_record(repo)
    if record.get("package", 1) == 1:
        verify_project(repo, read_manifest(ROOT / "config/approved_skills.json"))
        return {"status": "OK", "package": 1, "migration": "project-remove --apply e depois project-attach --apply"}
    validate_repo_record(record)
    return {"status": "OK", "package": 2, "preserved": record["preserved"],
            "files": {item["path"]: created_file_state(repo, item) for item in record["files"]}}


def repo_remove(repo: Path, apply: bool = False) -> dict:
    repo = project_root(repo)
    state = repo / PROJECT_STATE
    if not state.exists():
        assert_no_symlink(state)
        return {"status": "ALREADY_REMOVED"}
    record = read_repo_record(repo)
    if record.get("package", 1) == 1:
        return remove_project(repo, read_manifest(ROOT / "config/approved_skills.json"), apply=apply)
    validate_repo_record(record)
    states = {item["path"]: created_file_state(repo, item) for item in record["files"]}
    delete = [p for p, s in states.items() if s == "UNCHANGED"]
    kept = [p for p, s in states.items() if s == "EDITED_BY_PROJECT"]
    if not apply:
        return {"status": "PLANNED_NOT_REMOVED", "delete": delete + [PROJECT_STATE], "kept": kept}
    originals = {rel: owned_bytes(repo / rel) for rel in delete}
    originals[PROJECT_STATE] = owned_bytes(state)
    deleted, removed_dirs = [], []
    try:
        for rel, raw in originals.items():
            path = repo / rel
            assert_no_symlink(path)
            if owned_bytes(path) != raw:
                raise GateError("file changed during removal")
            path.unlink()
            deleted.append(rel)
        for rel in record["created_dirs"]:
            path = repo / rel
            assert_no_symlink(path)
            if path.is_dir() and next(path.iterdir(), None) is None:
                path.rmdir()
                removed_dirs.append(rel)
    except Exception:
        for rel in removed_dirs:
            (repo / rel).mkdir()
        for rel in deleted:
            with (repo / rel).open("xb") as handle:
                handle.write(originals[rel])
        raise
    return {"status": "REMOVED_EXACT_OWNED_FILES", "deleted": deleted, "kept": kept}


def lifecycle_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Repository layer (package 2): project rules only; never overwrites")
    parser.add_argument("action", choices=("project-attach", "project-verify", "project-remove"))
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--client", choices=("codex", "claude"), help="informational; the package serves both")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--preserve-contract", action="store_true",
                        help="kept for compatibility; existing rules are always preserved")
    # Accepted only so the old installed setup-harness keeps working until HE-R1-04.
    parser.add_argument("--source", type=Path, help="deprecated and ignored: package 2 copies no skills")
    args = parser.parse_args(argv)
    try:
        if args.action == "project-attach":
            if not args.apply:
                raise GateError("attach needs --apply; inspect project-plan first")
            result = repo_attach(args.repo)
            if args.source is not None:
                result["deprecated"] = "--source ignorado: o pacote 2 não copia skills para o repositório"
        elif args.action == "project-verify":
            result = repo_verify(args.repo)
        else:
            result = repo_remove(args.repo, apply=args.apply)
        print(json.dumps(result, indent=2))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, GateError) else "project lifecycle blocked; no raw contents emitted"
        print(json.dumps({"status": "BLOCKED", "reason": reason}), file=sys.stderr)
        return 2


# --- Machine layer (HE-R1-02): workflow skills once per computer, per detected tool ---

MACHINE_STATE = ".harness-machine.json"
MACHINE_SKILL_NAMES = sorted(ALLOWED | {"setup-harness"})
# Approved setup-harness versions installed by the old setup-skill-* bootstrap (HE-OP-02B/03),
# LF and CRLF checkouts. Only these are migrated or removed automatically.
LEGACY_BOOTSTRAP_SKILL_SHA = {
    "694da9570afcca1d79bcaeb092990cf6e7a87ee9d087e85d09c7baac8cf8cfea",
    "05300ed9051d001a5cfb79494a6e020f31ea6c471a81c031ab58a007fab8d9f9",
    "f2715d7c3b789227e06a04c6f36c279f6aee3bb02f1f7575d701d2628d198d35",
}
LEGACY_BOOTSTRAP_YAML_SHA = {
    "a1499d95abd8447558c535fe5554adcc3c9b988a0a39264a6283d430effe1e94",
    "3bf863a8856d04a6a1c4f23b3aae6cbf5388544129662c55cc733c2d9c23bbbf",
}


def read_adapters(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    adapters = data.get("adapters") if isinstance(data, dict) else None
    if data.get("schema_version") != 1 or not isinstance(adapters, dict) or not adapters:
        raise GateError("invalid adapter table")
    for name, entry in adapters.items():
        rel = entry.get("machine_skills") if isinstance(entry, dict) else None
        detect = entry.get("detect") if isinstance(entry, dict) else None
        if (not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts
                or not isinstance(detect, list) or not detect
                or any(not isinstance(d, str) or ".." in Path(d).parts for d in detect)):
            raise GateError(f"invalid adapter entry: {name}")
    return data


def is_link(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        attrs = getattr(path.lstat(), "st_file_attributes", 0)
    except (FileNotFoundError, NotADirectoryError):
        return False
    return bool(attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def machine_roots(home: Path, adapters: dict) -> tuple[Path, list[dict], list[str]]:
    """Resolve one install root per detected tool. A tool root may be a link only
    when it points exactly at another tool's real root (operator's own junction)."""
    home = home.absolute()
    assert_no_symlink(home)
    if not home.is_dir():
        raise GateError("home must be an existing directory")
    copies, links, skipped = [], [], []
    for name, entry in sorted(adapters["adapters"].items()):
        rel = entry["machine_skills"]
        root = home / rel
        installed = (home / rel / MACHINE_STATE).exists() if not is_link(root) else False
        if not installed and not any((home / d).exists() for d in entry["detect"]):
            skipped.append(name)
            continue
        assert_no_symlink(root.parent)
        if is_link(root):
            links.append({"adapter": name, "root": rel, "mode": "alias"})
        elif root.exists() and not root.is_dir():
            raise GateError(f"BLOCKED_COLLISION: {rel} is not a directory")
        else:
            copies.append({"adapter": name, "root": rel, "mode": "copy"})
    if not copies and not links:
        raise GateError("BLOCKED_NO_SUPPORTED_TOOL: neither Claude Code nor Codex detected in this home")
    for link in links:
        target = (home / link["root"]).resolve()
        match = [c for c in copies if (home / c["root"]).exists() and (home / c["root"]).resolve() == target]
        if not match:
            raise GateError(f"BLOCKED_LINK: {link['root']} links outside the Harness skill roots")
        link["alias_of"] = match[0]["adapter"]
    return home, copies + links, skipped


def machine_payload(catalog: dict) -> tuple[dict[str, bytes], str]:
    """Bundled ECC skills {name: SKILL.md bytes} and the MIT notice."""
    skills = check_source(VENDORED, catalog)
    notice = owned_bytes(VENDORED / "LICENSE")
    if digest(notice) != catalog["ecc"].get("license_sha256"):
        raise GateError("ECC license differs from approved hash")
    return {s["name"]: owned_bytes(Path(s["source"])) for s in skills}, notice.decode("utf-8")


def setup_skill_files() -> dict[str, bytes]:
    """setup-harness for the machine package (HE-R1-04): no fixed client."""
    descriptor = {"schema_version": 2, "harnessctl": str(ROOT / "scripts/harnessctl.py")}
    return {"setup-harness/SKILL.md": owned_bytes(ROOT / "skills/setup-harness/SKILL.md"),
            "setup-harness/agents/openai.yaml": owned_bytes(ROOT / "skills/setup-harness/agents/openai.yaml"),
            "setup-harness/harness-location.json": (json.dumps(descriptor, indent=2) + "\n").encode("utf-8")}


def machine_files(catalog: dict) -> tuple[dict[str, bytes], str]:
    skills, notice = machine_payload(catalog)
    return {**{f"{name}/SKILL.md": raw for name, raw in sorted(skills.items())}, **setup_skill_files()}, notice


def root_package(root: str, files: dict[str, bytes]) -> tuple[dict[str, bytes], str]:
    return {f"{root}/{rel}": raw for rel, raw in sorted(files.items())}, f"{root}/{MACHINE_STATE}"


def classify_machine_root(home: Path, root: dict, files: dict[str, bytes], catalog: dict) -> tuple[str, dict]:
    """CURRENT, or UPGRADE when an older package is intact and only lacks newer files."""
    expected, state = root_package(root["root"], files)
    record = json.loads(owned_bytes(home / state))
    if (not isinstance(record, dict) or record.get("kind") != "harness-machine"
            or record.get("adapter") != root["adapter"] or record.get("ecc_commit") != catalog["ecc"]["commit"]):
        raise GateError("machine ownership adapter or pin mismatch")
    entries = record.get("files")
    if not isinstance(entries, list) or not entries:
        raise GateError("invalid machine ownership record")
    seen = set()
    for item in entries:
        rel = item.get("path") if isinstance(item, dict) else None
        if rel not in expected or rel in seen:
            raise GateError("machine ownership record lists an unknown or duplicated path")
        seen.add(rel)
        if item.get("sha256") != digest(expected[rel]):
            if rel.endswith("harness-location.json"):
                try:
                    other = json.loads(owned_bytes(home / rel)).get("harnessctl")
                except (GateError, ValueError, AttributeError):
                    other = None
                raise GateError(f"installed by another Harness checkout ({other}); run machine-* from there")
            raise GateError(f"installed file differs from this Harness version: {rel}")
        if digest(owned_bytes(home / rel)) != item["sha256"]:
            raise GateError(f"managed file missing or modified: {rel}")
    dirs = record.get("created_dirs")
    if not isinstance(dirs, list) or any(d not in package_dirs([*expected, state]) for d in dirs):
        raise GateError("unsafe directory ownership")
    return ("CURRENT" if seen == set(expected) else "UPGRADE"), record


def legacy_bootstrap_state(root: str) -> str:
    return f"{root}/setup-harness/.harness-bootstrap.json"


def verify_legacy_bootstrap(home: Path, root: str) -> dict:
    """Old setup-skill-* install: verified against its own record plus frozen approved versions."""
    state = legacy_bootstrap_state(root)
    record = json.loads(owned_bytes(home / state))
    folder = f"{root}/setup-harness"
    allowed = {f"{folder}/SKILL.md", f"{folder}/harness-location.json", f"{folder}/agents/openai.yaml"}
    if not isinstance(record, dict) or record.get("kind") != "harness-bootstrap":
        raise GateError("unsupported bootstrap ownership record")
    entries = record.get("files")
    paths = [i.get("path") for i in entries if isinstance(i, dict)] if isinstance(entries, list) else []
    required = {f"{folder}/SKILL.md", f"{folder}/harness-location.json"}
    if len(paths) != len(entries or []) or len(set(paths)) != len(paths) or not required <= set(paths) \
            or not set(paths) <= allowed:
        raise GateError("bootstrap ownership file list differs from the approved package")
    current = setup_skill_files()
    approved = {f"{folder}/SKILL.md": LEGACY_BOOTSTRAP_SKILL_SHA | {digest(current["setup-harness/SKILL.md"])},
                f"{folder}/agents/openai.yaml": LEGACY_BOOTSTRAP_YAML_SHA
                | {digest(current["setup-harness/agents/openai.yaml"])}}
    for item in entries:
        rel = item["path"]
        if digest(owned_bytes(home / rel)) != item.get("sha256"):
            raise GateError(f"managed file missing or modified: {rel}")
        if rel in approved and item["sha256"] not in approved[rel]:
            raise GateError(f"unknown setup-harness version, not removed automatically: {rel}")
    descriptor = json.loads(owned_bytes(home / f"{folder}/harness-location.json"))
    if not isinstance(descriptor, dict) or descriptor.get("schema_version") not in (1, 2):
        raise GateError("unsupported bootstrap descriptor")
    dirs = record.get("created_dirs")
    if not isinstance(dirs, list) or any(d not in package_dirs([*allowed, state]) for d in dirs):
        raise GateError("unsafe directory ownership")
    return record


def machine_plan(home: Path, catalog: dict, adapters: dict) -> dict:
    home, roots, skipped = machine_roots(home, adapters)
    files, _ = machine_files(catalog)
    planned, installed, migrations = [], [], []
    for root in (r for r in roots if r["mode"] == "copy"):
        expected, state = root_package(root["root"], files)
        owned = set()
        if (home / state).exists():
            status, record = classify_machine_root(home, root, files, catalog)
            if status == "CURRENT":
                installed.append(root["adapter"])
                continue
            migrations.append({"adapter": root["adapter"], "action": "UPGRADE_PACKAGE"})
            owned = {i["path"] for i in record["files"]}
        new_names = {Path(rel).relative_to(root["root"]).parts[0] for rel in expected if rel not in owned}
        for name in sorted(new_names):
            path = home / root["root"] / name
            if not (path.exists() or is_link(path)):
                continue
            if any(rel.startswith(f"{root['root']}/{name}/") for rel in owned):
                continue
            if name == "setup-harness" and (home / legacy_bootstrap_state(root["root"])).is_file():
                verify_legacy_bootstrap(home, root["root"])
                migrations.append({"adapter": root["adapter"], "action": "MIGRATE_BOOTSTRAP"})
                continue
            raise GateError(f"BLOCKED_COLLISION: {root['root']}/{name} already exists and is not Harness-owned")
        planned += [*expected, state]
    return {"status": "PLANNED_NOT_INSTALLED" if planned else "ALREADY_INSTALLED", "home": str(home),
            "roots": roots, "skipped": skipped, "files": planned, "already_installed": installed,
            "migrations": migrations, "runtime_discovery": "NOT_RUN"}


def snapshot_package(home: Path, record: dict) -> tuple[dict[str, bytes], dict]:
    files = {i["path"]: owned_bytes(home / i["path"]) for i in record["files"]}
    base = {k: v for k, v in record.items() if k not in ("files", "created_dirs")}
    return files, base


def machine_install(home: Path, catalog: dict, adapters: dict) -> dict:
    result = machine_plan(home, catalog, adapters)
    if result["status"] == "ALREADY_INSTALLED":
        return result
    home = Path(result["home"])
    files, notice = machine_files(catalog)
    actions = {(m["adapter"], m["action"]) for m in result["migrations"]}
    removed, done = [], []  # packages removed by this call (to restore) / packages written (to undo)
    try:
        for root in (r for r in result["roots"]
                     if r["mode"] == "copy" and r["adapter"] not in result["already_installed"]):
            expected, state = root_package(root["root"], files)
            if (root["adapter"], "MIGRATE_BOOTSTRAP") in actions:
                lstate = legacy_bootstrap_state(root["root"])
                lrecord = verify_legacy_bootstrap(home, root["root"])
                snap = snapshot_package(home, lrecord)
                remove_package(home, lstate, lrecord)
                removed.append((lstate, *snap))
            if (root["adapter"], "UPGRADE_PACKAGE") in actions:
                _, old = classify_machine_root(home, root, files, catalog)
                snap = snapshot_package(home, old)
                remove_package(home, state, old)
                removed.append((state, *snap))
            record = write_package(home, expected, state, {
                "schema_version": 1, "kind": "harness-machine", "adapter": root["adapter"],
                "ecc_commit": catalog["ecc"]["commit"], "license_notice": notice})
            done.append((state, record))
    except Exception:
        for state, record in reversed(done):  # all roots or none from this call
            remove_package(home, state, record)
        for state, old_files, base in reversed(removed):
            write_package(home, old_files, state, base)
        raise
    return {"status": "FILES_INSTALLED_RUNTIME_NOT_VERIFIED", "roots": result["roots"],
            "skipped": result["skipped"], "migrations": result["migrations"], "runtime_discovery": "NOT_RUN"}


def machine_verify(home: Path, catalog: dict, adapters: dict) -> dict:
    home, roots, skipped = machine_roots(home, adapters)
    files, _ = machine_files(catalog)
    for root in (r for r in roots if r["mode"] == "copy"):
        if not (home / root_package(root["root"], files)[1]).exists():
            raise GateError(f"NOT_INSTALLED: {root['adapter']} detected but machine-install not applied")
        if classify_machine_root(home, root, files, catalog)[0] != "CURRENT":
            raise GateError(f"UPGRADE_AVAILABLE: {root['adapter']} has an older package; run machine-install --apply")
    return {"status": "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED", "roots": roots, "skipped": skipped,
            "runtime_discovery": "NOT_RUN"}


def machine_remove(home: Path, catalog: dict, adapters: dict, apply: bool = False) -> dict:
    home, roots, _ = machine_roots(home, adapters)
    files, _ = machine_files(catalog)
    owned = []
    for root in (r for r in roots if r["mode"] == "copy"):
        state = root_package(root["root"], files)[1]
        if (home / state).exists():
            owned.append((state, classify_machine_root(home, root, files, catalog)[1]))
    if not owned:
        return {"status": "ALREADY_REMOVED"}
    if not apply:
        return {"status": "PLANNED_NOT_REMOVED",
                "files": [item["path"] for _, record in owned for item in record["files"]]}
    for state, record in owned:
        remove_package(home, state, record)
    return {"status": "REMOVED_EXACT_OWNED_FILES"}


def match_discovery(listing: dict, names: list[str]) -> dict:
    entries = [s for block in listing.get("data", []) if isinstance(block, dict)
               for s in block.get("skills", []) if isinstance(s, dict) and s.get("scope") == "user"]
    result = {}
    for name in names:
        found = [s for s in entries if s.get("name") == name]
        status = "DISCOVERED" if any(s.get("enabled") for s in found) else ("DISABLED" if found else "MISSING")
        result[name] = {"status": status, "paths": [s.get("path") for s in found]}
    return result


def codex_skill_listing(timeout_s: float = 30.0) -> dict:
    """Native metadata only: initialize + skills/list. No thread, turn, model or secret."""
    exe = shutil.which("codex")
    if exe is None:
        raise GateError("BLOCKED_CLIENT_NOT_FOUND: codex CLI not on PATH")
    keep = {"PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE",
            "APPDATA", "LOCALAPPDATA", "CODEX_HOME"}
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    messages: queue.Queue = queue.Queue()
    # npm's codex shim spawns child processes that may release the cwd a moment late.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as cwd:
        process = subprocess.Popen([exe, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, cwd=cwd, env=env)

        def reader():
            for raw in process.stdout:
                try:
                    messages.put(json.loads(raw))
                except ValueError:
                    pass
            messages.put(None)

        threading.Thread(target=reader, daemon=True).start()

        def call(ident: int, method: str, params: dict) -> dict:
            process.stdin.write((json.dumps({"id": ident, "method": method, "params": params}) + "\n").encode())
            process.stdin.flush()
            for _ in range(4096):
                try:
                    message = messages.get(timeout=timeout_s)
                except queue.Empty:
                    raise GateError("codex app-server timed out") from None
                if message is None:
                    raise GateError("codex app-server exited")
                if message.get("id") == ident:
                    if not isinstance(message.get("result"), dict):
                        raise GateError(f"codex app-server rejected {method}")
                    return message["result"]
            raise GateError("codex app-server event limit")

        try:
            call(1, "initialize", {"clientInfo": {"name": "harnessctl", "version": "1"}})
            process.stdin.write(b'{"method":"initialized","params":{}}\n')
            process.stdin.flush()
            return call(2, "skills/list", {"cwds": [cwd], "forceReload": True})
        finally:
            stop_own_process_tree(process)


def stop_own_process_tree(process: subprocess.Popen) -> None:
    """Close stdin so the server exits by itself; otherwise end only the tree we started."""
    process.stdin.close()
    try:
        process.wait(timeout=10)
        return
    except subprocess.TimeoutExpired:
        pass
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, timeout=15, check=False)
    else:
        process.kill()
    process.wait(timeout=10)


def machine_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Machine layer: Harness skills once per computer, per detected tool")
    parser.add_argument("action", choices=("machine-plan", "machine-install", "machine-verify",
                                           "machine-remove", "machine-discover"))
    parser.add_argument("--home", type=Path, help="user home; defaults to the current user's home")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    home = args.home if args.home is not None else Path.home()
    try:
        catalog = read_manifest(ROOT / "config/approved_skills.json")
        adapters = read_adapters(ROOT / "config/adapters.json")
        if args.action == "machine-plan":
            result = machine_plan(home, catalog, adapters)
        elif args.action == "machine-install":
            if not args.apply:
                raise GateError("machine installation needs --apply; inspect machine-plan first")
            result = machine_install(home, catalog, adapters)
        elif args.action == "machine-verify":
            result = machine_verify(home, catalog, adapters)
        elif args.action == "machine-remove":
            result = machine_remove(home, catalog, adapters, apply=args.apply)
        else:
            if args.home is not None:
                raise GateError("discovery uses the real tool configuration; --home is not supported")
            names = MACHINE_SKILL_NAMES
            result = {"codex": match_discovery(codex_skill_listing(), names),
                      "claude": "MANUAL_CHECK_REQUIRED: open a new Claude Code session and list skills",
                      "model_turns_started": 0}
        print(json.dumps(result, indent=2))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, GateError) else "machine operation blocked; no raw contents emitted"
        print(json.dumps({"status": "BLOCKED", "reason": reason}), file=sys.stderr)
        return 2


def bootstrap_package(home: Path, client: str) -> tuple[Path, dict[str, bytes], str]:
    if client not in SUPPORTED or ".." in home.parts:
        raise GateError("invalid bootstrap client or home path")
    home = home.absolute()
    assert_no_symlink(home)
    if not home.is_dir():
        raise GateError("personal home must be an existing directory")
    folder = f"{SUPPORTED[client]}/setup-harness"
    location = {"schema_version": 1, "client": client,
                "harnessctl": str(ROOT / "scripts/harnessctl.py"),
                "ecc_source": str(ROOT / ".poc/ecc-pinned"),
                "project_client_supported": client == "codex"}
    files = {f"{folder}/SKILL.md": owned_bytes(ROOT / "skills/setup-harness/SKILL.md"),
             f"{folder}/harness-location.json": (json.dumps(location, indent=2) + "\n").encode("utf-8")}
    if client == "codex":
        files[f"{folder}/agents/openai.yaml"] = owned_bytes(ROOT / "skills/setup-harness/agents/openai.yaml")
    state = f"{folder}/.harness-bootstrap.json"
    for rel in [*files, state]:
        assert_no_symlink(home / rel)
    return home, files, state


def verify_setup_skill(home: Path, client: str) -> dict:
    home, files, state = bootstrap_package(home, client)
    # Accept the approved old versions too, so an install made before the HE-R1-04 rewrite
    # stays verifiable and removable (deprecated path; machine-install migrates it).
    record = verify_legacy_bootstrap(home, SUPPORTED[client])
    if record.get("client") != client:
        raise GateError("bootstrap ownership client mismatch")
    return record


def plan_setup_skill(home: Path, client: str) -> dict:
    home, files, state = bootstrap_package(home, client)
    if (home / state).exists():
        verify_setup_skill(home, client)
        return {"status": "ALREADY_INSTALLED", "runtime_discovery": "NOT_RUN"}
    folder = (home / state).parent
    if folder.exists():
        raise GateError("BLOCKED_COLLISION: personal setup-harness directory already exists")
    for rel in package_dirs([*files, state]):
        path = home / rel
        if path.exists() and not path.is_dir():
            raise GateError("BLOCKED_COLLISION: personal skill ancestor is not a directory")
    return {"status": "PLANNED_NOT_INSTALLED", "client": client, "home": str(home),
            "files": [*files, state], "runtime_discovery": "NOT_RUN",
            "project_client_supported": client == "codex"}


def install_setup_skill(home: Path, client: str) -> dict:
    result = plan_setup_skill(home, client)
    if result["status"] == "ALREADY_INSTALLED":
        return result
    home, files, state = bootstrap_package(home, client)
    write_package(home, files, state, {"schema_version": 1, "kind": "harness-bootstrap", "client": client})
    return {"status": "FILES_INSTALLED_RUNTIME_NOT_VERIFIED", "client": client,
            "runtime_discovery": "NOT_RUN", "project_client_supported": client == "codex"}


def remove_setup_skill(home: Path, client: str, apply: bool = False) -> dict:
    home, files, state = bootstrap_package(home, client)
    record = verify_setup_skill(home, client)
    if not apply:
        return {"status": "PLANNED_NOT_REMOVED", "files": [*files, state]}
    remove_package(home, state, record)
    return {"status": "REMOVED_EXACT_OWNED_FILES"}


def bootstrap_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Opt-in personal setup-harness skill installation; no project writes")
    parser.add_argument("action", choices=("setup-skill-plan", "setup-skill-install", "setup-skill-verify", "setup-skill-remove"))
    parser.add_argument("--client", choices=tuple(SUPPORTED), required=True)
    parser.add_argument("--home", type=Path, help="personal home; defaults to the current user's home")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    home = args.home if args.home is not None else Path.home()
    try:
        if args.action == "setup-skill-plan":
            result = plan_setup_skill(home, args.client)
        elif args.action == "setup-skill-install":
            if not args.apply:
                raise GateError("personal installation needs --apply; inspect setup-skill-plan first")
            result = install_setup_skill(home, args.client)
        elif args.action == "setup-skill-verify":
            verify_setup_skill(home, args.client)
            result = {"status": "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED", "runtime_discovery": "NOT_RUN"}
        else:
            result = remove_setup_skill(home, args.client, apply=args.apply)
        print(json.dumps(result, indent=2))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError) as exc:
        reason = str(exc) if isinstance(exc, GateError) else "personal skill operation blocked"
        print(json.dumps({"status": "BLOCKED", "reason": reason}), file=sys.stderr)
        return 2


def project_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Read-only repository inspection (package 2); never installs files")
    parser.add_argument("action", choices=("project-doctor", "project-plan"))
    parser.add_argument("--repo", type=Path, required=True, help="explicit repository root (absolute or relative)")
    parser.add_argument("--client", choices=("codex", "claude"), help="informational; the package serves both")
    parser.add_argument("--preserve-contract", action="store_true",
                        help="kept for compatibility; existing rules are always preserved")
    args = parser.parse_args(argv)
    try:
        result = repo_inspect(args.repo)
        if args.action == "project-plan":
            result["templates"] = {name: str(path.relative_to(ROOT).as_posix()) for name, path in REPO_RULES.items()}
            if result["status"] == "COMPATIBLE_NOT_RUNTIME_VERIFIED":
                result["status"] = "PLANNED_NOT_INSTALLED"
        print(json.dumps(result, indent=2))
        return 2 if result["blockers"] else 0
    except (GateError, OSError, ValueError) as exc:
        # Do not echo OS exceptions, filenames from directory listings or contents.
        reason = str(exc) if isinstance(exc, GateError) else "project inspection failed"
        print(json.dumps({"status": "BLOCKED", "reason": reason}), file=sys.stderr)
        return 2


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("project-doctor", "project-plan"):
        return project_main(argv)
    if argv and argv[0] in ("project-attach", "project-verify", "project-remove"):
        return lifecycle_main(argv)
    if argv and argv[0] in ("setup-skill-plan", "setup-skill-install", "setup-skill-verify", "setup-skill-remove"):
        return bootstrap_main(argv)
    if argv and argv[0].startswith("machine-"):
        return machine_main(argv)
    parser = argparse.ArgumentParser(description=__doc__, epilog=(
        "Read-only project commands: project-doctor / project-plan --repo PATH --client codex. "
        "Lifecycle: project-attach / project-verify / project-remove. "
        "Personal bootstrap: setup-skill-plan / setup-skill-install / setup-skill-verify / setup-skill-remove. "
        "Use COMMAND --help for their separate options."))
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
