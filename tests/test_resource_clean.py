"""HE-OPS-02: resource-clean plan (read-only) and apply (only chosen Harness items, re-checked)."""
import contextlib
import importlib.util
import io
import json
import os
import re
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("resource_clean", ROOT / "scripts/resource_clean.py")
cl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cl)
rc = cl.rc
BUDGET = rc.read_budget(ROOT / "config/resource_budget.json")
NOW = 1_800_000_000.0
DAY = 86400


def proc(pid, ppid, name, cmd="", created=100, ws=0):
    return {"pid": pid, "ppid": ppid, "name": name, "cmd": cmd, "created": created, "ws": ws}


def iso(ts):
    import datetime as dt
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat().replace("+00:00", "Z")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.dev, self.temp, self.home = self.root / "dev", self.root / "temp", self.root / "home"
        for p in (self.dev, self.temp, self.home):
            p.mkdir()

    def old(self, path, days=3):
        t = time.time() - days * DAY
        for base, dirs, files in os.walk(path):
            for n in dirs + files:
                os.utime(os.path.join(base, n), (t, t))
        os.utime(path, (t, t))


class SessionsCase(unittest.TestCase):
    def plan(self, sessions, states):
        with unittest.mock.patch.object(cl, "worktree_state", side_effect=lambda p: {"state": states[re.split(r"[\\/]", str(p))[-1]]}):
            return {x["session_id"]: x for x in cl.plan_sessions(sessions, NOW)}

    def s(self, sid, wt, **kw):
        return {"sessionId": sid, "title": sid, "cwd": rf"C:\dev\r\.claude\worktrees\{wt}", "isArchived": False,
                "isRunning": False, "lastActivityAt": iso(NOW - 3600), **kw}

    def test_classes(self):
        sessions = [self.s("merged", "a", prState="MERGED"), self.s("open", "b", prState="OPEN", lastActivityAt=iso(NOW - 30 * DAY)),
                    self.s("running", "c", prState="MERGED", isRunning=True), self.s("work", "d", prState="MERGED"),
                    self.s("idle", "e", lastActivityAt=iso(NOW - 10 * DAY)), self.s("recent", "f"),
                    self.s("closed", "g", prState="CLOSED"), self.s("gone", "h", isArchived=True, prState="MERGED"),
                    self.s("weird", "i", prState="MERGED")]
        got = self.plan(sessions, {"a": "clean", "b": "clean", "c": "clean", "d": "work", "e": "clean",
                                   "f": "clean", "g": "clean", "h": "clean", "i": "not_git"})
        self.assertEqual({k: v["safety"] for k, v in got.items()},
                         {"merged": "seguro", "open": "manter", "running": "manter", "work": "manter",
                          "idle": "decisao", "recent": "manter", "closed": "seguro", "weird": "manter"})
        self.assertNotIn("gone", got)
        self.assertTrue(all(x["executor"] == "app" and x["kind"] == "archive_session" for x in got.values()))

    def test_shared_worktree_with_a_kept_session_is_kept(self):
        # two nexus sessions with merged PRs share a worktree used by a third session with an open PR
        sessions = [self.s("m1", "shared", prState="MERGED"), self.s("m2", "shared", prState="MERGED"),
                    self.s("active", "shared", prState="OPEN")]
        got = self.plan(sessions, {"shared": "clean"})
        self.assertEqual({k: v["safety"] for k, v in got.items()}, {"m1": "manter", "m2": "manter", "active": "manter"})
        both = self.plan(sessions[:2], {"shared": "clean"})
        self.assertEqual({v["safety"] for v in both.values()}, {"seguro"})

    def test_parent_whose_archive_takes_a_kept_child_is_owner_decision(self):
        # measured 22/11: archiving "Forja" also archived its idle side session "SICIDN" (no PR, recent)
        sessions = [self.s("forja", "a", prState="MERGED"),
                    self.s("sicidn", "b", startedBy="forja"),
                    self.s("busy", "c", startedBy="forja", isRunning=True),
                    self.s("withpr", "d", startedBy="forja", prState="OPEN")]
        got = self.plan(sessions, {"a": "clean", "b": "clean", "c": "clean", "d": "clean"})
        self.assertEqual(got["forja"]["safety"], "decisao")
        self.assertIn("leva junto: sicidn", got["forja"]["reason"])
        self.assertEqual(got["forja"]["also_archives"], ["sicidn"])  # running / open-PR children stay
        merged_kid = self.plan([self.s("forja", "a", prState="MERGED"),
                                self.s("kid", "b", startedBy="forja", prState="MERGED")],
                               {"a": "clean", "b": "clean"})
        self.assertEqual(merged_kid["forja"]["safety"], "seguro")  # the child would be archived anyway

    def test_worktree_paths_read_on_any_os(self):
        self.assertTrue(cl.is_worktree(r"C:\dev\r\.claude\worktrees\a"))
        self.assertTrue(cl.is_worktree("/home/u/dev/r/.claude/worktrees/a"))
        self.assertFalse(cl.is_worktree(r"C:\dev\nexus-quant"))
        self.assertFalse(cl.is_worktree(None))

    def test_no_sessions_file_plans_nothing(self):
        self.assertEqual(cl.plan_sessions(None, NOW), [])


