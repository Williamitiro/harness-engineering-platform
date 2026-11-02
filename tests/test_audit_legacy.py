import csv
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("audit_legacy", ROOT / "scripts" / "audit_legacy.py")
audit_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_mod)


class LegacyAuditTests(unittest.TestCase):
    def test_aggregation_and_non_invocation(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "result.csv"
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "run_id", "task_id", "condition", "input_tokens",
                    "output_tokens", "total_tokens", "accepted_tests",
                    "passed_tests", "skill_invocation", "skill_execution"])
                writer.writeheader()
                for cond, n in (("A", 10), ("B", 20), ("C", 30)):
                    writer.writerow(dict(run_id=cond, task_id="T1", condition=cond,
                        input_tokens=n, output_tokens=2, total_tokens=n + 2,
                        accepted_tests=2, passed_tests=2,
                        skill_invocation="FALSE", skill_execution="FALSE"))
            result = audit_mod.audit(path)
            self.assertEqual(result["aggregates"]["input_tokens"], 60)
            self.assertEqual(result["aggregates"]["total_tokens"], 66)
            self.assertIn("efficacy untested", result["anomalies"][-1])

    def test_duplicate_detected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.csv"
            p.write_text(
                "run_id,task_id,condition,input_tokens,output_tokens,total_tokens,accepted_tests,passed_tests,skill_invocation,skill_execution\n"
                "x,T1,A,10,1,11,1,1,FALSE,FALSE\n"
                "x,T2,B,10,1,11,1,1,FALSE,FALSE\n")
            self.assertTrue(any("duplicate" in a for a in audit_mod.audit(p)["anomalies"]))


if __name__ == "__main__":
    unittest.main()
