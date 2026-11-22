#!/usr/bin/env python3
"""HE-OPS-02: cleanup plan and apply for agent sessions on this computer.

`plan` only reads. It lists what can be freed, each item with its size, its safety class and who executes it:
  - seguro   : regenerable, nobody is using it (orphan browser/MCP process trees, orphan Chrome profiles in Temp,
               `_local/tmp` entries idle for 48 h, the npm cache) or a session whose PR is closed and whose
               worktree holds no work;
  - decisao  : the owner decides (idle session with no PR, plugin and auto-archive settings);
  - manter   : shown so the owner sees it, never touched (work not pushed, PR open, running, shared worktree).
Executor `harness` is applied by `apply`; executor `app` is done by the agent with the desktop app's own tools
(archive_session, set_setting), because worktrees and sessions belong to the app.

`apply` touches only `harness` items chosen by id (or every `seguro` one with --safe), re-checks each item right
before acting (still orphan, still idle, same process creation time), and does nothing without --apply.
Exit codes: 0 ok, 1 some item failed, 2 BLOCKED.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resource_check as rc  # noqa: E402

STALE_HOURS = 48
IDLE_SESSION_DAYS = 7
PLAN_MAX_AGE_S = 2 * 3600
HARNESS_KINDS = ("orphan_tree", "orphan_profile", "repo_tmp", "npm_cache", "offload_backup")
OFFLOAD_MIN_BYTES = 100 * 2**20


class CleanError(ValueError):
    pass


# ---------------------------------------------------------------- facts

def git(path: Path, *args: str) -> str | None:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")  # never rewrite the index of someone else's worktree
    try:
        done = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout.strip() if done.returncode == 0 else None


def worktree_state(path: Path) -> dict:
    """clean / work (changes or commits not on any remote) / not_git / missing / error. Read-only."""
    if not path.is_dir():
        return {"state": "missing"}
    if not (path / ".git").exists():
        return {"state": "not_git"}
    status = git(path, "status", "--porcelain")
    if status is None:
        return {"state": "error"}
    dirty = len([line for line in status.splitlines() if line.strip()])
    upstream = git(path, "rev-parse", "--abbrev-ref", "@{u}")
    ahead = git(path, "rev-list", "--count", "@{u}..HEAD") if upstream else git(
        path, "rev-list", "--count", "HEAD", "--not", "--remotes")
    if ahead is None or not ahead.isdigit():
        return {"state": "error", "dirty": dirty}
    unpushed = int(ahead)
    return {"state": "work" if dirty or unpushed else "clean", "dirty": dirty, "unpushed": unpushed}


def newest_mtime(path: Path) -> float:
    """Newest modification time inside `path`, without following links or junctions."""
    newest = path.lstat().st_mtime
    if path.is_dir() and not rc._is_link(path):
        for base, dirs, files in os.walk(path, followlinks=False):
            dirs[:] = [d for d in dirs if not rc._is_link(Path(base) / d)]
            for name in dirs + files:
                try:
                    newest = max(newest, os.lstat(os.path.join(base, name)).st_mtime)
                except OSError:
                    continue
    return newest


def size_of(path: Path) -> int:
    if rc._is_link(path) or not path.is_dir():
        try:
            return 0 if rc._is_link(path) else path.lstat().st_size
        except OSError:
            return 0
    return rc.dir_bytes(path) or 0


def in_use(path: str, cmds: str) -> bool:
    return bool(re.search(re.escape(path) + r"(?![\w.-])", cmds, re.IGNORECASE))


def tmp_roots(dev_root: Path) -> list[Path]:
    """`<repo>/_local/tmp` and `<repo>/.claude/worktrees/<wt>/_local/tmp` (the disk standard of these repos)."""
    roots = []
    if not dev_root.is_dir():
        return roots
    for repo in sorted(p for p in dev_root.iterdir() if p.is_dir() and not rc._is_link(p)):
        roots.append(repo / "_local" / "tmp")
        wts = repo / ".claude" / "worktrees"
        if wts.is_dir():
            roots += [wt / "_local" / "tmp" for wt in sorted(wts.iterdir()) if wt.is_dir()]
    return [r for r in roots if r.is_dir() and not rc._is_link(r)]


def npm_cache_dir(home: Path) -> Path:
    local = os.environ.get("LOCALAPPDATA")
    return (Path(local) / "npm-cache" / "_cacache") if local else (home / ".npm" / "_cacache")


# ---------------------------------------------------------------- plan

def _item(kind: str, safety: str, executor: str, target: str, reason: str, **extra: Any) -> dict:
    return {"kind": kind, "safety": safety, "executor": executor, "target": target, "reason": reason, **extra}


def plan_processes(procs: list[dict] | None, budget: dict) -> list[dict]:
    if procs is None:
        return []
    members = rc.plugin_processes(procs, budget["plugin_pattern"])
    children: dict[int, list[dict]] = {}
    for p in procs:
        children.setdefault(p.get("ppid"), []).append(p)
    out = []
    for root in rc.orphan_roots(procs, members):
        tree, stack = [], [root]
        while stack:
            cur = stack.pop()
            tree.append(cur)
            stack += [c for c in children.get(cur["pid"], []) if c.get("created") is None or
                      cur.get("created") is None or c["created"] >= cur["created"]]
        ram = sum((p.get("ws") or 0) for p in tree)
        out.append(_item("orphan_tree", "seguro", "harness", f"pid {root['pid']} ({root.get('name')})",
                         "processo de navegador/MCP cuja sessão já fechou", pid=root["pid"],
                         created=root.get("created"), processes=len(tree), ram_bytes=ram, bytes=0))
    return out


def plan_profiles(temp: Path | None, procs: list[dict] | None, budget: dict) -> list[dict]:
    if temp is None or procs is None or not temp.is_dir():
        return []
    cmds = "\n".join((p.get("cmd") or "") for p in procs)
    prefixes = tuple(budget["profile_prefixes"])
    out = []
    for p in sorted(temp.iterdir()):
        if p.is_dir() and not rc._is_link(p) and p.name.startswith(prefixes) and not in_use(str(p), cmds):
            out.append(_item("orphan_profile", "seguro", "harness", str(p), "perfil de Chrome sem navegador usando",
                             bytes=size_of(p)))
    return out


def plan_repo_tmp(dev_root: Path, procs: list[dict] | None, now: float) -> list[dict]:
    cmds = "\n".join((p.get("cmd") or "") for p in procs or [])
    out = []
    for root in tmp_roots(dev_root):
        for entry in sorted(root.iterdir()):
            try:
                age_h = (now - newest_mtime(entry)) / 3600
            except OSError:
                continue
            if age_h < STALE_HOURS or in_use(str(entry), cmds):
                continue
            out.append(_item("repo_tmp", "seguro" if procs is not None else "decisao", "harness", str(entry),
                             f"_local/tmp parado há {int(age_h)} h", bytes=size_of(entry), idle_hours=int(age_h)))
    return out


def onedrive_dev_root(home: Path) -> Path:
    """The only OneDrive place allowed for repository backups: OneDrive/10-dev/<repo>/backups/."""
    base = os.environ.get("OneDrive")
    return (Path(base) if base else home / "OneDrive") / "10-dev"


def backup_readers(repo: Path, name: str) -> list[str] | None:
    """Tracked files that point at `_local/backups/<name>` (None when Git cannot be read)."""
    pattern = r"_local[\\/]+backups[\\/]+" + re.escape(name) + r"([\\/\"' ]|$)"
    try:
        done = subprocess.run(["git", "-C", str(repo), "grep", "-l", "-E", "-e", pattern], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=60,
                              env=dict(os.environ, GIT_OPTIONAL_LOCKS="0"))
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode == 1:
        return []
    return [line for line in done.stdout.splitlines() if line] if done.returncode == 0 else None


def has_links(path: Path) -> bool:
    if rc._is_link(path):
        return True
    if not path.is_dir():
        return False
    for base, dirs, _files in os.walk(path, followlinks=False):
        if any(rc._is_link(Path(base) / d) for d in dirs):
            return True
    return False


def plan_offload(dev_root: Path, home: Path, keep: dict[str, str] | None = None) -> list[dict]:
    """Big entries of `<repo>/_local/backups` that no tracked file reads: the owner may move them to OneDrive."""
    od = onedrive_dev_root(home)
    if not od.parent.is_dir() or not dev_root.is_dir():
        return []
    out = []
    for repo in sorted(p for p in dev_root.iterdir() if p.is_dir() and not rc._is_link(p)):
        backups = repo / "_local" / "backups"
        if not backups.is_dir() or rc._is_link(backups):
            continue
        for entry in sorted(backups.iterdir()):
            size = size_of(entry)
            if size < OFFLOAD_MIN_BYTES:
                continue
            dest = od / repo.name / "backups" / entry.name
            readers = backup_readers(repo, entry.name)
            if f"{repo.name}/{entry.name}" in (keep or {}):
                safety, reason = "manter", (keep or {})[f"{repo.name}/{entry.name}"]
            elif readers is None:
                safety, reason = "manter", "não deu para ler o Git do repositório"
            elif readers:
                safety, reason = "manter", "o repositório lê: " + ", ".join(readers[:3])
            elif has_links(entry):
                safety, reason = "manter", "tem link ou junction dentro"
            elif dest.exists():
                safety, reason = "manter", "já existe no OneDrive com esse nome"
            else:
                safety, reason = "decisao", "ninguém no repositório lê; vai para o OneDrive e fica só na nuvem"
            out.append(_item("offload_backup", safety, "harness", str(entry), reason, bytes=size, dest=str(dest),
                             repo=repo.name))
    return out


def plan_npm(home: Path) -> list[dict]:
    cache = npm_cache_dir(home)
    if not cache.is_dir() or shutil.which("npm") is None:
        return []
    size = size_of(cache)
    if size < 100 * 2**20:
        return []
    return [_item("npm_cache", "seguro", "harness", str(cache), "cache do npm (o _npx dos servidores MCP fica)",
                  bytes=size)]


def is_worktree(cwd: str | None) -> bool:
    """A session folder inside `<repo>/.claude/worktrees/` (the app reports Windows paths; any OS reads them)."""
    return bool(re.search(r"[\\/]\.claude[\\/]worktrees[\\/][^\\/]+", cwd or ""))


def plan_sessions(sessions: list[dict] | None, now: float) -> list[dict]:
    """Classify the app's sessions (list_sessions output). Archiving is done by the agent with archive_session."""
    if sessions is None:
        return []
    live = [s for s in sessions if isinstance(s, dict) and not s.get("isArchived")]
    states: dict[str, dict] = {}
    for s in live:
        cwd = s.get("cwd") or ""
        if cwd not in states:
            states[cwd] = worktree_state(Path(cwd)) if is_worktree(cwd) else {"state": "repo_root"}

    def verdict(s: dict) -> tuple[str, str]:
        st = states[s.get("cwd") or ""]["state"]
        pr = (s.get("prState") or "").upper()
        if s.get("isRunning"):
            return "manter", "rodando agora"
        if pr == "OPEN":
            return "manter", "PR aberto"
        if st in ("work", "error", "not_git"):
            return "manter", {"work": "trabalho não enviado ao GitHub", "error": "não deu para ler o Git",
                              "not_git": "pasta sem Git (pode ter arquivos fora do Git)"}[st]
        if pr in ("MERGED", "CLOSED"):
            return "seguro", f"PR {pr.lower()} e nada pendente"
        try:
            last = dt.datetime.fromisoformat(str(s.get("lastActivityAt")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return "manter", "sem data de atividade"
        days = (now - last) / 86400
        if days >= IDLE_SESSION_DAYS:
            return "decisao", f"parada há {int(days)} dias, sem PR, nada pendente"
        return "manter", "usada nos últimos dias"

    first = {s["sessionId"]: verdict(s) for s in live if s.get("sessionId")}
    out = []
    for s in live:
        sid = s.get("sessionId")
        if not sid:
            continue
        safety, reason = first[sid]
        if safety != "manter":
            # a worktree shared with a session that must stay is not freed by archiving: keep both
            sharing = [o for o in live if o is not s and o.get("cwd") == s.get("cwd") and first.get(o.get("sessionId"),
                       ("manter",))[0] == "manter"]
            if sharing and is_worktree(s.get("cwd")):
                safety, reason = "manter", "worktree compartilhada com sessão que fica"
        # the app archives a session's side sessions too (those started by it that are idle without an open PR):
        # if one of them should stay, archiving the parent is the owner's call, never 'seguro'
        taken = [o for o in live if o.get("startedBy") == sid and not o.get("isRunning")
                 and (o.get("prState") or "").upper() != "OPEN"]
        kept_kids = [o.get("title") or o.get("sessionId") for o in taken
                     if first.get(o.get("sessionId"), ("manter",))[0] == "manter"]
        if safety == "seguro" and kept_kids:
            safety, reason = "decisao", f"{reason}; arquivar leva junto: {', '.join(kept_kids)}"
        cwd = Path(s.get("cwd") or "")
        # what archiving frees: the worktree, if no other session keeps it (measured only for candidates)
        freed = size_of(cwd) if safety != "manter" and is_worktree(s.get("cwd")) and not any(
            o is not s and o.get("cwd") == s.get("cwd") for o in live) else 0
        out.append(_item("archive_session", safety, "app", s.get("title") or sid, reason, session_id=sid,
                         cwd=s.get("cwd"), pr=s.get("prNumber"), bytes=freed,
                         also_archives=[o.get("title") or o.get("sessionId") for o in taken]))
    return out


def plan_settings(snap: dict, app_settings: dict | None, budget: dict) -> list[dict]:
    out = []
    plugins, procs = snap.get("enabled_plugins"), snap.get("processes")
    rx = re.compile(budget["threejs_pattern"], re.IGNORECASE)
    servers = None if procs is None else sum(1 for p in procs if (p.get("name") or "").lower() in ("node.exe", "node")
                                             and rx.search(p.get("cmd") or "") and "npx-cli" not in (p.get("cmd") or ""))
    quiet = servers is not None and servers <= budget["limits"]["threejs_servers_max"]
    if plugins is not None and not quiet and not any(k.split("@")[0] == budget["heavy_plugin"] and v is False
                                                     for k, v in plugins.items()):
        out.append(_item("setting", "decisao", "dono", f"{budget['heavy_plugin']} desligado na conta",
                         "o plugin da conta abre Chromes em toda sessão; o dono desliga em claude.ai › "
                         "Personalizar › Plugins e religa só para o trabalho de 3D", bytes=0))
    if app_settings is not None:
        if app_settings.get("auto_archive_on_pr_close") is False:
            out.append(_item("setting", "decisao", "app", "auto_archive_on_pr_close = true",
                             "arquivar a sessão quando o PR fecha (libera worktree e processos)", bytes=0))
        if app_settings.get("auto_archive_inactive_days") in (0, None):
            out.append(_item("setting", "decisao", "app", "auto_archive_inactive_days = 7",
                             "arquivar sessão parada há 7 dias (worktree com alteração fica no disco)", bytes=0))
    return out


def build_plan(snap: dict, budget: dict, dev_root: Path, temp: Path | None, home: Path,
               sessions: list[dict] | None, app_settings: dict | None, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    procs = snap.get("processes")
    items = (plan_processes(procs, budget) + plan_profiles(temp, procs, budget) + plan_repo_tmp(dev_root, procs, now)
             + plan_npm(home) + plan_offload(dev_root, home, budget.get("offload_keep")) + plan_sessions(sessions, now)
             + plan_settings(snap, app_settings, budget))
    for i, item in enumerate(items, 1):
        item["id"] = f"{item['kind']}-{i}"
    totals = {s: sum(x["bytes"] for x in items if x["safety"] == s) for s in ("seguro", "decisao", "manter")}
    not_run = [name for name, missing in (("processos", procs is None), ("sessões", sessions is None),
                                          ("configuração do app", app_settings is None)) if missing]
    return {"schema_version": 1, "kind": "resource-plan", "created_at": now, "platform": snap.get("platform"),
            "dev_root": str(dev_root), "temp": None if temp is None else str(temp), "items": items,
            "bytes_by_safety": totals, "not_run": not_run,
            "note": "Plano: nada foi apagado, fechado nem alterado."}


# ---------------------------------------------------------------- apply

def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def remove_tree(path: Path) -> None:
    """Delete a folder without ever entering a link or junction (a link is removed as a link only)."""
    if rc._is_link(path):
        os.rmdir(path) if path.is_dir() else os.unlink(path)
        return
    if not path.is_dir():
        path.unlink()
        return
    for base, dirs, files in os.walk(path, topdown=True, followlinks=False):
        for d in list(dirs):
            full = Path(base) / d
            if rc._is_link(full):
                os.rmdir(full)  # junction/symlink to a folder: drop the link, keep the target
                dirs.remove(d)
    def onexc(func, p, exc):  # read-only files (git objects, pytest)
        os.chmod(p, 0o700)
        func(p)
    shutil.rmtree(path, onexc=onexc)


def kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=60, check=True)
    else:
        os.kill(pid, 15)


def recheck(item: dict, plan: dict, snap: dict, budget: dict, now: float, home: Path) -> str | None:
    """Reason to skip, or None when the item is still exactly what the plan said."""
    kind, target = item["kind"], item["target"]
    procs = snap.get("processes")
    if kind == "orphan_tree":
        if procs is None:
            return "processos não medidos agora"
        roots = {p["pid"]: p for p in rc.orphan_roots(procs, rc.plugin_processes(procs, budget["plugin_pattern"]))}
        root = roots.get(item["pid"])
        if root is None or root.get("created") != item.get("created"):
            return "já não é o mesmo processo órfão"
        return None
    path = Path(target)
    if not path.exists() and not rc._is_link(path):
        return "já saiu"
    cmds = "\n".join((p.get("cmd") or "") for p in procs or [])
    if kind == "orphan_profile":
        temp = plan.get("temp")
        if not temp or not _inside(path, Path(temp)) or not path.name.startswith(tuple(budget["profile_prefixes"])):
            return "fora do Temp ou nome inesperado"
        if procs is None or in_use(str(path), cmds):
            return "em uso agora"
        return None
    if kind == "repo_tmp":
        if not any(_inside(path, r) and path.parent == r for r in tmp_roots(Path(plan["dev_root"]))):
            return "fora de <repo>/_local/tmp"
        if procs is None or in_use(str(path), cmds):
            return "em uso agora"
        if (now - newest_mtime(path)) / 3600 < STALE_HOURS:
            return "gravado nas últimas 48 h"
        return None
    if kind == "npm_cache":
        return None if shutil.which("npm") else "npm não encontrado"
    if kind == "offload_backup":
        repo = Path(plan["dev_root"]) / str(item.get("repo"))
        expected = onedrive_dev_root(home) / str(item.get("repo")) / "backups" / path.name
        if path.parent != repo / "_local" / "backups" or not _inside(path, Path(plan["dev_root"])):
            return "fora de <repo>/_local/backups"
        if f"{item.get('repo')}/{path.name}" in budget.get("offload_keep", {}):
            return "protegido no orçamento (offload_keep)"
        if Path(item.get("dest") or "") != expected:
            return "destino fora de OneDrive/10-dev/<repo>/backups"
        if expected.exists() or expected.with_name(expected.name + ".partial").exists():
            return "já existe no OneDrive com esse nome"
        if backup_readers(repo, path.name) != []:
            return "o repositório lê (ou o Git não pôde ser lido)"
        if has_links(path):
            return "tem link ou junction dentro"
        if procs is None or in_use(str(path), cmds):
            return "em uso agora"
        return None
    return "tipo não aplicável pelo Harness"


def file_manifest(path: Path) -> dict[str, tuple[int, str]]:
    """{relative path: (size, sha256)} of every file, without following links."""
    import hashlib

    def digest(f: Path) -> tuple[int, str]:
        h = hashlib.sha256()
        with f.open("rb") as fh:
            for chunk in iter(lambda: fh.read(4 * 2**20), b""):
                h.update(chunk)
        return f.stat().st_size, h.hexdigest()
    if path.is_file():
        return {".": digest(path)}
    out = {}
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not rc._is_link(Path(base) / d)]
        for name in files:
            f = Path(base) / name
            out[f.relative_to(path).as_posix()] = digest(f)
    return out


def mark_online_only(path: Path) -> bool | None:
    """OneDrive 'Free up space' (attrib +U -P). None outside Windows; False when attrib failed."""
    if sys.platform != "win32":
        return None
    targets = [str(path)] + ([str(path / "*")] if path.is_dir() else [])
    ok = True
    for t in targets:
        args = ["attrib", "+U", "-P", t] + (["/S", "/D"] if t.endswith("*") else [])
        ok = subprocess.run(args, capture_output=True, timeout=600).returncode == 0 and ok
    return ok


def offload(src: Path, dest: Path) -> dict:
    """Copy to OneDrive, prove the copy is identical, mark it online-only, and only then delete the original."""
    partial = dest.with_name(dest.name + ".partial")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or partial.exists():
        raise FileExistsError(str(dest))
    try:
        if src.is_dir():
            shutil.copytree(src, partial)
        else:
            shutil.copy2(src, partial)
        if file_manifest(src) != file_manifest(partial):
            raise OSError("a cópia no OneDrive não confere com o original; original mantido")
    except BaseException:
        if partial.exists() or rc._is_link(partial):  # never leave a half copy in OneDrive
            remove_tree(partial)
        raise
    partial.rename(dest)
    online = mark_online_only(dest)
    remove_tree(src)
    return {"dest": str(dest), "online_only": online}


def apply_plan(plan: dict, ids: set[str] | None, safe: bool, really: bool, budget: dict, home: Path,
               now: float | None = None, snap: dict | None = None) -> dict:
    now = time.time() if now is None else now
    if plan.get("kind") != "resource-plan" or plan.get("schema_version") != 1:
        raise CleanError("not a resource-plan")
    if now - float(plan.get("created_at") or 0) > PLAN_MAX_AGE_S:
        raise CleanError("plan older than 2 h: run plan again and show it to the owner")
    if not ids and not safe:
        raise CleanError("choose items with --ids or --safe")
    items = {x["id"]: x for x in plan["items"]}
    unknown = sorted((ids or set()) - set(items))
    if unknown:
        raise CleanError(f"unknown ids: {unknown}")
    chosen = [x for x in plan["items"] if x["executor"] == "harness" and x["kind"] in HARNESS_KINDS
              and ((ids and x["id"] in ids) or (safe and not ids and x["safety"] == "seguro"))]
    refused = sorted(i for i in (ids or set()) if items[i]["executor"] != "harness")
    snap = snap if snap is not None else {"processes": (rc.collect_windows() or {}).get("processes")}
    before = shutil.disk_usage(plan["dev_root"] if Path(plan["dev_root"]).exists() else home).free
    results = []
    for item in chosen:
        why = recheck(item, plan, snap, budget, now, home)
        if why:
            results.append({"id": item["id"], "status": "SKIPPED", "reason": why})
            continue
        if not really:
            results.append({"id": item["id"], "status": "WOULD_DO", "target": item["target"]})
            continue
        try:
            if item["kind"] == "orphan_tree":
                kill_tree(item["pid"])
            elif item["kind"] == "npm_cache":
                subprocess.run([shutil.which("npm"), "cache", "clean", "--force"], capture_output=True,
                               timeout=300, check=True)
            elif item["kind"] == "offload_backup":
                moved = offload(Path(item["target"]), Path(item["dest"]))
                results.append({"id": item["id"], "status": "DONE", "target": item["target"], **moved})
                continue
            else:
                remove_tree(Path(item["target"]))
            results.append({"id": item["id"], "status": "DONE", "target": item["target"]})
        except (OSError, subprocess.SubprocessError) as exc:
            results.append({"id": item["id"], "status": "FAILED", "reason": f"{type(exc).__name__}: {exc}"})
    after = shutil.disk_usage(plan["dev_root"] if Path(plan["dev_root"]).exists() else home).free
    return {"kind": "resource-apply", "applied": really, "results": results,
            "refused_app_items": refused, "freed_bytes_measured": (after - before) if really else None,
            "note": "Só itens do Harness. Sessões e configurações são feitas pelo agente com as ferramentas do app."}


# ---------------------------------------------------------------- output

def gb(n: int | None) -> str:
    return "-" if not n else f"{n / rc.GB:.2f} GB"


def render_plan(plan: dict) -> str:
    lines = [f"resource-clean plan  ({dt.datetime.fromtimestamp(plan['created_at']).isoformat(timespec='seconds')})"]
    for safety, title in (("seguro", "SEGURO (eu faço depois do seu sim)"), ("decisao", "DECISÃO SUA"),
                          ("manter", "MANTER (não mexo)")):
        group = [x for x in plan["items"] if x["safety"] == safety]
        if not group:
            continue
        lines.append(f"== {title}: {len(group)} itens, {gb(plan['bytes_by_safety'][safety])}")
        for kind in dict.fromkeys(x["kind"] for x in group):
            same = [x for x in group if x["kind"] == kind]
            if len(same) > 5 and kind in HARNESS_KINDS:  # many files of one kind: one line, ids listed
                lines.append(f"  {len(same)} x {kind}: {gb(sum(x['bytes'] for x in same))}  "
                             f"(ex.: {same[0]['target']}; ids {same[0]['id']} .. {same[-1]['id']}; por: harness)")
                continue
            for x in same:
                extra = (f", {x['processes']} processos, {gb(x['ram_bytes'])} de RAM"
                         if x["kind"] == "orphan_tree" else "")
                if x.get("also_archives") and x["safety"] != "manter":
                    extra += f"; leva junto: {', '.join(x['also_archives'])}"
                lines.append(f"  [{x['id']}] {x['target']}  {gb(x['bytes'])}{extra}  "
                             f"({x['reason']}; por: {x['executor']})")
    if plan["not_run"]:
        lines.append("  NÃO MEDIDO: " + ", ".join(plan["not_run"]))
    lines.append("  " + plan["note"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harnessctl.py resource-clean", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("plan", "apply"))
    parser.add_argument("--budget", type=Path, default=rc.DEFAULT_BUDGET)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--dev-root", type=Path, default=Path(os.environ.get("HARNESS_DEV_ROOT", "C:/dev")))
    parser.add_argument("--temp", type=Path, default=Path(os.environ["TEMP"]) if os.environ.get("TEMP") else None)
    parser.add_argument("--sessions", type=Path, help="plan: JSON array from the app's list_sessions")
    parser.add_argument("--app-settings", type=Path, help="plan: JSON object {key: value} from the app's get_settings")
    parser.add_argument("--output", type=Path, help="plan: write the plan JSON here (apply reads it back)")
    parser.add_argument("--plan", type=Path, help="apply: the plan the owner approved")
    parser.add_argument("--ids", help="apply: comma-separated item ids")
    parser.add_argument("--safe", action="store_true", help="apply: every 'seguro' item of the Harness")
    parser.add_argument("--apply", action="store_true", help="apply: really do it (default: dry run)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    try:
        budget = rc.read_budget(args.budget)
        if args.action == "plan":
            sessions = json.loads(args.sessions.read_text(encoding="utf-8")) if args.sessions else None
            if sessions is not None and not isinstance(sessions, list):
                raise CleanError("--sessions must be a JSON array")
            app_settings = json.loads(args.app_settings.read_text(encoding="utf-8")) if args.app_settings else None
            if app_settings is not None and not isinstance(app_settings, dict):
                raise CleanError("--app-settings must be a JSON object")
            snap = rc.collect(args.home, args.dev_root, args.temp, budget)
            plan = build_plan(snap, budget, args.dev_root, args.temp, args.home, sessions, app_settings)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(json.dumps(plan, indent=2, ensure_ascii=False) if args.json else render_plan(plan))
            return 0
        if not args.plan:
            raise CleanError("apply needs --plan")
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
        ids = {i.strip() for i in args.ids.split(",") if i.strip()} if args.ids else None
        result = apply_plan(plan, ids, args.safe, args.apply, budget, args.home)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if any(r["status"] == "FAILED" for r in result["results"]) else 0
    except Exception as exc:  # BLOCKED, never a half-told success
        print(json.dumps({"status": "BLOCKED", "reason": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
