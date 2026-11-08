"""HE-R1-02/HE-R1-06: machine layer — the Harness package (setup-harness) once per computer, per detected tool."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_machine", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
CATALOG = h.read_manifest(ROOT / "config/approved_skills.json")
ADAPTERS = h.read_adapters(ROOT / "config/adapters.json")


def make_link(link: Path, target: Path) -> None:
    """Directory link like the operator's ~/.claude/skills junction."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


class MachineLayerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.home.mkdir()

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): (p.read_bytes() if p.is_file() else None)
                for p in self.home.rglob("*")}

    def tools(self, *names):
        for name in names:
            (self.home / name).mkdir()

    def test_adapter_table_enables_exactly_claude_and_codex_for_r1(self):
        self.assertEqual(set(ADAPTERS["adapters"]), {"claude", "codex"})
        self.assertEqual(ADAPTERS["adapters"]["codex"]["machine_skills"], ".agents/skills")
        self.assertEqual(ADAPTERS["adapters"]["claude"]["machine_skills"], ".claude/skills")

    def test_plan_lists_copy_roots_without_writing(self):
        self.tools(".codex", ".claude")
        before = self.snapshot()
        result = h.machine_plan(self.home, CATALOG, ADAPTERS)
        self.assertEqual(result["status"], "PLANNED_NOT_INSTALLED")
        self.assertEqual({r["adapter"]: r["mode"] for r in result["roots"]}, {"codex": "copy", "claude": "copy"})
        self.assertIn(".claude/skills/setup-harness/SKILL.md", result["files"])
        self.assertFalse(any("tdd-workflow" in f or "verification-loop" in f for f in result["files"]))
        self.assertEqual(before, self.snapshot())

    def test_package_is_only_setup_harness(self):
        self.assertEqual(h.MACHINE_SKILL_NAMES, ["setup-harness"])
        self.assertEqual({rel.split("/")[0] for rel in h.setup_skill_files()}, {"setup-harness"})

    def test_install_reapply_verify_remove_exact(self):
        self.tools(".codex", ".claude")
        other = self.home / ".agents/skills/my-own-skill/SKILL.md"
        other.parent.mkdir(parents=True)
        other.write_text("mine")
        before = self.snapshot()
        self.assertEqual(h.machine_install(self.home, CATALOG, ADAPTERS)["status"],
                         "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
        for root in (".agents/skills", ".claude/skills"):
            self.assertTrue((self.home / root / "setup-harness/SKILL.md").is_file())
            for name in CATALOG["ecc"]["skills"]:
                self.assertFalse((self.home / root / name).exists())
        record = json.loads((self.home / ".claude/skills" / h.MACHINE_STATE).read_text())
        self.assertNotIn("ecc_commit", record)
        self.assertNotIn("license_notice", record)
        installed = self.snapshot()
        self.assertEqual(h.machine_install(self.home, CATALOG, ADAPTERS)["status"], "ALREADY_INSTALLED")
        self.assertEqual(installed, self.snapshot())
        self.assertEqual(h.machine_verify(self.home, CATALOG, ADAPTERS)["status"], "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")
        self.assertEqual(h.machine_remove(self.home, CATALOG, ADAPTERS, apply=False)["status"], "PLANNED_NOT_REMOVED")
        self.assertEqual(installed, self.snapshot())
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_claude_link_to_agents_dir_is_one_install_with_alias(self):
        self.tools(".codex", ".claude")
        (self.home / ".agents/skills").mkdir(parents=True)
        make_link(self.home / ".claude/skills", self.home / ".agents/skills")
        roots = {r["adapter"]: r for r in h.machine_plan(self.home, CATALOG, ADAPTERS)["roots"]}
        self.assertEqual(roots["claude"]["mode"], "alias")
        self.assertEqual(roots["claude"]["alias_of"], "codex")
        h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertTrue((self.home / ".claude/skills/setup-harness/SKILL.md").is_file())
        self.assertEqual(h.machine_verify(self.home, CATALOG, ADAPTERS)["status"], "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertFalse((self.home / ".agents/skills/setup-harness").exists())
        self.assertTrue((self.home / ".claude/skills").exists())

    def test_link_to_any_other_directory_blocks(self):
        self.tools(".codex", ".claude")
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()
        make_link(self.home / ".claude/skills", elsewhere)
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(before, self.snapshot())

    def test_undetected_tool_is_skipped_and_not_created(self):
        self.tools(".codex")
        result = h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(result["skipped"], ["claude"])
        self.assertFalse((self.home / ".claude").exists())

    def test_no_supported_tool_blocks(self):
        with self.assertRaises(h.GateError):
            h.machine_plan(self.home, CATALOG, ADAPTERS)

    def test_collision_in_one_root_blocks_both_roots(self):
        # All or nothing across roots; the single-root case is in test_setup_harness_v2.
        self.tools(".codex", ".claude")
        foreign = self.home / ".claude/skills/setup-harness/SKILL.md"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("someone else's setup")
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(before, self.snapshot())

    def test_user_skill_named_like_a_retired_one_is_left_alone(self):
        self.tools(".codex")
        mine = self.home / ".agents/skills/tdd-workflow/SKILL.md"
        mine.parent.mkdir(parents=True)
        mine.write_text("my own tdd")
        h.machine_install(self.home, CATALOG, ADAPTERS)
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(mine.read_text(), "my own tdd")

    def test_modified_skill_blocks_verify_and_remove_and_is_preserved(self):
        self.tools(".codex")
        h.machine_install(self.home, CATALOG, ADAPTERS)
        edited = self.home / ".agents/skills/setup-harness/SKILL.md"
        edited.write_bytes(b"my edit")
        with self.assertRaises(h.GateError):
            h.machine_verify(self.home, CATALOG, ADAPTERS)
        with self.assertRaises(h.GateError):
            h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(edited.read_bytes(), b"my edit")
        self.assertTrue((self.home / ".agents/skills/setup-harness/agents/openai.yaml").is_file())

    def test_newly_detected_tool_is_added_on_rerun(self):
        self.tools(".codex")
        h.machine_install(self.home, CATALOG, ADAPTERS)
        self.tools(".claude")
        self.assertEqual(h.machine_install(self.home, CATALOG, ADAPTERS)["status"],
                         "FILES_INSTALLED_RUNTIME_NOT_VERIFIED")
        self.assertTrue((self.home / ".claude/skills/setup-harness/SKILL.md").is_file())


class DiscoveryMatchTests(unittest.TestCase):
    """Parsing of Codex app-server skills/list, without starting Codex."""

    def test_match_reports_discovered_and_missing(self):
        listing = {"data": [{"cwd": "x", "skills": [
            {"name": "tdd-workflow", "path": "C:\\h\\.agents\\skills\\tdd-workflow\\SKILL.md",
             "scope": "user", "enabled": True},
            {"name": "verification-loop", "path": "C:\\h\\.agents\\skills\\verification-loop\\SKILL.md",
             "scope": "user", "enabled": False}]}]}
        result = h.match_discovery(listing, ["tdd-workflow", "verification-loop"])
        self.assertEqual(result["tdd-workflow"]["status"], "DISCOVERED")
        self.assertEqual(result["verification-loop"]["status"], "DISABLED")

    def test_missing_skill(self):
        self.assertEqual(h.match_discovery({"data": []}, ["tdd-workflow"])["tdd-workflow"]["status"], "MISSING")


class MachineCliTests(unittest.TestCase):
    def test_install_requires_apply_then_installs_into_given_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".codex").mkdir()
            cli = [sys.executable, str(ROOT / "scripts/harnessctl.py")]
            dry = subprocess.run([*cli, "machine-install", "--home", str(home)], capture_output=True, text=True)
            self.assertEqual(dry.returncode, 2)
            self.assertFalse((home / ".agents").exists())
            real = subprocess.run([*cli, "machine-install", "--home", str(home), "--apply"],
                                  capture_output=True, text=True)
            self.assertEqual(real.returncode, 0, real.stderr)
            verify = subprocess.run([*cli, "machine-verify", "--home", str(home)], capture_output=True, text=True)
            self.assertEqual(json.loads(verify.stdout)["status"], "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")
            remove = subprocess.run([*cli, "machine-remove", "--home", str(home), "--apply"],
                                    capture_output=True, text=True)
            self.assertEqual(remove.returncode, 0, remove.stderr)
            self.assertEqual(sorted(p.name for p in home.iterdir()), [".codex"])


if __name__ == "__main__":
    unittest.main()
