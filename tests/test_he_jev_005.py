#!/usr/bin/env python3
"""Unit tests for HE-JEV-005: Infisical verifier, G1 canary probes, and native baseline."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.canary_probes import (
    check_git_isolation,
    check_ground_truth_isolation,
    check_host_credentials,
    check_network_egress,
    run_all_canaries,
)
from scripts.infisical_verifier import (
    check_cli_installed,
    check_local_project_config,
    check_secret_presence,
    run_full_verification,
)
from scripts.native_baseline import (
    NativeBaselineAdapter,
    build_native_prompt,
    compute_sha256,
)


class InfisicalVerifierTests(unittest.TestCase):
    def test_secret_presence_absent(self):
        old_val = os.environ.pop("TYPESAFE_API_KEY", None)
        try:
            res = check_secret_presence("TYPESAFE_API_KEY")
            self.assertEqual(res["status"], "AUSENTE")
            self.assertFalse(res["available_to_process"])
        finally:
            if old_val is not None:
                os.environ["TYPESAFE_API_KEY"] = old_val

    def test_secret_presence_present_without_leak(self):
        dummy_secret = "ts_live_secret_key_abcdef123456"
        old_val = os.environ.get("TYPESAFE_API_KEY")
        os.environ["TYPESAFE_API_KEY"] = dummy_secret
        try:
            res = check_secret_presence("TYPESAFE_API_KEY")
            self.assertEqual(res["status"], "PRESENTE")
            self.assertTrue(res["available_to_process"])
            self.assertEqual(res["char_length"], len(dummy_secret))
            # Critical: NEVER return the raw secret
            res_str = json.dumps(res)
            self.assertNotIn(dummy_secret, res_str)
        finally:
            if old_val is not None:
                os.environ["TYPESAFE_API_KEY"] = old_val
            else:
                os.environ.pop("TYPESAFE_API_KEY", None)

    def test_local_project_config_parses_yaml(self):
        cfg = check_local_project_config()
        self.assertTrue(cfg["configured"])
        self.assertEqual(cfg["project_id"], "24b65ce2-c2c7-45f9-b54b-9a1c345973cc")

    def test_cli_installed_detection(self):
        """CLI detection must work in CI without requiring a local Infisical login."""
        with patch("scripts.infisical_verifier.shutil.which", return_value="/mock/infisical"), \
             patch("scripts.infisical_verifier.subprocess.run",
                   return_value=SimpleNamespace(stdout="infisical version 0.44.11",
                                                stderr="", returncode=0)):
            cli = check_cli_installed()
            self.assertTrue(cli["installed"])
            self.assertEqual(cli["version"], "0.44.11")
        with patch("scripts.infisical_verifier.shutil.which", return_value=None):
            self.assertFalse(check_cli_installed()["installed"])


class CanaryProbesTests(unittest.TestCase):
    def test_host_detects_git_repository(self):
        """When executed in repo, git probe must detect .git and report LEAKED."""
        res = check_git_isolation()
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "LEAKED")
        self.assertTrue(any(".git" in str(p) for p in res["leaks"]))

    def test_host_detects_ground_truth(self):
        """When executed in repo, ground truth probe must detect golden holdout and report LEAKED."""
        res = check_ground_truth_isolation()
        self.assertFalse(res["passed"])
        self.assertEqual(res["status"], "LEAKED")

    def test_canary_passes_in_isolated_clean_dir(self):
        """In a clean empty temporary directory without git or golden files, git and gt pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                git_res = check_git_isolation()
                # If tmpdir is not under git repo, git probe should pass
                if not any((p / ".git").exists() for p in (Path(tmpdir), *Path(tmpdir).parents)):
                    self.assertTrue(git_res["passed"])
            finally:
                os.chdir(old_cwd)

    def test_run_all_canaries_verdict_structure(self):
        summary = run_all_canaries()
        self.assertIn("isolation_verdict", summary)
        self.assertIn("probes", summary)
        self.assertIn("credentials", summary["probes"])
        self.assertIn("git", summary["probes"])
        self.assertIn("ground_truth", summary["probes"])
        self.assertIn("network", summary["probes"])


class NativeBaselineTests(unittest.TestCase):
    def test_build_native_prompt_structure(self):
        task = {
            "domain": "ci_triage",
            "input_text": "Timeout in test_network after 30s",
            "candidate_labels": ["flaky-test", "timeout", "infra-environment"],
        }
        prompt = build_native_prompt(task)
        self.assertIn("ci_triage", prompt)
        self.assertIn("Timeout in test_network after 30s", prompt)
        self.assertIn('"timeout"', prompt)
        self.assertIn("Rules:", prompt)

    def test_native_baseline_simulation_mode(self):
        task = {
            "task_id": "test_triage_01",
            "domain": "ci_triage",
            "task_type": "standard",
            "input_text": "Connection reset by peer during build",
            "candidate_labels": ["infra-environment", "flaky-test", "code-bug"],
        }
        adapter = NativeBaselineAdapter(mode="simulation")
        res = adapter.classify_task(task)
        self.assertEqual(res["evidence_kind"], "SYNTHETIC")
        self.assertTrue(res["is_synthetic"])
        self.assertEqual(res["condition"], "CONDITION_A_NATIVE")
        self.assertIsNone(res["parsed_decision"]["confidence"])
        self.assertIsNone(res["parsed_decision"]["margin"])
        self.assertIsNone(res["observed_metrics"]["cost_usd"])
        self.assertGreater(res["observed_metrics"]["tokens_in"], 0)
        self.assertGreater(res["observed_metrics"]["tokens_out"], 0)
        self.assertEqual(res["raw_input_sha256"], compute_sha256(res["raw_input"]))
        self.assertEqual(res["raw_output_sha256"], compute_sha256(res["raw_output"]))

    def test_native_baseline_live_blocked_closed(self):
        adapter = NativeBaselineAdapter(mode="live")
        with self.assertRaises(RuntimeError) as ctx:
            adapter.classify_task({"task_id": "t1", "candidate_labels": ["a", "b"]})
        self.assertIn("BLOCKED_G1", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
