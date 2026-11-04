"""HE-R1-01: ECC skills bundled in the repository, so setup needs no local checkout."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_vendored", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
CATALOG = json.loads((ROOT / "config/approved_skills.json").read_text(encoding="utf-8"))["ecc"]
BUNDLE = ROOT / "vendor" / "ecc"


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


class BundledFilesTests(unittest.TestCase):
    """The committed bytes are exactly the approved upstream bytes."""

    def test_bundle_matches_catalog_hashes_and_license(self):
        for name, expected in CATALOG["skills"].items():
            self.assertEqual(h.digest((BUNDLE / "skills" / name / "SKILL.md").read_bytes()), expected)
        self.assertEqual(h.digest((BUNDLE / "LICENSE").read_bytes()), CATALOG["license_sha256"])

    def test_source_record_binds_upstream_commit(self):
        record = json.loads((BUNDLE / "SOURCE.json").read_text(encoding="utf-8"))
        self.assertEqual(record["commit"], CATALOG["commit"])
        self.assertEqual(record["repository"], CATALOG["repository"])

    def test_bundle_has_only_expected_files_and_no_crlf(self):
        files = {p.relative_to(BUNDLE).as_posix() for p in BUNDLE.rglob("*") if p.is_file()}
        self.assertEqual(files, h.BUNDLE_FILES)
        for rel in files:
            self.assertNotIn(b"\r\n", (BUNDLE / rel).read_bytes(), rel)

    def test_git_never_converts_bundle_line_endings(self):
        out = git(ROOT, "check-attr", "text", "--", "vendor/ecc/skills/tdd-workflow/SKILL.md")
        self.assertTrue(out.endswith("text: unset"), out)


class BundledSourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.repo = self.root / "project"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet")
        self.bundle = self.root / "bundle"
        hashes = {}
        for name in sorted(h.ALLOWED):
            file = self.bundle / "skills" / name / "SKILL.md"
            file.parent.mkdir(parents=True)
            file.write_bytes(f"---\nname: {name}\ndescription: fixture\n---\n".encode())
            hashes[name] = h.digest(file.read_bytes())
        (self.bundle / "LICENSE").write_bytes(b"MIT License\nfixture\n")
        commit = "a" * 40
        (self.bundle / "SOURCE.json").write_text(json.dumps({"repository": "x", "commit": commit}))
        self.manifest = {"schema_version": 1, "ecc": {
            "commit": commit, "skills": hashes, "license_sha256": h.digest((self.bundle / "LICENSE").read_bytes())}}
        patcher = patch.object(h, "VENDORED", self.bundle)
        patcher.start()
        self.addCleanup(patcher.stop)

    def files(self):
        return {p.relative_to(self.repo).as_posix() for p in self.repo.rglob("*")
                if p.is_file() and ".git" not in p.parts}

    def test_attach_from_bundle_without_git_checkout(self):
        self.assertEqual(h.attach_project(self.repo, self.bundle, self.manifest)["status"],
                         "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
        h.verify_project(self.repo, self.manifest)
        h.remove_project(self.repo, self.manifest)
        self.assertEqual(self.files(), set())

    def test_tampered_bundle_refused_before_writes(self):
        (self.bundle / "skills/tdd-workflow/SKILL.md").write_bytes(b"tampered")
        with self.assertRaises(h.GateError):
            h.attach_project(self.repo, self.bundle, self.manifest)
        self.assertEqual(self.files(), set())

    def test_unexpected_extra_file_in_bundle_refused(self):
        (self.bundle / "skills/tdd-workflow/run.sh").write_text("echo hi")
        with self.assertRaises(h.GateError):
            h.attach_project(self.repo, self.bundle, self.manifest)
        self.assertEqual(self.files(), set())

    def test_source_record_commit_mismatch_refused(self):
        (self.bundle / "SOURCE.json").write_text(json.dumps({"repository": "x", "commit": "b" * 40}))
        with self.assertRaises(h.GateError):
            h.attach_project(self.repo, self.bundle, self.manifest)

    def test_other_directory_without_git_refused_even_with_identical_bytes(self):
        copy = self.root / "copy"
        subprocess.check_call([sys.executable, "-c",
                               "import shutil,sys; shutil.copytree(sys.argv[1], sys.argv[2])",
                               str(self.bundle), str(copy)])
        with self.assertRaises(h.GateError):
            h.attach_project(self.repo, copy, self.manifest)
        self.assertEqual(self.files(), set())


class CliDefaultSourceTests(unittest.TestCase):
    """End to end with the real bundle and catalog: --source is no longer needed."""

    def test_project_attach_without_source_uses_bundle_then_removes_exactly(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git(repo, "init", "--quiet")
            cli = [sys.executable, str(ROOT / "scripts/harnessctl.py")]
            attach = subprocess.run([*cli, "project-attach", "--repo", str(repo), "--apply"],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(attach.returncode, 0, attach.stderr)
            self.assertEqual(json.loads(attach.stdout)["status"], "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
            installed = repo / ".agents/skills/tdd-workflow/SKILL.md"
            self.assertEqual(h.digest(installed.read_bytes()), CATALOG["skills"]["tdd-workflow"])
            remove = subprocess.run([*cli, "project-remove", "--repo", str(repo), "--apply"],
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(remove.returncode, 0, remove.stderr)
            self.assertEqual([p.name for p in repo.iterdir()], [".git"])


if __name__ == "__main__":
    unittest.main()
