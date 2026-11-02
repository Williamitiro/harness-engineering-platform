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

if __name__ == "__main__":
    unittest.main()
