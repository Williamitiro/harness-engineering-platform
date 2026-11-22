#!/usr/bin/env python3
"""HE-DOC-02: document organization gate (SPEC §11). Python 3.12+ stdlib only.

Three checks, all on new files and growth only (legacy never blocks):
  lugar      a new .md only in the places the repository policy lists;
  orcamento  entry, state and index within their byte limit; a file already above it cannot grow;
  indice     a new current document is linked from the index; the index links exist (when it changes).

Commands (also reachable as `harnessctl docs-<command>`):
  plan --repo R                 read-only report; without a policy, a skeleton to discuss
  verify --repo R               read-only, the whole repository against its policy (part of project-verify)
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
from urllib.parse import unquote

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
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?(?:^ {0,3}\1[ \t]*$|\Z)", re.MULTILINE | re.DOTALL)
INLINE_CODE = re.compile(r"(`+)(?!`).*?(?<!`)\1(?!`)")  # one line: a stray backtick hides nothing else
LINE_SUFFIX = re.compile(r":\d+(?::\d+)?\Z")  # editor-style file.md:12 or :12:3
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
    if not isinstance(data, dict):
        raise PolicyError(f"{POLICY}: precisa ser um objeto JSON")
    places = data.get("places")
    if data.get("schema_version") != 1 or not isinstance(places, dict) or not places:
        raise PolicyError(f"{POLICY}: precisa de schema_version 1 e places")
    for kind, pats in places.items():
        if not isinstance(pats, list) or not pats or any(not isinstance(p, str) or ".." in p for p in pats):
            raise PolicyError(f"{POLICY}: places.{kind} precisa ser uma lista de caminhos")
    for role in ROLES:
        if data.get(role) is not None and not isinstance(data[role], str):
            raise PolicyError(f"{POLICY}: {role} precisa ser um caminho ou null")
    if not isinstance(data.get("limits") or {}, dict):
        raise PolicyError(f"{POLICY}: limits precisa ser um objeto (papel: bytes)")
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


def specificity(pattern: str) -> int:
    """Literal characters of a pattern: docs/historico/** (14) is more specific than docs/** (5)."""
    return len(pattern.replace("*", "").replace("?", ""))


def kind_of(policy: dict, rel: str) -> str | None:
    """The kind of the most specific pattern that matches; on a tie, the first kind listed. So an archive folder
    inside docs/ keeps its kind even when a broader docs/** kind is listed first (review of v1.4.0)."""
    best, best_score = None, -1
    for kind, pats in policy["places"].items():
        for pat in pats:
            if specificity(pat) > best_score and glob_regex(pat).match(rel):
                best, best_score = kind, specificity(pat)
    return best


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

TRIGGER = "Vai mexer em X? Leia antes, obrigatório: <link>"  # same words as the setup-harness skill


def archive_place(policy: dict) -> str:
    """The archive folder the policy names, for the correction text (generic words when it has none)."""
    pats = policy["places"].get("arquivo") or []
    return pats[0].removesuffix("/**").removesuffix("/*") if pats else "a pasta de arquivo"


def budget_fix(policy: dict, role: str, rel: str) -> str:
    """How to make room, per role (HE-DOC-04): the AGENTS.md keeps general rules and points to area rules."""
    if role == "entry":
        return (f"corte o texto, ou leve a regra de uma área para um documento próprio e deixe no {rel} só a linha "
                f"de gatilho \"{TRIGGER}\"; regra geral fica por inteiro")
    if role == "state":
        return (f"deixe no estado só o que vale hoje; para guardar o estado antigo inteiro, faça git mv dele para "
                f"{archive_place(policy)} e comece um estado novo e curto")
    return ("agrupe os links, ou dê a uma pasta o próprio índice (um tipo próprio em places, fora de "
            "\"indexed\") e deixe aqui um link só para ele")


def first_upper(text: str) -> str:
    return text[:1].upper() + text[1:]


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
            if old is not None and old > limit:
                why = f" (já estava acima do teto, com {old}; não pode crescer)"
                room = f"não sobra nenhum byte: o arquivo já passa {old - limit} bytes do teto e precisa encolher"
            else:
                why = f" (antes {old})" if old is not None else ""
                room = (f"sobram {limit - (old or 0)} bytes até o teto e a mudança pede {new - (old or 0)}; "
                        f"faltam {new - limit}")
            found.append(violation(rel, "orcamento", f"{role} ficaria com {new} bytes, teto {limit}{why}",
                                   f"{room}. {first_upper(budget_fix(policy, role, rel))}"))
    return found


def key(rel: str) -> str:
    return rel.lower() if NT else rel


def index_links(root: Path, index: str, text: str) -> tuple[set[str], list[dict]]:
    """(link targets, broken links); each broken entry carries `target` (repository-relative, posix)."""
    base = PurePosixPath(index).parent
    targets, broken = set(), []
    # Examples inside code blocks and inline code are not links (review of v1.4.0).
    prose = INLINE_CODE.sub("", FENCE.sub("", text))
    for raw in LINK.findall(prose):
        target = raw.split("#", 1)[0]
        # Editor-style SPEC.md:12 is a file and a line, not a URL scheme "SPEC.md:"; a file name cannot hold ":".
        if LINE_SUFFIX.search(target) and "." in LINE_SUFFIX.sub("", target).rsplit("/", 1)[-1]:
            target = LINE_SUFFIX.sub("", target)
        if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.IGNORECASE) or target.startswith("/"):
            continue
        target = unquote(target)  # docs/Meu%20Guia.md is docs/Meu Guia.md
        rel = os.path.normpath(str(base / target)).replace("\\", "/")
        targets.add(key(rel))
        if not (root / rel).exists():
            broken.append({**violation(index, "indice", f"link quebrado: {raw}", "corrija o caminho ou tire o link"),
                           "target": rel})
    return targets, broken


def check_index(policy: dict, root: Path, new_files: list[str], index_changed: bool,
                removed: set[str] = frozenset()) -> list[dict]:
    """Broken links count when the index changed, or when this change removed/moved the file a link points to
    (HE-DOC-03 moves documents to the archive); a link that was already broken never blocks."""
    index = policy.get("index")
    if not index:
        return []
    path = root / index
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    targets, broken = index_links(root, index, text)
    gone = {key(r) for r in removed}
    found = [{k: v for k, v in b.items() if k != "target"} for b in broken
             if index_changed or key(b["target"]) in gone]
    for rel in new_files:
        kind = kind_of(policy, rel)
        if rel.lower().endswith(".md") and kind in policy["indexed"] and not roles_of(policy, rel) \
                and key(rel) not in targets:
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
    """Repository that contains `start`, from its nearest existing directory (a file may go in a new folder)."""
    start = Path(os.path.abspath(start))
    existing = next((p for p in (start, *start.parents) if p.is_dir()), None)
    if existing is None:
        return None
    try:
        top = git(existing, "rev-parse", "--show-toplevel").strip()
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


def run_check(root: Path, policy: dict, base: str | None = None, since: float | None = None) -> dict:
    """`since` (Stop hook): only files written at or after this time count, so a stray .md that was already in
    the working tree before the session does not hold every turn."""
    rev = git(root, "merge-base", base, "HEAD").strip() if base else "HEAD"
    old_sizes = tree_sizes(root, rev)
    changed = set(filter(None, git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    if old_sizes:
        changed |= set(filter(None, git(root, "diff", "--name-only", "--no-renames", "-z", rev).split("\0")))
    else:
        changed |= set(filter(None, git(root, "ls-files", "-z").split("\0")))
    found, new_files, removed, index_changed = [], [], set(), False
    for rel in sorted(changed):
        path = root / rel
        if not path.is_file():
            removed.add(rel)  # deleted, or the old side of a move
            continue
        if since is not None and path.stat().st_mtime < since:
            continue  # untouched in this session
        if not rel.lower().endswith(".md") and not roles_of(policy, rel):
            continue  # neither lugar nor orcamento looks at it: never read a video or a binary (review of v1.4.0)
        old = old_sizes.get(key(rel))
        if old is None:
            new_files.append(rel)
        if same(rel, policy.get("index")):
            index_changed = True
        found += check_change(policy, rel, old, disk_size(path))
    found += check_index(policy, root, new_files, index_changed, removed)
    return {"status": "DOCS_CHECK_FAIL" if found else "DOCS_CHECK_PASS", "base": rev,
            "changed": len(changed), "new_files": len(new_files), "violations": found}


def run_plan(root: Path) -> dict:
    tracked = [p for p in git(root, "ls-files", "-z").split("\0") if p.lower().endswith(".md")]
    policy = load_policy(root)
    if policy is None:
        dirs: dict[str, int] = {}
        for rel in tracked:
            # Two folder levels: docs/adr and docs/historico are different kinds, not one "docs".
            parent = "/".join(rel.split("/")[:-1][:2]) or "."
            dirs[parent] = dirs.get(parent, 0) + 1
        top: dict[str, int] = {}
        for rel in tracked:
            first = rel.split("/")[0] if "/" in rel else "."
            top[first] = top.get(first, 0) + 1
        guess = lambda words: next((p for p in tracked if any(w in p.upper() for w in words)), None)
        return {"status": "NO_POLICY", "writes": 0, "md_files": len(tracked), "md_by_dir": dict(sorted(dirs.items())),
                "md_by_top": dict(sorted(top.items())),
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
    outside = []
    for rel in tracked:
        kind = "ignorado" if matches(rel, policy["ignore"]) else (
            "papel" if roles_of(policy, rel) else kind_of(policy, rel) or "fora_da_politica")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        if kind == "fora_da_politica":
            outside.append(rel)
    return {"status": "POLICY_FOUND", "writes": 0, "md_files": len(tracked), "by_kind": by_kind, "budget": sizes,
            "outside": outside}


def run_verify(root: Path) -> dict:
    """The whole repository against its policy (HE-DOC-04, part of `project-verify`). Read-only.

    Unlike `check` (new files and growth only), this looks at what is already there: roles within their limit,
    every tracked .md in a kind or in `ignore`, every index link alive, and nothing pending in the working tree.
    Without a policy the result is `null` with reason SEM_PLANTA: not a failure and never 0.
    """
    try:
        policy = load_policy(root)
    except PolicyError as exc:
        return {"status": "FAIL", "reason": "PLANTA_INVALIDA", "problems": [str(exc)]}
    if policy is None:
        return {"status": None, "reason": "SEM_PLANTA", "policy": POLICY,
                "next": f"setup-harness: rode docs-plan e proponha {POLICY} com as pastas que já existem"}
    plan, problems, notes = run_plan(root), [], []
    for role, info in plan["budget"].items():
        if info["bytes"] is None:  # a new repository has no state file yet: not a failure
            notes.append(f"{role}: {info['file']} ainda não existe")
        elif info["over"]:
            problems.append(f"{role}: {info['file']} tem {info['bytes']} bytes, teto {info['limit']}")
    for rel in plan["outside"][:20]:
        problems.append(f"fora da planta: {rel} (dê um tipo em places ou ponha em ignore)")
    if len(plan["outside"]) > 20:
        problems.append(f"fora da planta: mais {len(plan['outside']) - 20} arquivos")
    index = policy.get("index")
    if index and (root / index).is_file():
        _, broken = index_links(root, index, (root / index).read_text(encoding="utf-8", errors="replace"))
        problems += [f"índice {index}: {b['message']}" for b in broken]
    # Broken index links are already listed above, from the whole index.
    # Files already listed as outside the policy (staged, not committed) are not listed twice.
    listed = {key(r) for r in plan["outside"]}
    over = {key(info["file"]) for info in plan["budget"].values() if info["over"]}
    pending = [v for v in run_check(root, policy)["violations"]
               if not (v["rule"] == "indice" and v["message"].startswith("link quebrado"))
               and not (v["rule"] == "lugar" and key(v["file"]) in listed)
               and not (v["rule"] == "orcamento" and key(v["file"]) in over)]
    problems += [f"{v['file']}: regra {v['rule']}: {v['message']}" for v in pending]
    budget = {role: {**info, "pct": round(100 * info["bytes"] / info["limit"]) if info["bytes"] is not None else None}
              for role, info in plan["budget"].items()}
    return {"status": "FAIL" if problems else "PASS", "policy": POLICY, "md_files": plan["md_files"],
            "by_kind": plan["by_kind"], "budget": budget, "problems": problems, "notes": notes}


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
        # apply_patch has no "---"/"+++" file headers: a line "----" is a removed Markdown rule "---".
        elif out and line.startswith("+"):
            out[-1]["delta"] += utf8_len(line[1:]) + 1
        elif out and line.startswith("-") and out[-1]["kind"] == "update":
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
    # and the hook goes silently inert (CI windows-latest, PR #17). Existing folders come back in their
    # on-disk case; the file name keeps the case the tool sent.
    full, base = os.path.realpath(path), os.path.realpath(root)
    try:
        check = os.path.relpath(os.path.normcase(full), os.path.normcase(base)).replace("\\", "/")
        rel = os.path.relpath(full, base).replace("\\", "/")
    except ValueError:
        return None  # other drive
    if check == ".." or check.startswith("../"):
        return None
    return rel


def format_violations(found: list[dict]) -> str:
    return "Harness (organização de documentos):\n" + "\n".join(
        f"- {v['file']}: regra {v['rule']}: {v['message']}. Correção: {v['fix']}." for v in found)


def session_start(event: dict) -> float | None:
    """When the session began: creation time of its transcript (Windows and macOS keep it; Linux has no
    birth time in os.stat, so there the Stop hook checks every changed file). A file moved with `git mv`
    keeps its old mtime and is left to the CI check."""
    transcript = event.get("transcript_path")
    try:
        return os.stat(transcript).st_birthtime if transcript else None
    except (OSError, AttributeError, TypeError):
        return None


def hook(event: dict) -> dict | None:
    """Returns the JSON to print (deny/block) or None to allow. Same shape for both tools."""
    name = event.get("hook_event_name")
    cwd = Path(event.get("cwd") or os.getcwd())
    if name == "PreToolUse":
        found = []
        for path, size in proposed_writes(event):
            path = path if path.is_absolute() else cwd / path
            root = repo_root(path.parent)
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
        result = run_check(root, policy, since=session_start(event))
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

def shell_path(path: Path) -> str:
    """A path every hook shell runs as a command word: Git Bash, PowerShell and cmd on Windows, sh elsewhere.

    A quoted first word ("C:/x/python.exe" ...) is a string expression in PowerShell, not a command, so the
    hook would fail on every call. Unquoted forward-slash paths work in all three; a Windows path with spaces
    falls back to its 8.3 short name, and is refused when the volume has none.
    """
    text = path.as_posix()
    if " " not in text:
        return text
    if not NT:
        import shlex
        return shlex.quote(text)
    import ctypes
    buf = ctypes.create_unicode_buffer(1024)
    if ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, len(buf)) and " " not in buf.value:
        return Path(buf.value).as_posix()
    raise PolicyError(f"BLOCKED_PATH_WITH_SPACES: {text} (sem nome curto 8.3 para usar no hook)")


def hook_command(python: Path, engine: Path, tool: str) -> str:
    return f"{shell_path(python)} {shell_path(engine)} hook --tool {tool} {MARKER}"


def is_ours(entry) -> bool:
    return isinstance(entry, dict) and MARKER in str(entry.get("command", ""))


def is_link(path: Path) -> bool:
    """Symlink or Windows reparse point (junction): the same test the machine installer uses."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from harnessctl import is_link as harness_is_link
    finally:
        sys.path.pop(0)
    return harness_is_link(path)


def read_config(path: Path, home: Path | None = None) -> dict:
    """The tool's config, refusing a link on the file or on its folders up to the home (SPEC §9)."""
    for part in (path, *path.parents):
        if home is not None and part == home:
            break
        if is_link(part):
            raise PolicyError(f"BLOCKED_LINK: {part.as_posix()} é link ou junction")
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


def our_entries(config: dict) -> list[tuple[str, str | None, dict]]:
    """[(event, matcher, entry)] of the Harness entries, wherever they sit among the user's hooks."""
    return [(event, group.get("matcher"), entry)
            for event, groups in config.get("hooks", {}).items() if isinstance(groups, list)
            for group in groups if isinstance(group, dict)
            for entry in (group.get("hooks") or []) if is_ours(entry)]


def hook_state(home: Path, engine: Path, python: Path) -> list[dict]:
    rows = []
    for tool, (detect, rel, matcher) in TOOLS.items():
        if not (home / detect).is_dir():
            rows.append({"tool": tool, "status": "NOT_DETECTED"})
            continue
        path = home / rel
        config = read_config(path, home)
        entry = {"type": "command", "command": hook_command(python, engine, tool), "timeout": 30}
        ours = our_entries(config)
        # Order-insensitive: hooks the user adds after ours do not make the installation "stale".
        exact = sorted(ours, key=lambda o: o[0]) == [("PreToolUse", matcher, entry), ("Stop", None, entry)]
        status = "INSTALLED" if exact else ("STALE" if ours else "ABSENT")
        rows.append({"tool": tool, "status": status, "config": rel, "exists": path.exists(),
                     "change": None if status == "INSTALLED" else f"PreToolUse ({matcher}) e Stop"})
    return rows


def default_engine(home: Path) -> Path:
    return home / ".harness-engineering" / "current" / "scripts" / "docs_gate.py"


def hook_python(python: Path | None) -> Path:
    """The interpreter the hook command pins. A virtual environment disappears with its folder and silently
    turns the hook off, so it is refused; pass --python to choose another interpreter."""
    if python is None:
        if sys.prefix != sys.base_prefix:
            raise PolicyError("BLOCKED_VENV_PYTHON: rode fora de um ambiente virtual ou passe --python")
        python = Path(sys.executable)
    return python.absolute()


def hook_admin(action: str, home: Path, engine: Path | None, apply: bool, python: Path | None = None) -> dict:
    home = home.absolute()
    if not home.is_dir():
        raise PolicyError("home precisa ser uma pasta existente")
    engine = (engine or default_engine(home)).absolute()
    python = hook_python(python)
    record_path = home / RECORD
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {"created": []}
    if not isinstance(record, dict) or not isinstance(record.get("created"), list):
        raise PolicyError(f"BLOCKED_INVALID_RECORD: {RECORD}")
    if action in ("hook-plan", "hook-install"):
        if not engine.is_file():
            raise PolicyError(f"BLOCKED_ENGINE_MISSING: {engine.as_posix()} não existe (instale a tag nova antes)")
        if not python.is_file():
            raise PolicyError(f"BLOCKED_PYTHON_MISSING: {python.as_posix()}")
        rows = hook_state(home, engine, python)
        if action == "hook-plan" or not apply:
            return {"status": "PLANNED_NOT_INSTALLED", "writes": 0, "engine": engine.as_posix(), "tools": rows,
                    "note": "altera configuração global: só com o 'sim' do operador (--apply)"}
        for row in rows:
            if row["status"] in ("ABSENT", "STALE"):
                path = home / TOOLS[row["tool"]][1]
                if not path.exists() and row["config"] not in record["created"]:
                    record["created"].append(row["config"])
                write_json(path, with_ours(read_config(path, home), TOOLS[row["tool"]][2],
                                           hook_command(python, engine, row["tool"])))
                row["status"] = "INSTALLED"
        write_json(record_path, record)
        codex = any(r["tool"] == "codex" and r["status"] == "INSTALLED" for r in rows)
        return {"status": "HOOK_INSTALLED_RUNTIME_NOT_VERIFIED", "tools": rows,
                "next": "Codex: aprovar o hook em /hooks (trust por hash)" if codex else None}
    if action == "hook-verify":
        rows = hook_state(home, engine, python)
        ok = [r for r in rows if r["status"] != "NOT_DETECTED"]
        installed = ok and all(r["status"] == "INSTALLED" for r in ok)
        # Installed entries pointing at an interpreter or engine that no longer exists do nothing.
        status = ("HOOK_FILES_OK_RUNTIME_NOT_VERIFIED" if engine.is_file() and python.is_file() else
                  "HOOK_BROKEN_MISSING_TARGET") if installed else "HOOK_NOT_INSTALLED"
        return {"status": status, "engine": engine.as_posix(), "engine_exists": engine.is_file(),
                "python": python.as_posix(), "python_exists": python.is_file(), "tools": rows}
    # hook-remove: only the Harness entries; other hooks stay as they are
    rows = []
    for tool, (_, rel, _) in TOOLS.items():
        path = home / rel
        if not path.exists():
            continue
        cleaned, removed = strip_ours(read_config(path, home))
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
    parser.add_argument("action", choices=("plan", "check", "verify", "hook-plan", "hook-install", "hook-verify", "hook-remove"))
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--base", help="check: compare with merge-base(BASE, HEAD) (CI)")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--engine", type=Path, help="hook: docs_gate.py to call (default ~/.harness-engineering/current)")
    parser.add_argument("--python", type=Path, help="hook: interpreter the hook runs with (default: this one)")
    parser.add_argument("--apply", action="store_true", help="explicit opt-in for writes")
    args = parser.parse_args(argv)
    try:
        if args.action.startswith("hook-"):
            result = hook_admin(args.action, args.home, args.engine, args.apply, args.python)
        else:
            root = repo_root(args.repo.absolute())
            if root is None:
                raise PolicyError("não é um repositório Git")
            if args.action == "plan":
                result = run_plan(root)
            elif args.action == "verify":
                result = run_verify(root)
            else:
                policy = load_policy(root)
                result = {"status": "NO_POLICY", "violations": []} if policy is None else run_check(root, policy, args.base)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.action == "check" and result["violations"]:
            print(format_violations(result["violations"]), file=sys.stderr)
            return 1
        if args.action == "verify" and result["status"] == "FAIL":
            return 1
        return 0
    except (PolicyError, OSError, json.JSONDecodeError) as exc:
        reason = str(exc) if isinstance(exc, PolicyError) else type(exc).__name__
        print(json.dumps({"status": "BLOCKED", "reason": reason}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
