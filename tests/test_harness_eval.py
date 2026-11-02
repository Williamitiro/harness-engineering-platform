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
        (ROOT / ".poc").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".poc")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "eval-test"
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
        def cmd(command, output="", rc=0):
            return {"type": "item.completed", "item": {"type": "command_execution",
                    "command": command, "aggregated_output": output,
                    "status": "completed", "exit_code": rc}}
        events = [
            cmd("Get-Content .agents/skills/tdd-workflow/SKILL.md",
                "---\\nname: tdd-workflow\\n---"),
            cmd("Get-Content .agents/skills/verification-loop/SKILL.md",
                "---\\nname: verification-loop\\n---"),
            cmd("python -m pytest -q", "1 failed", 1),
            cmd("python -m pytest -q", "1 passed", 0),
            cmd("python -m mypy --strict ratelimit.py"),
            cmd("python -m ruff check ratelimit.py"),
            cmd("python -m coverage report --fail-under=80"),
        ]
        res = eval_mod.analyze_trajectory(events, "codex")
        self.assertTrue(res["discovered"])
        self.assertTrue(res["invoked"])
        self.assertTrue(res["procedure_executed"])
        self.assertEqual(res["commands_count"], 7)

    def test_trajectory_does_not_accept_names_or_generic_tests(self):
        events = [
            {"type": "item.completed", "item": {"type": "agent_message",
             "text": "I used tdd-workflow and verification-loop fully"}},
            {"type": "item.completed", "item": {"type": "command_execution",
             "command": "python -m pytest", "aggregated_output": "OK",
             "status": "completed", "exit_code": 0}},
            {"type": "item.completed", "item": {"type": "command_execution",
             "command": "Get-Content .agents/skills/tdd-workflow/SKILL.md",
             "aggregated_output": "name: tdd-workflow",
             "status": "completed", "exit_code": 1}},
        ]
        result = eval_mod.analyze_trajectory(events, "codex")
        self.assertFalse(result["invoked"])
        self.assertFalse(result["procedure_executed"])

    def test_disposable_target_refuses_external_and_nonempty(self):
        with self.assertRaises(eval_mod.EvalError):
            eval_mod.assert_eval_target(self.root.parent.parent / "outside")
        (self.target / "sentinel.txt").write_text("preserve")
        with self.assertRaises(eval_mod.EvalError):
            eval_mod.assert_eval_target(self.target)
        self.assertEqual((self.target / "sentinel.txt").read_text(), "preserve")

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
        self.assertFalse(res["isolation_verified"])
        self.assertEqual(res["acceptance"]["status"], "PASS")

    def test_execute_eval_blocked_when_unauthenticated(self):
        manifest = {
            "schema_version": 1,
            "ecc": {"commit": "a" * 40, "skills": {"tdd-workflow": "0" * 64, "verification-loop": "1" * 64}}
        }
        with patch.object(eval_mod, "find_claude_binary", return_value="/mock/bin/claude"), \
             patch.object(eval_mod, "check_client_auth", return_value=(False, "Not logged in")):
            res = eval_mod.execute_eval(
                client="claude",
                task_dir=self.task_dir,
                condition="A",
                source=None,
                target=self.target,
                manifest=manifest,
                dry_run=False,
                live_authorized=True,
            )
            self.assertEqual(res["verdict"], "BLOCKED")
            self.assertEqual(res["reason"], "Not logged in")


if __name__ == "__main__":
    unittest.main()
