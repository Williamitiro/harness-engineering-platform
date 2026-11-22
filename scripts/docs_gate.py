#!/usr/bin/env python3
"""HE-DOC-02: document organization gate (SPEC §11). Python 3.12+ stdlib only.

Three checks, all on new files and growth only (legacy never blocks):
  lugar      a new .md only in the places the repository policy lists;
  orcamento  entry, state and index within their byte limit; a file already above it cannot grow;
  indice     a new current document is linked from the index; the index links exist (when it changes).

Commands (also reachable as `harnessctl docs-<command>`):
  plan --repo R                 read-only report; without a policy, a skeleton to discuss
  check --repo R [--base REF]   working tree vs HEAD, or vs merge-base(REF, HEAD) in CI
  hook                          Claude Code / Codex hook (PreToolUse and Stop) reading JSON on stdin
  hook-plan|hook-install|hook-verify|hook-remove --home H   machine hook entries (opt-in, SPEC §9)

The hook is not a security barrier: it is inert without `.harness/docs-policy.json`, does not see
writes made by shell commands, and lets the session continue on any internal error.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

POLICY = ".harness/docs-policy.json"
DEFAULT_LIMITS = {"entry": 8192, "state": 5120, "index": 10240}
ROLES = ("entry", "state", "index")
MARKER = "--harness-docs-hook"
RECORD = ".harness-engineering/docs-hook.json"
TOOLS = {  # tool: (detect dir, config file, PreToolUse matcher)
    "claude": (".claude", ".claude/settings.json", "Write|Edit|MultiEdit"),
    "codex": (".codex", ".codex/hooks.json", "apply_patch"),
}
LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
NT = os.name == "nt"


class PolicyError(ValueError):
    pass


# ---------------------------------------------------------------- policy and matching

def glob_regex(pattern: str) -> re.Pattern:
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?"); i += 3
        elif pattern.startswith("**", i):
            out.append(".*"); i += 2
        elif pattern[i] == "*":
            out.append("[^/]*"); i += 1
        elif pattern[i] == "?":
            out.append("[^/]"); i += 1
        else:
            out.append(re.escape(pattern[i])); i += 1
    return re.compile("".join(out) + r"\Z", re.IGNORECASE if NT else 0)


def matches(rel: str, patterns: list[str]) -> bool:
    return any(glob_regex(p).match(rel) for p in patterns)


def same(a: str | None, b: str | None) -> bool:
    return a is not None and b is not None and (a.lower() == b.lower() if NT else a == b)


def load_policy(root: Path) -> dict | None:
    path = root / POLICY
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"{POLICY}: JSON inválido") from exc
    places = data.get("places") if isinstance(data, dict) else None
    if data.get("schema_version") != 1 or not isinstance(places, dict) or not places:
        raise PolicyError(f"{POLICY}: precisa de schema_version 1 e places")
    for kind, pats in places.items():
        if not isinstance(pats, list) or not pats or any(not isinstance(p, str) or ".." in p for p in pats):
            raise PolicyError(f"{POLICY}: places.{kind} precisa ser uma lista de caminhos")
    for role in ROLES:
        if data.get(role) is not None and not isinstance(data[role], str):
            raise PolicyError(f"{POLICY}: {role} precisa ser um caminho ou null")
    limits = {**DEFAULT_LIMITS, **(data.get("limits") or {})}
    if any(not isinstance(v, int) or v <= 0 for v in limits.values()):
        raise PolicyError(f"{POLICY}: limits precisam ser inteiros positivos (bytes)")
    indexed = data.get("indexed", [])
    if not isinstance(indexed, list) or any(k not in places for k in indexed):
        raise PolicyError(f"{POLICY}: indexed só pode citar tipos de places")
    ignore = data.get("ignore", [])
    if not isinstance(ignore, list) or any(not isinstance(p, str) for p in ignore):
        raise PolicyError(f"{POLICY}: ignore precisa ser uma lista")
    return {**data, "limits": limits, "indexed": indexed, "ignore": ignore}


def kind_of(policy: dict, rel: str) -> str | None:
    for kind, pats in policy["places"].items():
        if matches(rel, pats):
            return kind
    return None


def roles_of(policy: dict, rel: str) -> list[str]:
    return [role for role in ROLES if same(policy.get(role), rel)]


def where(policy: dict) -> str:
    return "; ".join(f"{kind}: {', '.join(pats)}" for kind, pats in policy["places"].items())


def disk_size(path: Path) -> int:
    """Bytes as Git stores them: CRLF counted as LF, so autocrlf on Windows is not growth."""
    data = path.read_bytes()
    return len(data) - data.count(b"\r\n")


def violation(path: str, rule: str, message: str, fix: str) -> dict:
    return {"file": path, "rule": rule, "message": message, "fix": fix}


# ---------------------------------------------------------------- the three checks

def check_change(policy: dict, rel: str, old: int | None, new: int) -> list[dict]:
    """lugar + orcamento for one file: old is None when the file is new."""
    found = []
    is_md = rel.lower().endswith(".md")
    if old is None and is_md and not matches(rel, policy["ignore"]) and not roles_of(policy, rel) \
            and kind_of(policy, rel) is None:
        found.append(violation(rel, "lugar", ".md novo fora dos caminhos da política",
                               f"grave no lugar do tipo certo ({where(policy)}) ou mude {POLICY}"))
    for role in roles_of(policy, rel):
        limit = policy["limits"][role]
        if new > limit and new > (old or 0):
            found.append(violation(rel, "orcamento", f"{role} com {new} bytes, teto {limit}"
                                   + (f" (antes {old}; acima do teto não pode crescer)" if old else ""),
                                   "corte o texto ou mova o detalhe para a pasta de arquivo"))
    return found


def index_links(root: Path, index: str, text: str) -> tuple[set[str], list[dict]]:
    base = PurePosixPath(index).parent
    targets, broken = set(), []
    for raw in LINK.findall(text):
        target = raw.split("#", 1)[0]
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("/"):
            continue
        rel = os.path.normpath(str(base / target)).replace("\\", "/")
        targets.add(rel.lower() if NT else rel)
        if not (root / rel).exists():
            broken.append(violation(index, "indice", f"link quebrado: {raw}", "corrija o caminho ou tire o link"))
    return targets, broken


def check_index(policy: dict, root: Path, new_files: list[str], index_changed: bool) -> list[dict]:
    index = policy.get("index")
    if not index:
        return []
    path = root / index
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    targets, broken = index_links(root, index, text)
    found = broken if index_changed else []
    for rel in new_files:
        kind = kind_of(policy, rel)
        if rel.lower().endswith(".md") and kind in policy["indexed"] and not roles_of(policy, rel) \
                and (rel.lower() if NT else rel) not in targets:
            found.append(violation(rel, "indice", f"documento {kind} novo sem link em {index}",
                                   f"acrescente um link para {rel} em {index}"))
    return found


# ---------------------------------------------------------------- git view (check / Stop)

def git(root: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=60)
    if out.returncode:
        raise PolicyError(f"git {args[0]} falhou")
    return out.stdout


def repo_root(start: Path) -> Path | None:
    try:
        top = git(start if start.is_dir() else start.parent, "rev-parse", "--show-toplevel").strip()
    except (PolicyError, OSError, subprocess.SubprocessError):
        return None
    return Path(top) if top else None


def tree_sizes(root: Path, rev: str) -> dict[str, int]:
    try:
        listing = git(root, "ls-tree", "-r", "-l", "-z", rev)
    except PolicyError:
        return {}  # no commit yet: everything is new
    sizes = {}
    for entry in filter(None, listing.split("\0")):
        meta, path = entry.split("\t", 1)
        size = meta.split()[-1]
        if size.isdigit():
            sizes[path.lower() if NT else path] = int(size)
    return sizes


def run_check(root: Path, policy: dict, base: str | None = None) -> dict:
    rev = git(root, "merge-base", base, "HEAD").strip() if base else "HEAD"
    old_sizes = tree_sizes(root, rev)
    changed = set(filter(None, git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    if old_sizes:
        changed |= set(filter(None, git(root, "diff", "--name-only", "--no-renames", "-z", rev).split("\0")))
    else:
        changed |= set(filter(None, git(root, "ls-files", "-z").split("\0")))
    found, new_files, index_changed = [], [], False
    for rel in sorted(changed):
        path = root / rel
        if not path.is_file():
            continue  # deleted
        old = old_sizes.get(rel.lower() if NT else rel)
        if old is None:
            new_files.append(rel)
        if same(rel, policy.get("index")):
            index_changed = True
        found += check_change(policy, rel, old, disk_size(path))
    found += check_index(policy, root, new_files, index_changed)
    return {"status": "DOCS_CHECK_FAIL" if found else "DOCS_CHECK_PASS", "base": rev,
            "changed": len(changed), "new_files": len(new_files), "violations": found}


def run_plan(root: Path) -> dict:
    tracked = [p for p in git(root, "ls-files", "-z").split("\0") if p.lower().endswith(".md")]
    policy = load_policy(root)
    if policy is None:
        dirs: dict[str, int] = {}
        for rel in tracked:
            parent = "/".join(rel.split("/")[:2][:-1]) if "/" in rel else "."
            dirs[parent] = dirs.get(parent, 0) + 1
        guess = lambda words: next((p for p in tracked if any(w in p.upper() for w in words)), None)
        return {"status": "NO_POLICY", "writes": 0, "md_files": len(tracked), "md_by_dir": dict(sorted(dirs.items())),
                "skeleton": {"schema_version": 1, "entry": "AGENTS.md" if (root / "AGENTS.md").is_file() else None,
                             "state": guess(("ESTADO", "STATE", "STATUS")), "index": guess(("INDICE", "INDEX")),
                             "limits": DEFAULT_LIMITS, "places": {"vigente": ["<caminhos que o repositório já usa>"]},
                             "indexed": ["vigente"], "ignore": ["vendor/**", "tests/**"]},
                "next": f"classifique as pastas com o operador e grave {POLICY}; nada é renomeado"}
    sizes = {}
    for role in ROLES:
        rel = policy.get(role)
        if rel:
            path = root / rel
            size = disk_size(path) if path.is_file() else None
            sizes[role] = {"file": rel, "bytes": size, "limit": policy["limits"][role],
                           "over": size is not None and size > policy["limits"][role]}
    by_kind: dict[str, int] = {}
    for rel in tracked:
        kind = "ignorado" if matches(rel, policy["ignore"]) else (
            "papel" if roles_of(policy, rel) else kind_of(policy, rel) or "fora_da_politica")
        by_kind[kind] = by_kind.get(kind, 0) + 1
    return {"status": "POLICY_FOUND", "writes": 0, "md_files": len(tracked), "by_kind": by_kind, "budget": sizes}


# ---------------------------------------------------------------- hook (stdin JSON)

def utf8_len(text) -> int:
    return len(text.encode("utf-8")) if isinstance(text, str) else 0


def patch_changes(patch: str, cwd: Path) -> list[tuple[Path, Path | None, int]]:
    """Codex apply_patch: [(written path, path whose bytes it starts from, byte delta)]."""
    out: list[dict] = []
    tags = (("*** Add File: ", "add"), ("*** Update File: ", "update"), ("*** Delete File: ", "delete"))
    for line in patch.splitlines():
        head = line.strip()
        tag = next(((t, k) for t, k in tags if head.startswith(t)), None)
        if tag:
            path = cwd / head[len(tag[0]):].strip()
            out.append({"path": path, "base": path if tag[1] == "update" else None, "kind": tag[1], "delta": 0})
        elif head.startswith("*** Move to: ") and out:
            out[-1]["path"] = cwd / head[len("*** Move to: "):].strip()
        elif out and line.startswith("+") and not line.startswith("+++"):
            out[-1]["delta"] += utf8_len(line[1:]) + 1
        elif out and line.startswith("-") and not line.startswith("---") and out[-1]["kind"] == "update":
            out[-1]["delta"] -= utf8_len(line[1:]) + 1
    return [(c["path"], c["base"], c["delta"]) for c in out if c["kind"] != "delete"]


def proposed_writes(event: dict) -> list[tuple[Path, int]]:
    """[(absolute path, size after the write)] for the tool call, or [] when not a file write."""
    tool, data = event.get("tool_name"), event.get("tool_input") or {}
    cwd = Path(event.get("cwd") or os.getcwd())
    def current(path: Path) -> bytes:
        return path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    if tool == "Write":
        return [(Path(data["file_path"]), utf8_len(data.get("content", "")))]
    if tool in ("Edit", "MultiEdit"):
        path = Path(data["file_path"])
        raw = current(path)
        size, text = len(raw), raw.decode("utf-8", errors="replace")
        for edit in data.get("edits") or [data]:
            old, new = edit.get("old_string", ""), edit.get("new_string", "")
            count = max(1, text.count(old)) if edit.get("replace_all") and old else 1
            size += (utf8_len(new) - utf8_len(old)) * count
        return [(path, size)]
    if tool == "apply_patch":
        cmd = data.get("command") or data.get("patch") or data.get("input") or ""
        if isinstance(cmd, list):
            cmd = "\n".join(str(c) for c in cmd)
        return [(p, (len(current(b)) if b else 0) + d) for p, b, d in patch_changes(str(cmd), cwd)]
    return []


def rel_in(root: Path, path: Path) -> str | None:
    # realpath on both sides: on Windows the tool may send an 8.3 short name (C:\Users\RUNNER~1\...) or a
    # junction while git reports the long, final path; a text-only comparison then calls the file "outside"
    # and the hook goes silently inert (CI windows-latest, PR #17).
    full, base = os.path.realpath(path), os.path.realpath(root)
    try:
        check = os.path.relpath(os.path.normcase(full), os.path.normcase(base)).replace("\\", "/")
    except ValueError:
        return None  # other drive
    if check == ".." or check.startswith("../"):
        return None
    return full[len(base):].lstrip("\\/").replace("\\", "/")  # keeps the caller's case


def format_violations(found: list[dict]) -> str:
    return "Harness (organização de documentos):\n" + "\n".join(
        f"- {v['file']}: regra {v['rule']}: {v['message']}. Correção: {v['fix']}." for v in found)


def hook(event: dict) -> dict | None:
    """Returns the JSON to print (deny/block) or None to allow. Same shape for both tools."""
    name = event.get("hook_event_name")
    cwd = Path(event.get("cwd") or os.getcwd())
    if name == "PreToolUse":
        found = []
        for path, size in proposed_writes(event):
            path = path if path.is_absolute() else cwd / path
            root = repo_root(path.parent if path.parent.exists() else cwd)
            policy = load_policy(root) if root else None
            rel = rel_in(root, path) if policy else None
            if rel is None:
                continue  # outside a repository with a policy: inert
            found += check_change(policy, rel, disk_size(path) if path.is_file() else None, size)
        if found:
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": format_violations(found)}}
        return None
    if name == "Stop":
        if event.get("stop_hook_active"):
            return None  # never holds the session more than once
        root = repo_root(cwd)
        policy = load_policy(root) if root else None
        if policy is None:
            return None
        result = run_check(root, policy)
        if result["violations"]:
            return {"decision": "block", "reason": format_violations(result["violations"])
                    + "\nCorrija antes de dizer que terminou (ou explique por que não)."}
    return None


def hook_main() -> int:
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
        answer = hook(event) if isinstance(event, dict) else None
    except Exception as exc:  # the hook never breaks a session
        print(f"harness docs hook: ignorado ({type(exc).__name__})", file=sys.stderr)
        return 0
    if answer:
        sys.stdout.buffer.write(json.dumps(answer, ensure_ascii=False).encode("utf-8"))
        sys.stdout.flush()
    return 0


# ---------------------------------------------------------------- machine hook entries

def hook_command(python: Path, engine: Path, tool: str) -> str:
    return f'"{python.as_posix()}" "{engine.as_posix()}" hook --tool {tool} {MARKER}'


def is_ours(entry) -> bool:
    return isinstance(entry, dict) and MARKER in str(entry.get("command", ""))


def read_config(path: Path) -> dict:
    if path.is_symlink():
        raise PolicyError(f"BLOCKED_LINK: {path.name} é link")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"BLOCKED_INVALID_CONFIG: {path.name} não é JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        raise PolicyError(f"BLOCKED_INVALID_CONFIG: {path.name} com formato inesperado")
    return data


def strip_ours(config: dict) -> tuple[dict, int]:
    hooks, removed = dict(config.get("hooks", {})), 0
    for event in list(hooks):
        groups = hooks[event] if isinstance(hooks[event], list) else None
        if groups is None:
            continue
        kept = []
        for group in groups:
            inner = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(inner, list) and any(is_ours(h) for h in inner):
                removed += sum(is_ours(h) for h in inner)
                inner = [h for h in inner if not is_ours(h)]
                if inner:
                    kept.append({**group, "hooks": inner})
            else:
                kept.append(group)
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]
    out = {k: v for k, v in config.items() if k != "hooks"}
    if hooks:
        out["hooks"] = hooks
    return out, removed


def with_ours(config: dict, matcher: str, command: str) -> dict:
    out, _ = strip_ours(config)
    hooks = dict(out.get("hooks", {}))
    entry = {"type": "command", "command": command, "timeout": 30}
    hooks["PreToolUse"] = [*hooks.get("PreToolUse", []), {"matcher": matcher, "hooks": [entry]}]
    hooks["Stop"] = [*hooks.get("Stop", []), {"hooks": [dict(entry)]}]
    return {**out, "hooks": hooks}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".harness-tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def hook_state(home: Path, engine: Path, python: Path) -> list[dict]:
    rows = []
    for tool, (detect, rel, matcher) in TOOLS.items():
        if not (home / detect).is_dir():
            rows.append({"tool": tool, "status": "NOT_DETECTED"})
            continue
        path = home / rel
        config = read_config(path)
        wanted = with_ours(config, matcher, hook_command(python, engine, tool))
        ours = sum(is_ours(h) for groups in config.get("hooks", {}).values() if isinstance(groups, list)
                   for g in groups if isinstance(g, dict) for h in (g.get("hooks") or []))
        status = "INSTALLED" if ours and wanted == config else ("STALE" if ours else "ABSENT")
        rows.append({"tool": tool, "status": status, "config": rel, "exists": path.exists(),
                     "change": None if status == "INSTALLED" else f"PreToolUse ({matcher}) e Stop"})
    return rows


def default_engine(home: Path) -> Path:
    return home / ".harness-engineering" / "current" / "scripts" / "docs_gate.py"


def hook_admin(action: str, home: Path, engine: Path | None, apply: bool) -> dict:
    home = home.absolute()
    if not home.is_dir():
        raise PolicyError("home precisa ser uma pasta existente")
    engine = (engine or default_engine(home)).absolute()
    python = Path(sys.executable).absolute()
    record_path = home / RECORD
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {"created": []}
    if action in ("hook-plan", "hook-install"):
        if not engine.is_file():
            raise PolicyError(f"BLOCKED_ENGINE_MISSING: {engine.as_posix()} não existe (instale a tag nova antes)")
        rows = hook_state(home, engine, python)
        if action == "hook-plan" or not apply:
            return {"status": "PLANNED_NOT_INSTALLED", "writes": 0, "engine": engine.as_posix(), "tools": rows,
                    "note": "altera configuração global: só com o 'sim' do operador (--apply)"}
        for row in rows:
            if row["status"] in ("ABSENT", "STALE"):
                path = home / TOOLS[row["tool"]][1]
                if not path.exists() and row["config"] not in record["created"]:
                    record["created"].append(row["config"])
                write_json(path, with_ours(read_config(path), TOOLS[row["tool"]][2],
                                           hook_command(python, engine, row["tool"])))
                row["status"] = "INSTALLED"
        write_json(record_path, record)
        codex = any(r["tool"] == "codex" and r["status"] == "INSTALLED" for r in rows)
        return {"status": "HOOK_INSTALLED_RUNTIME_NOT_VERIFIED", "tools": rows,
                "next": "Codex: aprovar o hook em /hooks (trust por hash)" if codex else None}
    if action == "hook-verify":
        rows = hook_state(home, engine, python)
        ok = [r for r in rows if r["status"] != "NOT_DETECTED"]
        status = "HOOK_FILES_OK_RUNTIME_NOT_VERIFIED" if ok and all(r["status"] == "INSTALLED" for r in ok) \
            else "HOOK_NOT_INSTALLED"
        return {"status": status, "engine": engine.as_posix(), "engine_exists": engine.is_file(), "tools": rows}
    # hook-remove: only the Harness entries; other hooks stay as they are
    rows = []
    for tool, (_, rel, _) in TOOLS.items():
        path = home / rel
        if not path.exists():
            continue
        cleaned, removed = strip_ours(read_config(path))
        rows.append({"tool": tool, "config": rel, "removed_entries": removed})
        if apply and removed:
            if rel in record["created"] and not cleaned:
                path.unlink()
            else:
                write_json(path, cleaned)
    if apply:
        record_path.unlink(missing_ok=True)
        return {"status": "HOOK_REMOVED", "tools": rows}
    return {"status": "PLANNED_REMOVAL", "writes": 0, "tools": rows}


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if argv[:1] == ["hook"]:
        return hook_main()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("plan", "check", "hook-plan", "hook-install", "hook-verify", "hook-remove"))
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base", help="check: compare with merge-base(BASE, HEAD) (CI)")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--engine", type=Path, help="hook: docs_gate.py to call (default ~/.harness-engineering/current)")
    parser.add_argument("--apply", action="store_true", help="explicit opt-in for writes")
    args = parser.parse_args(argv)
    try:
        if args.action.startswith("hook-"):
            result = hook_admin(args.action, args.home, args.engine, args.apply)
        else:
            root = repo_root(args.repo.absolute())
            if root is None:
                raise PolicyError("não é um repositório Git")
            if args.action == "plan":
                result = run_plan(root)
            else:
                policy = load_policy(root)
                result = {"status": "NO_POLICY", "violations": []} if policy is None else run_check(root, policy, args.base)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.action == "check" and result["violations"]:
            print(format_violations(result["violations"]), file=sys.stderr)
            return 1
        return 0
    except (PolicyError, OSError, json.JSONDecodeError) as exc:
        reason = str(exc) if isinstance(exc, PolicyError) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": reason}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
