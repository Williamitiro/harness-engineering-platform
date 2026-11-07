import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import r2_bench as b  # noqa: E402


def ev(**kw):
    return json.dumps(kw)


class ParseEventsTests(unittest.TestCase):
    def test_usage_is_cumulative_last_turn_wins(self):
        # Codex rust-v0.166.0: turn.completed.usage = total acumulado da sessão; somar contaria em dobro.
        lines = [ev(type="turn.completed", usage={"input_tokens": 10, "cached_input_tokens": 4, "output_tokens": 2}),
                 ev(type="turn.completed", usage={"input_tokens": 15, "cached_input_tokens": 4, "output_tokens": 3,
                                                  "reasoning_output_tokens": 3})]
        p = b.parse_events(lines)
        self.assertEqual(p["usage"], {"input_tokens": 15, "cached_input_tokens": 4, "cache_write_input_tokens": None,
                                      "output_tokens": 3, "reasoning_output_tokens": 3})
        self.assertEqual(p["turns"], 2)

    def test_missing_usage_is_null_not_zero(self):
        parsed = b.parse_events([ev(type="item.completed", item={"type": "agent_message", "text": "oi"})])
        self.assertIsNone(parsed["usage"])
        self.assertEqual(parsed["turns"], 0)

    def test_field_never_reported_stays_null(self):
        u = b.parse_events([ev(type="turn.completed", usage={"input_tokens": 7})])["usage"]
        self.assertEqual(u["input_tokens"], 7)
        self.assertIsNone(u["reasoning_output_tokens"])

    def test_commands_messages_and_garbage(self):
        lines = ["Reading additional input from stdin...",
                 ev(type="item.completed", item={"type": "command_execution", "command": "ls"}),
                 ev(type="item.completed", item={"type": "agent_message", "text": "primeiro"}),
                 ev(type="item.completed", item={"type": "agent_message", "text": "último"})]
        p = b.parse_events(lines)
        self.assertEqual(p["commands"], ["ls"])
        self.assertEqual(p["final_message"], "último")
        self.assertEqual(p["non_json_lines"], 1)


class SkillsAndLeaksTests(unittest.TestCase):
    def test_skill_read_detected_on_both_separators(self):
        cmds = [r"Get-Content .agents\skills\search-first\SKILL.md", "cat .agents/skills/karpathy-guidelines/SKILL.md",
                "cat skills/notaskill/README.md"]
        self.assertEqual(b.skills_read(cmds), ["karpathy-guidelines", "search-first"])

    def test_platform_python_is_allowed_but_checkout_is_a_leak(self):
        py = "C:/dev/plataforma-metalurgica/.venv/Scripts/python.exe"
        cmds = [f"{py} -m pytest -q tests/test_dxf.py",
                r"git -C C:\dev\plataforma-metalurgica log -p",
                r"cat C:\Users\x\hxb\r\T1A1\src\a.py",
                r"cat C:\Users\x\hxb\r\T1B2\src\a.py"]
        hits = b.leak_hits(cmds, forbidden=[r"C:\dev\plataforma-metalurgica", r"C:\Users\x\hxb"],
                           allowed=[py, r"C:\Users\x\hxb\r\T1A1"])
        self.assertEqual(len(hits), 2)
        self.assertIn("log -p", hits[0])
        self.assertIn("T1B2", hits[1])


class NumstatTests(unittest.TestCase):
    def test_tests_code_and_ignored_paths(self):
        text = "\n".join(["3\t1\tsrc/metalurgia/a.py", "10\t0\ttests/test_a.py", "-\t-\tsrc/img.png",
                          "5\t5\t.agents/skills/x/SKILL.md", "1\t0\tsrc/__pycache__/a.pyc"])
        d = b.classify_numstat(text)
        self.assertEqual(d["files"]["code"], ["src/metalurgia/a.py", "src/img.png"])
        self.assertEqual(d["files"]["tests"], ["tests/test_a.py"])
        self.assertEqual(d["changed_lines"], {"code": 4, "tests": 10})
        self.assertEqual(d["changed_files_total"], 3)

    def test_empty_diff(self):
        self.assertEqual(b.classify_numstat("")["changed_files_total"], 0)


class SpecTests(unittest.TestCase):
    def test_spec_is_consistent(self):
        spec = b.load_spec()
        root = Path(b.ROOT)
        for name, rel in spec["kit_skills"].items():
            self.assertTrue((root / rel / "SKILL.md").is_file(), name)
        for task in spec["tasks"].values():
            if "hidden_tests" in task:
                hidden = (root / task["hidden_tests"]["append"]).read_text(encoding="utf-8")
                self.assertTrue(b.hidden_names(hidden))
        self.assertEqual(set(spec["arms"]), {"A", "B", "R"})
        self.assertFalse(spec["arms"]["A"]["kit"])
        self.assertTrue(spec["arms"]["B"]["kit"])
        self.assertEqual(spec["arms"]["A"]["model"], spec["arms"]["B"]["model"])

    def test_disable_config_lists_every_user_skill(self):
        spec = b.load_spec()
        config = b.disabled_skills_config(spec)
        for name in spec["isolation"]["user_skills_disabled_in_all_arms"]:
            self.assertIn(f"/{name}/SKILL.md", config)
        self.assertEqual(config.count("enabled=false"), len(spec["isolation"]["user_skills_disabled_in_all_arms"]))


class AggregateTests(unittest.TestCase):
    def rec(self, rid, task, arm, accepted, usage, valid=True, reuse=None, skills=()):
        return {"run_id": rid, "task": task, "arm": arm, "valid": valid, "usage": usage, "command_count": 3,
                "wall_seconds": 10.0, "verify": {"accepted": accepted}, "reuse_signal": reuse, "skills_read": list(skills),
                "diff": {"changed_lines": {"code": 4, "tests": 2}, "files": {"code": ["a"], "tests": []}}}

    def test_invalid_runs_are_listed_not_counted(self):
        cells = b.aggregate([self.rec("T1A1", "T1", "A", True, {"input_tokens": 100, "cached_input_tokens": 60}),
                             self.rec("T1A2", "T1", "A", False, None),
                             self.rec("T1A3", "T1", "A", True, {"input_tokens": 1}, valid=False)])
        a = cells["T1"]["A"]
        self.assertEqual((a["n"], a["accepted"], a["invalid"]), (2, 1, ["T1A3"]))
        self.assertEqual(a["input_tokens"], 100)          # a execução sem uso fica fora da média, não vira 0
        self.assertEqual(a["uncached_input_tokens"], 40)
        self.assertIsNone(a["reuse"])

    def test_reuse_and_skills_counted_for_t2(self):
        cells = b.aggregate([self.rec("T2B1", "T2", "B", True, None, reuse=True, skills=["search-first"]),
                             self.rec("T2B2", "T2", "B", True, None, reuse=False, skills=["search-first", "karpathy-guidelines"])])
        cell = cells["T2"]["B"]
        self.assertEqual(cell["reuse"], 1)
        self.assertEqual(cell["skills_read"], {"search-first": 2, "karpathy-guidelines": 1})
        self.assertIsNone(cell["input_tokens"])


if __name__ == "__main__":
    unittest.main()
