"""HE-OP-01: external fixtures, metadata only, no installer or runtime."""
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
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_project", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class ProjectInspectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "external repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.repo)], check=True)

    def cli(self, action="project-plan", *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = h.main([action, "--repo", str(self.repo), "--client", "codex", *extra])
        return code, json.loads(out.getvalue() or err.getvalue())

    def test_external_repo_plan_is_repeatable_and_read_only(self):
        before = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*"))
        code, plan = self.cli()
        self.assertEqual(code, 0)
        self.assertEqual(plan["status"], "PLANNED_NOT_INSTALLED")
        self.assertEqual({c["path"] for c in plan["changes"]}, {
            "AGENTS.md", ".agents/skills/tdd-workflow/SKILL.md",
            ".agents/skills/verification-loop/SKILL.md", ".harness/manifest.json"})
        self.assertEqual(plan["runtime_discovery"], "NOT_RUN")
        self.assertEqual(self.cli()[1], plan)
        self.assertEqual(before, sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*")))

    def test_doctor_reports_static_compatibility_only(self):
        code, result = self.cli("project-doctor")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "COMPATIBLE_NOT_RUNTIME_VERIFIED")
        self.assertEqual(result["compatibility"]["client_runtime"], "NOT_PROBED")
        self.assertEqual(result["compatibility"]["repository"], "GIT_MARKER_ONLY")

    def test_existing_contract_skills_and_state_block_without_reading_contents(self):
        for rel in ("AGENTS.md", ".agents/skills/third-party/SKILL.md", ".harness/manifest.json", h.STATE):
            p = self.repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("PRIVATE_CANARY_DO_NOT_READ")
        (self.repo / ".env").write_text("PRIVATE_CANARY_DO_NOT_READ")
        # Only Harness's own allowlist is read. No target file or Git config is opened.
        original = Path.open
        def guard(path, *args, **kwargs):
            if path.is_relative_to(self.repo):
                raise AssertionError("target contents accessed")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guard), patch.object(h.subprocess, "run", side_effect=AssertionError("process spawned")):
            code, result = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "BLOCKED_COLLISION")
        self.assertEqual({b["path"] for b in result["blockers"]}, {
            "AGENTS.md", ".agents/skills", ".harness", ".harness/manifest.json", h.STATE})
        self.assertNotIn("PRIVATE_CANARY", json.dumps(result))
        self.assertTrue(any(c["action"] == "BLOCKED_COLLISION" for c in result["changes"]))

    def test_file_in_parent_path_blocks(self):
        (self.repo / ".agents").write_text("keep")
        code, result = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "BLOCKED_COLLISION")
        self.assertEqual((self.repo / ".agents").read_text(), "keep")

    def test_empty_skill_directory_and_other_client_contract_preserved(self):
        (self.repo / ".agents/skills").mkdir(parents=True)
        (self.repo / "CLAUDE.md").write_text("private existing contract")
        self.assertEqual(self.cli()[0], 0)
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), "private existing contract")

    def test_git_marker_symlink_refused(self):
        # Replace the empty Git fixture with a separate structural fixture.
        root = self.repo.parent / "linked-marker"
        root.mkdir()
        try:
            os.symlink(self.repo / ".git", root / ".git", target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks not permitted")
        with self.assertRaises(h.GateError):
            h.inspect_project(root, "codex")

    def test_arbitrary_directory_missing_and_traversal_paths_refused(self):
        for target in (self.repo.parent, self.repo / "missing", Path("relative"), self.repo / ".." / self.repo.name):
            with self.subTest(target=target):
                with contextlib.redirect_stderr(io.StringIO()) as err:
                    code = h.main(["project-plan", "--repo", str(target), "--client", "codex"])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(err.getvalue())["status"], "BLOCKED")

    def test_explicit_relative_repo_from_spec_is_read_only(self):
        before = sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*"))
        for action in ("project-doctor", "project-plan"):
            with self.subTest(action=action):
                result = subprocess.run(
                    [sys.executable, str(ROOT / "scripts/harnessctl.py"), action,
                     "--repo", ".", "--client", "codex"], cwd=self.repo,
                    capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                report = json.loads(result.stdout)
                self.assertEqual(Path(report["repo"]), self.repo)
                self.assertTrue(report["read_only"])
        self.assertEqual(before, sorted(p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*")))

    def test_worktree_git_file_is_not_opened(self):
        # Structural worktree fixture; Git resolution intentionally NOT_RUN.
        other = self.repo.parent / "worktree"
        other.mkdir()
        (other / ".git").write_text("gitdir: PRIVATE_CANARY")
        with patch.object(Path, "open", side_effect=AssertionError("content read")):
            result = h.inspect_project(other, "codex")
        self.assertEqual(result["status"], "COMPATIBLE_NOT_RUNTIME_VERIFIED")

    def test_symlink_root_ancestor_git_and_destination_refused(self):
        for rel in ("linked-root", "AGENTS.md", ".agents", ".harness", ".git-link"):
            with self.subTest(rel=rel):
                link = self.repo / rel
                try:
                    os.symlink(self.repo.parent, link, target_is_directory=True)
                except OSError:
                    self.skipTest("Symlinks not permitted")
                try:
                    target = link / self.repo.name if rel == "linked-root" else self.repo
                    if rel == ".git-link":
                        with self.assertRaises(h.GateError):
                            h.assert_no_symlink(link)
                    elif rel == "linked-root":
                        with self.assertRaises(h.GateError):
                            h.inspect_project(target, "codex")
                    else:
                        self.assertEqual(self.cli()[1]["status"], "BLOCKED_PATH")
                finally:
                    link.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows junction")
    def test_junction_destination_refused(self):
        link = self.repo / ".agents"
        # Explicit directory junction fixture; no shell or deletion helpers.
        import _winapi
        _winapi.CreateJunction(str(self.repo.parent), str(link))
        try:
            self.assertEqual(self.cli()[1]["status"], "BLOCKED_PATH")
        finally:
            link.rmdir()

    def test_project_options_never_enable_writes_or_claude(self):
        for extra in (("--apply",), ("--client", "claude"), ("--source", str(self.repo)), ("--target", str(self.repo))):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as ctx:
                    self.cli("project-plan", *extra)
                self.assertEqual(ctx.exception.code, 2)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                h.main(["project-plan", "--client", "codex"])

    def test_cli_subprocess_json_and_no_secret_output(self):
        (self.repo / ".env").write_text("PRIVATE_CANARY")
        p = subprocess.run([sys.executable, str(ROOT / "scripts/harnessctl.py"),
                            "project-plan", "--repo", str(self.repo), "--client", "codex"],
                           capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)["status"], "PLANNED_NOT_INSTALLED")
        self.assertNotIn("PRIVATE_CANARY", p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
