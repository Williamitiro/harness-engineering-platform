#!/usr/bin/env python3
"""Independent evaluator and verifier for empirical Jev and native model runs.

Pure standard library. Evaluates execution records against independent holdout
ground truth (gabarito) without contamination.
Enforces strict evidence hierarchy:
  - SYNTHETIC: marks entire scorecard as SYNTHETIC_SIMULATION_ONLY; refuses model claims.
  - OBSERVED: captures from actual live provider responses with SHA-256 verified.
  - VERIFIED: captured in attested container with G1 isolation checks passed.

Reports separate metrics and Macro-F1 per domain (skills, ci_triage, code_review).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import mean

class EvaluatorError(ValueError):
    pass

def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def number(value: object, label: str, allow_null: bool = False) -> float | None:
    if value is None and allow_null:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluatorError(f"{label} must be numeric")
    v = float(value)
    if not math.isfinite(v):
        raise EvaluatorError(f"{label} must be finite")
    return v

def load_policy(path: Path) -> dict:
    if not path.is_file():
        raise EvaluatorError(f"Policy file not found: {path}")
    doc = json.loads(path.read_text(encoding="utf-8"))
    labels = doc.get("allowed_labels")
    if doc.get("schema_version") != 1 or not isinstance(labels, list) or len(labels) < 2:
        raise EvaluatorError("Unsupported policy schema")
    for key in ("auto_accept_confidence", "minimum_margin"):
        val = number(doc.get(key), key)
        if not 0 <= val <= 1:
            raise EvaluatorError(f"{key} out of range [0, 1]")
    return doc

def load_ground_truth(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise EvaluatorError(f"Ground truth file not found: {path}")
    truths = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluatorError(f"Ground truth line {line_no} invalid JSON") from exc
        task_id = item.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in truths:
            raise EvaluatorError(f"Ground truth line {line_no} missing or duplicate task_id")
        if not item.get("expected_label") or not item.get("domain"):
            raise EvaluatorError(f"Ground truth line {line_no} missing expected_label or domain")
        truths[task_id] = item
    if not truths:
        raise EvaluatorError("Ground truth is empty")
    return truths

def load_and_verify_run(path: Path) -> list[dict]:
    if not path.is_file():
        raise EvaluatorError(f"Run file not found: {path}")
    records = []
    seen_ids = set()
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvaluatorError(f"Run record line {line_no} invalid JSON") from exc
        
        task_id = rec.get("task_id")
        if not isinstance(task_id, str) or not task_id or task_id in seen_ids:
            raise EvaluatorError(f"Run line {line_no} missing or duplicate task_id: {task_id}")
        seen_ids.add(task_id)
        
        # Verify SHA-256 cryptographic hashes of raw input and raw output
        raw_in = rec.get("raw_input", "")
        raw_in_sha = rec.get("raw_input_sha256", "")
        if compute_sha256(raw_in) != raw_in_sha:
            raise EvaluatorError(f"Run line {line_no} raw_input SHA-256 mismatch! Tampering detected.")
        
        raw_out = rec.get("raw_output", "")
        raw_out_sha = rec.get("raw_output_sha256", "")
        if compute_sha256(raw_out) != raw_out_sha:
            raise EvaluatorError(f"Run line {line_no} raw_output SHA-256 mismatch! Tampering detected.")
        
        records.append(rec)
    if not records:
        raise EvaluatorError("Run records file is empty")
    return records

def calculate_macro_f1(confusion: dict[str, dict[str, int]], labels: list[str]) -> float:
    f1_scores = []
    for c in labels:
        tp = confusion.get(c, {}).get(c, 0)
        fp = sum(confusion.get(other, {}).get(c, 0) for other in labels if other != c)
        fn = sum(confusion.get(c, {}).get(other, 0) for other in labels if other != c)
        
        # Only evaluate classes that appear in ground truth or predictions
        if (tp + fn) == 0 and (tp + fp) == 0:
            continue
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        f1_scores.append(f1)
    
    return mean(f1_scores) if f1_scores else 0.0

def evaluate_domain(records: list[dict], ground_truths: dict[str, dict], policy: dict) -> dict:
    allowed_labels = policy["allowed_labels"]
    matrix = {x: {y: 0 for y in allowed_labels} for x in allowed_labels}
    
    correct_total = 0
    accepted = 0
    correct_auto = 0
    wrong_high_confidence = []
    latencies = []
    tokens_in_list = []
    tokens_out_list = []
    costs_list = []
    
    for rec in records:
        task_id = rec["task_id"]
        gt = ground_truths.get(task_id)
        if not gt:
            raise EvaluatorError(f"Task {task_id} not found in holdout ground truth!")
        
        expected = gt["expected_label"]
        decision = rec.get("parsed_decision", {})
        predicted = decision.get("label")
        
        if expected not in allowed_labels or predicted not in allowed_labels:
            raise EvaluatorError(f"Label '{expected}' or '{predicted}' outside policy allowlist")
        
        matrix[expected][predicted] += 1
        is_correct = (expected == predicted)
        correct_total += int(is_correct)
        
        confidence = decision.get("confidence")
        margin = decision.get("margin")
        
        # Policy gate: abstain if label is 'uncertain', or confidence < threshold, or margin < threshold
        automatic = (
            predicted != "uncertain"
            and confidence is not None
            and margin is not None
            and confidence >= policy["auto_accept_confidence"]
            and margin >= policy["minimum_margin"]
        )
        
        if automatic:
            accepted += 1
            correct_auto += int(is_correct)
            if not is_correct:
                wrong_high_confidence.append(task_id)
        
        metrics = rec.get("observed_metrics", {})
        if metrics.get("latency_ms") is not None:
            latencies.append(float(metrics["latency_ms"]))
        if metrics.get("tokens_in") is not None:
            tokens_in_list.append(int(metrics["tokens_in"]))
        if metrics.get("tokens_out") is not None:
            tokens_out_list.append(int(metrics["tokens_out"]))
        if metrics.get("cost_usd") is not None:
            costs_list.append(float(metrics["cost_usd"]))
    
    n = len(records)
    macro_f1 = calculate_macro_f1(matrix, allowed_labels)
    
    return {
        "count": n,
        "micro_accuracy": correct_total / n,
        "macro_f1": macro_f1,
        "automatic_coverage": accepted / n,
        "automatic_accuracy": (correct_auto / accepted if accepted else None),
        "accepted_count": accepted,
        "review_or_abstention_count": n - accepted,
        "wrong_high_confidence_ids": wrong_high_confidence,
        "mean_latency_ms": (mean(latencies) if latencies else None),
        "mean_tokens_in": (mean(tokens_in_list) if tokens_in_list else None),
        "mean_tokens_out": (mean(tokens_out_list) if tokens_out_list else None),
        "total_cost_usd": (sum(costs_list) if costs_list else None),
        "confusion_matrix": matrix,
    }

def evaluate_run(records: list[dict], ground_truths: dict[str, dict], policy: dict) -> dict:
    # Determine evidence level strictly
    is_any_synthetic = any(r.get("evidence_kind") == "SYNTHETIC" or r.get("is_synthetic") for r in records)
    is_all_verified = all(r.get("evidence_kind") == "VERIFIED" for r in records)
    
    if is_any_synthetic:
        evidence_level = "SYNTHETIC_SIMULATION_ONLY"
        model_quality_proven = False
        recommendation = "NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION"
        status = "SYNTHETIC_FIXTURE_ARITHMETIC_ONLY"
    elif is_all_verified:
        evidence_level = "VERIFIED_ISOLATED_BENCHMARK"
        model_quality_proven = True
        recommendation = "VALIDATED_EMPIRICAL_DATA"
        status = "COMPLETED_VERIFIED"
    else:
        evidence_level = "OBSERVED_REAL_EXECUTION"
        model_quality_proven = True
        recommendation = "OBSERVED_DATA_PENDING_G1_VERIFICATION"
        status = "COMPLETED_OBSERVED"
    
    # Split records by domain to evaluate each domain independently
    by_domain: dict[str, list[dict]] = {}
    for r in records:
        dom = r.get("domain", "default")
        by_domain.setdefault(dom, []).append(r)
    
    domain_results = {}
    for dom, dom_records in by_domain.items():
        domain_results[dom] = evaluate_domain(dom_records, ground_truths, policy)
    
    overall = evaluate_domain(records, ground_truths, policy)
    
    return {
        "status": status,
        "evidence_level": evidence_level,
        "model_quality_proven": model_quality_proven,
        "recommendation": recommendation,
        "provenance": {
            "source_kind": "SIMULATION_MOCK" if is_any_synthetic else "REAL_EXECUTION",
            "codex_or_native_called": not is_any_synthetic,
            "jev_model_called": not is_any_synthetic,
            "runtime_metrics_observed": not is_any_synthetic,
            "sample_size": len(records),
        },
        "overall": overall,
        "by_domain": domain_results,
        "limits": [
            "Synthetic simulation runs prove pipeline logic and policy thresholds only; they do not attest model quality.",
            "Live adoption requires Gate G1 external isolation and authorized API billing.",
        ],
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True, help="Path to run records JSONL")
    parser.add_argument("--ground-truth", type=Path, required=True, help="Path to holdout ground truth JSONL")
    parser.add_argument("--policy", type=Path, required=True, help="Path to policy JSON")
    parser.add_argument("--compare-run", type=Path, default=None, help="Optional second run file to compare")
    
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        ground_truths = load_ground_truth(args.ground_truth)
        records_main = load_and_verify_run(args.run)
        
        res_main = evaluate_run(records_main, ground_truths, policy)
        
        if args.compare_run:
            records_compare = load_and_verify_run(args.compare_run)
            res_compare = evaluate_run(records_compare, ground_truths, policy)
            
            # Form comparison report
            is_synthetic = (
                res_main["evidence_level"] == "SYNTHETIC_SIMULATION_ONLY"
                or res_compare["evidence_level"] == "SYNTHETIC_SIMULATION_ONLY"
            )
            comparison_report = {
                "status": "SYNTHETIC_FIXTURE_ARITHMETIC_ONLY" if is_synthetic else "COMPARATIVE_EMPIRICAL_BENCHMARK",
                "evidence_level": "SYNTHETIC_SIMULATION_ONLY" if is_synthetic else "OBSERVED_COMPARATIVE_EXECUTION",
                "recommendation": "NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION" if is_synthetic else "REVIEW_EMPIRICAL_DIFFERENCES",
                "condition_main": {
                    "condition": records_main[0].get("condition", "UNKNOWN"),
                    "micro_accuracy": res_main["overall"]["micro_accuracy"],
                    "accepted_count": res_main["overall"]["accepted_count"],
                    "automatic_accuracy": res_main["overall"]["automatic_accuracy"],
                    "review_abstentions": res_main["overall"]["review_or_abstention_count"],
                    "mean_latency_ms": res_main["overall"]["mean_latency_ms"],
                    "mean_tokens_in": res_main["overall"]["mean_tokens_in"],
                    "mean_tokens_out": res_main["overall"]["mean_tokens_out"],
                },
                "condition_comparison": {
                    "condition": records_compare[0].get("condition", "UNKNOWN"),
                    "micro_accuracy": res_compare["overall"]["micro_accuracy"],
                    "accepted_count": res_compare["overall"]["accepted_count"],
                    "automatic_accuracy": res_compare["overall"]["automatic_accuracy"],
                    "review_abstentions": res_compare["overall"]["review_or_abstention_count"],
                    "mean_latency_ms": res_compare["overall"]["mean_latency_ms"],
                    "mean_tokens_in": res_compare["overall"]["mean_tokens_in"],
                    "mean_tokens_out": res_compare["overall"]["mean_tokens_out"],
                },
                "detailed_eval_main": res_main,
                "detailed_eval_comparison": res_compare,
            }
            print(json.dumps(comparison_report, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(res_main, indent=2, ensure_ascii=False))
        
        return 0
    except (EvaluatorError, OSError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)}, ensure_ascii=False))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
