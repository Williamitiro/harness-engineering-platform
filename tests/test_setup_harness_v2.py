"""HE-R1-04: setup-harness joins the machine package; old installs migrate exactly."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("harnessctl_setup_v2", ROOT / "scripts/harnessctl.py")
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
CATALOG = h.read_manifest(ROOT / "config/approved_skills.json")
ADAPTERS = h.read_adapters(ROOT / "config/adapters.json")
SKILL = (ROOT / "skills/setup-harness/SKILL.md").read_bytes()
OLD_SKILL = b"---\nname: setup-harness\ndescription: old\n---\nold bootstrap\n"
OLD_YAML = b"policy:\n  allow_implicit_invocation: false\n"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


class SkillFileTests(unittest.TestCase):
    def test_skill_is_tool_agnostic_and_explicit_only(self):
        text = SKILL.decode("utf-8")
        self.assertTrue(text.startswith("---\nname: setup-harness\n"))
        self.assertIn("disable-model-invocation: true", text)
        self.assertIn("harness-location.json", text)
        for command in ("machine-verify", "project-plan", "project-attach", "project-verify", "project-remove"):
            self.assertIn(command, text)
        self.assertNotIn("--client codex", text)
        self.assertNotIn("--source", text)
        self.assertNotIn(b"\r\n", SKILL)

    def test_skill_guides_codex_sandbox_and_lists_ok_statuses(self):
        text = SKILL.decode("utf-8")
        self.assertIn("FILE_HASHES_OK_RUNTIME_NOT_VERIFIED", text)  # what machine-verify really returns
        self.assertIn("permissão elevada", text)                   # Codex sandbox blocks user Python
        self.assertIn("Acesso negado", text)                        # the real Windows error, with its remedy

    def test_skill_offers_missing_rules_for_an_existing_agents_md(self):
        # HE-R1-07: the agent compares, shows what is missing and edits only with the operator's "sim".
        text = SKILL.decode("utf-8")
        self.assertIn("templates/repo/AGENTS.md", text)
        self.assertIn("## Como trabalhar", text)
        self.assertIn("já a cobre", text)
        self.assertIn('só edite com o "sim"', text)
        self.assertIn("passo 6", text)  # also offered on "verificar"
        template = (ROOT / "templates/repo/AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("\n## Como trabalhar\n", template)  # the section the skill reads

    def test_skills_folder_has_fixed_bytes_on_every_machine(self):
        out = git("check-attr", "text", "--", "skills/setup-harness/SKILL.md")
        self.assertTrue(out.endswith("text: unset"), out)

    def test_known_legacy_bootstrap_hashes_are_frozen(self):
        # Real install on the operator machine (HE-OP-02B/03) and its CRLF checkout twin.
        self.assertIn("694da9570afcca1d79bcaeb092990cf6e7a87ee9d087e85d09c7baac8cf8cfea", h.LEGACY_BOOTSTRAP_SKILL_SHA)
        self.assertIn("a1499d95abd8447558c535fe5554adcc3c9b988a0a39264a6283d430effe1e94", h.LEGACY_BOOTSTRAP_YAML_SHA)


class MachinePackageV2Tests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "home"
        self.home.mkdir()
        (self.home / ".codex").mkdir()
        self.root = self.home / ".agents/skills"

    def snapshot(self):
        return {p.relative_to(self.home).as_posix(): (p.read_bytes() if p.is_file() else None)
                for p in self.home.rglob("*")}

    def legacy_bootstrap(self, skill=OLD_SKILL):
        descriptor = json.dumps({"schema_version": 1, "client": "codex", "harnessctl": "C:/old/harnessctl.py",
                                 "ecc_source": "C:/old/.poc/ecc-pinned", "project_client_supported": True})
        files = {".agents/skills/setup-harness/SKILL.md": skill,
                 ".agents/skills/setup-harness/harness-location.json": (descriptor + "\n").encode(),
                 ".agents/skills/setup-harness/agents/openai.yaml": OLD_YAML}
        h.write_package(self.home, files, ".agents/skills/setup-harness/.harness-bootstrap.json",
                        {"schema_version": 1, "kind": "harness-bootstrap", "client": "codex"})

    def frozen(self):
        return patch.multiple(h, LEGACY_BOOTSTRAP_SKILL_SHA={h.digest(OLD_SKILL)},
                              LEGACY_BOOTSTRAP_YAML_SHA={h.digest(OLD_YAML)})

    def test_fresh_install_includes_setup_harness_with_descriptor(self):
        h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual((self.root / "setup-harness/SKILL.md").read_bytes(), SKILL)
        self.assertTrue((self.root / "setup-harness/agents/openai.yaml").is_file())
        descriptor = json.loads((self.root / "setup-harness/harness-location.json").read_text())
        self.assertEqual(descriptor, {"schema_version": 2, "harnessctl": str(ROOT / "scripts/harnessctl.py")})
        self.assertIn("setup-harness", h.MACHINE_SKILL_NAMES)

    def test_old_bootstrap_migrates_exactly(self):
        self.root.mkdir(parents=True)
        mine = self.root / "my-skill/SKILL.md"
        mine.parent.mkdir()
        mine.write_text("mine")
        with self.frozen():
            self.legacy_bootstrap()
            plan = h.machine_plan(self.home, CATALOG, ADAPTERS)
            self.assertEqual(plan["migrations"], [{"adapter": "codex", "action": "MIGRATE_BOOTSTRAP"}])
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertFalse((self.root / "setup-harness/.harness-bootstrap.json").exists())
        self.assertEqual((self.root / "setup-harness/SKILL.md").read_bytes(), SKILL)
        self.assertEqual(h.machine_verify(self.home, CATALOG, ADAPTERS)["status"], "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")
        self.assertEqual(mine.read_text(), "mine")

    def test_edited_old_bootstrap_blocks_without_writes(self):
        self.root.mkdir(parents=True)
        with self.frozen():
            self.legacy_bootstrap()
            (self.root / "setup-harness/SKILL.md").write_bytes(b"my local edit")
            before = self.snapshot()
            with self.assertRaises(h.GateError):
                h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(before, self.snapshot())

    def test_unknown_old_bootstrap_version_blocks(self):
        self.root.mkdir(parents=True)
        self.legacy_bootstrap()  # OLD_SKILL hash is not in the real frozen set
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(before, self.snapshot())

    def old_package(self, with_setup: bool):
        """Machine package as installed up to v1.0.0: the 2 ECC skills (and, from HE-R1-04, setup-harness)."""
        skills = h.check_source(h.VENDORED, CATALOG)  # same pinned bytes v1.0.0 installed
        notice = (h.VENDORED / "LICENSE").read_text(encoding="utf-8")
        files = {f".agents/skills/{s['name']}/SKILL.md": Path(s["source"]).read_bytes() for s in skills}
        if with_setup:
            files.update({f".agents/skills/{rel}": raw for rel, raw in h.setup_skill_files().items()})
        h.write_package(self.home, files, ".agents/skills/" + h.MACHINE_STATE, {
            "schema_version": 1, "kind": "harness-machine", "adapter": "codex",
            "ecc_commit": CATALOG["ecc"]["commit"], "license_notice": notice})

    def assert_upgrade_drops_ecc_skills(self):
        plan = h.machine_plan(self.home, CATALOG, ADAPTERS)
        self.assertEqual(plan["migrations"], [{"adapter": "codex", "action": "UPGRADE_PACKAGE"}])
        with self.assertRaises(h.GateError):
            h.machine_verify(self.home, CATALOG, ADAPTERS)  # outdated is not OK
        h.machine_install(self.home, CATALOG, ADAPTERS)
        for name in CATALOG["ecc"]["skills"]:
            self.assertFalse((self.root / name).exists())
        self.assertTrue((self.root / "setup-harness/SKILL.md").is_file())
        self.assertEqual(h.machine_verify(self.home, CATALOG, ADAPTERS)["status"], "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")

    def test_machine_package_v1_upgrades_and_then_removes_exactly(self):
        before = self.snapshot()
        self.old_package(with_setup=False)
        self.assert_upgrade_drops_ecc_skills()
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_package_v1_0_0_upgrade_removes_the_two_ecc_skills(self):
        before = self.snapshot()
        self.old_package(with_setup=True)
        self.assert_upgrade_drops_ecc_skills()
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_old_package_is_removable_by_the_new_code(self):
        before = self.snapshot()
        self.old_package(with_setup=True)
        h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(before, self.snapshot())

    def test_outdated_package_with_edited_file_blocks_upgrade(self):
        self.old_package(with_setup=True)
        (self.root / "tdd-workflow/SKILL.md").write_bytes(b"edited")
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        with self.assertRaises(h.GateError):
            h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)
        self.assertEqual(before, self.snapshot())

    def old_record_without_pin(self):
        state = self.root / h.MACHINE_STATE
        record = json.loads(state.read_text())
        del record["ecc_commit"]
        state.write_text(json.dumps(record))

    def test_old_package_without_the_ecc_pin_blocks(self):
        self.old_package(with_setup=True)
        self.old_record_without_pin()
        before = self.snapshot()
        for call in (lambda: h.machine_install(self.home, CATALOG, ADAPTERS),
                     lambda: h.machine_remove(self.home, CATALOG, ADAPTERS, apply=True)):
            with self.assertRaises(h.GateError):
                call()
        self.assertEqual(before, self.snapshot())

    def test_new_package_with_an_ecc_pin_blocks(self):
        h.machine_install(self.home, CATALOG, ADAPTERS)
        state = self.root / h.MACHINE_STATE
        record = json.loads(state.read_text())
        record["ecc_commit"] = CATALOG["ecc"]["commit"]
        state.write_text(json.dumps(record))
        with self.assertRaises(h.GateError):
            h.machine_verify(self.home, CATALOG, ADAPTERS)

    def test_retired_skill_of_unknown_version_blocks(self):
        # Record and file agree, but the bytes are not the approved ECC version.
        h.write_package(self.home, {".agents/skills/tdd-workflow/SKILL.md": b"other tdd"},
                        ".agents/skills/" + h.MACHINE_STATE,
                        {"schema_version": 1, "kind": "harness-machine", "adapter": "codex",
                         "ecc_commit": CATALOG["ecc"]["commit"]})
        before = self.snapshot()
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(before, self.snapshot())

    def newer_skill(self):
        current = h.setup_skill_files()
        newer = {**current, "setup-harness/SKILL.md": current["setup-harness/SKILL.md"] + b"\nnova linha\n"}
        return patch.object(h, "setup_skill_files", return_value=newer)

    def test_new_version_of_an_installed_skill_updates_untouched_files(self):
        h.machine_install(self.home, CATALOG, ADAPTERS)
        with self.newer_skill():
            plan = h.machine_plan(self.home, CATALOG, ADAPTERS)
            self.assertEqual(plan["migrations"], [{"adapter": "codex", "action": "UPGRADE_PACKAGE"}])
            with self.assertRaises(h.GateError):
                h.machine_verify(self.home, CATALOG, ADAPTERS)
            h.machine_install(self.home, CATALOG, ADAPTERS)
            self.assertTrue((self.root / "setup-harness/SKILL.md").read_bytes().endswith(b"nova linha\n"))
            self.assertEqual(h.machine_verify(self.home, CATALOG, ADAPTERS)["status"],
                             "FILE_HASHES_OK_RUNTIME_NOT_VERIFIED")

    def test_new_version_never_overwrites_a_file_the_user_edited(self):
        h.machine_install(self.home, CATALOG, ADAPTERS)
        edited = self.root / "setup-harness/SKILL.md"
        edited.write_bytes(b"minha versao")
        with self.newer_skill():
            with self.assertRaises(h.GateError):
                h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(edited.read_bytes(), b"minha versao")

    def test_foreign_setup_harness_folder_blocks(self):
        foreign = self.root / "setup-harness/SKILL.md"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("someone else's")
        with self.assertRaises(h.GateError):
            h.machine_install(self.home, CATALOG, ADAPTERS)
        self.assertEqual(foreign.read_text(), "someone else's")

    def test_install_from_another_checkout_is_reported_clearly(self):
        h.machine_install(self.home, CATALOG, ADAPTERS)
        descriptor = self.root / "setup-harness/harness-location.json"
        other = json.dumps({"schema_version": 2, "harnessctl": "C:/elsewhere/scripts/harnessctl.py"}) + "\n"
        # Simulate an install made by a different Harness checkout (record matches its bytes).
        state = self.root / h.MACHINE_STATE
        record = json.loads(state.read_text())
        for item in record["files"]:
            if item["path"].endswith("harness-location.json"):
                item["sha256"] = h.digest(other.encode())
        descriptor.write_text(other, newline="\n")
        state.write_text(json.dumps(record))
        with self.assertRaises(h.GateError) as ctx:
            h.machine_verify(self.home, CATALOG, ADAPTERS)
        self.assertIn("C:/elsewhere", str(ctx.exception))


class LegacySetupSkillCommandsTests(unittest.TestCase):
    """setup-skill-* stay able to verify and remove a real old install (frozen hashes)."""

    def test_old_install_verifies_and_removes_after_skill_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            descriptor = json.dumps({"schema_version": 1, "client": "codex", "harnessctl": "x",
                                     "ecc_source": "y", "project_client_supported": True}) + "\n"
            files = {".agents/skills/setup-harness/SKILL.md": OLD_SKILL,
                     ".agents/skills/setup-harness/harness-location.json": descriptor.encode(),
                     ".agents/skills/setup-harness/agents/openai.yaml": OLD_YAML}
            h.write_package(home, files, ".agents/skills/setup-harness/.harness-bootstrap.json",
                            {"schema_version": 1, "kind": "harness-bootstrap", "client": "codex"})
            with patch.multiple(h, LEGACY_BOOTSTRAP_SKILL_SHA={h.digest(OLD_SKILL)},
                                LEGACY_BOOTSTRAP_YAML_SHA={h.digest(OLD_YAML)}):
                h.verify_setup_skill(home, "codex")
                h.remove_setup_skill(home, "codex", apply=True)
            self.assertFalse((home / ".agents/skills/setup-harness").exists())


if __name__ == "__main__":
    unittest.main()
