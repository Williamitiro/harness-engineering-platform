"""harness_release: instalar o Harness no computador a partir de uma versão marcada (tag), fora da pasta de
desenvolvimento. Tudo numa home sintética e num repositório Git temporário: nada toca a home real."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import harness_release as rel  # noqa: E402

TREE = ("scripts", "skills", "vendor", "templates", "config")


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.base = Path(tmp.name)
        cls.src = cls.base / "src"
        cls.src.mkdir()
        for name in TREE:  # cópia do que está no disco (inclui mudanças ainda não commitadas)
            shutil.copytree(ROOT / name, cls.src / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / ".gitattributes", cls.src / ".gitattributes")
        git(cls.src, "init", "-q")
        git(cls.src, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "core.autocrlf=false",
            "add", "-A")
        git(cls.src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "v1")
        git(cls.src, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "v1.0.0", "-m", "v1")
        # v1.0.1: só muda a setup-harness (versão nova do pacote do computador)
        skill = cls.src / "skills" / "setup-harness" / "SKILL.md"
        skill.write_bytes(skill.read_bytes() + b"\n<!-- v1.0.1 -->\n")
        git(cls.src, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-am", "v1.0.1")
        git(cls.src, "-c", "user.name=t", "-c", "user.email=t@t", "tag", "-a", "v1.0.1", "-m", "v1.0.1")
        git(cls.src, "branch", "-q", "feature")

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        for d in (".codex", ".agents", ".claude"):
            (self.home / d).mkdir(parents=True)
        self.releases = Path(tmp.name) / "releases"

    def install(self, tag, apply=True):
        return rel.install(tag, home=self.home, releases=self.releases, source_repo=self.src, apply=apply)

    def location(self):
        data = json.loads((self.home / ".agents/skills/setup-harness/harness-location.json").read_text("utf-8"))
        return Path(data["harnessctl"])

    def test_fresh_install_from_tag(self):
        out = self.install("v1.0.0")
        self.assertEqual(out["status"], "INSTALLED")
        target = self.releases / "v1.0.0"
        self.assertEqual(self.location(), (target / "scripts" / "harnessctl.py").resolve())
        self.assertFalse((target / ".git").exists())
        meta = json.loads((target / "RELEASE.json").read_text("utf-8"))
        self.assertEqual(meta["tag"], "v1.0.0")
        self.assertEqual(meta["commit"], git(self.src, "rev-parse", "v1.0.0^{commit}"))
        self.assertEqual((self.releases / "current").resolve(), target.resolve())
        self.assertEqual(rel.status(home=self.home, releases=self.releases)["machine_verify"],
                         "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")

    def test_upgrade_moves_install_and_keeps_old_release(self):
        self.install("v1.0.0")
        out = self.install("v1.0.1")
        self.assertEqual(out["status"], "INSTALLED")
        self.assertEqual(out["previous"], str((self.releases / "v1.0.0" / "scripts" / "harnessctl.py").resolve()))
        self.assertEqual(self.location(), (self.releases / "v1.0.1" / "scripts" / "harnessctl.py").resolve())
        self.assertIn(b"<!-- v1.0.1 -->", (self.home / ".agents/skills/setup-harness/SKILL.md").read_bytes())
        self.assertTrue((self.releases / "v1.0.0" / "RELEASE.json").is_file())  # versão antiga fica intacta
        self.assertEqual((self.releases / "current").resolve(), (self.releases / "v1.0.1").resolve())

    def test_same_tag_again_is_idempotent(self):
        self.install("v1.0.0")
        self.assertEqual(self.install("v1.0.0")["status"], "ALREADY_CURRENT")

    def test_dry_run_writes_nothing(self):
        out = self.install("v1.0.0", apply=False)
        self.assertEqual(out["status"], "PLANNED")
        self.assertFalse(self.releases.exists())
        self.assertFalse((self.home / ".agents" / "skills").exists())

    def test_branch_is_refused(self):
        with self.assertRaises(rel.ReleaseError):
            self.install("feature")
        with self.assertRaises(rel.ReleaseError):
            self.install("v9.9.9")

    def test_tampered_release_dir_is_refused(self):
        self.install("v1.0.0")
        meta = self.releases / "v1.0.0" / "RELEASE.json"
        data = json.loads(meta.read_text("utf-8"))
        data["commit"] = "0" * 40
        meta.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(rel.ReleaseError):
            self.install("v1.0.0")

    def test_failed_new_install_restores_previous(self):
        self.install("v1.0.0")
        real = rel.harnessctl

        def failing(path, *args, **kw):
            if "v1.0.1" in str(path) and "machine-install" in args:
                raise rel.ReleaseError("simulated install failure")
            return real(path, *args, **kw)
        with patch.object(rel, "harnessctl", side_effect=failing):
            with self.assertRaises(rel.ReleaseError):
                self.install("v1.0.1")
        self.assertEqual(self.location(), (self.releases / "v1.0.0" / "scripts" / "harnessctl.py").resolve())
        self.assertEqual((self.releases / "current").resolve(), (self.releases / "v1.0.0").resolve())
        self.assertEqual(rel.status(home=self.home, releases=self.releases)["machine_verify"],
                         "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")


if __name__ == "__main__":
    unittest.main()
