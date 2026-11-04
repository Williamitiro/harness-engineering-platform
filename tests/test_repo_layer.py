"""HE-R1-03: repository layer — project rules only; generic skills live on the machine."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_repo", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
AGENTS_TEMPLATE = (ROOT / "templates/repo/AGENTS.md").read_bytes()
CLAUDE_TEMPLATE = (ROOT / "templates/repo/CLAUDE.md").read_bytes()


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class RepoLayerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "projeto"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet")

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): (p.read_bytes() if p.is_file() else None)
                for p in self.repo.rglob("*") if ".git" not in p.relative_to(self.repo).parts}

    def write(self, rel, data=b"projeto\n"):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def actions(self, result):
        return {c["path"]: c["action"] for c in result["changes"]}

    def test_templates_have_fixed_bytes_on_every_machine(self):
        out = git(ROOT, "check-attr", "text", "--", "templates/repo/AGENTS.md", "templates/repo/CLAUDE.md")
        self.assertEqual(out.count("text: unset"), 2, out)
        self.assertNotIn(b"\r\n", AGENTS_TEMPLATE + CLAUDE_TEMPLATE)

    def test_claude_template_imports_agents_md(self):
        self.assertTrue(CLAUDE_TEMPLATE.startswith(b"@AGENTS.md\n"))
        self.assertNotIn(b"/SKILL.md", AGENTS_TEMPLATE)  # skills by name, never repo paths

    def test_new_repo_plan_is_read_only(self):
        before = self.snapshot()
        result = h.repo_inspect(self.repo)
        self.assertEqual(result["case"], "NEW_REPO")
        self.assertEqual(self.actions(result), {"AGENTS.md": "WOULD_CREATE", "CLAUDE.md": "WOULD_CREATE",
                                                ".harness/manifest.json": "WOULD_CREATE"})
        self.assertEqual(before, self.snapshot())

    def test_new_repo_attach_creates_rules_only_and_removes_exactly(self):
        result = h.repo_attach(self.repo)
        self.assertEqual(result["status"], "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
        self.assertEqual(result["created"], ["AGENTS.md", "CLAUDE.md", ".harness/manifest.json"])  # matches the plan
        self.assertEqual((self.repo / "AGENTS.md").read_bytes(), AGENTS_TEMPLATE)
        self.assertEqual((self.repo / "CLAUDE.md").read_bytes(), CLAUDE_TEMPLATE)
        self.assertFalse((self.repo / ".agents").exists())
        self.assertFalse((self.repo / ".claude").exists())
        installed = self.snapshot()
        self.assertEqual(h.repo_attach(self.repo)["status"], "ALREADY_ATTACHED")
        self.assertEqual(installed, self.snapshot())
        self.assertEqual(h.repo_verify(self.repo)["status"], "OK")
        self.assertEqual(h.repo_remove(self.repo, apply=False)["status"], "PLANNED_NOT_REMOVED")
        self.assertEqual(installed, self.snapshot())
        h.repo_remove(self.repo, apply=True)
        self.assertEqual(self.snapshot(), {})

    def test_existing_repo_preserves_rules_and_ignores_third_party_skills(self):
        own = self.write("AGENTS.md", b"regras de CAD do projeto\n")
        self.write(".agents/skills/minha-skill/SKILL.md")
        self.write(".claude/skills/outra/SKILL.md")
        self.write("src/app.py", b"print(1)\n")
        before = self.snapshot()
        plan = h.repo_inspect(self.repo)
        self.assertEqual(plan["case"], "EXISTING_REPO")
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(self.actions(plan)["AGENTS.md"], "PRESERVE")
        h.repo_attach(self.repo)
        self.assertEqual(own.read_bytes(), b"regras de CAD do projeto\n")
        self.assertEqual((self.repo / "CLAUDE.md").read_bytes(), CLAUDE_TEMPLATE)
        h.repo_remove(self.repo, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_existing_claude_md_is_preserved_and_flagged_for_import_check(self):
        self.write("AGENTS.md")
        self.write("CLAUDE.md", b"regras antigas do claude\n")
        plan = h.repo_inspect(self.repo)
        self.assertEqual(self.actions(plan)["CLAUDE.md"], "PRESERVE_CHECK_IMPORT")
        h.repo_attach(self.repo)
        self.assertEqual((self.repo / "CLAUDE.md").read_bytes(), b"regras antigas do claude\n")
        record = json.loads((self.repo / h.PROJECT_STATE).read_text())
        self.assertEqual(record["files"], [])
        self.assertEqual(sorted(record["preserved"]), ["AGENTS.md", "CLAUDE.md"])

    def test_rules_never_read_during_inspection_or_attach(self):
        self.write("AGENTS.md", b"SEGREDO_DO_PROJETO\n")
        rules = self.repo / "AGENTS.md"
        original_open, original_read = Path.open, Path.read_bytes

        def guard(original):
            def wrapper(path, *a, **k):
                if path.absolute() == rules.absolute():
                    raise AssertionError("project rules were read")
                return original(path, *a, **k)
            return wrapper

        with patch.object(Path, "open", guard(original_open)), patch.object(Path, "read_bytes", guard(original_read)):
            h.repo_inspect(self.repo)
            h.repo_attach(self.repo)
            h.repo_verify(self.repo)
            h.repo_remove(self.repo, apply=True)

    def test_edited_created_rules_are_reported_and_kept_on_remove(self):
        h.repo_attach(self.repo)
        (self.repo / "AGENTS.md").write_bytes(b"agora o projeto tem regras proprias\n")
        report = h.repo_verify(self.repo)
        self.assertEqual(report["status"], "OK")
        self.assertEqual(report["files"]["AGENTS.md"], "EDITED_BY_PROJECT")
        self.assertEqual(report["files"]["CLAUDE.md"], "UNCHANGED")
        result = h.repo_remove(self.repo, apply=True)
        self.assertEqual(result["kept"], ["AGENTS.md"])
        self.assertEqual((self.repo / "AGENTS.md").read_bytes(), b"agora o projeto tem regras proprias\n")
        self.assertFalse((self.repo / "CLAUDE.md").exists())
        self.assertFalse((self.repo / ".harness").exists())

    def test_forged_record_cannot_make_remove_delete_project_rules(self):
        h.repo_attach(self.repo)
        own = b"regras do usuario\n"
        (self.repo / "AGENTS.md").write_bytes(own)
        state = self.repo / h.PROJECT_STATE
        record = json.loads(state.read_text())
        for item in record["files"]:
            if item["path"] == "AGENTS.md":
                item["sha256"] = h.digest(own)
        state.write_text(json.dumps(record))
        h.repo_remove(self.repo, apply=True)
        self.assertEqual((self.repo / "AGENTS.md").read_bytes(), own)

    def test_unknown_path_in_record_blocks(self):
        h.repo_attach(self.repo)
        state = self.repo / h.PROJECT_STATE
        record = json.loads(state.read_text())
        record["files"].append({"path": "src/app.py", "sha256": "0" * 64})
        state.write_text(json.dumps(record))
        with self.assertRaises(h.GateError):
            h.repo_verify(self.repo)
        with self.assertRaises(h.GateError):
            h.repo_remove(self.repo, apply=True)

    def test_rules_path_that_is_a_directory_blocks_without_writes(self):
        (self.repo / "AGENTS.md").mkdir()
        before = self.snapshot()
        self.assertEqual(h.repo_inspect(self.repo)["status"], "BLOCKED_COLLISION")
        with self.assertRaises(h.GateError):
            h.repo_attach(self.repo)
        self.assertEqual(before, self.snapshot())

    def test_foreign_harness_dir_blocks(self):
        self.write(".harness/notes.txt")
        with self.assertRaises(h.GateError):
            h.repo_attach(self.repo)
        self.assertFalse((self.repo / "AGENTS.md").exists())

    def test_non_git_directory_refused(self):
        with tempfile.TemporaryDirectory() as plain:
            with self.assertRaises(h.GateError):
                h.repo_inspect(Path(plain))


class LegacyPackageTests(unittest.TestCase):
    """Package 1 installs (skills copied into the repo) stay verifiable and removable."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "legado"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet")
        self.catalog = h.read_manifest(ROOT / "config/approved_skills.json")
        h.attach_project(self.repo, h.VENDORED, self.catalog)

    def test_attach_reports_legacy_without_writes_and_remove_still_works(self):
        before = sorted(p.as_posix() for p in self.repo.rglob("*") if ".git" not in p.parts)
        result = h.repo_attach(self.repo)
        self.assertEqual(result["status"], "LEGACY_ATTACHED")
        self.assertIn("project-remove", result["migration"])
        self.assertEqual(before, sorted(p.as_posix() for p in self.repo.rglob("*") if ".git" not in p.parts))
        self.assertEqual(h.repo_verify(self.repo)["package"], 1)
        h.repo_remove(self.repo, apply=True)
        self.assertFalse((self.repo / ".agents/skills/tdd-workflow").exists())


