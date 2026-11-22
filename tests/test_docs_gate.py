"""HE-DOC-02: document organization gate — three checks, the hook (both tools) and hook install/remove."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

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
        self.assertEqual(self.rules(d.run_check(self.repo, policy)), [("docs/ESTADO.md", "orcamento")])

    def test_file_already_above_limit_cannot_grow_but_may_shrink(self):
        policy = self.with_policy()
        self.write("docs/ESTADO.md", "e" * 300)
        self.commit()  # legacy: already above the limit
        self.write("docs/ESTADO.md", "e" * 250)
        self.assertEqual(d.run_check(self.repo, policy)["status"], "DOCS_CHECK_PASS")
        self.write("docs/ESTADO.md", "e" * 301)
        self.assertEqual(self.rules(d.run_check(self.repo, policy)), [("docs/ESTADO.md", "orcamento")])

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

    def admin(self, action, apply=False):
        return d.hook_admin(action, self.home, None, apply)

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