class WorktreeStateCase(Base):
    def test_real_git_states_and_index_untouched(self):
        bare, main = self.root / "remote.git", self.root / "main"
        subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
        subprocess.run(["git", "init", "-q", str(main)], check=True)
        git(main, "config", "user.email", "t@t")
        git(main, "config", "user.name", "t")
        (main / "a.txt").write_text("a", encoding="utf-8")
        git(main, "add", "a.txt")
        git(main, "commit", "-q", "-m", "a")
        self.assertEqual(cl.worktree_state(main)["state"], "work")  # commit on no remote
        git(main, "remote", "add", "origin", str(bare))
        git(main, "push", "-q", "-u", "origin", "HEAD")
        index = main / ".git" / "index"
        before = index.stat().st_mtime_ns
        self.assertEqual(cl.worktree_state(main), {"state": "clean", "dirty": 0, "unpushed": 0})
        self.assertEqual(index.stat().st_mtime_ns, before)
        (main / "b.txt").write_text("b", encoding="utf-8")
        self.assertEqual(cl.worktree_state(main)["state"], "work")
        (main / "b.txt").unlink()
        (main / "a.txt").write_text("a2", encoding="utf-8")
        git(main, "commit", "-q", "-am", "a2")
        self.assertEqual(cl.worktree_state(main), {"state": "work", "dirty": 0, "unpushed": 1})
        self.assertEqual(cl.worktree_state(self.root / "nope")["state"], "missing")
        (self.root / "plain").mkdir()
        self.assertEqual(cl.worktree_state(self.root / "plain")["state"], "not_git")


