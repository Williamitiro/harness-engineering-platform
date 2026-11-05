import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import quality_baseline as q  # noqa: E402

FIX_BODY = """Correções dos achados da revisão do Codex dos PRs 219–243.

| # | Achado | Teste |
|---|---|---|
| 1 | D1 aprova cota errada (#234) | t1 |
| 2 | Caderno legado (#234) | t2 |
| 3 | Total com dobra (#225) | t3 |
| 9 | Documentação | docs |
"""


def pr(number, title="feat: x", body="", branch=None, files=()):
    return {"number": number, "title": title, "body": body, "headRefName": branch or f"b{number}",
            "mergedAt": "2026-11-04T00:00:00Z", "files": list(files)}


class FindingsTests(unittest.TestCase):
    def test_rows_attributed_to_origin_and_range_marks_reviewed(self):
        f = q.parse_findings_pr(pr(245, "fix: achados do Codex (PRs 225–243)", FIX_BODY))
        self.assertEqual(f["per_origin"], {234: 2, 225: 1})
        self.assertEqual(f["unattributed_rows"], 1)
        self.assertIn(219, f["reviewed"])
        self.assertIn(243, f["reviewed"])

    def test_list_of_prs_in_title(self):
        f = q.parse_findings_pr(pr(247, "fix: seis achados da revisão (PRs 220, 226, 230, 239)", ""))
        self.assertEqual(f["reviewed"], [220, 226, 230, 239])

    def test_not_a_findings_pr(self):
        self.assertIsNone(q.parse_findings_pr(pr(10, "feat: tela nova", FIX_BODY)))
        self.assertIsNone(q.parse_findings_pr(pr(232, "docs: erros, achados e aprendizados", FIX_BODY)))

    def test_unreviewed_pr_has_null_findings_not_zero(self):
        prs = [pr(100), pr(230), pr(234), pr(245, "fix: achados (PRs 225–243)", FIX_BODY)]
        recs = {r["pr"]: r for r in q.build(prs, {}, {})["records"]}
        self.assertIsNone(recs[100]["findings"])
        self.assertEqual(recs[230]["findings"], 0)
        self.assertEqual(recs[234]["findings"], 2)
        self.assertTrue(recs[245]["is_findings_fix"])
        s = q.build(prs, {}, {})["summary"]
        self.assertEqual((s["reviewed"], s["reviewed_with_findings"], s["findings_total"]), (2, 1, 2))
        self.assertIsNone(s["median_claude_output_per_pr"])

    def test_review_without_table_leaves_findings_null(self):
        prs = [pr(158), pr(166, "ra1: achados do #158 (linha em dois trechos)", "texto sem tabela")]
        res = q.build(prs, {}, {})
        self.assertIsNone(res["records"][0]["findings"])
        self.assertEqual(res["summary"]["findings_prs_without_table"], [166])


class SmallParsersTests(unittest.TestCase):
    def test_model_line(self):
        self.assertEqual(q.model_from_body("x\n\nModelo/esforço: Opus/médio (regra). O nível bastou."),
                         "Opus/médio (regra). O nível bastou")
        self.assertIsNone(q.model_from_body("sem linha"))

    def test_diff_size_separates_docs_tests_code(self):
        d = q.diff_size([{"path": "src/a.py", "additions": 3, "deletions": 1},
                         {"path": "tests/test_a.py", "additions": 10, "deletions": 0},
                         {"path": "docs/INDICE.md", "additions": 5, "deletions": 5},
                         {"path": "README.md", "additions": 1, "deletions": 1}])
        self.assertEqual(d, {"code": 4, "tests": 10, "docs": 12})


class LogTests(unittest.TestCase):
    def write(self, folder, name, rows):
        p = Path(folder) / name
        p.write_text("\n".join(json.dumps(r) for r in rows) + "\nnão é json\n", encoding="utf-8")
        return p

    def test_claude_dedupes_message_and_groups_by_branch(self):
        msg = {"id": "m1", "model": "claude-opus-5-5",
               "usage": {"input_tokens": 2, "cache_creation_input_tokens": 10, "cache_read_input_tokens": 50,
                         "output_tokens": 7}}
        rows = [{"gitBranch": "b1", "requestId": "r1", "sessionId": "s", "message": msg},
                {"gitBranch": "b1", "requestId": "r1", "sessionId": "s", "message": msg},
                {"gitBranch": "b2", "requestId": "r2", "sessionId": "s",
                 "message": {"id": "m2", "model": "claude-haiku-5-5", "usage": {"output_tokens": 3}}},
                {"requestId": "r3", "message": {"id": "m3", "usage": {"output_tokens": 99}}}]
        with tempfile.TemporaryDirectory() as d:
            out = q.claude_usage([self.write(d, "a.jsonl", rows)])
        self.assertEqual((out["b1"]["output"], out["b1"]["cache_read"]), (7, 50))
        self.assertEqual(dict(out["b2"]["models"]), {"claude-haiku-5-5": 1})
        self.assertEqual(set(out), {"b1", "b2"})

    def test_codex_takes_last_cumulative_total(self):
        rows = [{"type": "session_meta", "payload": {"git": {"branch": "b1"}}},
                {"type": "turn_context", "payload": {"model": "gpt-6-luna",
                                                     "collaboration_mode": {"settings": {"reasoning_effort": "medium"}}}},
                {"type": "event_msg", "payload": {"type": "token_count",
                                                  "info": {"total_token_usage": {"input_tokens": 10, "output_tokens": 1}}}},
                {"type": "event_msg", "payload": {"type": "token_count",
                                                  "info": {"total_token_usage": {"input_tokens": 30, "cached_input_tokens": 20,
                                                                                 "output_tokens": 4}}}}]
        no_branch = [{"type": "session_meta", "payload": {}}]
        with tempfile.TemporaryDirectory() as d:
            out = q.codex_usage([self.write(d, "rollout-1.jsonl", rows), self.write(d, "rollout-2.jsonl", no_branch)])
        self.assertEqual((out["b1"]["input"], out["b1"]["cached"], out["b1"]["output"]), (30, 20, 4))
        self.assertEqual(dict(out["b1"]["models"]), {"gpt-6-luna/medium": 1})
        self.assertEqual(len(out), 1)


if __name__ == "__main__":
    unittest.main()