class RepoCliTests(unittest.TestCase):
    def test_cli_plan_attach_verify_remove_for_both_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            cli = [sys.executable, str(ROOT / "scripts/harnessctl.py")]

            def run(*args):
                return subprocess.run([*cli, *args, "--repo", str(repo)], capture_output=True, text=True)

            self.assertEqual(json.loads(run("project-plan", "--client", "claude").stdout)["status"],
                             "PLANNED_NOT_INSTALLED")
            self.assertEqual(run("project-attach").returncode, 2)  # --apply required
            attach = run("project-attach", "--apply")
            self.assertEqual(attach.returncode, 0, attach.stderr)
            self.assertEqual(json.loads(run("project-verify").stdout)["status"], "OK")
            self.assertEqual(run("project-remove", "--apply").returncode, 0)
            self.assertEqual([p.name for p in repo.iterdir()], [".git"])

    def test_old_setup_skill_command_line_still_works_and_source_is_ignored(self):
        # Exact form used by the installed package-1 setup-harness (until HE-R1-04).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            (repo / "AGENTS.md").write_text("regras")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = h.main(["project-attach", "--repo", str(repo), "--client", "codex",
                               "--source", str(Path(tmp) / "nao-usado"), "--preserve-contract", "--apply"])
            self.assertEqual(code, 0)
            result = json.loads(out.getvalue())
            self.assertIn("--source ignorado", result["deprecated"])
            self.assertFalse((repo / ".agents").exists())
            self.assertEqual((repo / "AGENTS.md").read_text(), "regras")


if __name__ == "__main__":
    unittest.main()