class FilesPlanCase(Base):
    def test_profiles_skip_in_use_links_and_other_names(self):
        for name in ("puppeteer_dev_chrome_profile-a", "puppeteer_dev_chrome_profile-ab", "other"):
            (self.temp / name).mkdir()
        (self.temp / "puppeteer_dev_chrome_profile-a" / "f").write_bytes(b"x" * 100)
        procs = [proc(1, 0, "chrome.exe", f"chrome --user-data-dir={self.temp / 'puppeteer_dev_chrome_profile-ab'}")]
        items = cl.plan_profiles(self.temp, procs, BUDGET)
        self.assertEqual([Path(x["target"]).name for x in items], ["puppeteer_dev_chrome_profile-a"])
        self.assertEqual(items[0]["bytes"], 100)
        self.assertEqual(cl.plan_profiles(self.temp, None, BUDGET), [])  # processes unknown: no deletion planned

    def test_repo_tmp_only_idle_and_unused(self):
        tmp = self.dev / "repo" / "_local" / "tmp"
        wt_tmp = self.dev / "repo" / ".claude" / "worktrees" / "w1" / "_local" / "tmp"
        for d in (tmp / "old", tmp / "fresh", tmp / "used", tmp / "oldwithnew", wt_tmp / "wold"):
            d.mkdir(parents=True)
            (d / "f").write_bytes(b"x" * 10)
        for d in (tmp / "old", tmp / "used", tmp / "oldwithnew", wt_tmp / "wold"):
            self.old(d)
        (tmp / "oldwithnew" / "new").write_bytes(b"n")
        procs = [proc(1, 0, "python.exe", f"pytest --basetemp {tmp / 'used'}")]
        items = cl.plan_repo_tmp(self.dev, procs, time.time())
        self.assertEqual(sorted(Path(x["target"]).name for x in items), ["old", "wold"])
        self.assertTrue(all(x["safety"] == "seguro" for x in items))
        unknown = cl.plan_repo_tmp(self.dev, None, time.time())
        self.assertEqual({x["safety"] for x in unknown}, {"decisao"})  # without process list, owner decides

    def test_orphan_tree_plan_collects_children(self):
        procs = [proc(10, 999, "node.exe", "npx @playwright/mcp", created=10, ws=2**20),
                 proc(11, 10, "chrome.exe", "chrome playwright_chromiumdev_profile-1", created=11, ws=2**20),
                 proc(12, 11, "chrome.exe", "chrome --type=renderer", created=12, ws=2**20),
                 proc(20, 1, "claude.exe", created=1), proc(1, 0, "explorer.exe", created=0),
                 proc(21, 20, "node.exe", "node chrome-devtools-mcp", created=21)]
        items = cl.plan_processes(procs, BUDGET)
        self.assertEqual([(x["pid"], x["processes"], x["ram_bytes"]) for x in items], [(10, 3, 3 * 2**20)])

    def test_settings_items(self):
        servers = [proc(i, 1, "node.exe", "node threejs-devtools-mcp", i) for i in range(3)]
        snap = {"enabled_plugins": {}, "processes": servers}
        items = cl.plan_settings(snap, {"auto_archive_on_pr_close": False, "auto_archive_inactive_days": 0}, BUDGET)
        self.assertEqual(len(items), 3)
        self.assertEqual({x["safety"] for x in items}, {"decisao"})
        self.assertEqual(items[0]["executor"], "dono")  # account plugin: only the owner can switch it off
        done = cl.plan_settings({"enabled_plugins": {"parallax-threejs@m": False}},
                                {"auto_archive_on_pr_close": True, "auto_archive_inactive_days": 7}, BUDGET)
        self.assertEqual(done, [])
        quiet = cl.plan_settings({"enabled_plugins": {}, "processes": servers[:1]},
                                 {"auto_archive_on_pr_close": True, "auto_archive_inactive_days": 7}, BUDGET)
        self.assertEqual(quiet, [])  # switched off in the account: nothing running, nothing to propose


