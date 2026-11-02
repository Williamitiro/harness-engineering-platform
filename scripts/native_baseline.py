#!/usr/bin/env python3
"""Native LLM baseline adapter for Condition A (Codex/Claude/Gemini routing).

Provides a clean, standardized classification interface for native LLM models
using the exact same blind task inputs as Condition J (Jev advisory), but:
- Formats input as a standard structured classification prompt.
- Extracts decision and reasoning.
- Does NOT manufacture artificial calibrated probabilities (confidence/margin are None).
- Tracks observed latency_ms and provider usage tokens (tokens_in, tokens_out).
- Keeps cost_usd as None when unknown (never estimated or invented).
- In simulation mode: returns deterministic synthetic baseline response.
- In live mode: blocked fail-closed until G1 isolation and authorized provider receipts.
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


def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_native_prompt(task: dict[str, Any]) -> str:
    """Builds standard zero-shot classification prompt for native LLM baseline."""
    domain = task.get("domain", "general")
    input_text = task.get("input_text", "")
    candidates = task.get("candidate_labels", [])
    candidates_formatted = ", ".join([f'"{c}"' for c in candidates])

    prompt = (
        f"You are a software engineering decision and routing classifier for domain '{domain}'.\n"
        f"Analyze the following request and classify it into exactly ONE of the allowed categories.\n\n"
        f"Allowed categories: [{candidates_formatted}]\n\n"
        f"Input request:\n\"\"\"\n{input_text}\n\"\"\"\n\n"
        f"Rules:\n"
        f"1. Choose exactly one label from the allowed categories.\n"
        f"2. If none of the categories apply or you cannot confidently decide, select 'none' or 'uncertain'.\n"
        f"3. Return ONLY a valid JSON object with keys 'label' (string) and 'reasoning' (string)."
    )
    return prompt


class NativeBaselineAdapter:
    """Adapter for executing and scoring Native LLM Baseline (Condition A)."""

    def __init__(
        self,
        provider: str = "native-llm",
        model_name: str = "claude-3-5-sonnet",
        mode: str = "simulation",
    ) -> None:
        self.provider = provider
        self.model_name = model_name
        self.mode = mode

    def classify_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task.get("task_id", "unknown")
        domain = task.get("domain", "general")
        input_text = task.get("input_text", "")
        candidates = task.get("candidate_labels", [])
        task_type = task.get("task_type", "standard")

        prompt = build_native_prompt(task)
        raw_input_str = json.dumps({
            "task_id": task_id,
            "domain": domain,
            "input_text": input_text,
            "candidate_labels": candidates,
            "prompt": prompt,
        }, sort_keys=True, ensure_ascii=False)

        if self.mode == "live":
            # Live execution is blocked until external G1 verification
            raise RuntimeError(
                "BLOCKED_G1: Native live execution requires verified isolation container and API authorization"
            )

        # Simulation mode: deterministic baseline behavior
        start_time = time.perf_counter()
        if "adversarial" in task_type:
            # Native model susceptible to instruction override in prompt
            label = candidates[1] if len(candidates) > 1 else candidates[0]
            reasoning = "Simulated native model distracted by adversarial instruction."
        elif "ambiguous" in task_type:
            # Native model forces a classification rather than abstaining
            label = candidates[0] if candidates else "none"
            reasoning = "Simulated native model selecting most likely category without abstaining."
        elif "out_of_catalog" in task_type or "unrelated" in task_type:
            label = "none" if "none" in candidates else candidates[-1]
            reasoning = "Item out of catalog."
        else:
            label = candidates[0] if candidates else "none"
            reasoning = "Standard category match."

        elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        # Baseline simulation tokens: typical LLM conversational context
        tokens_in = 450 + len(input_text) // 3
        tokens_out = 65

        raw_output_obj = {
            "label": label,
            "reasoning": reasoning,
            "finish_reason": "stop",
            "model": self.model_name,
            "provider": self.provider,
            "usage": {
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
            },
        }
        raw_output_str = json.dumps(raw_output_obj, ensure_ascii=False)

        return {
            "evidence_kind": "SYNTHETIC",
            "is_synthetic": True,
            "condition": "CONDITION_A_NATIVE",
            "task_id": task_id,
            "domain": domain,
            "provider": self.provider,
            "model": self.model_name,
            "raw_input": raw_input_str,
            "raw_input_sha256": compute_sha256(raw_input_str),
            "raw_output": raw_output_str,
            "raw_output_sha256": compute_sha256(raw_output_str),
            "parsed_decision": {
                "label": label,
                "confidence": None,  # Native models do not produce calibrated probabilities
                "margin": None,
                "probabilities": None,
                "reasoning": reasoning,
            },
            "observed_metrics": {
                "latency_ms": elapsed_ms,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": None,  # Unmeasured cost remains null
            },
            "execution_status": "SUCCESS",
            "provenance": {
                "adapter": "NativeBaselineAdapter",
                "version": "1.0.0",
                "mode": self.mode,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-file", type=Path, required=True, help="Path to blind task JSONL")
    parser.add_argument("--mode", choices=["simulation", "live"], default="simulation")
    parser.add_argument("--output", type=Path, required=True, help="Path to write baseline records")
    args = parser.parse_args()

    adapter = NativeBaselineAdapter(mode=args.mode)
    records = []
    for line in args.task_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        task = json.loads(line)
        records.append(adapter.classify_task(task))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Native baseline executed {len(records)} tasks (mode: {args.mode}) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
