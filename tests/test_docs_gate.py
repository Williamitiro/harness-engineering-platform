"""HE-DOC-02: document organization gate — three checks, the hook (both tools) and hook install/remove."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("docs_gate", ROOT / "scripts/docs_gate.py")
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

POLICY = {
    "schema_version": 1, "entry": "AGENTS.md", "state": "docs/ESTADO.md", "index": "docs/INDICE.md",
    "limits": {"entry": 200, "state": 100, "index": 400},
    "places": {"vigente": ["docs/*.md", "README.md"], "evidencia": ["docs/runs/**"], "arquivo": ["docs/arquivo/**"]},
    "indexed": ["vigente"], "ignore": ["vendor/**"],
}


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class GateCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "core.autocrlf", "false")

    def write(self, rel, text="x\n"):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        return path

    def commit(self):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "--quiet", "-m", "base")

    def with_policy(self, policy=POLICY):
        self.write(".harness/docs-policy.json", json.dumps(policy))
        self.write("AGENTS.md", "regras\n")
        self.write("docs/ESTADO.md", "estado\n")
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n")
        self.write("docs/SPEC.md", "spec\n")
        self.commit()
        return d.load_policy(self.repo)

    def rules(self, result):
        return sorted((v["file"], v["rule"]) for v in result["violations"])


class ChecksTests(GateCase):
    def test_clean_change_passes(self):
        policy = self.with_policy()
        self.write("docs/runs/2026-11-21.md", "rodada\n")  # evidence: right place, not indexed
        self.write("docs/ESTADO.md", "estado novo\n")
        result = d.run_check(self.repo, policy)
        self.assertEqual(result["status"], "DOCS_CHECK_PASS", result)

    def test_lugar_refuses_md_outside_policy_and_names_the_places(self):
        policy = self.with_policy()
        self.write("RELATORIO_FINAL.md")
        self.write("vendor/lib/README.md")  # ignored
        self.write("notas.txt")  # not markdown
        result = d.run_check(self.repo, policy)
        self.assertEqual(self.rules(result), [("RELATORIO_FINAL.md", "lugar")])
        self.assertIn("docs/runs/**", result["violations"][0]["fix"])

    def test_orcamento_blocks_crossing_the_limit(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e" * 150)
        result = d.run_check(self.repo, policy)
        self.assertEqual(self.rules(result), [("docs/ESTADO.md", "orcamento")])
        # Real Claude Code trial (21/11): the file was below the limit, so the message must not say "already above".
        self.assertNotIn("já estava acima", result["violations"][0]["message"])
        fix = result["violations"][0]["fix"]
        self.assertIn("sobram 93 bytes até o teto e a mudança pede 143; faltam 50", fix)  # "estado\n" = 7 bytes
        self.assertIn("git mv do estado inteiro para docs/arquivo", fix)  # the archive folder of this policy

    def test_entry_over_budget_suggests_the_trigger_line_for_an_area_rule(self):
        # HE-DOC-04: the refusal says how many bytes are left and how to make room without losing a rule.
        policy = self.with_policy()
        hook = HookTests.pre(self, "Write", {"file_path": str(self.repo / "AGENTS.md"), "content": "r" * 250})
        self.assertIn("Vai mexer em", hook["hookSpecificOutput"]["permissionDecisionReason"])  # what the agent sees
        self.write("AGENTS.md", "r" * 250)
        violation = d.run_check(self.repo, policy)["violations"][0]
        self.assertEqual((violation["file"], violation["rule"]), ("AGENTS.md", "orcamento"))
        self.assertIn("sobram 193 bytes", violation["fix"])  # "regras\n" = 7 bytes, teto 200
        self.assertIn("Vai mexer em X? Leia antes, obrigatório: <link>", violation["fix"])  # the skill's words
        self.assertIn("regra geral fica por inteiro", violation["fix"])

    def test_file_already_above_says_no_byte_is_left(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e" * 300)
        self.commit()
        self.write("docs/ESTADO.md", "e" * 310)
        fix = d.run_check(self.repo, policy)["violations"][0]["fix"]
        self.assertIn("não sobra nenhum byte: o arquivo já passa 200 bytes do teto", fix)

    def test_file_already_above_limit_cannot_grow_but_may_shrink(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e" * 300)
        self.commit()  # legacy: already above the limit
        self.write("docs/ESTADO.md", "e" * 250)
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")
        self.write("docs/ESTADO.md", "e" * 301)
        result = d.run_check(self.repo, policy)
        self.assertEqual(self.rules(result), [("docs/ESTADO.md", "orcamento")])
        self.assertIn("já estava acima do teto, com 300", result["violations"][0]["message"])

    def test_indice_requires_link_for_new_current_document(self):
        policy = self.with_policy()
        self.write("docs/MANUAL.md", "manual\n")
        self.assertEqual(self.rules(d.run_check(self.repo, policy)), [("docs/MANUAL.md", "indice")])
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n[manual](MANUAL.md#uso)\n")
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")

    def test_indice_broken_link_only_when_index_changes(self):
        policy = self.with_policy()
        (self.repo / "docs/SPEC.md").unlink()
        self.commit()  # legacy broken link does not block
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n[site](https://example.com)\n")
        self.assertEqual(self.rules(d.run_check(self.repo, policy)), [("docs/INDICE.md", "indice")])

    def test_ci_mode_compares_with_merge_base(self):
        policy = self.with_policy()
        base = git(self.repo, "rev-parse", "HEAD")
        self.write("solto.md")
        self.commit()
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")  # vs HEAD: nothing new
        self.assertEqual(self.rules(d.run_check(self.repo, policy, base)), [("solto.md", "lugar")])

    def test_moving_to_archive_is_allowed(self):
        policy = self.with_policy()
        (self.repo / "docs/arquivo").mkdir()
        git(self.repo, "mv", "docs/SPEC.md", "docs/arquivo/SPEC_2026.md")
        self.write("docs/INDICE.md", "indice\n")
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")

    def test_moving_a_linked_doc_without_fixing_the_index_is_caught(self):
        # Review #3: HE-DOC-03 moves documents to the archive; the index must not keep a dead link.
        policy = self.with_policy()
        (self.repo / "docs/arquivo").mkdir()
        git(self.repo, "mv", "docs/SPEC.md", "docs/arquivo/SPEC_2026.md")
        result = d.run_check(self.repo, policy)
        self.assertEqual(self.rules(result), [("docs/INDICE.md", "indice")])
        self.assertIn("SPEC.md", result["violations"][0]["message"])
        self.assertNotIn("target", result["violations"][0])
        self.write("docs/INDICE.md", "[spec](arquivo/SPEC_2026.md)\n")
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")

    def test_check_since_skips_files_untouched_in_the_session(self):
        # Review #4: a stray .md that predates the session does not hold every Stop.
        policy = self.with_policy()
        old = self.write("ANTIGO.md")
        os.utime(old, (1_000_000, 1_000_000))
        self.assertEqual(d.run_check(self.repo, policy, since=2_000_000)["status"], "DOCS_CHECK_PASS")
        self.write("NOVO.md")
        self.assertEqual(self.rules(d.run_check(self.repo, policy, since=2_000_000)), [("NOVO.md", "lugar")])
        self.assertEqual(len(d.run_check(self.repo, policy)["violations"]), 2)  # CI: no time filter

    def test_invalid_policy_is_refused(self):
        for bad in ({"schema_version": 2, "places": {"a": ["x"]}}, {"schema_version": 1, "places": {}},
                    {"schema_version": 1, "places": {"a": ["../fora/*.md"]}},
                    {"schema_version": 1, "places": {"a": ["x"]}, "indexed": ["b"]},
                    {"schema_version": 1, "places": {"a": ["x"]}, "limits": {"state": 0}}):
            self.write(".harness/docs-policy.json", json.dumps(bad))
            with self.assertRaises(d.PolicyError):
                d.load_policy(self.repo)

    def test_crlf_on_disk_is_not_growth(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e\n" * 60)
        self.commit()  # 120 bytes in Git: above the limit of 100
        (self.repo / "docs/ESTADO.md").write_bytes(b"e\r\n" * 59 + b"f\r\n")  # same size as LF
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")

    def test_glob(self):
        self.assertTrue(d.matches("docs/runs/a/b.md", ["docs/runs/**"]))
        self.assertTrue(d.matches("docs/a.md", ["docs/**/*.md"]))
        self.assertFalse(d.matches("docs/sub/a.md", ["docs/*.md"]))

    def test_plan_without_policy_groups_two_folder_levels(self):
        # The skill asks a "yes" per folder: docs/adr and docs/historico must not collapse into "docs".
        for rel in ("docs/a.md", "docs/adr/1.md", "docs/historico/velho/x.md", "README.md"):
            self.write(rel)
        self.commit()
        self.assertEqual(d.run_plan(self.repo)["md_by_dir"],
                         {".": 1, "docs": 1, "docs/adr": 1, "docs/historico": 1})

    def test_cli_check_exit_codes_and_no_policy(self):
        def run(*args):
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = d.main(list(args))
            return code, json.loads(out.getvalue()) if out.getvalue() else None
        self.write("x.md")
        self.commit()
        self.assertEqual(run("check", "--repo", str(self.repo))[1]["status"], "NO_POLICY")
        plan_code, plan = run("plan", "--repo", str(self.repo))
        self.assertEqual((plan_code, plan["status"], plan["writes"]), (0, "NO_POLICY", 0))
        self.with_policy()
        self.write("solto.md")
        self.assertEqual(run("check", "--repo", str(self.repo))[0], 1)
        self.assertEqual(run("plan", "--repo", str(self.repo))[1]["status"], "POLICY_FOUND")


class VerifyTests(GateCase):
    """HE-DOC-04: the whole repository against its policy (inside project-verify)."""

    # ---- v1.4.1: findings of the independent review of v1.4.0

    def test_links_that_open_are_not_reported_as_broken(self):
        self.with_policy()
        self.write("docs/Meu Guia.md", "guia\n")
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n[g](Meu%20Guia.md)\n[linha](SPEC.md:12)\n[col](SPEC.md:3:4)\n"
                                     "```\n[exemplo](NAO_EXISTE.md)\n```\nUse `[x](TAMBEM_NAO.md)` assim.\n")
        self.commit()
        result = d.run_verify(self.repo)
        self.assertEqual(result["status"], "PASS", result["problems"])

    def test_a_really_broken_link_is_still_caught(self):
        self.with_policy()
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n[some](SUMIU.md:12)\n[esp](Sem%20Arquivo.md)\n")
        self.commit()
        text = "\n".join(d.run_verify(self.repo)["problems"])
        self.assertIn("SUMIU.md:12", text)
        self.assertIn("Sem%20Arquivo.md", text)

    def test_most_specific_pattern_wins_whatever_the_order(self):
        policy = {**POLICY, "places": {"vigente": ["docs/**"], "arquivo": ["docs/arquivo/**"]}}
        loaded = self.with_policy(policy)
        self.assertEqual(d.kind_of(loaded, "docs/arquivo/velho.md"), "arquivo")
        self.assertEqual(d.kind_of(loaded, "docs/novo.md"), "vigente")
        (self.repo / "docs/arquivo").mkdir()
        git(self.repo, "mv", "docs/SPEC.md", "docs/arquivo/SPEC.md")  # archiving is not "a new current document"
        self.write("docs/INDICE.md", "indice\n")
        result = d.run_check(self.repo, loaded)
        self.assertEqual(result["status"], "DOCS_CHECK_PASS", result)

    def test_policy_that_is_not_an_object_is_invalid_not_a_crash(self):
        for bad in ("[]", "null", '"x"', '{"schema_version": 1, "places": {"v": ["*.md"]}, "limits": 5}'):
            self.write(".harness/docs-policy.json", bad)
            result = d.run_verify(self.repo)
            self.assertEqual((result["status"], result["reason"]), ("FAIL", "PLANTA_INVALIDA"), bad)

    def test_large_non_markdown_file_is_never_read(self):
        policy = self.with_policy()
        self.write("video.bin", "v")
        original = Path.read_bytes

        def guard(path, *a, **k):
            if path.name == "video.bin":
                raise AssertionError("read a file the checks never use")
            return original(path, *a, **k)

        with unittest.mock.patch.object(Path, "read_bytes", guard):
            self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")
            d.run_verify(self.repo)

    def test_state_over_the_limit_and_growing_is_listed_once(self):
        self.with_policy()
        self.write("docs/ESTADO.md", "e" * 150)
        self.commit()
        self.write("docs/ESTADO.md", "e" * 160)
        problems = d.run_verify(self.repo)["problems"]
        self.assertEqual(sum("docs/ESTADO.md" in p for p in problems), 1, problems)

    def test_budget_correction_starts_with_a_capital_and_says_how_to_archive_the_state(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e" * 150)
        fix = d.run_check(self.repo, policy)["violations"][0]["fix"]
        self.assertIn("faltam 50. Faça git mv do estado inteiro para docs/arquivo", fix)
        self.assertIn("comece um estado novo e curto", fix)
        self.assertNotIn("deixe no estado", fix)  # the cleanup rule: the state is archived whole, never trimmed

    def test_code_fences_follow_commonmark_and_never_hide_the_rest_of_the_index(self):
        # Second review of v1.4.1: a longer closing fence, or a line starting with ```x```, swallowed the tail.
        self.with_policy()
        cases = {
            "longer closing fence": "```\n[ex](NAO.md)\n````\n[sumiu](SUMIU.md)\n",
            "inline code at line start": "```bash``` é inline\n[sumiu](SUMIU.md)\n",
            "tilde fence closed by more tildes": "~~~\n[ex](NAO.md)\n~~~~\n[sumiu](SUMIU.md)\n",
            "crlf": "```\r\n[ex](NAO.md)\r\n```\r\n[sumiu](SUMIU.md)\r\n",
        }
        for name, text in cases.items():
            _, broken = d.index_links(self.repo, "docs/INDICE.md", text)
            self.assertEqual([b["target"] for b in broken], ["docs/SUMIU.md"], name)

    def test_new_document_linked_after_a_code_block_is_still_indexed(self):
        policy = self.with_policy()
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n```\nexemplo\n````\n[manual](MANUAL.md)\n")
        self.write("docs/MANUAL.md", "manual\n")
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")

    def test_host_and_port_is_not_taken_for_a_file_with_a_line(self):
        self.with_policy()
        _, broken = d.index_links(self.repo, "docs/INDICE.md", "[s](example.com:8080)\n[a](SPEC.md:7)\n")
        self.assertEqual(broken, [])

    def test_specificity_counts_folders_not_the_double_star(self):
        def kind(places, rel):
            return d.kind_of({"places": places}, rel)
        self.assertEqual(kind({"raiz": ["*.md"], "outros": ["**/*.md"]}, "README.md"), "raiz")
        self.assertEqual(kind({"outros": ["**/*.md"], "raiz": ["*.md"]}, "README.md"), "outros")  # tie: first listed
        self.assertEqual(kind({"arquivo": ["docs/old/**"], "vigente": ["**/CHANGELOG.md"]}, "docs/old/CHANGELOG.md"),
                         "arquivo")
        self.assertEqual(kind({"vigente": ["docs/**"], "arquivo": ["docs/historico/**"]}, "docs/historico/a.md"),
                         "arquivo")

    def test_policy_values_of_the_wrong_type_are_invalid(self):
        base = {"schema_version": 1, "places": {"v": ["*.md"]}}
        for bad in ({"limits": []}, {"limits": ""}, {"limits": 0}, {"limits": {"state": True}}, {"indexed": [["v"]]}):
            self.write(".harness/docs-policy.json", json.dumps({**base, **bad}))
            result = d.run_verify(self.repo)
            self.assertEqual((result["status"], result["reason"]), ("FAIL", "PLANTA_INVALIDA"), bad)

    def test_plan_without_policy_also_groups_by_first_folder_for_big_repositories(self):
        for rel in ("packages/a/README.md", "packages/b/README.md", "docs/x.md"):
            self.write(rel)
        self.commit()
        self.assertEqual(d.run_plan(self.repo)["md_by_top"], {"docs": 1, "packages": 2})

    def test_without_policy_the_result_is_null_not_zero_nor_error(self):
        self.write("x.md")
        self.commit()
        result = d.run_verify(self.repo)
        self.assertIsNone(result["status"])
        self.assertEqual(result["reason"], "SEM_PLANTA")
        self.assertIn("docs-plan", result["next"])

    def test_policy_and_everything_within_limits_passes(self):
        self.with_policy()
        result = d.run_verify(self.repo)
        self.assertEqual(result["status"], "PASS", result["problems"])
        self.assertEqual(result["budget"]["state"]["pct"], 7)  # 7 of 100 bytes
        self.assertEqual(result["problems"], [])

    def test_legacy_problems_fail_even_without_a_new_change(self):
        # check() lets legacy pass on purpose; verify() is the full inspection the cleanup starts from.
        self.with_policy()
        self.write("docs/ESTADO.md", "e" * 150)
        self.write("RELATORIO_ANTIGO.md")
        self.write("docs/INDICE.md", "[spec](SPEC.md)\n[some](SUMIU.md)\n")
        self.commit()
        self.assertEqual(d.run_check(self.repo, d.load_policy(self.repo))["status"], "DOCS_CHECK_PASS")
        result = d.run_verify(self.repo)
        self.assertEqual(result["status"], "FAIL")
        text = "\n".join(result["problems"])
        self.assertIn("state: docs/ESTADO.md tem 150 bytes, teto 100", text)
        self.assertIn("fora da planta: RELATORIO_ANTIGO.md", text)
        self.assertIn("link quebrado: SUMIU.md", text)
        self.assertEqual(text.count("SUMIU.md"), 1)  # listed once, not again by the change check

    def test_pending_change_in_the_working_tree_fails(self):
        self.with_policy()
        self.write("SOLTO.md")
        self.assertIn("SOLTO.md: regra lugar", "\n".join(d.run_verify(self.repo)["problems"]))

    def test_missing_state_file_is_a_note_not_a_failure(self):
        self.with_policy()
        (self.repo / "docs/ESTADO.md").unlink()
        self.commit()
        result = d.run_verify(self.repo)
        self.assertEqual(result["status"], "PASS", result["problems"])
        self.assertIn("state: docs/ESTADO.md ainda não existe", result["notes"])

    def test_staged_md_outside_the_policy_is_listed_once(self):
        self.with_policy()
        self.write("SOLTO.md")
        git(self.repo, "add", "SOLTO.md")
        problems = d.run_verify(self.repo)["problems"]
        self.assertEqual(sum("SOLTO.md" in p for p in problems), 1, problems)

    def test_invalid_policy_fails_with_reason(self):
        self.write(".harness/docs-policy.json", "{nao e json")
        self.commit()
        result = d.run_verify(self.repo)
        self.assertEqual((result["status"], result["reason"]), ("FAIL", "PLANTA_INVALIDA"))

    def test_cli_verify_exit_codes(self):
        def run():
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = d.main(["verify", "--repo", str(self.repo)])
            return code, json.loads(out.getvalue())
        self.write("a.txt")
        self.commit()
        code, result = run()
        self.assertEqual((code, result["status"], result["reason"]), (0, None, "SEM_PLANTA"))
        self.with_policy()
        self.assertEqual(run()[0], 0)
        self.write("SOLTO.md")
        self.assertEqual(run()[0], 1)


class HookTests(GateCase):
    def pre(self, tool, tool_input, cwd=None):
        return d.hook({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input,
                       "cwd": str(cwd or self.repo)})

    def test_repo_without_policy_is_inert(self):
        self.write("a.txt")
        self.commit()
        self.assertIsNone(self.pre("Write", {"file_path": str(self.repo / "SOLTO.md"), "content": "x"}))
        self.assertIsNone(d.hook({"hook_event_name": "Stop", "cwd": str(self.repo)}))

    def test_outside_any_repository_is_inert(self):
        with tempfile.TemporaryDirectory() as out:
            self.assertIsNone(self.pre("Write", {"file_path": str(Path(out) / "x.md"), "content": "x"}, out))

    def test_claude_write_in_wrong_place_denied_with_right_path(self):
        self.with_policy()
        answer = self.pre("Write", {"file_path": str(self.repo / "RELATORIO.md"), "content": "x"})
        out = answer["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "deny"))
        self.assertIn("RELATORIO.md: regra lugar", out["permissionDecisionReason"])
        self.assertIn("docs/runs/**", out["permissionDecisionReason"])
        self.assertIsNone(self.pre("Write", {"file_path": str(self.repo / "docs/runs/r.md"), "content": "x"}))
        self.assertIsNone(self.pre("Write", {"file_path": str(self.repo / "app.py"), "content": "x"}))

    @unittest.skipUnless(sys.platform == "win32", "8.3 short names exist only on Windows")
    def test_short_8dot3_path_is_still_inside_the_repository(self):
        # PR #17 regression: the windows-latest runner's temp is C:\Users\RUNNER~1\...; git reports the long
        # path, so a text-only comparison put every file "outside" and the hook stayed silent.
        import ctypes
        long_dir = self.repo.parent / "repositorio-com-nome-bem-longo"
        long_dir.mkdir()
        buf = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetShortPathNameW(str(long_dir), buf, 1024)
        if buf.value.lower() == str(long_dir).lower():
            self.skipTest("8.3 names disabled on this volume")
        self.repo = long_dir
        git(self.repo, "init", "--quiet")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "t")
        self.with_policy()
        short = Path(buf.value)
        answer = self.pre("Write", {"file_path": str(short / "RELATORIO.md"), "content": "x"}, short)
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("RELATORIO.md: regra lugar", answer["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertIsNone(self.pre("Write", {"file_path": str(short / "docs/runs/r.md"), "content": "x"}, short))

    def test_claude_edit_growth_over_limit_denied(self):
        self.with_policy()
        path = str(self.repo / "docs/ESTADO.md")
        self.assertIsNotNone(self.pre("Edit", {"file_path": path, "old_string": "estado", "new_string": "e" * 200}))
        self.assertIsNone(self.pre("Edit", {"file_path": path, "old_string": "estado", "new_string": "curto"}))

    def test_codex_apply_patch(self):
        self.with_policy()
        add = "*** Begin Patch\n*** Add File: NOTAS.md\n+oi\n*** End Patch\n"
        answer = self.pre("apply_patch", {"command": add})
        self.assertEqual(answer["hookSpecificOutput"]["permissionDecision"], "deny")
        ok = "*** Begin Patch\n*** Add File: docs/runs/r.md\n+oi\n*** End Patch\n"
        self.assertIsNone(self.pre("apply_patch", {"command": ok}))
        grow = "*** Begin Patch\n*** Update File: docs/ESTADO.md\n@@\n-estado\n+" + "e" * 200 + "\n*** End Patch\n"
        self.assertIn("orcamento", self.pre("apply_patch", {"command": grow})["hookSpecificOutput"]
                      ["permissionDecisionReason"])
        move = "*** Begin Patch\n*** Update File: docs/SPEC.md\n*** Move to: SPEC.md\n*** End Patch\n"
        self.assertIsNotNone(self.pre("apply_patch", {"command": move}))
        delete = "*** Begin Patch\n*** Delete File: docs/SPEC.md\n*** End Patch\n"
        self.assertIsNone(self.pre("apply_patch", {"command": delete}))

    def test_codex_patch_counts_lines_that_start_with_dashes(self):
        # Review #2: apply_patch has no ---/+++ headers; a removed Markdown rule "---" is the line "----".
        changes = d.patch_changes("*** Begin Patch\n*** Update File: a.md\n@@\n----\n-texto\n*** End Patch\n",
                                  self.repo)
        self.assertEqual(changes[0][2], -4 - 6)
        self.assertEqual(d.patch_changes("*** Add File: b.md\n+++\n", self.repo)[0][2], 3)
        self.with_policy()
        self.write("docs/ESTADO.md", "---\n" + "e" * 120 + "\n")
        self.commit()  # already above the limit of 100
        # Removes "---" (4 bytes) and adds "x" (2 bytes): the file shrinks, so it must be allowed.
        trim = "*** Begin Patch\n*** Update File: docs/ESTADO.md\n@@\n----\n+x\n e" + "e" * 119 + "\n*** End Patch\n"
        self.assertIsNone(self.pre("apply_patch", {"command": trim}))

    def test_new_folder_in_another_repository_is_checked(self):
        # Review #6: the file's own repository counts, even when its folder does not exist yet.
        self.with_policy()
        with tempfile.TemporaryDirectory() as elsewhere:
            target = self.repo / "docs/novo/fundo/RELATORIO.md"
            answer = self.pre("Write", {"file_path": str(target), "content": "x"}, elsewhere)
            self.assertIsNotNone(answer)
            self.assertIn("docs/novo/fundo/RELATORIO.md", answer["hookSpecificOutput"]["permissionDecisionReason"])

    def test_stop_ignores_files_from_before_the_session(self):
        # Review #4: a stray .md already in the tree does not force a continuation on every Codex turn.
        self.with_policy()
        os.utime(self.write("ANTIGO.md"), (1_000_000, 1_000_000))
        event = {"hook_event_name": "Stop", "cwd": str(self.repo), "stop_hook_active": False}
        with unittest.mock.patch.object(d, "session_start", return_value=2_000_000):
            self.assertIsNone(d.hook(event))
            self.write("NOVO.md")
            self.assertIn("NOVO.md", d.hook(event)["reason"])
            self.assertNotIn("ANTIGO.md", d.hook(event)["reason"])
        self.assertIsNone(d.session_start({"transcript_path": str(self.repo / "nao-existe.jsonl")}))

    def test_stop_blocks_once(self):
        self.with_policy()
        self.write("SOLTO.md")
        answer = d.hook({"hook_event_name": "Stop", "cwd": str(self.repo), "stop_hook_active": False})
        self.assertEqual(answer["decision"], "block")
        self.assertIn("SOLTO.md", answer["reason"])
        self.assertIsNone(d.hook({"hook_event_name": "Stop", "cwd": str(self.repo), "stop_hook_active": True}))

    def test_hook_process_never_breaks_session(self):
        script = str(ROOT / "scripts/docs_gate.py")
        for stdin in (b"not json", b"[]", b'{"hook_event_name":"PreToolUse","tool_name":"Write"}'):
            out = subprocess.run([sys.executable, script, "hook"], input=stdin, capture_output=True, timeout=60)
            self.assertEqual((out.returncode, out.stdout), (0, b""), out.stderr)

    def test_hook_process_denies_via_stdout_json(self):
        self.with_policy()
        event = {"hook_event_name": "PreToolUse", "tool_name": "Write", "cwd": str(self.repo),
                 "tool_input": {"file_path": str(self.repo / "X.md"), "content": "x"}}
        out = subprocess.run([sys.executable, str(ROOT / "scripts/docs_gate.py"), "hook", "--tool", "claude"],
                             input=json.dumps(event).encode(), capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")


class HookInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.engine = self.home / ".harness-engineering/current/scripts/docs_gate.py"
        self.engine.parent.mkdir(parents=True)
        self.engine.write_text("# engine\n", encoding="utf-8")
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        self.user_hook = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "node meu-hook.mjs"}]}]}, "model": "opus"}
        self.claude = self.home / ".claude/settings.json"
        self.claude.write_text(json.dumps(self.user_hook), encoding="utf-8")
        self.codex = self.home / ".codex/hooks.json"

    def admin(self, action, apply=False, python=None):
        return d.hook_admin(action, self.home, None, apply, python or Path(sys.executable))

    def installed_command(self):
        return json.loads(self.claude.read_text(encoding="utf-8"))["hooks"]["Stop"][0]["hooks"][0]["command"]

    def test_installed_command_runs_in_the_hook_shells(self):
        # Review #1: a quoted first word is a string in PowerShell, so the hook failed on every call.
        engine = ROOT / "scripts/docs_gate.py"
        d.hook_admin("hook-install", self.home, engine, True, Path(sys.executable))
        command = self.installed_command()
        self.assertFalse(command.startswith('"'), command)
        shells = [["powershell", "-NoProfile", "-NonInteractive", "-Command"], ["cmd", "/c"]] if sys.platform == "win32" \
            else [["sh", "-c"]]
        for shell in shells:
            out = subprocess.run([*shell, command], input=b'{"hook_event_name":"Stop","cwd":"."}',
                                 capture_output=True, timeout=60)
            self.assertEqual(out.returncode, 0, (shell[0], out.stderr.decode(errors="replace")))

    def test_path_with_spaces_is_made_safe_or_refused(self):
        spaced = self.home / "pasta com espaco" / "python.exe"
        spaced.parent.mkdir()
        spaced.write_bytes(b"")
        if sys.platform == "win32":
            try:
                word = d.shell_path(spaced)
            except d.PolicyError as exc:
                self.assertIn("BLOCKED_PATH_WITH_SPACES", str(exc))
            else:
                self.assertNotIn(" ", word)
        else:
            self.assertEqual(d.shell_path(spaced), "'" + spaced.as_posix() + "'")

    def test_verify_ignores_order_of_user_hooks_added_later(self):
        # Review #7: a hook the user appends after ours is not "stale".
        self.admin("hook-install", apply=True)
        config = json.loads(self.claude.read_text(encoding="utf-8"))
        config["hooks"]["PreToolUse"].append({"matcher": "Read", "hooks": [{"type": "command", "command": "x"}]})
        config["hooks"]["Stop"].insert(0, {"hooks": [{"type": "command", "command": "y"}]})
        self.claude.write_text(json.dumps(config), encoding="utf-8")
        self.assertEqual(self.admin("hook-verify")["status"], "HOOK_FILES_OK_RUNTIME_NOT_VERIFIED")
        self.assertEqual(self.admin("hook-remove", apply=True)["status"], "HOOK_REMOVED")
        left = json.loads(self.claude.read_text(encoding="utf-8"))["hooks"]
        self.assertEqual([g["hooks"][0]["command"] for g in left["Stop"]], ["y"])

    def test_virtualenv_python_refused_and_missing_python_reported(self):
        # Review #8: the hook pins an interpreter; a venv or a removed Python turns it off silently.
        with unittest.mock.patch.object(d.sys, "prefix", "/venv"), \
                unittest.mock.patch.object(d.sys, "base_prefix", "/usr"):
            with self.assertRaisesRegex(d.PolicyError, "BLOCKED_VENV_PYTHON"):
                d.hook_admin("hook-plan", self.home, None, False)
        gone = self.home / "python-que-sumiu.exe"
        with self.assertRaisesRegex(d.PolicyError, "BLOCKED_PYTHON_MISSING"):
            self.admin("hook-plan", python=gone)
        gone.write_bytes(b"")
        self.admin("hook-install", apply=True, python=gone)
        gone.unlink()
        self.assertEqual(self.admin("hook-verify", python=gone)["status"], "HOOK_BROKEN_MISSING_TARGET")

    def test_config_folder_that_is_a_link_is_refused(self):
        # Review #9: same link test as the machine installer (symlink or junction).
        real = self.home / "codex-real"
        real.mkdir()
        (self.home / ".codex").rmdir()
        if sys.platform == "win32":
            subprocess.run(["cmd", "/c", "mklink", "/J", str(self.home / ".codex"), str(real)],
                           check=True, capture_output=True)
        else:
            os.symlink(real, self.home / ".codex")
        with self.assertRaisesRegex(d.PolicyError, "BLOCKED_LINK"):
            self.admin("hook-install", apply=True)
        self.assertEqual(list(real.iterdir()), [])

    def test_plan_writes_nothing(self):
        before = self.claude.read_bytes()
        result = self.admin("hook-plan")
        self.assertEqual((result["status"], result["writes"]), ("PLANNED_NOT_INSTALLED", 0))
        self.assertEqual(self.claude.read_bytes(), before)
        self.assertFalse(self.codex.exists())
        self.assertEqual(self.admin("hook-install")["status"], "PLANNED_NOT_INSTALLED")  # no --apply
        self.assertFalse(self.codex.exists())

    def test_install_verify_remove_keeps_user_hooks(self):
        result = self.admin("hook-install", apply=True)
        self.assertEqual(result["status"], "HOOK_INSTALLED_RUNTIME_NOT_VERIFIED")
        self.assertIn("/hooks", result["next"])
        claude = json.loads(self.claude.read_text(encoding="utf-8"))
        self.assertEqual(claude["model"], "opus")
        self.assertEqual(claude["hooks"]["PreToolUse"][0], self.user_hook["hooks"]["PreToolUse"][0])
        self.assertEqual(claude["hooks"]["PreToolUse"][1]["matcher"], "Write|Edit|MultiEdit")
        self.assertIn(d.MARKER, claude["hooks"]["Stop"][0]["hooks"][0]["command"])
        codex = json.loads(self.codex.read_text(encoding="utf-8"))
        self.assertEqual(codex["hooks"]["PreToolUse"][0]["matcher"], "apply_patch")
        self.assertEqual(self.admin("hook-verify")["status"], "HOOK_FILES_OK_RUNTIME_NOT_VERIFIED")
        self.admin("hook-install", apply=True)  # idempotent
        self.assertEqual(len(json.loads(self.claude.read_text(encoding="utf-8"))["hooks"]["Stop"]), 1)
        self.assertEqual(self.admin("hook-remove")["status"], "PLANNED_REMOVAL")
        self.assertTrue(self.codex.exists())
        self.assertEqual(self.admin("hook-remove", apply=True)["status"], "HOOK_REMOVED")
        self.assertEqual(json.loads(self.claude.read_text(encoding="utf-8")), self.user_hook)
        self.assertFalse(self.codex.exists())  # created by the Harness, removed with it
        self.assertEqual(self.admin("hook-verify")["status"], "HOOK_NOT_INSTALLED")

    def test_only_detected_tools(self):
        (self.home / ".codex").rmdir()
        rows = {r["tool"]: r["status"] for r in self.admin("hook-install", apply=True)["tools"]}
        self.assertEqual(rows, {"claude": "INSTALLED", "codex": "NOT_DETECTED"})
        self.assertFalse((self.home / ".codex").exists())

    def test_blocks_without_engine_or_with_invalid_config(self):
        self.engine.unlink()
        with self.assertRaisesRegex(d.PolicyError, "BLOCKED_ENGINE_MISSING"):
            self.admin("hook-plan")
        self.engine.write_text("# engine\n", encoding="utf-8")
        before = b"{ nao e json"
        self.claude.write_bytes(before)
        with self.assertRaisesRegex(d.PolicyError, "BLOCKED_INVALID_CONFIG"):
            self.admin("hook-install", apply=True)
        self.assertEqual(self.claude.read_bytes(), before)

    def test_harnessctl_dispatches_docs_commands(self):
        out = subprocess.run([sys.executable, str(ROOT / "scripts/harnessctl.py"), "docs-hook-plan",
                              "--home", str(self.home)], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["status"], "PLANNED_NOT_INSTALLED")


class ThisRepositoryTests(unittest.TestCase):
    def test_this_repository_policy_is_valid_and_within_budget(self):
        policy = d.load_policy(ROOT)
        self.assertIsNotNone(policy)
        for role in d.ROLES:
            rel = policy.get(role)
            if rel:
                self.assertLessEqual(d.disk_size(ROOT / rel), policy["limits"][role], rel)
        _, broken = d.index_links(ROOT, policy["index"], (ROOT / policy["index"]).read_text(encoding="utf-8"))
        self.assertEqual(broken, [])

    def test_action_calls_the_engine(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/docs_gate.py", text)
        self.assertIn("check", text)


if __name__ == "__main__":
    unittest.main()
