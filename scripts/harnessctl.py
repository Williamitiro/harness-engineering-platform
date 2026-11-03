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
import stat
import subprocess
import sys

SUPPORTED = {"codex": ".agents/skills", "claude": ".claude/skills"}
STATE = ".harness-install-record.json"
ALLOWED = {"tdd-workflow", "verification-loop"}
ROOT = Path(__file__).resolve().parents[1]
PROJECT_STATE = ".harness/manifest.json"


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
    if not source.is_dir():
        raise GateError("ECC source checkout not found")
    assert_no_symlink(source)
    probe = git_probe(source, "rev-parse", "--verify", "HEAD")
    if probe.returncode != 0 or probe.stdout.strip().lower() != manifest["ecc"]["commit"].lower():
        raise GateError("ECC source HEAD differs from the pinned commit")
    status_probe = git_probe(source, "status", "--porcelain", "--ignore-submodules=all")
    if status_probe.returncode != 0 or status_probe.stdout.strip():
        raise GateError("ECC source worktree has uncommitted modifications or untracked files")
    # Never trust Git HEAD alone: the worktree can contain modified/untracked files.
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


def inspect_project(repo: Path, client: str) -> dict:
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

    destinations = ["AGENTS.md", *[
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


def project_hashes(manifest: dict) -> dict[str, str]:
    return {"AGENTS.md": digest(owned_bytes(ROOT / "templates/AGENTS.md")), **{
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
    record = validate_record(repo, PROJECT_STATE, project_hashes(manifest), "harness-project")
    notice = record.get("license_notice")
    if (record.get("client") != "codex" or record.get("ecc_commit") != manifest["ecc"]["commit"]
            or not isinstance(notice, str) or digest(notice.encode("utf-8")) != manifest["ecc"].get("license_sha256")):
        raise GateError("ownership pin, client or license differs from approved package")
    return record


def attach_project(repo: Path, source: Path, manifest: dict) -> dict:
    repo = project_root(repo)
    if (repo / PROJECT_STATE).exists():
        verify_project(repo, manifest)
        return {"status": "ALREADY_ATTACHED", "runtime_execution": "NOT_RUN"}
    inspection = inspect_project(repo, "codex")
    if inspection["blockers"]:
        raise GateError(f"{inspection['status']}: review project-plan; no files overwritten")
    skills = check_source(source.absolute(), manifest)
    notice = owned_bytes(source / "LICENSE")
    if digest(notice) != manifest["ecc"].get("license_sha256"):
        raise GateError("ECC license differs from approved hash")
    files = {"AGENTS.md": owned_bytes(ROOT / "templates/AGENTS.md")}
    for skill in skills:
        raw = owned_bytes(Path(skill["source"]))
        if digest(raw) != skill["sha256"]:
            raise GateError("source changed since validation")
        files[f"{SUPPORTED['codex']}/{skill['name']}/SKILL.md"] = raw
    # Recheck paths and collisions after source verification and before writing.
    if inspect_project(repo, "codex")["blockers"]:
        raise GateError("project changed since inspection")
    record = {"schema_version": 1, "kind": "harness-project", "client": "codex",
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


def lifecycle_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Explicit Codex project lifecycle; never overwrites existing files")
    parser.add_argument("action", choices=("project-attach", "project-verify", "project-remove"))
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--client", choices=("codex",), default="codex")
    parser.add_argument("--source", type=Path, help="existing pinned ECC checkout; required on first attach")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        manifest = read_manifest(ROOT / "config/approved_skills.json")
        if args.action == "project-attach":
            if not args.apply:
                raise GateError("attach needs --apply; inspect project-plan first")
            if args.source is None:
                raise GateError("attach needs --source pointing to the pinned ECC checkout")
            result = attach_project(args.repo, args.source, manifest)
        elif args.action == "project-verify":
            verify_project(args.repo, manifest)
            result = {"status": "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED", "runtime_execution": "NOT_RUN"}
        else:
            result = remove_project(args.repo, manifest, apply=args.apply)
        print(json.dumps(result, indent=2))
        return 0
    except (GateError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        reason = str(exc) if isinstance(exc, GateError) else "project lifecycle blocked; no raw contents emitted"
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
    record = validate_record(home, state, {p: digest(raw) for p, raw in files.items()}, "harness-bootstrap")
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
    parser = argparse.ArgumentParser(description="Read-only Codex project metadata inspection; never installs files")
    parser.add_argument("action", choices=("project-doctor", "project-plan"))
    parser.add_argument("--repo", type=Path, required=True, help="explicit repository root (absolute or relative)")
    parser.add_argument("--client", choices=("codex",), required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect_project(args.repo, args.client)
        if args.action == "project-plan":
            root = Path(__file__).resolve().parents[1]
            manifest_path = root / "config" / "approved_skills.json"
            assert_no_symlink(manifest_path)
            manifest = read_manifest(manifest_path)
            result["pinned_ecc_commit"] = manifest["ecc"]["commit"]
            result["approved_skill_sha256"] = manifest["ecc"]["skills"]
            result["contract_source"] = "templates/AGENTS.md"
            if not result["blockers"]:
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
