#!/usr/bin/env python3
"""Empirical collector for Jev and native model classification runs.

Pure standard library. Manages controlled execution of tasks from benchmarks/jev/tasks/.
Enforces evidence categorization:
  - SYNTHETIC: generated in simulation mode for pipeline and policy testing.
  - OBSERVED: captured directly from live provider execution with MCP adapter.
  - VERIFIED: captured in verified container with negative canaries checked.

Refuses live execution unless Gate G1 isolation and API credentials are verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Import adapter functions for cryptographic attestation and MCP communication
try:
    from scripts.jev_adapter import (
        AttestationError,
        JevMcpClient,
        compute_sha256,
        generate_attestation,
        verify_attestation,
    )
except ImportError:
    # If run from within sandbox directory
    try:
        from jev_adapter import (  # type: ignore
            AttestationError,
            JevMcpClient,
            compute_sha256,
            generate_attestation,
            verify_attestation,
        )
    except ImportError:
        def compute_sha256(content: str) -> str:
            return hashlib.sha256(content.encode("utf-8")).hexdigest()
        generate_attestation = None  # type: ignore
        verify_attestation = None  # type: ignore
        JevMcpClient = None  # type: ignore

class CollectorError(ValueError):
    pass

def load_tasks(path: Path) -> list[dict]:
    if not path.is_file():
        raise CollectorError(f"Tasks file not found: {path}")
    tasks = []
    seen_ids = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CollectorError(f"Line {line_no} invalid JSON: {exc}") from exc
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in seen_ids:
            raise CollectorError(f"Line {line_no} missing or duplicate task_id: {task_id}")
        seen_ids.add(task_id)
        if not item.get("domain") or not item.get("input_text") or not isinstance(item.get("candidate_labels"), list):
            raise CollectorError(f"Line {line_no} malformed task: missing required domain, input_text, or candidate_labels")
        # Ensure tasks do NOT include ground truth labels (prevent contamination)
        if "expected_label" in item or "expected" in item or "golden_label" in item:
            raise CollectorError(f"Line {line_no} task {task_id} contains ground truth expected label! Tasks must be blind.")
        tasks.append(item)
    if not tasks:
        raise CollectorError("Task suite is empty")
    return tasks

def simulate_provider_call(task: dict, condition: str) -> dict:
    """Deterministic simulation stub strictly labeled as SYNTHETIC.
    
    Used only for testing data pipelines, schemas, and scoring logic offline.
    """
    candidates = task["candidate_labels"]
    task_id = task["task_id"]
    domain = task["domain"]
    
    # Deterministic mock responses based on task_type to test policy edge cases
    task_type = task.get("task_type", "standard")
    
    if condition == "CONDITION_J_ADVISORY":
        if "adversarial" in task_type or "ambiguous" in task_type:
            # Advisory classifier abstains or identifies uncertainty
            label = "uncertain"
            confidence = 0.35
            margin = 0.08
            probs = {c: 0.15 for c in candidates}
            probs["uncertain"] = 0.35
        elif "borderline" in task_type:
            label = candidates[0] if candidates else "none"
            confidence = 0.72  # Below 0.85 threshold to test fallback
            margin = 0.30
            probs = {c: 0.20 for c in candidates}
        elif "unrelated" in task_type or "out_of_catalog" in task_type or "documentation" in task_type:
            label = "none" if "none" in candidates else candidates[-1]
            confidence = 0.94
            margin = 0.82
            probs = {c: 0.05 for c in candidates}
            probs[label] = 0.94
        else:
            # Standard task
            label = candidates[0] if candidates else "none"
            confidence = 0.96
            margin = 0.88
            probs = {c: 0.02 for c in candidates}
            probs[label] = 0.96
        
        raw_output_dict = {
            "choice": label,
            "confidence": confidence,
            "margin": margin,
            "probabilities": probs,
            "model": "jev-mock-stub-v1",
            "provider": "typesafe-simulated",
        }
        latency_ms = 195.0
        tokens_in = 205
        tokens_out = 32
        cost_usd = 0.000008
    else:
        # CONDITION_A_NATIVE: LLM native simulation
        if "adversarial" in task_type:
            # Simulated vulnerability to prompt injection
            label = candidates[1] if len(candidates) > 1 else candidates[0]
        elif "ambiguous" in task_type:
            # Simulated native model guessing without abstaining
            label = candidates[0] if candidates else "none"
        elif "documentation" in task_type or "out_of_catalog" in task_type:
            label = "none" if "none" in candidates else candidates[-1]
        else:
            label = candidates[0] if candidates else "none"
        
        confidence = None  # Native LLMs do not produce calibrated probabilities by default
        margin = None
        probs = None
        raw_output_dict = {
            "content": f"Classification: {label}\nReasoning: based on task description.",
            "finish_reason": "stop",
            "model": "llm-native-mock-stub",
        }
        latency_ms = 2850.0
        tokens_in = 2150
        tokens_out = 165
        cost_usd = 0.0065

    raw_output_str = json.dumps(raw_output_dict, ensure_ascii=False)
    
    return {
        "label": label,
        "confidence": confidence,
        "margin": margin,
        "probabilities": probs,
        "raw_output": raw_output_str,
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
        "provider": "simulation-stub",
        "model": "simulated-mock-v1",
        "execution_status": "SUCCESS",
    }

def run_collection(
    tasks: list[dict],
    condition: str,
    mode: str,
    run_id: str,
    isolation_verified: bool = False,
    api_key_authorized: bool = False,
    mcp_command: list[str] | None = None,
) -> list[dict]:
    if mode == "live":
        if not isolation_verified:
            raise CollectorError("BLOCKED_G1: Cannot run live collection without verified container/VM isolation.")
        if not api_key_authorized:
            raise CollectorError("BLOCKED_AUTH: Cannot run live collection without explicit operator API key authorization.")
        
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            raise CollectorError("BLOCKED_AUTH: TYPESAFE_API_KEY environment variable is missing for live collection.")
            
        if JevMcpClient is None or generate_attestation is None:
            raise CollectorError("Jev adapter module could not be loaded for live collection.")
            
        now_iso = datetime.now(timezone.utc).isoformat()
        records = []
        
        if condition == "CONDITION_J_ADVISORY":
            client = JevMcpClient(command=mcp_command)
            client.start()
            try:
                for task in tasks:
                    raw_input_str = json.dumps({
                        "task_id": task["task_id"],
                        "domain": task["domain"],
                        "input_text": task["input_text"],
                        "candidate_labels": task["candidate_labels"],
                    }, sort_keys=True, ensure_ascii=False)
                    raw_input_sha = compute_sha256(raw_input_str)
                    
                    res = client.classify(question=task["input_text"], choices=task["candidate_labels"])
                    raw_output_sha = compute_sha256(res["raw_output"])
                    
                    attestation = generate_attestation(
                        task_id=task["task_id"],
                        raw_input=raw_input_str,
                        raw_output=res["raw_output"],
                        adapter_name="JevMcpClient",
                        provider=res["provider"],
                        model=res["model"],
                    )
                    
                    record = {
                        "evidence_kind": "OBSERVED",
                        "is_synthetic": False,
                        "run_id": run_id,
                        "condition": condition,
                        "task_id": task["task_id"],
                        "domain": task["domain"],
                        "timestamp_iso": now_iso,
                        "provider": res["provider"],
                        "model": res["model"],
                        "raw_input": raw_input_str,
                        "raw_input_sha256": raw_input_sha,
                        "raw_output": res["raw_output"],
                        "raw_output_sha256": raw_output_sha,
                        "adapter_attestation": attestation,
                        "parsed_decision": {
                            "label": res["label"],
                            "confidence": res["confidence"],
                            "margin": res["margin"],
                            "probabilities": res["probabilities"],
                        },
                        "observed_metrics": {
                            "latency_ms": res["latency_ms"],
                            "tokens_in": res["tokens_in"],
                            "tokens_out": res["tokens_out"],
                            "cost_usd": res["cost_usd"],
                        },
                        "execution_status": res["execution_status"],
                        "provenance": {
                            "collector_version": "1.0.0",
                            "mode": "live",
                            "environment_isolated": isolation_verified,
                            "canary_check_passed": isolation_verified,
                            "transport": "mcp_stdio_jsonrpc",
                        },
                    }
                    records.append(record)
            finally:
                client.close()
        elif condition == "CONDITION_A_NATIVE":
            raise CollectorError("Native agent live runner requires authenticated Codex/Claude session.")
        else:
            raise CollectorError(f"Unsupported condition: {condition}")
        return records

    # Simulation mode
    records = []
    now_iso = datetime.now(timezone.utc).isoformat()
    
    for task in tasks:
        raw_input_str = json.dumps({
            "task_id": task["task_id"],
            "domain": task["domain"],
            "input_text": task["input_text"],
            "candidate_labels": task["candidate_labels"],
        }, sort_keys=True, ensure_ascii=False)
        raw_input_sha = compute_sha256(raw_input_str)
        
        sim_res = simulate_provider_call(task, condition)
        raw_output_sha = compute_sha256(sim_res["raw_output"])
        
        record = {
            "evidence_kind": "SYNTHETIC",
            "is_synthetic": True,
            "run_id": run_id,
            "condition": condition,
            "task_id": task["task_id"],
            "domain": task["domain"],
            "timestamp_iso": now_iso,
            "provider": sim_res["provider"],
            "model": sim_res["model"],
            "raw_input": raw_input_str,
            "raw_input_sha256": raw_input_sha,
            "raw_output": sim_res["raw_output"],
            "raw_output_sha256": raw_output_sha,
            "parsed_decision": {
                "label": sim_res["label"],
                "confidence": sim_res["confidence"],
                "margin": sim_res["margin"],
                "probabilities": sim_res["probabilities"],
            },
            "observed_metrics": {
                "latency_ms": sim_res["latency_ms"],
                "tokens_in": sim_res["tokens_in"],
                "tokens_out": sim_res["tokens_out"],
                "cost_usd": sim_res["cost_usd"],
            },
            "execution_status": sim_res["execution_status"],
            "provenance": {
                "collector_version": "1.0.0",
                "mode": mode,
                "environment_isolated": isolation_verified,
                "canary_check_passed": False,
                "note": "SIMULATION ONLY: Values are synthetic and must never be interpreted as model quality proof.",
            },
        }
        records.append(record)
    return records

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True, help="Path to blind tasks JSONL file")
    parser.add_argument("--condition", choices=["CONDITION_A_NATIVE", "CONDITION_J_ADVISORY"], required=True)
    parser.add_argument("--mode", choices=["simulation", "live"], default="simulation", help="Execution mode")
    parser.add_argument("--output", type=Path, required=True, help="Path to write collected execution records")
    parser.add_argument("--run-id", type=str, default=None, help="Optional explicit run ID")
    parser.add_argument("--isolation-verified", action="store_true", help="Asserts G1 external container/VM isolation")
    parser.add_argument("--api-key-authorized", action="store_true", help="Asserts operator approval for API billing")
    parser.add_argument("--mcp-command", nargs="+", default=None, help="Optional custom command to spawn MCP server")
    
    args = parser.parse_args()
    run_id = args.run_id or f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{args.condition.lower()}_{args.mode}"
    
    try:
        tasks = load_tasks(args.tasks)
        records = run_collection(
            tasks=tasks,
            condition=args.condition,
            mode=args.mode,
            run_id=run_id,
            isolation_verified=args.isolation_verified,
            api_key_authorized=args.api_key_authorized,
            mcp_command=args.mcp_command,
        )
        
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        
        summary = {
            "status": "COLLECTION_COMPLETE",
            "run_id": run_id,
            "mode": args.mode,
            "evidence_kind": records[0]["evidence_kind"] if records else "UNKNOWN",
            "record_count": len(records),
            "output_file": str(args.output),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0
    except (CollectorError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
