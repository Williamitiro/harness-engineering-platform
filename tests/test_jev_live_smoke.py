"""Safety and no-network tests for the opt-in HE-JEV-006 smoke runner."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.jev_adapter import JevMcpClient
from scripts.jev_live_smoke import (
    SmokePreflightError, isolated_child_env, run_one_call, verify_package,
)


class JEVLiveSmokeOfflineTests(unittest.TestCase):
    def _package(self, folder: Path) -> Path:
        pkg = folder / "jev-code"
        (pkg / "dist").mkdir(parents=True)
        (pkg / "package.json").write_text(
            json.dumps({"name": "@french-castle/jev-code", "version": "0.5.0"}),
            encoding="utf-8",
        )
        entry = pkg / "dist" / "cli.js"
        entry.write_text("// dummy; never executed by test", encoding="utf-8")
        return entry

    def test_explicit_env_does_not_inherit_unrelated_secrets(self):
        parent = {
            "TYPESAFE_API_KEY": "synthetic-not-real",
            "UNRELATED_API_KEY": "must-not-pass",
            "PATH": "example-path",
            "HOME": "sensitive-home",
        }
        env = isolated_child_env(parent)
        self.assertEqual(env["TYPESAFE_API_KEY"], "synthetic-not-real")
        self.assertEqual(env["PATH"], "example-path")
        self.assertNotIn("UNRELATED_API_KEY", env)
        self.assertNotIn("HOME", env)

    def test_missing_key_fails_before_any_call(self):
        with self.assertRaisesRegex(SmokePreflightError, "absent"):
            isolated_child_env({"PATH": "x"})

    def test_unpinned_package_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._package(Path(tmp))
            (path.parent.parent / "package.json").write_text(
                json.dumps({"name": "@french-castle/jev-code", "version": "0.6.0"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SmokePreflightError, "version"):
                verify_package(path)

    def test_one_call_has_no_raw_output_or_credential_and_no_cost_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._package(Path(tmp))
            env = {
                "PATH": os.environ.get("PATH", ""),
                "TYPESAFE_API_KEY": "synthetic-not-real",
                "UNRELATED_API_KEY": "must-not-pass",
            }
            result = {
                "label": "software-development",
                "execution_status": "SUCCESS",
                "model": "typed-model-1",
                "latency_ms": 12.0,
                "tokens_in": 13,
                "tokens_out": 2,
                "raw_output": "do not log this body",
            }
            with patch("scripts.jev_live_smoke.shutil.which", return_value="/fake/node"), \
                 patch("scripts.jev_live_smoke.JevMcpClient") as ctor:
                client = ctor.return_value.__enter__.return_value
                client.classify.return_value = result
                emitted = run_one_call(path, env)
                self.assertEqual(client.classify.call_count, 1)
                passed = ctor.call_args.kwargs["env"]
                self.assertNotIn("UNRELATED_API_KEY", passed)
                self.assertEqual(passed["TYPESAFE_API_KEY"], "synthetic-not-real")
            serialized = json.dumps(emitted)
            self.assertNotIn("do not log this body", serialized)
            self.assertNotIn("synthetic-not-real", serialized)
            self.assertEqual(emitted["cost_usd"], None)
            self.assertFalse(emitted["G1_verified"])
            self.assertFalse(emitted["benchmark_evidence"])
            self.assertEqual(emitted["status"], "PROVIDER_RESPONSE_OBSERVED")

    def test_untrusted_model_string_is_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._package(Path(tmp))
            with patch("scripts.jev_live_smoke.shutil.which", return_value="/fake/node"), \
                 patch("scripts.jev_live_smoke.JevMcpClient") as ctor:
                client = ctor.return_value.__enter__.return_value
                client.classify.return_value = {
                    "model": "untrusted\nstring-or-secret",
                    "label": "software-development",
                    "execution_status": "SUCCESS",
                }
                output = run_one_call(path, {"TYPESAFE_API_KEY": "synthetic-key"})
                self.assertEqual(output["model"], "REDACTED")

    def test_mcp_explicit_env_is_not_merged_with_parent(self):
        with patch.dict(os.environ, {"PARENT_TOKEN": "should-not-inherit"}, clear=False):
            client = JevMcpClient(
                command=["fake-not-executed"],
                env={"TYPESAFE_API_KEY": "synthetic-key"},
            )
            self.assertNotIn("PARENT_TOKEN", client.env)
            self.assertEqual(client.env["TYPESAFE_API_KEY"], "synthetic-key")


if __name__ == "__main__":
    unittest.main()
