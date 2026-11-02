import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jev_offline_eval", ROOT / "scripts" / "jev_offline_eval.py")
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)

POLICY = {
    "schema_version": 1, "status": "PROPOSED_NOT_APPROVED",
    "allowed_labels": ["a", "b", "none"],
    "auto_accept_confidence": 0.85, "minimum_margin": 0.5,
}

class JevOfflineTests(unittest.TestCase):
    def test_synthetic_fixture_is_not_claimed_as_jev(self):
        result = jev.evaluate([
            {"id":"x","expected":"a","predicted":"a","confidence":0.91,"margin":0.7,"latency_ms":10},
            {"id":"y","expected":"b","predicted":"a","confidence":0.5,"margin":0.2,"latency_ms":20},
        ], POLICY)
        self.assertEqual(result["status"], "OFFLINE_SCORE_ONLY_NOT_MODEL_PROOF")
        self.assertEqual(result["accepted"], 1)
        self.assertEqual(result["review_or_missing"], 1)
        self.assertEqual(result["total_accuracy"], 0.5)

    def test_high_confidence_error_is_reported(self):
        r = jev.evaluate([{"id":"wrong","expected":"b","predicted":"a",
                           "confidence":0.99,"margin":0.9,"latency_ms":10}], POLICY)
        self.assertEqual(r["wrong_high_confidence_ids"], ["wrong"])

    def test_uncertain_never_autorouted_even_if_confident(self):
        policy = {**POLICY, "allowed_labels": ["a", "b", "none", "uncertain"]}
        result = jev.evaluate([{"id":"u","expected":"uncertain","predicted":"uncertain",
                                "confidence":1.0,"margin":1.0,"latency_ms":1}], policy)
        self.assertEqual(result["accepted"], 0)
        self.assertEqual(result["review_or_missing"], 1)

    def test_invalid_and_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"cases.jsonl"
            path.write_text('{"id":"a","expected":"a","predicted":"a","confidence":0.9,"margin":0.9}\n'
                            '{"id":"a","expected":"b","predicted":"a","confidence":0.9,"margin":0.9}\n')
            with self.assertRaises(jev.ValidationError):
                jev.load_rows(path, set(POLICY["allowed_labels"]))

    def test_bad_confidence_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"cases.jsonl"
            path.write_text(json.dumps({"id":"a","expected":"a","predicted":"b",
                                         "confidence":1.5,"margin":0.9}))
            with self.assertRaises(jev.ValidationError):
                jev.load_rows(path, set(POLICY["allowed_labels"]))

    def test_missing_probability_requires_review(self):
        r = jev.evaluate([{"id":"p","expected":"none","predicted":"none",
                           "confidence":None,"margin":None,"latency_ms":None}], POLICY)
        self.assertEqual(r["accepted"], 0)
        self.assertIsNone(r["automatic_accuracy"])
        self.assertEqual(r["missing_probability_fields"], 1)

    def test_comparative_evaluation(self):
        rows = [
            {"id":"1","expected":"a","predicted":"a","confidence":0.95,"margin":0.8,
             "latency_ms":180,"tokens_in":200,"tokens_out":30,
             "native_predicted":"a","native_latency_ms":2500,"native_tokens_in":2000,"native_tokens_out":150},
            {"id":"2","expected":"b","predicted":"b","confidence":0.90,"margin":0.7,
             "latency_ms":190,"tokens_in":210,"tokens_out":35,
             "native_predicted":"none","native_latency_ms":2800,"native_tokens_in":2200,"native_tokens_out":180},
        ]
        comp = jev.evaluate_comparison(rows, POLICY)
        self.assertEqual(comp["status"], "SYNTHETIC_FIXTURE_ARITHMETIC_ONLY")
        self.assertFalse(comp["provenance"]["jev_model_called"])
        self.assertFalse(comp["provenance"]["runtime_metrics_observed"])
        self.assertEqual(comp["sample_size"], 2)
        self.assertEqual(comp["condition_a_native"]["accuracy"], 0.5)
        self.assertEqual(comp["condition_a_native"]["error_count"], 1)
        self.assertEqual(comp["condition_j_advisory"]["total_accuracy"], 1.0)
        self.assertEqual(comp["condition_j_advisory"]["accepted_count"], 2)
        self.assertEqual(comp["recommendation"], "NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION")

    def test_comparative_requires_native_predicted(self):
        rows = [{"id":"1","expected":"a","predicted":"a","confidence":0.95,"margin":0.8}]
        with self.assertRaises(jev.ValidationError):
            jev.evaluate_comparison(rows, POLICY)

    def test_native_predicted_outside_allowlist_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"cases.jsonl"
            path.write_text(json.dumps({"id":"1","expected":"a","predicted":"a",
                                         "native_predicted":"invalid_label"}))
            with self.assertRaises(jev.ValidationError):
                jev.load_rows(path, set(POLICY["allowed_labels"]))

    def test_nonfinite_and_negative_native_metrics_rejected(self):
        bad_cases = [
            {"native_latency_ms": float("inf")},
            {"native_tokens_in": -1},
            {"tokens_out": True},
            {"tokens_in": "200"},
        ]
        with tempfile.TemporaryDirectory() as d:
            for i, fields in enumerate(bad_cases):
                path = Path(d)/f"bad_{i}.jsonl"
                row = {"id": str(i), "expected": "a", "predicted": "a", **fields}
                path.write_text(json.dumps(row))
                with self.assertRaises(jev.ValidationError):
                    jev.load_rows(path, set(POLICY["allowed_labels"]))

    def test_comparison_never_claims_real_model_accuracy(self):
        row = {"id":"sim","expected":"a","predicted":"a","native_predicted":"a",
               "confidence":1.0,"margin":1.0,"latency_ms":1.0,
               "native_latency_ms":2000,"native_tokens_in":1000,"tokens_in":1}
        r = jev.evaluate_comparison([row], POLICY)
        self.assertEqual(r["provenance"]["source_kind"], "HAND_AUTHORED_FIXTURE")
        self.assertFalse(r["provenance"]["empirical_effect_or_savings_estimated"])
        self.assertEqual(r["recommendation"], "NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION")

    def test_all_pilot_fixture_files_valid(self):
        configs_and_fixtures = [
            ("config/jev_pilot_policy.json", "benchmarks/jev/fixtures_skills.jsonl"),
            ("config/jev_ci_triage_policy.json", "benchmarks/jev/fixtures_ci_triage.jsonl"),
            ("config/jev_review_priority_policy.json", "benchmarks/jev/fixtures_code_review.jsonl"),
            ("config/jev_multi_domain_policy.json", "benchmarks/jev/fixtures_pilot.jsonl"),
        ]
        for cfg_rel, fix_rel in configs_and_fixtures:
            policy = jev.load_policy(ROOT / cfg_rel)
            rows = jev.load_rows(ROOT / fix_rel, set(policy["allowed_labels"]))
            self.assertGreaterEqual(len(rows), 10)
            res = jev.evaluate(rows, policy)
            self.assertEqual(res["status"], "OFFLINE_SCORE_ONLY_NOT_MODEL_PROOF")

if __name__ == "__main__":
    unittest.main()
