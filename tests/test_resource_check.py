"""HE-OPS-01: resource-check (read-only resource budget). Synthetic snapshots; no real processes needed."""
import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("resource_check", ROOT / "scripts/resource_check.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)
BUDGET = rc.read_budget(ROOT / "config/resource_budget.json")


def proc(pid, ppid, name, cmd="", created=100, ws=0):
    return {"pid": pid, "ppid": ppid, "name": name, "cmd": cmd, "created": created, "ws": ws}


def healthy():
    return {
        "platform": "win32", "checked_at": "2026-11-22T00:00:00-03:00",
        "disk_free_gb": 50.0, "ram_gb": 32.0, "commit_gb": 30.0, "pagefile_gb": 10.0,
        "processes": [proc(1, 0, "explorer.exe", created=1), proc(10, 1, "claude.exe", created=10),
                      proc(11, 10, "node.exe", "node threejs-devtools-mcp/index.js", created=11, ws=100 * 2**20)],
        "temp_profiles": [], "claude_worktrees": {"a": 3, "b": 2}, "codex_worktrees": 1,
        "enabled_plugins": {"parallax-threejs@x": False}, "user_mcp": ["gemini-notebook"],
        "history_gb": {"claude": 2.0, "codex": 1.0},
    }


def by_id(rep):
    return {c["id"]: c for c in rep["checks"]}


class EvaluateCase(unittest.TestCase):
    def test_healthy_machine_passes(self):
        rep = rc.evaluate(healthy(), BUDGET)
        self.assertEqual(rep["status"], "PASS", [c for c in rep["checks"] if c["status"] != "PASS"])
        self.assertNotIn("cause", by_id(rep)["disk_free"])

    def test_each_limit_fails_with_cause_and_fix(self):
        cases = {
            "disk_free": lambda s: s.update(disk_free_gb=19.9),
            "commit": lambda s: s.update(commit_gb=40.1),
            "pagefile": lambda s: s.update(pagefile_gb=16.5),
            "claude_worktrees": lambda s: s.update(claude_worktrees={"a": 20, "b": 11}),
            "history": lambda s: s.update(history_gb={"claude": 15.0, "codex": 6.0}),
            "heavy_plugin_off": lambda s: s.update(enabled_plugins={"parallax-threejs@x": True}),
            "user_mcp": lambda s: s.update(user_mcp=["gemini-notebook", "rea"]),
            "claude_processes": lambda s: s["processes"].extend(
                proc(100 + i, 1, "claude.exe", created=100 + i) for i in range(15)),
            "threejs_servers": lambda s: s["processes"].extend(
                proc(200 + i, 10, "node.exe", "node threejs-devtools-mcp", created=200) for i in range(2)),
            "plugin_ram": lambda s: s["processes"].append(
                proc(300, 10, "chrome.exe", "chrome --user-data-dir=puppeteer_dev_chrome_profile-x", 300, 3 * 2**30)),
        }
        for cid, mutate in cases.items():
            with self.subTest(cid):
                snap = healthy()
                mutate(snap)
                rep = rc.evaluate(snap, BUDGET)
                self.assertEqual(rep["status"], "FAIL")
                failed = [c["id"] for c in rep["checks"] if c["status"] == "FAIL"]
                self.assertEqual(failed, [cid])
                self.assertTrue(by_id(rep)[cid]["cause"] and by_id(rep)[cid]["fix"])

    def test_limits_are_inclusive(self):
        snap = healthy()
        snap.update(disk_free_gb=20.0, commit_gb=40.0, pagefile_gb=16.0, claude_worktrees={"a": 30})
        self.assertEqual(rc.evaluate(snap, BUDGET)["status"], "PASS")

    def test_missing_heavy_plugin_entry_fails(self):
        snap = healthy()
        snap["enabled_plugins"] = {"hyperframes@h": True}
        check = by_id(rc.evaluate(snap, BUDGET))["heavy_plugin_off"]
        self.assertEqual(check["status"], "FAIL")
        self.assertIn("sem entrada", check["value"])

    def test_orphan_profiles_ignore_profiles_in_use(self):
        snap = healthy()
        used = r"C:\T\puppeteer_dev_chrome_profile-USED"
        snap["temp_profiles"] = [used] + [rf"C:\T\puppeteer_dev_chrome_profile-{i}" for i in range(6)]
        snap["processes"].append(proc(400, 11, "chrome.exe", f"chrome --user-data-dir={used.lower()}", 400))
        check = by_id(rc.evaluate(snap, BUDGET))["orphan_profiles"]
        self.assertEqual((check["status"], check["value"]), ("FAIL", 6))
        snap["temp_profiles"] = snap["temp_profiles"][:6]
        self.assertEqual(by_id(rc.evaluate(snap, BUDGET))["orphan_profiles"]["value"], 5)

    def test_orphan_tree_dead_parent_and_reused_pid(self):
        snap = healthy()
        snap["processes"].append(proc(500, 999, "node.exe", "npx @playwright/mcp", created=500))
        snap["processes"].append(proc(501, 500, "chrome.exe", "chrome playwright_chromiumdev_profile-1", created=501))
        # parent PID 10 exists but is younger than the child: the PID was reused, the real parent is gone
        snap["processes"].append(proc(502, 10, "node.exe", "node chrome-devtools-mcp", created=5))
        rep = rc.evaluate(snap, BUDGET)
        self.assertEqual(by_id(rep)["orphan_trees"]["value"], 2)
        orphan = [g for g in rep["owners"] if g["owner_pid"] is None][0]
        self.assertEqual(orphan["processes"], 3)

    def test_owners_group_by_nearest_agent(self):
        snap = healthy()
        snap["processes"] += [proc(20, 1, "claude.exe", created=20),
                              proc(21, 20, "cmd.exe", created=21),
                              proc(22, 21, "node.exe", "node chrome-devtools-mcp", created=22, ws=2**30),
                              proc(23, 22, "chrome.exe", "chrome puppeteer_dev_chrome_profile-a", created=23, ws=2**30)]
        owners = rc.evaluate(snap, BUDGET)["owners"]
        self.assertEqual(owners[0], {"owner_pid": 20, "owner": "claude.exe", "processes": 2, "ram_gb": 2.0})
        self.assertEqual(owners[1]["owner_pid"], 10)

    def test_unmeasured_is_null_and_inconclusive_not_zero(self):
        snap = healthy()
        snap.update(processes=None, ram_gb=None, commit_gb=None, pagefile_gb=None)
        rep = rc.evaluate(snap, BUDGET)
        self.assertEqual(rep["status"], "INCONCLUSIVE")
        checks = by_id(rep)
        for cid in ("commit", "pagefile", "threejs_servers", "plugin_ram", "orphan_trees", "claude_processes",
                    "orphan_profiles"):
            self.assertEqual((checks[cid]["status"], checks[cid]["value"]), ("NOT_RUN", None), cid)
        self.assertIsNone(rep["owners"])

    def test_fail_wins_over_not_run(self):
        snap = healthy()
        snap.update(processes=None, disk_free_gb=1.0)
        self.assertEqual(rc.evaluate(snap, BUDGET)["status"], "FAIL")

    def test_text_names_cause_and_says_read_only(self):
        snap = healthy()
        snap["disk_free_gb"] = 5.0
        text = rc.render_text(rc.evaluate(snap, BUDGET))
        self.assertIn("FAIL", text)
        self.assertIn("causa:", text)
        self.assertIn("nada foi apagado", text)


class BudgetCase(unittest.TestCase):
    def write(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "b.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_bad_budgets_are_refused(self):
        base = json.loads((ROOT / "config/resource_budget.json").read_text(encoding="utf-8"))
        bad = []
        for mutate in (lambda b: b.update(extra=1), lambda b: b["limits"].pop("pagefile_gb_max"),
                       lambda b: b["limits"].update(pagefile_gb_max=-1), lambda b: b["limits"].update(pagefile_gb_max=True),
                       lambda b: b["limits"].update(unknown_max=1), lambda b: b.update(plugin_pattern="("),
                       lambda b: b.update(schema_version=2), lambda b: b.update(user_mcp_allowed="gemini"),
                       lambda b: b.update(heavy_plugin="")):
            data = copy.deepcopy(base)
            mutate(data)
            bad.append(data)
        for data in bad:
            with self.subTest(data=str(data)[:60]), self.assertRaises(rc.BudgetError):
                rc.read_budget(self.write(data))
        with self.assertRaises(rc.BudgetError):
            rc.read_budget(Path(tempfile.gettempdir()) / "does-not-exist-he-ops.json")


class CollectAndMainCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.home, self.dev, self.temp = self.root / "home", self.root / "dev", self.root / "temp"
        for p in (self.home / ".claude" / "projects" / "x", self.dev / "repo1" / ".claude" / "worktrees" / "w1",
                  self.dev / "repo1" / ".claude" / "worktrees" / "w2", self.dev / "repo2",
                  self.temp / "puppeteer_dev_chrome_profile-1", self.temp / "other"):
            p.mkdir(parents=True)
        (self.home / ".claude" / "projects" / "x" / "s.jsonl").write_bytes(b"x" * 2048)
        (self.home / ".claude" / "settings.json").write_text('{"enabledPlugins": {"parallax-threejs@m": false}}',
                                                           encoding="utf-8")
        (self.home / ".claude.json").write_text(
            '{"mcpServers": {"gemini-notebook": {"command": "py"}, "remote": {"url": "https://x"}}}', encoding="utf-8")

    def test_collect_without_windows_measures_files_and_leaves_processes_null(self):
        before = sorted(str(p) for p in self.root.rglob("*"))
        with unittest.mock.patch.object(rc, "collect_windows", return_value=None), \
                unittest.mock.patch.dict("os.environ", {"CODEX_HOME": str(self.home / ".codex")}):
            snap = rc.collect(self.home, self.dev, self.temp, BUDGET)
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), before)  # read-only
        self.assertIsNone(snap["processes"])
        self.assertEqual(snap["claude_worktrees"], {"repo1": 2})
        self.assertIsNone(snap["codex_worktrees"])
        self.assertEqual(len(snap["temp_profiles"]), 1)
        self.assertEqual(snap["user_mcp"], ["gemini-notebook"])
        self.assertEqual(snap["enabled_plugins"], {"parallax-threejs@m": False})
        self.assertAlmostEqual(snap["history_gb"]["claude"] * rc.GB, 2048)
        self.assertIsNone(snap["history_gb"]["codex"])
        rep = rc.evaluate(snap, BUDGET)
        self.assertEqual(by_id(rep)["orphan_profiles"]["status"], "NOT_RUN")

    def run_main(self, *extra, snap=None):
        out, err = io.StringIO(), io.StringIO()
        with unittest.mock.patch.object(rc, "collect", return_value=snap or healthy()), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rc.main(["--home", str(self.home), "--dev-root", str(self.dev), *extra])
        return code, out.getvalue(), err.getvalue()

    def test_exit_codes_and_output_file(self):
        code, out, _ = self.run_main("--json", "--output", str(self.root / "_local" / "artifacts" / "r.json"))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["status"], "PASS")
        self.assertEqual(json.loads((self.root / "_local" / "artifacts" / "r.json").read_text(encoding="utf-8"))["status"],
                         "PASS")
        bad = healthy()
        bad["disk_free_gb"] = 1.0
        self.assertEqual(self.run_main(snap=bad)[0], 1)
        unknown = healthy()
        unknown["processes"] = None
        self.assertEqual(self.run_main(snap=unknown)[0], 3)

    def test_bad_budget_blocks(self):
        path = self.root / "b.json"
        path.write_text("{}", encoding="utf-8")
        code, out, err = self.run_main("--budget", str(path))
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(json.loads(err)["status"], "BLOCKED")

    def test_harnessctl_dispatches(self):
        hspec = importlib.util.spec_from_file_location("harnessctl_rc", ROOT / "scripts/harnessctl.py")
        h = importlib.util.module_from_spec(hspec)
        hspec.loader.exec_module(h)
        with unittest.mock.patch.dict(sys.modules, {"resource_check": rc}), \
                unittest.mock.patch.object(rc, "main", return_value=7) as called:
            self.assertEqual(h.main(["resource-check", "--json"]), 7)
        called.assert_called_once_with(["--json"])


if __name__ == "__main__":
    unittest.main()
