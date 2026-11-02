#!/usr/bin/env python3
"""Offline scorecard for pre-labelled Jev routing decisions.

Pure standard library. No model/API/network invocation, no secrets or writes.
Scores observations; confidence gating is advisory, never authorization.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean

class ValidationError(ValueError):
    pass

def number(value: object, label: str, allow_null: bool = False) -> float | None:
    if value is None and allow_null:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be numeric")
    v = float(value)
    if not math.isfinite(v):
        raise ValidationError(f"{label} must be finite")
    return v

def load_policy(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    labels = doc.get("allowed_labels")
    if doc.get("schema_version") != 1 or not isinstance(labels, list) or len(labels) < 2:
        raise ValidationError("unsupported policy")
    if not all(isinstance(x, str) and x and x.strip() == x for x in labels) or len(set(labels)) != len(labels):
        raise ValidationError("invalid/duplicate labels")
    for key in ("auto_accept_confidence", "minimum_margin"):
        value = number(doc.get(key), key)
        if not 0 <= value <= 1:
            raise ValidationError(f"{key} out of [0,1]")
    return doc

def load_rows(path: Path, labels: set[str]) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(f"line {line_number} invalid JSON") from exc
        if not isinstance(row, dict):
            raise ValidationError(f"line {line_number} must be object")
        item = row.get("id")
        if not isinstance(item, str) or not item or item in seen:
            raise ValidationError(f"line {line_number} duplicate/empty id")
        seen.add(item)
        if row.get("expected") not in labels or row.get("predicted") not in labels:
            raise ValidationError(f"line {line_number} label outside allowlist")
        for field in ("confidence", "margin"):
            v = number(row.get(field), field, allow_null=True)
            if v is not None and not 0 <= v <= 1:
                raise ValidationError(f"line {line_number} {field} out of [0,1]")
        latency = number(row.get("latency_ms"), "latency_ms", allow_null=True)
        if latency is not None and latency < 0:
            raise ValidationError(f"line {line_number} negative latency")
        rows.append(row)
    if not rows:
        raise ValidationError("empty decision set")
    return rows

def evaluate(rows: list[dict], policy: dict) -> dict:
    labels = policy["allowed_labels"]
    matrix = {x: {y: 0 for y in labels} for x in labels}
    accepted, errors = 0, 0
    correct_total, correct_auto = 0, 0
    latencies = []
    wrong_high_confidence = []
    for row in rows:
        truth, predicted = row["expected"], row["predicted"]
        matrix[truth][predicted] += 1
        correct_total += int(truth == predicted)
        confidence, margin = row.get("confidence"), row.get("margin")
        automatic = (predicted != "uncertain"
                     and confidence is not None and margin is not None
                     and confidence >= policy["auto_accept_confidence"]
                     and margin >= policy["minimum_margin"])
        if automatic:
            accepted += 1
            correct_auto += int(truth == predicted)
            if truth != predicted:
                wrong_high_confidence.append(row["id"])
        if row.get("latency_ms") is not None:
            latencies.append(float(row["latency_ms"]))
        errors += int(confidence is None or margin is None)
    n = len(rows)
    return {
        "status": "OFFLINE_SCORE_ONLY_NOT_MODEL_PROOF",
        "policy_status": policy.get("status", "UNKNOWN"),
        "count": n,
        "total_accuracy": correct_total / n,
        "automatic_coverage": accepted / n,
        "automatic_accuracy": (correct_auto / accepted if accepted else None),
        "accepted": accepted,
        "review_or_missing": n - accepted,
        "missing_probability_fields": errors,
        "wrong_high_confidence_ids": wrong_high_confidence,
        "mean_latency_ms_known_only": (mean(latencies) if latencies else None),
        "latency_samples": len(latencies),
        "confusion_expected_by_predicted": matrix,
        "limits": ["Synthetic fixture is NOT a Jev API result",
                   "No billing, agent quality or external safety proven",
                   "Confidence thresholds here do not authorize tool calls"],
    }

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    args = p.parse_args()
    try:
        policy = load_policy(args.policy)
        rows = load_rows(args.input, set(policy["allowed_labels"]))
        print(json.dumps(evaluate(rows, policy), indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status":"BLOCKED", "reason":str(exc)}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
