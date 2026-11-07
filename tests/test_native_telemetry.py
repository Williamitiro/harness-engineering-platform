"""HE-R2-01: parser offline da telemetria nativa do Codex (`exec --json`) e do Claude Code (`stream-json`).

Os formatos seguem o upstream pinado: Codex `rust-v0.166.0`
(codex-rs/exec/src/event_processor_with_jsonl_output.rs: `turn.completed.usage` = total acumulado da sessão)
e Claude Code 2.1.x (`-p --output-format stream-json --verbose`).
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import native_telemetry as t  # noqa: E402


def lines(*events):
    return [json.dumps(e) for e in events]


def codex_cmd(command, output="", rc=0, status="completed"):
    return {"type": "item.completed", "item": {"type": "command_execution", "command": command,
            "aggregated_output": output, "status": status, "exit_code": rc}}


class CodexTelemetryTests(unittest.TestCase):
    def test_usage_is_cumulative_last_turn_wins(self):
        parsed = t.parse_codex(lines(
            {"type": "thread.started", "thread_id": "th_1"},
            {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 40,
                                                 "output_tokens": 10, "reasoning_output_tokens": 3}},
            {"type": "turn.completed", "usage": {"input_tokens": 150, "cached_input_tokens": 60,
                                                 "cache_write_input_tokens": 5, "output_tokens": 12,
                                                 "reasoning_output_tokens": 4}},
        ))
        self.assertEqual(parsed["usage"], {"input_tokens": 150, "cached_input_tokens": 60,
                                           "cache_write_input_tokens": 5, "output_tokens": 12,
                                           "reasoning_output_tokens": 4})
        self.assertEqual(parsed["turns"], 2)
        self.assertEqual(parsed["usage_semantics"], "codex_cumulative_thread_total")
        self.assertEqual(parsed["session_id"], "th_1")

    def test_no_turn_means_usage_null(self):
        parsed = t.parse_codex(lines({"type": "thread.started", "thread_id": "x"}))
        self.assertIsNone(parsed["usage"])
        self.assertEqual(parsed["turns"], 0)

    def test_all_zero_usage_is_unobserved_not_zero(self):
        # Usage::default() é emitido quando o Codex não recebeu nenhuma contagem de tokens.
        parsed = t.parse_codex(lines({"type": "turn.completed", "usage": {
            "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_output_tokens": 0}}))
        self.assertIsNone(parsed["usage"])

    def test_field_not_reported_stays_null(self):
        parsed = t.parse_codex(lines({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 1}}))
        self.assertEqual(parsed["usage"]["input_tokens"], 7)
        self.assertIsNone(parsed["usage"]["reasoning_output_tokens"])
        self.assertIsNone(parsed["usage"]["cache_write_input_tokens"])

    def test_commands_keep_exit_code_and_skip_incomplete(self):
        parsed = t.parse_codex(["Reading additional input from stdin..."] + lines(
            codex_cmd("pytest", "1 failed", 1),
            codex_cmd("pytest", "ok", 0),
            codex_cmd("sleep 9", "", None, status="in_progress"),
            {"type": "item.completed", "item": {"type": "agent_message", "text": "fim"}},
        ))
        self.assertEqual([(c["command"], c["exit_code"], c["succeeded"]) for c in parsed["tool_calls"]],
                         [("pytest", 1, False), ("pytest", 0, True)])
        self.assertEqual(parsed["final_message"], "fim")
        self.assertEqual(parsed["non_json_lines"], 1)

    def test_failed_turn_is_recorded(self):
        parsed = t.parse_codex(lines({"type": "turn.failed", "error": {"message": "quota"}}))
        self.assertEqual(parsed["errors"], ["turn.failed"])
        self.assertIsNone(parsed["usage"])

    def test_no_cost_from_codex(self):
        parsed = t.parse_codex(lines({"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}))
        self.assertIsNone(parsed["cost"]["cost_usd"])
        self.assertEqual(parsed["cost"]["cost_source"], "unknown")
        self.assertFalse(parsed["cost"]["observed"])


def claude_init(**extra):
    base = {"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-opus-5-5",
            "claude_code_version": "2.1.319", "apiKeySource": "none", "cwd": "/w",
            "tools": ["Bash", "Read", "Skill"], "skills": ["tdd-workflow", "verification-loop"]}
    base.update(extra)
    return base


def assistant(*blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": list(blocks)}}


def tool_use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def tool_result(tid, content, is_error=False):
    return {"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tid, "content": content, "is_error": is_error}]}}


def claude_result(**extra):
    base = {"type": "result", "subtype": "success", "is_error": False, "num_turns": 4, "duration_ms": 9000,
            "total_cost_usd": 0.42, "result": "pronto",
            "usage": {"input_tokens": 20, "cache_creation_input_tokens": 300, "cache_read_input_tokens": 1000,
                      "output_tokens": 80},
            "modelUsage": {"claude-opus-5-5": {"inputTokens": 20}}}
    base.update(extra)
    return base


class ClaudeTelemetryTests(unittest.TestCase):
    def test_init_metadata(self):
        parsed = t.parse_claude(lines(claude_init(), claude_result()))
        self.assertEqual(parsed["model"], "claude-opus-5-5")
        self.assertEqual(parsed["client_version"], "2.1.319")
        self.assertEqual(parsed["skills_available"], ["tdd-workflow", "verification-loop"])
        self.assertEqual(parsed["session_id"], "s1")

    def test_usage_normalized_including_cache(self):
        parsed = t.parse_claude(lines(claude_init(), claude_result()))
        self.assertEqual(parsed["usage"], {"input_tokens": 1320, "cached_input_tokens": 1000,
                                           "cache_write_input_tokens": 300, "output_tokens": 80,
                                           "reasoning_output_tokens": None})
        self.assertEqual(parsed["raw_usage"]["input_tokens"], 20)
        self.assertEqual(parsed["turns"], 4)

    def test_cost_is_client_estimate_never_billed(self):
        parsed = t.parse_claude(lines(claude_init(apiKeySource="none"), claude_result()))
        self.assertEqual(parsed["cost"], {"cost_usd": 0.42, "cost_source": "subscription_estimate",
                                          "observed": False})
        parsed_api = t.parse_claude(lines(claude_init(apiKeySource="ANTHROPIC_API_KEY"), claude_result()))
        self.assertEqual(parsed_api["cost"]["cost_source"], "unknown")
        self.assertFalse(parsed_api["cost"]["observed"])

    def test_missing_result_means_null_usage_and_cost(self):
        parsed = t.parse_claude(lines(claude_init()))
        self.assertIsNone(parsed["usage"])
        self.assertIsNone(parsed["cost"]["cost_usd"])
        self.assertIsNone(parsed["turns"])
        self.assertEqual(parsed["errors"], ["result_missing"])

    def test_error_result_is_recorded(self):
        parsed = t.parse_claude(lines(claude_init(), claude_result(subtype="error_max_turns", is_error=True)))
        self.assertEqual(parsed["errors"], ["error_max_turns"])

    def test_tool_calls_paired_with_results(self):
        parsed = t.parse_claude(lines(
            claude_init(),
            assistant({"type": "text", "text": "vou testar"}, tool_use("a", "Bash", command="pytest -q")),
            tool_result("a", "1 failed", is_error=True),
            assistant(tool_use("b", "Bash", command="pytest -q")),
            tool_result("b", [{"type": "text", "text": "1 passed"}]),
            assistant(tool_use("c", "Skill", skill="tdd-workflow")),
            tool_result("c", "Launching skill: tdd-workflow"),
            assistant(tool_use("d", "Read", file_path="/h/.claude/skills/verification-loop/SKILL.md")),
            tool_result("d", "---\nname: verification-loop\n---"),
            assistant(tool_use("e", "Bash", command="never answered")),
            claude_result(),
        ))
        calls = parsed["tool_calls"]
        self.assertEqual([(c["tool"], c["succeeded"]) for c in calls],
                         [("shell", False), ("shell", True), ("skill", True), ("read", True), ("shell", None)])
        self.assertEqual(calls[1]["output"], "1 passed")
        self.assertIsNone(calls[0]["exit_code"])  # o Claude Code não expõe o código de saída
        self.assertEqual(calls[2]["skill"], "tdd-workflow")
        self.assertEqual(calls[3]["path"], "/h/.claude/skills/verification-loop/SKILL.md")
        self.assertEqual(parsed["final_message"], "pronto")

    def test_non_json_lines_counted(self):
        parsed = t.parse_claude(["warning: x"] + lines(claude_init(), claude_result()))
        self.assertEqual(parsed["non_json_lines"], 1)


class DispatchTests(unittest.TestCase):
    def test_parse_by_client(self):
        self.assertEqual(t.parse("codex", [])["client"], "codex")
        self.assertEqual(t.parse("claude", [])["client"], "claude")
        with self.assertRaises(ValueError):
            t.parse("gemini", [])


if __name__ == "__main__":
    unittest.main()
