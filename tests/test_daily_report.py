"""Relatório diário de funcionamento: lê sessões locais do Claude Code e do Codex (formatos sintéticos)."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_report as r  # noqa: E402

DAY = dt.date(2026, 11, 7)
TS = "2026-11-07T15:00:{:02d}.000Z"
OLD = "2026-11-05T15:00:00.000Z"


def write(path: Path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(e) for e in events) + "\nnot json\n", encoding="utf-8")


def c_use(i, tid, name, **inp):
    return {"type": "assistant", "timestamp": TS.format(i), "sessionId": "cs1", "cwd": "REPO",
            "message": {"id": f"m{i}", "model": "claude-opus-5-5", "content": [
                {"type": "tool_use", "id": tid, "name": name, "input": inp}],
                "usage": {"input_tokens": 10, "cache_read_input_tokens": 100,
                          "cache_creation_input_tokens": 5, "output_tokens": 3}}}


def c_res(i, tid, text, err=False):
    return {"type": "user", "timestamp": TS.format(i), "sessionId": "cs1", "cwd": "REPO",
            "message": {"content": [{"type": "tool_result", "tool_use_id": tid, "content": text, "is_error": err}]}}


def x(i, typ, payload):
    return {"timestamp": TS.format(i), "type": typ, "payload": payload}


def x_cmd(i, cmd, code):
    return x(i, "event_msg", {"type": "item_completed", "item": {
        "type": "CommandExecution", "command": ["pwsh.exe", "-Command", cmd], "parsed_cmd": [{"type": "unknown", "cmd": cmd}],
        "status": "completed", "exit_code": code, "aggregated_output": "..."}})


def x_tokens(i, total_in, total_out, ts=None):
    e = x(i, "event_msg", {"type": "token_count", "info": {"total_token_usage": {
        "input_tokens": total_in, "cached_input_tokens": total_in // 2, "output_tokens": total_out,
        "reasoning_output_tokens": 1}}})
    if ts:
        e["timestamp"] = ts
    return e


class Fixture(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "dev" / "proj"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / ".harness").mkdir()
        (self.repo / ".harness" / "manifest.json").write_text("{}", encoding="utf-8")
        (self.repo / "src").mkdir()
        self.plain = self.root / "dev" / "plain"
        (self.plain / ".git").mkdir(parents=True)
        self.claude = self.root / "claude"
        self.codex = self.root / "codex"
        rp = str(self.repo / "src")

        claude_events = [
            {"type": "custom-title", "sessionId": "cs1", "customTitle": "x"},
            c_use(1, "a", "Skill", skill="tdd-workflow"), c_res(2, "a", "Launching skill: tdd-workflow"),
            c_use(3, "b", "Bash", command="python -m pytest -q"), c_res(4, "b", "1 failed", True),
            c_use(5, "c", "Edit", file_path="x.py"), c_res(6, "c", "ok"),
            c_use(7, "d", "Bash", command="python -m pytest -q"), c_res(8, "d", "1 passed"),
            c_use(9, "e", "Read", file_path="C:/Users/u/.claude/skills/verification-loop/SKILL.md"), c_res(10, "e", "..."),
        ]
        # a mesma mensagem da API repetida em duas linhas não conta tokens duas vezes
        claude_events.append(dict(claude_events[-2]))
        claude_events.append({"type": "assistant", "timestamp": TS.format(11), "sessionId": "cs1", "cwd": "REPO",
                              "isApiErrorMessage": True, "message": {"id": "err", "content": []}})
        for e in claude_events:
            if e.get("cwd") == "REPO":
                e["cwd"] = rp
        write(self.claude / "C--dev-proj" / "cs1.jsonl", claude_events)
        write(self.claude / "C--dev-old" / "old.jsonl", [
            {"type": "assistant", "timestamp": OLD, "sessionId": "old", "cwd": str(self.plain),
             "message": {"id": "o", "content": []}}])

        write(self.codex / "2026" / "11" / "07" / "rollout-1.jsonl", [
            x(0, "session_meta", {"id": "xs1", "cwd": str(self.plain), "cli_version": "0.167.0"}),
            x_tokens(0, 1000, 10, ts=OLD),  # antes do dia: desconta do total
            x(1, "turn_context", {"cwd": str(self.plain), "model": "gpt-5.5-codex", "effort": "high"}),
            x_cmd(2, "Get-Content C:/Users/u/.agents/skills/tdd-workflow/SKILL.md", 0),
            x_cmd(3, "npm test", 1),
            x_cmd(4, "npm test", "0"),
            x(5, "event_msg", {"type": "turn_aborted", "reason": "interrupted"}),
            x_tokens(6, 1500, 25),
        ])
        self.report = r.build_report(DAY, claude_root=self.claude, codex_root=self.codex)


class ReportTests(Fixture):
    def session(self, client):
        return next(s for s in self.report["sessions"] if s["client"] == client)

    def test_only_sessions_of_the_day(self):
        self.assertEqual(sorted(s["client"] for s in self.report["sessions"]), ["claude", "codex"])

    def test_claude_session(self):
        s = self.session("claude")
        self.assertEqual(s["repo"], "proj")
        self.assertTrue(s["harness_attached"])
        self.assertEqual(s["skills_used"], ["tdd-workflow", "verification-loop"])
        self.assertEqual(s["tests"], {"runs": 2, "failed": 1, "red_then_green": True, "last_passed": True})
        self.assertEqual(s["tokens"], {"input_tokens": 115 * 5, "cached_input_tokens": 500, "output_tokens": 15,
                                       "reasoning_output_tokens": None})
        self.assertEqual(s["errors"], {"api_errors": 1, "tool_errors": 1, "aborted_turns": None})
        self.assertEqual(s["models"], ["claude-opus-5-5"])

    def test_codex_session(self):
        s = self.session("codex")
        self.assertEqual(s["repo"], "plain")
        self.assertFalse(s["harness_attached"])
        self.assertEqual(s["skills_used"], ["tdd-workflow"])
        self.assertEqual(s["tests"], {"runs": 2, "failed": 1, "red_then_green": True, "last_passed": True})
        self.assertEqual(s["tokens"]["input_tokens"], 500)  # 1500 no fim do dia - 1000 antes
        self.assertEqual(s["tokens"]["output_tokens"], 15)
        self.assertEqual(s["errors"]["aborted_turns"], 1)
        self.assertEqual(s["models"], ["gpt-5.5-codex"])
        self.assertEqual(s["client_version"], "0.167.0")

    def test_summary_and_honesty_label(self):
        sm = self.report["summary"]
        self.assertEqual(sm["sessions"], 2)
        self.assertEqual(sm["sessions_in_harness_repos"], 1)
        self.assertEqual(sm["sessions_with_skill_use"], 2)
        self.assertEqual(sm["sessions_with_tests"], 2)
        self.assertEqual(self.report["evidence_level"], "OPERATIONAL_LOG_ONLY_NOT_A_BENCHMARK")

    def test_markdown_has_no_conversation_content(self):
        md = r.render_markdown(self.report)
        self.assertIn("tdd-workflow", md)
        self.assertNotIn("1 failed", md)
        self.assertNotIn("Launching skill", md)
        self.assertIn("não é benchmark", md.lower())


class RepoOfTests(unittest.TestCase):
    def test_worktree_maps_to_main_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "plataforma"
            (main / ".git" / "worktrees" / "b27").mkdir(parents=True)
            wt = Path(tmp) / "wts" / "b27-abc"
            (wt / ".harness").mkdir(parents=True)
            (wt / ".harness" / "manifest.json").write_text("{}", encoding="utf-8")
            (wt / ".git").write_text(f"gitdir: {main / '.git' / 'worktrees' / 'b27'}\n", encoding="utf-8")
            self.assertEqual(r.repo_of(str(wt / "src")), ("plataforma", True))
            self.assertEqual(r.repo_of("file:///" + str(wt).replace("\\", "/")), ("plataforma", True))


class EmptyDayTests(unittest.TestCase):
    def test_no_sessions_is_null_not_zero_rates(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = r.build_report(DAY, claude_root=Path(tmp) / "c", codex_root=Path(tmp) / "x")
        self.assertEqual(rep["summary"]["sessions"], 0)
        self.assertIsNone(rep["summary"]["share_with_skill_use"])

    def test_session_without_tests_reports_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root / "c" / "p" / "s.jsonl", [c_use(1, "a", "Bash", command="ls")])
            rep = r.build_report(DAY, claude_root=root / "c", codex_root=root / "x")
        s = rep["sessions"][0]
        self.assertEqual(s["tests"], {"runs": 0, "failed": 0, "red_then_green": False, "last_passed": None})
        self.assertIsNone(s["repo"])  # cwd sem Git não vira repositório inventado


if __name__ == "__main__":
    unittest.main()
