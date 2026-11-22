#!/usr/bin/env python3
"""HE-OPS-01: resource budget of this computer for agent sessions (read-only).

Measures disk, committed memory, pagefile, the hidden Chromes and MCP servers that agent plugins leave
running, orphan process trees, sessions, worktrees and conversation history, and compares each value
with config/resource_budget.json. It never deletes, kills or changes anything: cleanup stays with the
limpeza-de-disco skill, after the owner's yes.

Status per check: PASS, FAIL or NOT_RUN (value null, never 0). Overall: FAIL if any check failed,
INCONCLUSIVE if none failed but some did not run, PASS otherwise. Exit code 0 PASS, 1 FAIL,
3 INCONCLUSIVE, 2 BLOCKED (bad budget or arguments).
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
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUDGET = ROOT / "config" / "resource_budget.json"
GB = 1024 ** 3
LIMIT_KEYS = {
    "disk_free_gb_min", "commit_over_ram_gb_max", "pagefile_gb_max", "threejs_servers_max", "plugin_ram_gb_max",
    "orphan_profiles_max", "orphan_trees_max", "claude_processes_max", "claude_worktrees_max", "history_gb_max",
}
BUDGET_KEYS = {"schema_version", "note", "limits", "plugin_pattern", "threejs_pattern", "profile_prefixes",
               "heavy_plugin", "user_mcp_allowed", "owner_names"}

PS_SNAPSHOT = r"""
$ErrorActionPreference = 'Stop'
$os = Get-CimInstance Win32_OperatingSystem
$pf = (Get-CimInstance Win32_PageFileUsage | Measure-Object AllocatedBaseSize -Sum).Sum
$procs = @(Get-CimInstance Win32_Process | ForEach-Object {
  [pscustomobject]@{
    pid = [int]$_.ProcessId; ppid = [int]$_.ParentProcessId; name = [string]$_.Name; cmd = [string]$_.CommandLine
    created = $(if ($_.CreationDate) { ([DateTimeOffset]$_.CreationDate).ToUnixTimeSeconds() } else { $null })
    ws = [int64]$_.WorkingSetSize
  }
})
[pscustomobject]@{
  ram_kb = [int64]$os.TotalVisibleMemorySize; total_virtual_kb = [int64]$os.TotalVirtualMemorySize
  free_virtual_kb = [int64]$os.FreeVirtualMemory; pagefile_mb = $pf; processes = $procs
} | ConvertTo-Json -Depth 4 -Compress
"""


class BudgetError(ValueError):
    pass


# ---------------------------------------------------------------- budget

def read_budget(path: Path) -> dict:
    try:
        budget = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BudgetError(f"budget unreadable: {path}: {exc}") from exc
    if not isinstance(budget, dict) or budget.get("schema_version") != 1:
        raise BudgetError("budget schema_version must be 1")
    unknown = set(budget) - BUDGET_KEYS
    if unknown:
        raise BudgetError(f"unknown budget keys: {sorted(unknown)}")
    limits = budget.get("limits")
    if not isinstance(limits, dict) or set(limits) != LIMIT_KEYS:
        raise BudgetError(f"budget limits must have exactly {sorted(LIMIT_KEYS)}")
    for key, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise BudgetError(f"limit {key} must be a non-negative number")
    for key in ("plugin_pattern", "threejs_pattern"):
        try:
            re.compile(str(budget.get(key, "")))
        except re.error as exc:
            raise BudgetError(f"{key} is not a valid regex: {exc}") from exc
        if not budget.get(key):
            raise BudgetError(f"{key} required")
    for key in ("profile_prefixes", "user_mcp_allowed", "owner_names"):
        if not isinstance(budget.get(key), list) or not all(isinstance(x, str) for x in budget[key]):
            raise BudgetError(f"{key} must be a list of strings")
    if not isinstance(budget.get("heavy_plugin"), str) or not budget["heavy_plugin"]:
        raise BudgetError("heavy_plugin required")
    return budget


# ---------------------------------------------------------------- collection (each part may fail -> None)

def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def collect_windows(timeout_s: float = 90.0) -> dict | None:
    """Memory, pagefile and the process table, from one CIM call. None outside Windows or on failure."""
    if sys.platform != "win32":
        return None
    exe = _powershell()
    if not exe:
        return None
    try:
        done = subprocess.run([exe, "-NoProfile", "-NonInteractive", "-Command", PS_SNAPSHOT],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s)
        if done.returncode != 0:
            return None
        data = json.loads(done.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    procs = data.get("processes") or []
    if isinstance(procs, dict):
        procs = [procs]
    return {
        "ram_gb": data["ram_kb"] / 1024 ** 2,
        "commit_gb": (data["total_virtual_kb"] - data["free_virtual_kb"]) / 1024 ** 2,
        "pagefile_gb": (data["pagefile_mb"] or 0) / 1024,
        "processes": procs,
    }


def dir_bytes(path: Path) -> int | None:
    """Size without following links or junctions. None when the folder does not exist."""
    if not path.is_dir():
        return None
    total = 0
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not _is_link(Path(base) / d)]
        for name in files:
            try:
                st = os.lstat(os.path.join(base, name))
            except OSError:
                continue
            total += st.st_size
    return total


def _is_link(path: Path) -> bool:
    try:
        return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
    except OSError:
        return True


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def collect(home: Path, dev_root: Path, temp: Path | None, budget: dict) -> dict:
    snap: dict[str, Any] = {"platform": sys.platform, "checked_at": dt.datetime.now().astimezone().isoformat()}
    anchor = dev_root if dev_root.exists() else home
    try:
        snap["disk_free_gb"] = shutil.disk_usage(anchor).free / GB
    except OSError:
        snap["disk_free_gb"] = None
    win = collect_windows()
    snap.update(win or {"ram_gb": None, "commit_gb": None, "pagefile_gb": None, "processes": None})
    snap["temp_profiles"] = None
    if temp is not None and temp.is_dir():
        prefixes = tuple(budget["profile_prefixes"])
        try:
            snap["temp_profiles"] = sorted(str(p) for p in temp.iterdir() if p.is_dir() and p.name.startswith(prefixes))
        except OSError:
            snap["temp_profiles"] = None
    worktrees: dict[str, int] = {}
    if dev_root.is_dir():
        for repo in sorted(p for p in dev_root.iterdir() if p.is_dir()):
            wt = repo / ".claude" / "worktrees"
            if wt.is_dir():
                worktrees[repo.name] = sum(1 for p in wt.iterdir() if p.is_dir())
        snap["claude_worktrees"] = worktrees
    else:
        snap["claude_worktrees"] = None
    codex_home = Path(os.environ.get("CODEX_HOME") or home / ".codex")
    codex_wt = codex_home / "worktrees"
    snap["codex_worktrees"] = sum(1 for p in codex_wt.iterdir() if p.is_dir()) if codex_wt.is_dir() else None
    settings = _read_json(home / ".claude" / "settings.json")
    snap["enabled_plugins"] = (settings or {}).get("enabledPlugins") if settings is not None else None
    user_cfg = _read_json(home / ".claude.json")
    snap["user_mcp"] = None if user_cfg is None else sorted(
        name for name, cfg in (user_cfg.get("mcpServers") or {}).items() if isinstance(cfg, dict) and cfg.get("command"))
    claude_h = dir_bytes(home / ".claude" / "projects")
    codex_h = dir_bytes(codex_home / "sessions")
    snap["history_gb"] = None if claude_h is None and codex_h is None else {
        "claude": None if claude_h is None else claude_h / GB, "codex": None if codex_h is None else codex_h / GB}
    return snap


# ---------------------------------------------------------------- evaluation (pure)

def _check(cid: str, rule: str, value: Any, limit: Any, ok: bool | None, cause: str, fix: str) -> dict:
    status = "NOT_RUN" if ok is None else ("PASS" if ok else "FAIL")
    item = {"id": cid, "rule": rule, "status": status, "value": value, "limit": limit}
    if status == "FAIL":
        item.update(cause=cause, fix=fix)
    return item


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 1)


def plugin_processes(procs: list[dict], pattern: str) -> list[dict]:
    rx = re.compile(pattern, re.IGNORECASE)
    return [p for p in procs if rx.search(p.get("cmd") or "")]


def orphan_roots(procs: list[dict], members: list[dict]) -> list[dict]:
    """Plugin processes whose parent is gone (missing PID, or PID reused by a younger process)."""
    live = {p["pid"]: p for p in procs}
    roots = []
    for p in members:
        parent = live.get(p.get("ppid"))
        reused = (parent is not None and parent.get("created") is not None and p.get("created") is not None
                  and parent["created"] > p["created"])
        if parent is None or reused:
            roots.append(p)
    return roots


def owners(procs: list[dict], members: list[dict], owner_names: list[str]) -> list[dict]:
    """Group plugin processes by the nearest ancestor that is an agent (claude/codex): who keeps them alive."""
    live = {p["pid"]: p for p in procs}
    names = {n.lower() for n in owner_names}
    groups: dict[Any, dict] = {}
    for p in members:
        cur, seen, owner = p, set(), None
        while cur is not None and cur["pid"] not in seen:
            seen.add(cur["pid"])
            if (cur.get("name") or "").lower() in names and cur is not p:
                owner = cur
                break
            parent = live.get(cur.get("ppid"))
            if parent is not None and cur.get("created") is not None and parent.get("created") is not None \
                    and parent["created"] > cur["created"]:
                parent = None
            cur = parent
        key = owner["pid"] if owner else None
        g = groups.setdefault(key, {"owner_pid": key, "owner": owner["name"] if owner else "órfão (pai morto)",
                                    "processes": 0, "ram_gb": 0.0})
        g["processes"] += 1
        g["ram_gb"] += (p.get("ws") or 0) / GB
    out = sorted(groups.values(), key=lambda g: -g["ram_gb"])
    for g in out:
        g["ram_gb"] = round(g["ram_gb"], 2)
    return out


def evaluate(snap: dict, budget: dict) -> dict:
    L = budget["limits"]
    checks = []
    free = snap.get("disk_free_gb")
    checks.append(_check("disk_free", "espaço livre", _r(free), L["disk_free_gb_min"],
                         None if free is None else free >= L["disk_free_gb_min"],
                         "disco abaixo da margem de um dia de sessões",
                         "rodar a skill limpeza-de-disco (diagnóstico e simulação antes de apagar)"))
    ram, commit = snap.get("ram_gb"), snap.get("commit_gb")
    commit_limit = None if ram is None else _r(ram + L["commit_over_ram_gb_max"])
    checks.append(_check("commit", "memória comprometida <= RAM + folga", _r(commit), commit_limit,
                         None if ram is None or commit is None else commit <= ram + L["commit_over_ram_gb_max"],
                         "memória comprometida acima da RAM: o Windows aumenta o pagefile no disco",
                         "arquivar as sessões paradas; desligar o plugin pesado onde não é usado"))
    pf = snap.get("pagefile_gb")
    checks.append(_check("pagefile", "tamanho do pagefile", _r(pf), L["pagefile_gb_max"],
                         None if pf is None else pf <= L["pagefile_gb_max"],
                         "pagefile inchado: só encolhe depois que a memória comprometida cai e o PC reinicia",
                         "baixar a memória comprometida e então reiniciar"))
    procs = snap.get("processes")
    members = None if procs is None else plugin_processes(procs, budget["plugin_pattern"])
    tjs_rx = re.compile(budget["threejs_pattern"], re.IGNORECASE)
    tjs = None if procs is None else [p for p in procs if (p.get("name") or "").lower() in ("node.exe", "node")
                                      and tjs_rx.search(p.get("cmd") or "") and "npx-cli" not in (p.get("cmd") or "")]
    checks.append(_check("threejs_servers", "servidores do plugin 3D", None if tjs is None else len(tjs),
                         L["threejs_servers_max"], None if tjs is None else len(tjs) <= L["threejs_servers_max"],
                         f"plugin {budget['heavy_plugin']} ligado em todas as sessões (abre um Chrome ao iniciar)",
                         f"desligar {budget['heavy_plugin']} na conta e ligar só nos repositórios de 3D"))
    plug_gb = None if members is None else sum((p.get("ws") or 0) for p in members) / GB
    checks.append(_check("plugin_ram", "RAM de servidores MCP de navegador e seus Chromes", _r(plug_gb),
                         L["plugin_ram_gb_max"], None if plug_gb is None else plug_gb <= L["plugin_ram_gb_max"],
                         "servidores MCP de navegador e Chromes escondidos ocupando RAM",
                         "arquivar as sessões paradas; ver 'owners' para saber quem os mantém"))
    profiles = snap.get("temp_profiles")
    if profiles is None or procs is None:
        orphan_prof = None
    else:
        cmds = "\n".join((p.get("cmd") or "") for p in procs).lower()
        orphan_prof = [x for x in profiles if x.lower() not in cmds]
    checks.append(_check("orphan_profiles", "perfis de Chrome órfãos no Temp",
                         None if orphan_prof is None else len(orphan_prof), L["orphan_profiles_max"],
                         None if orphan_prof is None else len(orphan_prof) <= L["orphan_profiles_max"],
                         "perfis de Chrome deixados para trás por servidores MCP",
                         "limpeza-de-disco: limpar.ps1 -Itens perfis (simular, mostrar, aplicar após o sim)"))
    roots = None if members is None else orphan_roots(procs, members)
    checks.append(_check("orphan_trees", "processos de navegador/MCP com o pai morto",
                         None if roots is None else len(roots), L["orphan_trees_max"],
                         None if roots is None else len(roots) <= L["orphan_trees_max"],
                         "a sessão dona fechou e os processos ficaram vivos",
                         "fechar essas árvores de processo (com o sim do dono) e relatar o defeito à ferramenta"))
    claude = None if procs is None else [p for p in procs if (p.get("name") or "").lower() in ("claude.exe", "claude")]
    checks.append(_check("claude_processes", "processos claude abertos", None if claude is None else len(claude),
                         L["claude_processes_max"], None if claude is None else len(claude) <= L["claude_processes_max"],
                         "sessões demais abertas ao mesmo tempo, mesmo paradas",
                         "arquivar as sessões paradas; ligar o arquivamento automático após o PR"))
    wts = snap.get("claude_worktrees")
    total_wt = None if wts is None else sum(wts.values())
    checks.append(_check("claude_worktrees", "worktrees do Claude em todos os repositórios", total_wt,
                         L["claude_worktrees_max"], None if total_wt is None else total_wt <= L["claude_worktrees_max"],
                         "worktrees acumuladas (cada uma pode ter seu node_modules)",
                         "arquivar sessões de PR mesclado; no app, limpar worktrees; avaliar worktree.symlinkDirectories"))
    hist = snap.get("history_gb")
    hist_total = None if hist is None else sum(v for v in hist.values() if v is not None)
    checks.append(_check("history", "histórico de conversas (Claude + Codex)", _r(hist_total), L["history_gb_max"],
                         None if hist_total is None else hist_total <= L["history_gb_max"],
                         "histórico de conversas sem limite de idade",
                         "decisão do dono: cleanupPeriodDays no Claude; arquivar sessões antigas do Codex"))
    plugins = snap.get("enabled_plugins")
    if plugins is None:
        heavy_off, heavy_val = None, None
    else:
        offs = sorted(k for k, v in plugins.items() if k.split("@")[0] == budget["heavy_plugin"] and v is False)
        heavy_off, heavy_val = bool(offs), (offs[0] + " = false") if offs else "sem entrada (vale o ligado da conta)"
    checks.append(_check("heavy_plugin_off", f"{budget['heavy_plugin']} desligado em ~/.claude/settings.json",
                         heavy_val, "false", heavy_off,
                         "o plugin da conta vale para todo repositório",
                         "decisão do dono: desligar no computador e ligar no .claude/settings.json dos repositórios de 3D"))
    mcp = snap.get("user_mcp")
    extra = None if mcp is None else [m for m in mcp if m not in budget["user_mcp_allowed"]]
    checks.append(_check("user_mcp", "MCP local no escopo do usuário fora da lista", extra, budget["user_mcp_allowed"],
                         None if extra is None else not extra,
                         "servidor MCP local que sobe em toda sessão de todo repositório",
                         "mover para o escopo do projeto que o usa"))
    statuses = {c["status"] for c in checks}
    overall = "FAIL" if "FAIL" in statuses else ("INCONCLUSIVE" if "NOT_RUN" in statuses else "PASS")
    report = {"schema_version": 1, "kind": "resource-check", "status": overall,
              "checked_at": snap.get("checked_at"), "platform": snap.get("platform"), "checks": checks,
              "owners": None if members is None else owners(procs, members, budget["owner_names"])[:8],
              "worktrees_by_repo": None if wts is None else dict(sorted(wts.items(), key=lambda kv: -kv[1])),
              "codex_worktrees": snap.get("codex_worktrees"),
              "history_gb_by_tool": None if hist is None else {k: _r(v) for k, v in hist.items()},
              "note": "Somente leitura: nada foi apagado, fechado ou alterado."}
    return report


def render_text(rep: dict) -> str:
    lines = [f"resource-check: {rep['status']}  ({rep['checked_at']})"]
    for c in rep["checks"]:
        lines.append(f"  {c['status']:<8} {c['rule']}: {c['value']} (limite {c['limit']})")
        if c["status"] == "FAIL":
            lines.append(f"           causa: {c['cause']}. o que fazer: {c['fix']}")
    if rep.get("owners"):
        lines.append("  quem mantém os processos de navegador/MCP (por RAM):")
        for g in rep["owners"][:5]:
            lines.append(f"    {g['owner']} pid={g['owner_pid']}: {g['processes']} processos, {g['ram_gb']} GB")
    lines.append("  " + rep["note"])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harnessctl.py resource-check", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--dev-root", type=Path, default=Path(os.environ.get("HARNESS_DEV_ROOT", "C:/dev")))
    parser.add_argument("--temp", type=Path, default=Path(os.environ["TEMP"]) if os.environ.get("TEMP") else None)
    parser.add_argument("--json", action="store_true", help="saída JSON (padrão: texto curto)")
    parser.add_argument("--output", type=Path, help="gravar também o JSON neste arquivo (ex.: _local/artifacts/)")
    args = parser.parse_args(argv)
    try:
        budget = read_budget(args.budget)
    except BudgetError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    rep = evaluate(collect(args.home, args.dev_root, args.temp, budget), budget)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False) if args.json else render_text(rep))
    return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 3}[rep["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
