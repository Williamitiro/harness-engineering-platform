"""R1 project lifecycle: real Git fixtures, pinned synthetic source, no models."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_lifecycle", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class ProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / "external project"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet")
        self.source = self.root / "ecc"
        self.source.mkdir()
        hashes = {}
        for name in sorted(h.ALLOWED):
            file = self.source / "skills" / name / "SKILL.md"
            file.parent.mkdir(parents=True)
            file.write_bytes(f"---\nname: {name}\ndescription: fixture\n---\n".encode())
            hashes[name] = h.digest(file.read_bytes())
        (self.source / "LICENSE").write_bytes(b"MIT License\nCopyright fixture\n")
        git(self.source, "init", "--quiet")
        git(self.source, "config", "core.autocrlf", "false")
        git(self.source, "add", ".")
        git(self.source, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture")
        self.manifest = {"schema_version": 1, "ecc": {
            "commit": git(self.source, "rev-parse", "HEAD"), "skills": hashes,
            "license_sha256": h.digest((self.source / "LICENSE").read_bytes())}}

    def attach(self):
        return h.attach_project(self.repo, self.source, self.manifest)

    def snapshot(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob("*") if p.is_file()}

    def test_attach_reapply_verify_remove_exact_with_preexisting_dirs(self):
        (self.repo / ".agents/skills").mkdir(parents=True)
        (self.repo / "keep.txt").write_text("existing work")
        before = self.snapshot()
        result = self.attach()
        self.assertEqual(result["status"], "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
        after = self.snapshot()
        self.assertEqual(self.attach()["status"], "ALREADY_ATTACHED")
        self.assertEqual(after, self.snapshot())
        record = h.verify_project(self.repo, self.manifest)
        self.assertEqual(len(record["files"]), 3)
        self.assertIn("MIT License", record["license_notice"])
        h.remove_project(self.repo, self.manifest)
        self.assertEqual(before, self.snapshot())
        self.assertTrue((self.repo / ".agents/skills").is_dir())
        self.assertFalse((self.repo / ".harness").exists())
        self.assertEqual(h.remove_project(self.repo, self.manifest)["status"], "ALREADY_REMOVED")

    def test_existing_contract_and_unrelated_skill_block_without_writes(self):
        for rel in ("AGENTS.md", ".agents/skills/third-party/SKILL.md"):
            file = self.repo / rel
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("preserve")
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            self.attach()
        self.assertEqual(before, self.snapshot())

    def test_modified_missing_or_forged_record_prevents_partial_remove(self):
        self.attach()
        record_file = self.repo / ".harness/manifest.json"
        original_record = record_file.read_bytes()
        owned = self.repo / "AGENTS.md"
        original = owned.read_bytes()
        for modification in ("changed", "missing", "traversal", "hash", "dirs", "pin"):
            with self.subTest(modification=modification):
                record_file.write_bytes(original_record)
                owned.write_bytes(original)
                record = json.loads(original_record)
                if modification == "changed":
                    owned.write_text("human edit")
                elif modification == "missing":
                    owned.unlink()
                elif modification == "traversal":
                    record["files"][0]["path"] = "../private"
                elif modification == "hash":
                    record["files"][0]["sha256"] = "0" * 64
                elif modification == "dirs":
                    record["created_dirs"].append(".git")
                else:
                    record["ecc_commit"] = "0" * 40
                if modification not in ("changed", "missing"):
                    record_file.write_text(json.dumps(record))
                before = self.snapshot()
                with self.assertRaises(h.GateError):
                    h.remove_project(self.repo, self.manifest)
                self.assertEqual(before, self.snapshot())

    def test_partial_install_failure_rolls_back_only_created_paths(self):
        before = self.snapshot()
        real = Path.open
        def fail_manifest(path, mode="r", *args, **kwargs):
            if path == self.repo / ".harness/manifest.json" and mode == "xb":
                raise OSError("simulated disk error")
            return real(path, mode, *args, **kwargs)
        with patch.object(Path, "open", fail_manifest), self.assertRaises(OSError):
            self.attach()
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.repo / ".agents").exists())
        self.assertFalse((self.repo / ".harness").exists())

    def test_fake_git_marker_refused_before_any_write(self):
        fake = self.root / "not-a-repository"
        (fake / ".git").mkdir(parents=True)
        with self.assertRaises(h.GateError):
            h.attach_project(fake, self.source, self.manifest)
        self.assertFalse((fake / "AGENTS.md").exists())

    def test_wrong_source_or_license_refused(self):
        before = self.snapshot()
        self.manifest["ecc"]["license_sha256"] = "0" * 64
        with self.assertRaises(h.GateError):
            self.attach()
        self.assertEqual(before, self.snapshot())

    def test_destination_symlink_and_hardlink_refused(self):
        self.attach()
        owned = self.repo / "AGENTS.md"
        original = owned.read_bytes()
        private = self.root / "private"
        private.write_text("DO_NOT_READ")
        owned.unlink()
        try:
            os.symlink(private, owned)
        except OSError:
            owned.write_bytes(original)
            self.skipTest("symlink unavailable")
        with self.assertRaises(h.GateError):
            h.verify_project(self.repo, self.manifest)
        owned.unlink()
        os.link(private, owned)
        with self.assertRaises(h.GateError):
            h.verify_project(self.repo, self.manifest)
        self.assertEqual(private.read_text(), "DO_NOT_READ")

    def test_remove_preserves_new_unowned_files(self):
        self.attach()
        other = self.repo / ".agents/skills/tdd-workflow/notes.txt"
        other.write_text("new work")
        h.remove_project(self.repo, self.manifest)
        self.assertEqual(other.read_text(), "new work")

    def test_partial_removal_failure_restores_original_bytes(self):
        self.attach()
        before = self.snapshot()
        real = Path.unlink
        def fail_second(path, *args, **kwargs):
            if path == self.repo / ".agents/skills/tdd-workflow/SKILL.md":
                raise OSError("simulated removal failure")
            return real(path, *args, **kwargs)
        with patch.object(Path, "unlink", fail_second), self.assertRaises(OSError):
            h.remove_project(self.repo, self.manifest)
        self.assertEqual(before, self.snapshot())

    def test_cli_requires_apply_and_removal_preview_is_read_only(self):
        before = self.snapshot()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = h.main(["project-attach", "--repo", str(self.repo), "--client", "codex", "--source", str(self.source)])
        self.assertEqual(code, 2)
        self.assertEqual(before, self.snapshot())
        self.attach()
        before = self.snapshot()
        with patch.object(h, "read_manifest", return_value=self.manifest), contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(h.main(["project-remove", "--repo", str(self.repo)]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "PLANNED_NOT_REMOVED")
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
