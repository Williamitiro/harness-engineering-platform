#!/usr/bin/env python3
"""Read-only numeric consistency audit of HE-AG-001 CSV; not execution proof."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


class AuditError(ValueError):
    pass


def audit(path: Path) -> dict:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    required = {"run_id", "task_id", "condition", "input_tokens", "output_tokens",
                "total_tokens", "accepted_tests", "passed_tests",
                "skill_invocation", "skill_execution"}
    if not rows or not required.issubset(rows[0]):
        raise AuditError("CSV missing required fields or rows")
    seen = set()
    by_condition = {}
    anomalies = []
    aggregates = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    for r in rows:
        rid = r["run_id"]
        if not rid or rid in seen:
            anomalies.append(f"duplicate or empty run_id: {rid!r}")
        seen.add(rid)
        try:
            numbers = {k: int(r[k]) for k in ("input_tokens", "output_tokens",
                       "total_tokens", "accepted_tests", "passed_tests")}
        except (ValueError, KeyError) as exc:
            raise AuditError(f"invalid integer in {rid}") from exc
        if any(n < 0 for n in numbers.values()):
            anomalies.append(f"negative metrics: {rid}")
        if numbers["input_tokens"] + numbers["output_tokens"] != numbers["total_tokens"]:
            anomalies.append(f"token row mismatch: {rid}")
        if numbers["passed_tests"] > numbers["accepted_tests"]:
            anomalies.append(f"test count invalid: {rid}")
        cond = r["condition"]
        if cond not in ("A", "B", "C"):
            anomalies.append(f"unknown condition: {rid}")
        slot = by_condition.setdefault(cond, {"runs": 0, "total_tokens": 0,
                                               "input_tokens": 0, "output_tokens": 0,
                                               "skills_invoked": 0, "skills_executed": 0})
        slot["runs"] += 1
        for k in aggregates:
            aggregates[k] += numbers[k]
            slot[k] += numbers[k]
        slot["skills_invoked"] += int(r["skill_invocation"].strip().lower() == "true")
        slot["skills_executed"] += int(r["skill_execution"].strip().lower() == "true")
    if aggregates["input_tokens"] + aggregates["output_tokens"] != aggregates["total_tokens"]:
        anomalies.append("aggregate tokens not additive")
    if by_condition.get("C", {}).get("skills_executed") == 0:
        anomalies.append("C has no observed skill execution; efficacy untested")
    return {
        "classification": "DESCRIPTIVE_UNVERIFIED",
        "run_count": len(rows),
        "aggregates": aggregates,
        "by_condition": by_condition,
        "anomalies": anomalies,
        "limits": [
            "This script checks CSV arithmetic only; it does not attest transcripts, runtime, oracles or hashes",
            "A, B and C were run once per task; no inferential claim is supported",
            "Do not equate reported subscription billing to zero resource usage"
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--expected-input", type=int, default=None,
                        help="optionally compare input sum with a figure from a report")
    args = parser.parse_args()
    try:
        result = audit(args.csv)
        if args.expected_input is not None and args.expected_input != result["aggregates"]["input_tokens"]:
            result["anomalies"].append(
                f"reported aggregate input {args.expected_input} != CSV {result['aggregates']['input_tokens']}"
            )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, AuditError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