class OffloadCase(Base):
    """_local/backups -> OneDrive/10-dev/<repo>/backups, only what no tracked file reads, only by explicit id."""

    def setUp(self):
        super().setUp()
        self.od = self.home / "OneDrive"
        (self.od / "10-dev").mkdir(parents=True)
        self.env = unittest.mock.patch.dict("os.environ", {"OneDrive": str(self.od)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.repo = self.dev / "repo"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        git(self.repo, "config", "user.email", "t@t")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "cfg.env").write_text("DATA=_local/backups/lido/dados.csv\n", encoding="utf-8")
        git(self.repo, "add", "cfg.env")
        git(self.repo, "commit", "-q", "-m", "c")
        b = self.repo / "_local" / "backups"
        for name in ("lido", "livre", "pequeno"):
            (b / name).mkdir(parents=True)
        (b / "lido" / "dados.csv").write_bytes(b"1" * 10)
        (b / "livre" / "sub").mkdir()
        (b / "livre" / "sub" / "a.bin").write_bytes(b"2" * 20)
        (b / "livre.tar").write_bytes(b"3" * 30)
        (b / "pequeno" / "x").write_bytes(b"4")
        self.min = unittest.mock.patch.object(cl, "OFFLOAD_MIN_BYTES", 5)
        self.min.start()
        self.addCleanup(self.min.stop)

    def by_name(self, items):
        return {Path(x["target"]).name: x for x in items}

    def test_plan_classes(self):
        items = self.by_name(cl.plan_offload(self.dev, self.home))
        self.assertEqual(items["lido"]["safety"], "manter")
        self.assertIn("cfg.env", items["lido"]["reason"])
        self.assertEqual(items["livre"]["safety"], "decisao")
        self.assertEqual(Path(items["livre"]["dest"]), self.od / "10-dev" / "repo" / "backups" / "livre")
        self.assertEqual(items["livre.tar"]["safety"], "decisao")
        self.assertNotIn("pequeno", items)  # below the size floor
        self.assertTrue(all(x["kind"] == "offload_backup" and x["safety"] != "seguro" for x in items.values()))
        (self.od / "10-dev" / "repo" / "backups" / "livre").mkdir(parents=True)
        self.assertEqual(self.by_name(cl.plan_offload(self.dev, self.home))["livre"]["safety"], "manter")
        kept = self.by_name(cl.plan_offload(self.dev, self.home, {"repo/livre.tar": "catálogo protegido"}))
        self.assertEqual((kept["livre.tar"]["safety"], kept["livre.tar"]["reason"]), ("manter", "catálogo protegido"))
        no_onedrive = self.root / "other-home"
        no_onedrive.mkdir()
        with unittest.mock.patch.dict("os.environ", {"OneDrive": str(no_onedrive / "OneDrive")}):
            self.assertEqual(cl.plan_offload(self.dev, no_onedrive), [])

    def plan(self):
        snap = {"processes": [], "platform": sys.platform, "enabled_plugins": None}
        return cl.build_plan(snap, BUDGET, self.dev, self.temp, self.home, None, None), snap

    def test_safe_never_moves_backups_and_id_moves_with_proof(self):
        plan, snap = self.plan()
        res = cl.apply_plan(plan, None, True, True, BUDGET, self.home, snap=snap)
        self.assertEqual(res["results"], [])  # --safe: offload is the owner's decision, never automatic
        ids = {x["id"] for x in plan["items"] if x["kind"] == "offload_backup" and x["safety"] == "decisao"}
        with unittest.mock.patch.object(cl, "mark_online_only", return_value=True) as mark:
            res = cl.apply_plan(plan, ids, False, True, BUDGET, self.home, snap=snap)
        self.assertEqual({r["status"] for r in res["results"]}, {"DONE"})
        self.assertEqual(mark.call_count, 2)
        dest = self.od / "10-dev" / "repo" / "backups"
        self.assertEqual((dest / "livre" / "sub" / "a.bin").read_bytes(), b"2" * 20)
        self.assertEqual((dest / "livre.tar").read_bytes(), b"3" * 30)
        self.assertFalse((self.repo / "_local" / "backups" / "livre").exists())
        self.assertTrue((self.repo / "_local" / "backups" / "lido" / "dados.csv").exists())

    def test_bad_copy_keeps_original(self):
        plan, snap = self.plan()
        item = [x for x in plan["items"] if Path(x["target"]).name == "livre"][0]
        real = cl.shutil.copytree

        def corrupt(src, dst, *a, **k):  # copytree recurses through itself: corrupt only the top call
            out = real(src, dst, *a, **k)
            if str(dst).endswith(".partial"):
                (Path(dst) / "sub" / "a.bin").write_bytes(b"x")
            return out

        def broken(src, dst, *a, **k):  # copy dies halfway
            Path(dst).mkdir()
            (Path(dst) / "half").write_bytes(b"h")
            raise OSError("disk full")
        backups = self.od / "10-dev" / "repo" / "backups"
        for fake, why in ((corrupt, "não confere"), (broken, "disk full")):
            with self.subTest(why), unittest.mock.patch.object(cl.shutil, "copytree", fake):
                res = cl.apply_plan(plan, {item["id"]}, False, True, BUDGET, self.home, snap=snap)
                self.assertEqual(res["results"][0]["status"], "FAILED")
                self.assertIn(why, res["results"][0]["reason"])
                self.assertTrue((self.repo / "_local" / "backups" / "livre" / "sub" / "a.bin").exists())
                self.assertFalse((backups / "livre").exists())
                self.assertFalse((backups / "livre.partial").exists())

    def test_recheck_refuses_tampered_or_newly_read(self):
        plan, snap = self.plan()
        item = [x for x in plan["items"] if Path(x["target"]).name == "livre"][0]
        tampered = json.loads(json.dumps(plan))
        [x for x in tampered["items"] if x["id"] == item["id"]][0]["dest"] = str(self.root / "elsewhere" / "livre")
        res = cl.apply_plan(tampered, {item["id"]}, False, True, BUDGET, self.home, snap=snap)
        self.assertIn("destino fora", res["results"][0]["reason"])
        (self.repo / "uses.py").write_text('open("_local/backups/livre/sub/a.bin")\n', encoding="utf-8")
        git(self.repo, "add", "uses.py")
        res = cl.apply_plan(plan, {item["id"]}, False, True, BUDGET, self.home, snap=snap)
        self.assertEqual(res["results"][0]["status"], "SKIPPED")
        self.assertTrue((self.repo / "_local" / "backups" / "livre").exists())
        busy = {"processes": [proc(1, 0, "python.exe", f"python x {self.repo / '_local' / 'backups' / 'livre.tar'}")]}
        tar = [x for x in plan["items"] if Path(x["target"]).name == "livre.tar"][0]
        res = cl.apply_plan(plan, {tar["id"]}, False, True, BUDGET, self.home, snap=busy)
        self.assertEqual(res["results"][0]["reason"], "em uso agora")
        protected = dict(BUDGET, offload_keep={"repo/livre.tar": "catálogo"})
        res = cl.apply_plan(plan, {tar["id"]}, False, True, protected, self.home, snap=snap)
        self.assertIn("protegido", res["results"][0]["reason"])
        self.assertTrue((self.repo / "_local" / "backups" / "livre.tar").exists())


class RemoveTreeCase(Base):
    def test_readonly_files_are_removed(self):
        d = self.temp / "x" / "y"
        d.mkdir(parents=True)
        f = d / "ro"
        f.write_bytes(b"1")
        os.chmod(f, stat.S_IREAD)
        cl.remove_tree(self.temp / "x")
        self.assertFalse((self.temp / "x").exists())

    @unittest.skipUnless(sys.platform == "win32", "junction is Windows-only")
    def test_junction_target_survives(self):
        target = self.root / "precious"
        target.mkdir()
        (target / "keep.txt").write_text("keep", encoding="utf-8")
        victim = self.temp / "victim"
        (victim / "sub").mkdir(parents=True)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(victim / "sub" / "node_modules"), str(target)],
                       check=True, capture_output=True)
        subprocess.run(["cmd", "/c", "mklink", "/J", str(self.temp / "toplink"), str(target)],
                       check=True, capture_output=True)
        cl.remove_tree(victim)
        cl.remove_tree(self.temp / "toplink")
        self.assertFalse(victim.exists())
        self.assertFalse((self.temp / "toplink").exists())
        self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "keep")


