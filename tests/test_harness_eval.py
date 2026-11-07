import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
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
            # HE-R2-01: não medido é null, nunca 0; versão nunca é o caminho do binário
            self.assertIsNone(res["acceptance"]["tests_passed"])
            self.assertIsNone(res["acceptance"]["tests_total"])
            self.assertIsNone(res["metrics"]["duration_seconds"])
            self.assertNotEqual(res["client_version"], "/mock/bin/claude")

    def test_not_authorized_live_has_null_duration(self):
        manifest = {"schema_version": 1, "ecc": {"commit": "a" * 40, "skills": {}}}
        res = eval_mod.execute_eval(client="codex", task_dir=self.task_dir, condition="A", source=None,
                                    target=self.target, manifest=manifest)
        self.assertEqual(res["verdict"], "BLOCKED")
        self.assertIsNone(res["metrics"]["duration_seconds"])


def claude_stream(*events):
    return "\n".join(json.dumps(e) for e in events) + "\n"


def c_use(tid, name, **inp):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": tid, "name": name,
                                                          "input": inp}]}}


def c_res(tid, text, err=False):
    return {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": tid,
                                                     "content": text, "is_error": err}]}}


CLAUDE_INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "claude_code_version": "2.1.319",
               "apiKeySource": "none", "session_id": "s"}
CLAUDE_RESULT = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 3, "total_cost_usd": 0.5,
                 "usage": {"input_tokens": 10, "cache_read_input_tokens": 90, "cache_creation_input_tokens": 0,
                           "output_tokens": 7}}


class ClaudeTrajectoryTests(unittest.TestCase):
    def test_skill_tool_and_red_green_reach_procedure(self):
        events = [CLAUDE_INIT,
                  c_use("1", "Skill", skill="tdd-workflow"), c_res("1", "Launching skill: tdd-workflow"),
                  c_use("2", "Read", file_path="/h/.claude/skills/verification-loop/SKILL.md"),
                  c_res("2", "---\nname: verification-loop\n---"),
                  c_use("3", "Bash", command="python -m pytest -q"), c_res("3", "1 failed", True),
                  c_use("4", "Bash", command="python -m pytest -q"), c_res("4", "1 passed"),
                  c_use("5", "Bash", command="python -m mypy --strict x.py"), c_res("5", "ok"),
                  c_use("6", "Bash", command="python -m ruff check x.py"), c_res("6", "ok"),
                  c_use("7", "Bash", command="python -m coverage report"), c_res("7", "90%"),
                  CLAUDE_RESULT]
        res = eval_mod.analyze_trajectory(events, "claude")
        self.assertTrue(res["invoked"])
        self.assertTrue(res["red_green_observed"])
        self.assertTrue(res["procedure_executed"])
        self.assertEqual(res["commands_count"], 5)

    def test_claude_mentions_and_failed_reads_do_not_count(self):
        events = [CLAUDE_INIT,
                  {"type": "assistant", "message": {"content": [
                      {"type": "text", "text": "usei tdd-workflow e verification-loop"}]}},
                  c_use("1", "Read", file_path="/h/.claude/skills/tdd-workflow/SKILL.md"),
                  c_res("1", "name: tdd-workflow", True),
                  c_use("2", "Bash", command="python -m pytest")]  # sem resultado: não conta
        res = eval_mod.analyze_trajectory(events, "claude")
        self.assertFalse(res["discovered"])
        self.assertFalse(res["red_green_observed"])


class LiveTelemetryTests(unittest.TestCase):
    """Execução 'live' com subprocess simulado: nenhum modelo é chamado."""

    def setUp(self):
        (ROOT / ".poc").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".poc")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.target = root / "eval-live"
        self.task_dir = root / "task"
        self.task_dir.mkdir()
        (self.task_dir / "specification.md").write_text("# Spec")
        (self.task_dir / "oracle.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
            "if __name__ == '__main__':\n    unittest.main()\n")
        self.manifest = {"schema_version": 1, "ecc": {"commit": "a" * 40, "skills": {}}}
        self.calls = []

    def fake_run(self, stdout):
        real_run = eval_mod.subprocess.run

        def run(cmd, *args, **kwargs):
            if cmd and cmd[0] == sys.executable:  # oráculo roda de verdade
                return real_run(cmd, *args, **kwargs)
            self.calls.append(cmd)
            if "--version" in cmd:
                return eval_mod.subprocess.CompletedProcess(cmd, 0, "codex-cli 0.166.0\n", "")
            return eval_mod.subprocess.CompletedProcess(cmd, 0, stdout, "")
        return run

    def live(self, client, stdout, **kw):
        finder = "find_codex_binary" if client == "codex" else "find_claude_binary"
        with patch.object(eval_mod, finder, return_value="/mock/bin/" + client), \
             patch.object(eval_mod, "check_client_auth", return_value=(True, "ok")), \
             patch.object(eval_mod.subprocess, "run", side_effect=self.fake_run(stdout)):
            return eval_mod.execute_eval(client=client, task_dir=self.task_dir, condition="A", source=None,
                                         target=self.target, manifest=self.manifest, live_authorized=True, **kw)

    def test_claude_uses_stream_json_and_records_usage_cost_model(self):
        res = self.live("claude", claude_stream(CLAUDE_INIT, CLAUDE_RESULT), model="claude-opus-5-5")
        cmd = next(c for c in self.calls if "-p" in c)
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "claude-opus-5-5")
        m = res["metrics"]
        self.assertEqual((m["input_tokens"], m["cached_input_tokens"], m["output_tokens"]), (100, 90, 7))
        self.assertIsNone(m["reasoning_output_tokens"])
        self.assertEqual(m["cost_usd"], 0.5)
        self.assertEqual(m["cost_source"], "subscription_estimate")
        self.assertFalse(m["cost_observed"])
        self.assertEqual(res["client_version"], "2.1.319")
        self.assertEqual(res["model"], {"requested": "claude-opus-5-5", "observed": "claude-opus-5-5"})

    def test_codex_usage_last_turn_wins_and_model_effort_pinned(self):
        out = "\n".join(json.dumps(e) for e in (
            {"type": "thread.started", "thread_id": "t"},
            {"type": "turn.completed", "usage": {"input_tokens": 50, "cached_input_tokens": 10, "output_tokens": 5}},
            {"type": "turn.completed", "usage": {"input_tokens": 80, "cached_input_tokens": 20, "output_tokens": 9,
                                                 "reasoning_output_tokens": 2}},
        ))
        res = self.live("codex", out, model="gpt-5.5-codex", effort="high")
        cmd = next(c for c in self.calls if "exec" in c)
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-5.5-codex")
        self.assertIn("model_reasoning_effort=high", cmd)
        m = res["metrics"]
        self.assertEqual((m["input_tokens"], m["output_tokens"], m["reasoning_output_tokens"]), (80, 9, 2))
        self.assertIsNone(m["cost_usd"])
        self.assertEqual(res["client_version"], "codex-cli 0.166.0")
        self.assertEqual(res["model"], {"requested": "gpt-5.5-codex", "observed": None})
        self.assertEqual(res["effort"], "high")

    def test_codex_without_usage_reports_null_tokens(self):
        res = self.live("codex", "not json\n")
        self.assertIsNone(res["metrics"]["input_tokens"])
        self.assertIsNone(res["metrics"]["output_tokens"])
        self.assertEqual(res["telemetry"]["non_json_lines"], 1)


if __name__ == "__main__":
    unittest.main()
