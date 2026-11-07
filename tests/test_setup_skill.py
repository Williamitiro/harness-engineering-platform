"""Personal bootstrap installation is opt-in and tested in a synthetic home."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_bootstrap", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


class SetupSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)

    def test_plan_install_verify_reapply_remove_both_clients(self):
        for client, base in (("codex", ".agents"), ("claude", ".claude")):
            with self.subTest(client=client):
                plan = h.plan_setup_skill(self.home, client)
                self.assertEqual(plan["status"], "PLANNED_NOT_INSTALLED")
                self.assertFalse((self.home / base).exists())
                result = h.install_setup_skill(self.home, client)
                self.assertEqual(result["runtime_discovery"], "NOT_RUN")
                folder = self.home / base / "skills/setup-harness"
                descriptor = json.loads((folder / "harness-location.json").read_text())
                self.assertEqual(Path(descriptor["harnessctl"]), ROOT / "scripts/harnessctl.py")
                self.assertEqual(descriptor["client"], client)
                self.assertEqual(h.install_setup_skill(self.home, client)["status"], "ALREADY_INSTALLED")
                h.verify_setup_skill(self.home, client)
                before = sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*"))
                h.remove_setup_skill(self.home, client, apply=False)
                self.assertEqual(before, sorted(p.relative_to(self.home).as_posix() for p in self.home.rglob("*")))
                h.remove_setup_skill(self.home, client, apply=True)
                self.assertFalse((self.home / base).exists())

    def test_existing_skill_is_not_owned_even_if_bytes_identical(self):
        folder = self.home / ".agents/skills/setup-harness"
        folder.mkdir(parents=True)
        file = folder / "SKILL.md"
        file.write_bytes((ROOT / "skills/setup-harness/SKILL.md").read_bytes())
        before = file.read_bytes()
        with self.assertRaises(h.GateError):
            h.install_setup_skill(self.home, "codex")
        self.assertEqual(file.read_bytes(), before)
        self.assertFalse((folder / ".harness-bootstrap.json").exists())

    def test_edited_skill_or_descriptor_blocks_removal(self):
        h.install_setup_skill(self.home, "codex")
        folder = self.home / ".agents/skills/setup-harness"
        for filename in ("SKILL.md", "harness-location.json"):
            file = folder / filename
            raw = file.read_bytes()
            file.write_text("human change")
            with self.assertRaises(h.GateError):
                h.remove_setup_skill(self.home, "codex", apply=True)
            self.assertTrue((folder / ".harness-bootstrap.json").exists())
            self.assertEqual(file.read_text(), "human change")
            file.write_bytes(raw)

    def test_global_home_not_touched_without_explicit_apply(self):
        with patch.object(Path, "home", return_value=self.home):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(h.main(["setup-skill-install", "--client", "codex"]), 2)
                self.assertEqual(h.main(["setup-skill-plan", "--client", "codex"]), 0)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_cli_explicit_synthetic_home_roundtrip(self):
        for action, extra in (("setup-skill-install", ["--apply"]),
                              ("setup-skill-verify", []), ("setup-skill-remove", ["--apply"])):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(h.main([action, "--home", str(self.home), "--client", "codex", *extra]), 0)
            self.assertNotIn("PRIVATE", out.getvalue())
        self.assertEqual(list(self.home.iterdir()), [])

    def test_unrelated_user_skills_survive_remove(self):
        other = self.home / ".agents/skills/other/SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("unrelated")
        h.install_setup_skill(self.home, "codex")
        h.remove_setup_skill(self.home, "codex", apply=True)
        self.assertEqual(other.read_text(), "unrelated")

    def test_linked_personal_skill_ancestor_refused(self):
        outside = self.home / "elsewhere"
        outside.mkdir()
        link = self.home / ".agents"
        try:
            os.symlink(outside, link, target_is_directory=True)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaises(h.GateError):
            h.install_setup_skill(self.home, "codex")
        self.assertEqual(list(outside.iterdir()), [])

    def test_failed_personal_install_removes_only_new_files(self):
        real = Path.open
        def fail_state(path, mode="r", *args, **kwargs):
            if path.name == ".harness-bootstrap.json" and mode == "xb":
                raise OSError("simulated disk failure")
            return real(path, mode, *args, **kwargs)
        with patch.object(Path, "open", fail_state), self.assertRaises(OSError):
            h.install_setup_skill(self.home, "codex")
        self.assertEqual(list(self.home.iterdir()), [])

    def test_save_after_bootstrap_verification_is_preserved(self):
        h.install_setup_skill(self.home, "codex")
        skill = self.home / ".agents/skills/setup-harness/SKILL.md"
        real_verify = h.verify_setup_skill
        def save_after_verify(*args):
            record = real_verify(*args)
            skill.write_bytes(b"human edit")
            return record
        with patch.object(h, "verify_setup_skill", side_effect=save_after_verify), self.assertRaises(h.GateError):
            h.remove_setup_skill(self.home, "codex", apply=True)
        self.assertEqual(skill.read_bytes(), b"human edit")
        self.assertTrue((skill.parent / ".harness-bootstrap.json").is_file())

    def test_failed_personal_directory_cleanup_keeps_removal_retryable(self):
        h.install_setup_skill(self.home, "codex")
        before = {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        real_rmdir = Path.rmdir
        def fail_namespace(path, *args, **kwargs):
            if path == self.home / ".agents":
                raise PermissionError("directory busy")
            return real_rmdir(path, *args, **kwargs)
        with patch.object(Path, "rmdir", fail_namespace), self.assertRaises(PermissionError):
            h.remove_setup_skill(self.home, "codex", apply=True)
        self.assertEqual(before, {p.relative_to(self.home): p.read_bytes() for p in self.home.rglob("*") if p.is_file()})
        h.verify_setup_skill(self.home, "codex")
        h.remove_setup_skill(self.home, "codex", apply=True)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
