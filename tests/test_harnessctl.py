import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl", ROOT / "scripts" / "harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


@unittest.skipUnless(shutil.which("git"), "Git not installed")
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".poc").mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / ".poc")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source = root / "ecc"
        self.source.mkdir()
        self.target = root / ".poc" / "disposable-a1"
        self.target.mkdir(parents=True)
        checksums = {}
        for name in sorted(h.ALLOWED):
            path = self.source / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            body = f"---\nname: {name}\ndescription: pilot\n---\n".encode()
            path.write_bytes(body)
            checksums[name] = hashlib.sha256(body).hexdigest()
        def git(*args):
            result = subprocess.run(["git", "-C", str(self.source), *args],
                                    capture_output=True, text=True, check=True)
            return result.stdout.strip()
        git("init")
        git("-c", "user.name=Harness Test", "-c", "user.email=harness@example.invalid",
            "add", ".")
        git("-c", "user.name=Harness Test", "-c", "user.email=harness@example.invalid",
            "commit", "-m", "fixture")
        self.manifest = {"schema_version": 1, "ecc": {"commit": git("rev-parse", "HEAD"),
                        "skills": checksums}}

    def test_plan_is_read_only_and_pinned(self):
        p = h.plan(self.source, self.target, "codex", self.manifest)
        self.assertEqual(p["status"], "PLANNED_NOT_INSTALLED")
        self.assertEqual(len(p["changes"]), 2)
        self.assertFalse((self.target / h.STATE).exists())

    def test_install_verify_remove_exact_roundtrip(self):
        p = h.plan(self.source, self.target, "claude", self.manifest)
        h.install(p, self.target)
        rec, paths = h.record_and_paths(self.target)
        self.assertEqual(rec["runtime_status"], "NOT_RUN")
        self.assertEqual(len(paths), 2)
        h.remove(self.target)
        self.assertFalse((self.target / h.STATE).exists())
        self.assertFalse(any(self.target.rglob("SKILL.md")))
        # Ensure no empty adapter directory is orphaned
        self.assertFalse((self.target / ".claude").exists())

    def test_exact_roundtrip_cleans_empty_adapter_directories(self):
        for adapter, dir_name in (("codex", ".agents"), ("claude", ".claude")):
            target = Path(self.tmp.name) / ".poc" / f"roundtrip-{adapter}"
            target.mkdir(parents=True)
            p = h.plan(self.source, target, adapter, self.manifest)
            h.install(p, target)
            self.assertTrue((target / dir_name).exists())
            h.remove(target)
            self.assertFalse((target / dir_name).exists(), f"{dir_name} was left behind for {adapter}")

    def test_collision_prevents_all_writes(self):
        dst = self.target / ".agents" / "skills" / "tdd-workflow" / "SKILL.md"
        dst.parent.mkdir(parents=True)
        dst.write_text("sentinel")
        with self.assertRaises(h.GateError):
            h.plan(self.source, self.target, "codex", self.manifest)
        self.assertEqual(dst.read_text(), "sentinel")
        self.assertFalse((self.target / h.STATE).exists())

    def test_hash_mismatch_blocks(self):
        file = self.source / "skills" / "tdd-workflow" / "SKILL.md"
        file.write_text("tampered")
        with self.assertRaises(h.GateError):
            h.plan(self.source, self.target, "codex", self.manifest)

    def test_changed_managed_file_prevents_any_removal(self):
        h.install(h.plan(self.source, self.target, "codex", self.manifest), self.target)
        dst = self.target / ".agents" / "skills" / "tdd-workflow" / "SKILL.md"
        dst.write_text("modified")
        with self.assertRaises(h.GateError):
            h.remove(self.target)
        self.assertTrue((self.target / h.STATE).exists())

    def test_outside_sandbox_refused(self):
        with self.assertRaises(h.GateError):
            h.check_sandbox(ROOT)
        # Also reject directories outside the repository-owned sandbox.
        with self.assertRaises(h.GateError):
            h.check_sandbox(ROOT.parent)

    def test_source_wrong_revision_refused(self):
        self.manifest["ecc"]["commit"] = "a" * 40
        with self.assertRaises(h.GateError):
            h.plan(self.source, self.target, "codex", self.manifest)

    def test_checkout_dirty_refused(self):
        # Adding an uncommitted file makes the worktree dirty
        untracked = self.source / "skills" / "untracked.txt"
        untracked.write_text("dirty")
        with self.assertRaises(h.GateError) as ctx:
            h.check_source(self.source, self.manifest)
        self.assertIn("uncommitted modifications or untracked files", str(ctx.exception))

    def test_ancestor_symlink_refused(self):
        symlink_base = Path(self.tmp.name) / "symlink_container"
        symlink_base.mkdir()
        symlink_dir = symlink_base / "link_target"
        try:
            os.symlink(self.target, symlink_dir, target_is_directory=True)
        except OSError:
            self.skipTest("Symlinks not permitted in this test environment")
        child_in_symlink = symlink_dir / "child"
        with self.assertRaises(h.GateError) as ctx:
            h.assert_no_symlink(child_in_symlink)
        self.assertIn("symlink path refused", str(ctx.exception))

    def test_partial_interruption_rolls_back_cleanly(self):
        p = h.plan(self.source, self.target, "codex", self.manifest)
        # Patch json.dump to raise an error during STATE file writing (after skill files written)
        with patch("json.dump", side_effect=RuntimeError("simulated crash during write")):
            with self.assertRaises(RuntimeError):
                h.install(p, self.target)
        # Confirm complete rollback: no files, no state, no orphan directories
        self.assertFalse((self.target / h.STATE).exists())
        self.assertFalse(any(self.target.rglob("SKILL.md")))
        self.assertFalse((self.target / ".agents").exists())

    def test_record_path_traversal_refused(self):
        h.install(h.plan(self.source, self.target, "codex", self.manifest), self.target)
        state_file = self.target / h.STATE
        rec = json.loads(state_file.read_text())
        rec["files"][0]["path"] = "../oops/SKILL.md"
        state_file.write_text(json.dumps(rec))
        with self.assertRaises(h.GateError):
            h.remove(self.target)

    def test_tampered_state_hash_mismatch_refused(self):
        h.install(h.plan(self.source, self.target, "codex", self.manifest), self.target)
        state_file = self.target / h.STATE
        rec = json.loads(state_file.read_text())
        rec["files"][0]["sha256"] = "0" * 64
        state_file.write_text(json.dumps(rec))
        with self.assertRaises(h.GateError):
            h.record_and_paths(self.target, manifest=self.manifest)

    def test_tampered_record_commit_refused(self):
        h.install(h.plan(self.source, self.target, "codex", self.manifest), self.target)
        state_file = self.target / h.STATE
        rec = json.loads(state_file.read_text())
        rec["ecc_commit"] = "f" * 40
        state_file.write_text(json.dumps(rec))
        with self.assertRaises(h.GateError):
            h.record_and_paths(self.target, manifest=self.manifest)


if __name__ == "__main__":
    unittest.main()
