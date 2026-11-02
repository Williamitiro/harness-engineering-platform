import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harness_eval", ROOT / "scripts" / "harness_eval.py")
eval_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_mod)

spec_h = importlib.util.spec_from_file_location("harnessctl", ROOT / "scripts" / "harnessctl.py")
h = importlib.util.module_from_spec(spec_h)
spec_h.loader.exec_module(h)


class HarnessEvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / ".poc" / "eval-test"
        self.target.mkdir(parents=True)
        self.task_dir = self.root / "task"
        self.task_dir.mkdir()
        (self.task_dir / "specification.md").write_text("# Spec\nImplement addition.")
        oracle_code = (
            "import unittest\n"
            "class DummyTest(unittest.TestCase):\n"
            "    def test_pass(self):\n"
            "        self.assertTrue(True)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        (self.task_dir / "oracle.py").write_text(oracle_code)

    def test_run_oracle_success_and_failure(self):
        res = eval_mod.run_oracle(self.task_dir / "oracle.py", self.target)
        self.assertEqual(res["status"], "PASS")
        self.assertEqual(res["tests_passed"], 1)
        self.assertEqual(res["tests_total"], 1)

        failing_oracle = self.task_dir / "oracle_fail.py"
        failing_oracle.write_text(
            "import unittest\n"
            "class FailTest(unittest.TestCase):\n"
            "    def test_fail(self):\n"
            "        self.assertEqual(1, 2)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        fail_res = eval_mod.run_oracle(failing_oracle, self.target)
        self.assertEqual(fail_res["status"], "FAIL")
        self.assertEqual(fail_res["tests_passed"], 0)

    def test_analyze_trajectory_levels(self):
        events = [
            {"type": "item.completed", "item": {"type": "agent_message", "text": "I will check .agents/skills"}},
            {"type": "item.completed", "item": {"type": "command_execution",
             "command": "Get-Content .agents/skills/tdd-workflow/SKILL.md", "aggregated_output": "tdd content"}},
            {"type": "item.completed", "item": {"type": "command_execution",
             "command": "python -m unittest test_feature.py", "aggregated_output": "Ran 1 test in 0.01s: OK"}},
        ]
        res = eval_mod.analyze_trajectory(events, "codex")
        self.assertTrue(res["discovered"])
        self.assertTrue(res["invoked"])
        self.assertTrue(res["procedure_executed"])
        self.assertEqual(res["commands_count"], 2)

    def test_execute_eval_dry_run(self):
        manifest = {
            "schema_version": 1,
            "ecc": {"commit": "a" * 40, "skills": {"tdd-workflow": "0" * 64, "verification-loop": "1" * 64}}
        }
        res = eval_mod.execute_eval(
            client="codex",
            task_dir=self.task_dir,
            condition="A",
            source=None,
            target=self.target,
            manifest=manifest,
            dry_run=True,
        )
        self.assertEqual(res["verdict"], "PREPARED")
        self.assertTrue(res["isolation_verified"])
        self.assertEqual(res["acceptance"]["status"], "PASS")

    def test_execute_eval_blocked_when_unauthenticated(self):
        manifest = {
            "schema_version": 1,
            "ecc": {"commit": "a" * 40, "skills": {"tdd-workflow": "0" * 64, "verification-loop": "1" * 64}}
        }
        with patch.object(eval_mod, "check_client_auth", return_value=(False, "Not logged in")):
            res = eval_mod.execute_eval(
                client="claude",
                task_dir=self.task_dir,
                condition="A",
                source=None,
                target=self.target,
                manifest=manifest,
                dry_run=False,
            )
            self.assertEqual(res["verdict"], "BLOCKED")
            self.assertEqual(res["reason"], "Not logged in")


if __name__ == "__main__":
    unittest.main()