class ApplyCase(Base):
    def make_plan(self, procs, **extra):
        (self.temp / "puppeteer_dev_chrome_profile-z").mkdir()
        (self.temp / "puppeteer_dev_chrome_profile-z" / "f").write_bytes(b"x" * 50)
        snap = {"processes": procs, "platform": "win32", "enabled_plugins": None}
        sessions = [{"sessionId": "s1", "title": "s1", "cwd": str(self.dev), "isArchived": False,
                     "isRunning": False, "prState": "MERGED", "lastActivityAt": iso(time.time())}]
        plan = cl.build_plan(snap, BUDGET, self.dev, self.temp, self.home, sessions, None, **extra)
        return plan, snap

    def ids(self, plan, kind):
        return {x["id"] for x in plan["items"] if x["kind"] == kind}

    def test_dry_run_changes_nothing_and_apply_deletes(self):
        procs = [proc(1, 0, "explorer.exe", created=0)]
        plan, snap = self.make_plan(procs)
        self.assertIn("configuração do app", plan["not_run"])
        dry = cl.apply_plan(plan, None, True, False, BUDGET, self.home, snap=snap)
        self.assertEqual([r["status"] for r in dry["results"]], ["WOULD_DO"])
        self.assertTrue((self.temp / "puppeteer_dev_chrome_profile-z").exists())
        self.assertIsNone(dry["freed_bytes_measured"])
        done = cl.apply_plan(plan, None, True, True, BUDGET, self.home, snap=snap)
        self.assertEqual([r["status"] for r in done["results"]], ["DONE"])
        self.assertFalse((self.temp / "puppeteer_dev_chrome_profile-z").exists())

    def test_recheck_skips_what_changed(self):
        plan, _ = self.make_plan([proc(1, 0, "explorer.exe", created=0)])
        now_used = {"processes": [proc(5, 1, "chrome.exe",
                                       f"chrome --user-data-dir={self.temp / 'puppeteer_dev_chrome_profile-z'}")]}
        res = cl.apply_plan(plan, None, True, True, BUDGET, self.home, snap=now_used)
        self.assertEqual(res["results"][0]["status"], "SKIPPED")
        self.assertTrue((self.temp / "puppeteer_dev_chrome_profile-z").exists())
        res = cl.apply_plan(plan, None, True, True, BUDGET, self.home, snap={"processes": None})
        self.assertEqual(res["results"][0]["reason"], "em uso agora")

    def test_tampered_target_outside_allowed_places_is_skipped(self):
        plan, snap = self.make_plan([proc(1, 0, "explorer.exe", created=0)])
        outside = self.root / "puppeteer_dev_chrome_profile-evil"
        outside.mkdir()
        for x in plan["items"]:
            if x["kind"] == "orphan_profile":
                x["target"] = str(outside)
        res = cl.apply_plan(plan, None, True, True, BUDGET, self.home, snap=snap)
        self.assertEqual(res["results"][0]["status"], "SKIPPED")
        self.assertTrue(outside.exists())

    def test_orphan_tree_killed_only_if_still_same(self):
        procs = [proc(10, 999, "node.exe", "npx @playwright/mcp", created=10)]
        plan, snap = self.make_plan(procs)
        tree = self.ids(plan, "orphan_tree")
        with unittest.mock.patch.object(cl, "kill_tree") as kill:
            res = cl.apply_plan(plan, tree, False, True, BUDGET, self.home, snap=snap)
            kill.assert_called_once_with(10)
            self.assertEqual(res["results"][0]["status"], "DONE")
            reused = {"processes": [proc(10, 999, "node.exe", "npx @playwright/mcp", created=77)]}
            res = cl.apply_plan(plan, tree, False, True, BUDGET, self.home, snap=reused)
            self.assertEqual(res["results"][0]["status"], "SKIPPED")
            self.assertEqual(kill.call_count, 1)

    def test_refusals(self):
        plan, snap = self.make_plan([proc(1, 0, "explorer.exe", created=0)])
        with self.assertRaises(cl.CleanError):
            cl.apply_plan(plan, None, False, True, BUDGET, self.home, snap=snap)  # nothing chosen
        with self.assertRaises(cl.CleanError):
            cl.apply_plan(plan, {"nope-1"}, False, True, BUDGET, self.home, snap=snap)
        old = dict(plan, created_at=time.time() - 3 * 3600)
        with self.assertRaises(cl.CleanError):
            cl.apply_plan(old, None, True, True, BUDGET, self.home, snap=snap)
        with self.assertRaises(cl.CleanError):
            cl.apply_plan(dict(plan, kind="x"), None, True, True, BUDGET, self.home, snap=snap)
        sess = self.ids(plan, "archive_session")
        res = cl.apply_plan(plan, sess, False, True, BUDGET, self.home, snap=snap)
        self.assertEqual((res["results"], res["refused_app_items"]), ([], sorted(sess)))

    def test_main_plan_then_apply_and_blocked(self):
        sessions = self.root / "s.json"
        sessions.write_text("[]", encoding="utf-8")
        out_file = self.root / "_local" / "plan.json"
        args = ["--home", str(self.home), "--dev-root", str(self.dev), "--temp", str(self.temp)]
        snap = {"processes": [], "platform": "win32", "enabled_plugins": None}
        with unittest.mock.patch.object(rc, "collect", return_value=snap), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cl.main(["plan", *args, "--sessions", str(sessions), "--output", str(out_file)]), 0)
        self.assertIn("Plano: nada foi apagado", out.getvalue())
        self.assertEqual(json.loads(out_file.read_text(encoding="utf-8"))["kind"], "resource-plan")
        with unittest.mock.patch.object(rc, "collect_windows", return_value={"processes": []}), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cl.main(["apply", *args, "--plan", str(out_file), "--safe"]), 0)
        self.assertFalse(json.loads(out.getvalue())["applied"])
        sessions.write_text("{}", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(cl.main(["plan", *args, "--sessions", str(sessions)]), 2)
        self.assertEqual(json.loads(err.getvalue())["status"], "BLOCKED")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(cl.main(["apply", *args]), 2)

    def test_harnessctl_dispatches(self):
        hspec = importlib.util.spec_from_file_location("harnessctl_cl", ROOT / "scripts/harnessctl.py")
        h = importlib.util.module_from_spec(hspec)
        hspec.loader.exec_module(h)
        with unittest.mock.patch.dict(sys.modules, {"resource_clean": cl}), \
                unittest.mock.patch.object(cl, "main", return_value=9) as called:
            self.assertEqual(h.main(["resource-clean", "plan"]), 9)
        called.assert_called_once_with(["plan"])


if __name__ == "__main__":
    unittest.main()
