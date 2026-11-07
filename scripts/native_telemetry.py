#!/usr/bin/env python3
"""Telemetria nativa do Codex e do Claude Code, normalizada num formato só (HE-R2-01).

Fontes, conferidas no upstream:
- Codex `exec --json` (rust-v0.166.0, codex-rs/exec/src/event_processor_with_jsonl_output.rs): o `usage` de
  `turn.completed` é o **total acumulado da sessão** (`usage.total`), não o do turno. Somar turnos conta em dobro;
  vale o último. Quando nada foi contado, o Codex emite tudo `0` (`Usage::default()`): isso é "não observado".
  Em `input_tokens` o cache já está incluído (`cached_input_tokens` é parte dele). Não há custo.
- Claude Code `-p --output-format stream-json --verbose`: evento `system/init` (modelo, versão, skills), mensagens
  com `tool_use`/`tool_result` e um `result` final com `usage` e `total_cost_usd`. Em `input_tokens` o cache NÃO
  está incluído; aqui ele é somado para ficar comparável ao Codex. `total_cost_usd` é estimativa do cliente.

Regras: ausente é `None`, nunca `0`; custo estimado nunca vira custo observado.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

USAGE_KEYS = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens", "output_tokens",
              "reasoning_output_tokens")


def _empty(client: str) -> dict[str, Any]:
    return {
        "client": client,
        "client_version": None,
        "model": None,
        "session_id": None,
        "skills_available": None,
        "turns": None,
        "usage": None,
        "raw_usage": None,
        "usage_semantics": None,
        "cost": {"cost_usd": None, "cost_source": "unknown", "observed": False},
        "tool_calls": [],
        "final_message": None,
        "errors": [],
        "non_json_lines": 0,
    }


def _events(lines: Iterable[str | dict], out: dict[str, Any]) -> list[dict]:
    """Aceita linhas JSONL ou eventos já decodificados."""
    events = []
    for raw in lines:
        if isinstance(raw, dict):
            events.append(raw)
            continue
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except ValueError:
            out["non_json_lines"] += 1
            continue
        if isinstance(event, dict):
            events.append(event)
        else:
            out["non_json_lines"] += 1
    return events


def _int(value: Any) -> int | None:
    return value if type(value) is int else None


def parse_codex(lines: Iterable[str]) -> dict[str, Any]:
    out = _empty("codex")
    last_usage: dict | None = None
    turns = 0
    messages: list[str] = []
    for event in _events(lines, out):
        kind = event.get("type")
        if kind == "thread.started":
            out["session_id"] = event.get("thread_id")
        elif kind == "turn.completed":
            turns += 1
            if isinstance(event.get("usage"), dict):
                last_usage = event["usage"]
        elif kind == "turn.failed":
            out["errors"].append("turn.failed")
        elif kind == "error":
            out["errors"].append("error")
        elif kind == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                messages.append(str(item.get("text", "")))
            elif item.get("type") == "command_execution" and item.get("status") == "completed":
                code = _int(item.get("exit_code"))
                if code is None:
                    continue
                out["tool_calls"].append({
                    "tool": "shell",
                    "command": str(item.get("command", "")),
                    "output": str(item.get("aggregated_output", "")),
                    "exit_code": code,
                    "succeeded": code == 0,
                })
    out["turns"] = turns
    out["final_message"] = messages[-1] if messages else None
    if last_usage is not None:
        usage = {key: _int(last_usage.get(key)) for key in USAGE_KEYS}
        if any(usage.values()):  # tudo 0/ausente = Usage::default(), nada contado
            out["usage"] = usage
            out["raw_usage"] = dict(last_usage)
            out["usage_semantics"] = "codex_cumulative_thread_total"
    return out


def _text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(str(b.get("text", "")) for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _claude_call(block: dict) -> dict[str, Any]:
    name = block.get("name")
    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
    call: dict[str, Any] = {"id": block.get("id"), "name": name, "output": None, "exit_code": None,
                            "succeeded": None}
    if name == "Bash":
        call.update(tool="shell", command=str(inp.get("command", "")))
    elif name == "Skill":
        call.update(tool="skill", skill=str(inp.get("skill") or inp.get("command") or ""))
    elif name == "Read":
        call.update(tool="read", path=str(inp.get("file_path", "")))
    else:
        call.update(tool="other")
    return call


def parse_claude(lines: Iterable[str]) -> dict[str, Any]:
    out = _empty("claude")
    by_id: dict[str, dict] = {}
    result: dict | None = None
    api_key_source = None
    for event in _events(lines, out):
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            out["model"] = event.get("model")
            out["client_version"] = event.get("claude_code_version")
            out["session_id"] = event.get("session_id")
            skills = event.get("skills")
            out["skills_available"] = list(skills) if isinstance(skills, list) else None
            api_key_source = event.get("apiKeySource")
        elif kind == "assistant":
            for block in (event.get("message") or {}).get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    call = _claude_call(block)
                    out["tool_calls"].append(call)
                    if call["id"]:
                        by_id[call["id"]] = call
        elif kind == "user":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    call = by_id.get(block.get("tool_use_id"))
                    if call is not None:
                        call["output"] = _text(block.get("content"))
                        call["succeeded"] = not bool(block.get("is_error"))
        elif kind == "result":
            result = event
    for call in out["tool_calls"]:
        call.pop("id", None)
        call.pop("name", None)

    if result is None:
        out["errors"].append("result_missing")
        return out
    if result.get("is_error") or result.get("subtype") != "success":
        out["errors"].append(str(result.get("subtype") or "error"))
    out["turns"] = _int(result.get("num_turns"))
    if isinstance(result.get("result"), str):
        out["final_message"] = result["result"]
    if out["model"] is None and isinstance(result.get("modelUsage"), dict) and len(result["modelUsage"]) == 1:
        out["model"] = next(iter(result["modelUsage"]))
    raw = result.get("usage")
    if isinstance(raw, dict):
        fresh, read, write = (_int(raw.get(k)) for k in
                              ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        parts = [p for p in (fresh, read, write) if p is not None]
        out["usage"] = {
            "input_tokens": sum(parts) if parts else None,
            "cached_input_tokens": read,
            "cache_write_input_tokens": write,
            "output_tokens": _int(raw.get("output_tokens")),
            "reasoning_output_tokens": None,  # o Claude Code não separa raciocínio
        }
        out["raw_usage"] = dict(raw)
        out["usage_semantics"] = "claude_session_total_incl_cache"
    cost = result.get("total_cost_usd")
    if isinstance(cost, (int, float)) and not isinstance(cost, bool):
        out["cost"] = {
            "cost_usd": cost,
            # assinatura: estimativa do cliente; com chave de API também é estimativa, não fatura
            "cost_source": "subscription_estimate" if api_key_source == "none" else "unknown",
            "observed": False,
        }
    return out


def parse(client: str, lines: Iterable[str]) -> dict[str, Any]:
    if client == "codex":
        return parse_codex(lines)
    if client == "claude":
        return parse_claude(lines)
    raise ValueError(f"cliente sem parser de telemetria: {client}")
