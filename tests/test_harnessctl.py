import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl", ROOT / "scripts" / "harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)


@unittest.skipUnless(shutil.which("git"), "Git not installed")
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
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
            h.check_sandbox(Path(self.tmp.name))

    def test_source_wrong_revision_refused(self):
        self.manifest["ecc"]["commit"] = "a" * 40
        with self.assertRaises(h.GateError):
            h.plan(self.source, self.target, "codex", self.manifest)

    def test_record_path_traversal_refused(self):
        h.install(h.plan(self.source, self.target, "codex", self.manifest), self.target)
        state_file = self.target / h.STATE
        rec = json.loads(state_file.read_text())
        rec["files"][0]["path"] = "../oops/SKILL.md"
        state_file.write_text(json.dumps(rec))
        with self.assertRaises(h.GateError):
            h.remove(self.target)


if __name__ == "__main__":
    unittest.main()
