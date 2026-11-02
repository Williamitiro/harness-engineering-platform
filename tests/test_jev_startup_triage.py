"""Keyless JEV startup diagnostics; no paid API and no Node download."""
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.jev_startup_triage import clean_runtime_env, stderr_category, check_node, check_mcp
from scripts.jev_adapter import JevAdapterError


class JevStartupTriageTests(unittest.TestCase):
    def test_minimal_environment_never_inherits_keys(self):
        parent = {
            "PATH": "simulated-path", "SystemRoot": "C:\\Windows",
            "TYPESAFE_API_KEY": "private-typesafe", "OPENROUTER_API_KEY": "private-openrouter",
            "INFISICAL_TOKEN": "private-infisical", "CODEX_TOKEN": "private-codex",
            "SystemDrive": "C:", "USERPROFILE": "C:\\User", "APPDATA": "C:\\User\\AppData",
        }
        minimal = clean_runtime_env(parent)
        operational = clean_runtime_env(parent, windows_os=True)
        self.assertNotIn("SystemDrive", minimal)
        self.assertEqual(operational["SystemDrive"], "C:")
        self.assertEqual(operational["APPDATA"], "C:\\User\\AppData")
        for selected in (minimal, operational):
            self.assertEqual(selected["JEV_CODE_PROVIDER"], "openrouter")
            self.assertNotIn("TYPESAFE_API_KEY", selected)
            self.assertNotIn("OPENROUTER_API_KEY", selected)
            self.assertNotIn("INFISICAL_TOKEN", selected)
            self.assertNotIn("CODEX_TOKEN", selected)
            self.assertNotIn("private", str(selected))

    def test_stderr_does_not_echo_raw_data(self):
        output = stderr_category(b"Assertion failed: private-api-key in uv_loop_init")
        self.assertEqual(output, ["NODE_ASSERTION_OR_ABORT", "NODE_FATAL_RUNTIME"])
        self.assertNotIn("private-api-key", str(output))

    def test_node_abort_has_bounded_safe_diagnostic(self):
        completed = subprocess.CompletedProcess(["node", "-e", "..."], 134, b"", b"FATAL ERROR private-token")
        with patch("scripts.jev_startup_triage.subprocess.run", return_value=completed) as run:
            result = check_node("node", {"PATH": "simulated"})
        self.assertEqual(result["exit_code"], 134)
        self.assertEqual(result["stderr_categories"], ["NODE_FATAL_RUNTIME"])
        self.assertEqual(result["status"], "FAIL")
        self.assertNotIn("private-token", str(result))
        self.assertEqual(run.call_args.kwargs["timeout"], 8)

    def test_node_timeout_is_terminal(self):
        with patch("scripts.jev_startup_triage.subprocess.run",
                   side_effect=subprocess.TimeoutExpired("node", 8)):
            self.assertEqual(check_node("node", {})["code"], "NODE_TIMEOUT")

    def test_mcp_failure_reports_only_safe_codes(self):
        fake = MagicMock()
        fake.__enter__.side_effect = JevAdapterError("private error from provider", "MCP_STDOUT_CLOSED")
        fake.startup_diagnostic.return_value = {"process_exited": True, "exit_code": 134}
        with patch("scripts.jev_startup_triage.JevMcpClient", return_value=fake):
            result = check_mcp("node", Path("package/dist/cli.js"), {})
        self.assertEqual(result["code"], "MCP_STDOUT_CLOSED")
        self.assertEqual(result["diagnostic"]["exit_code"], 134)
        self.assertNotIn("private", str(result))

    def test_mcp_success_does_not_call_provider_tool(self):
        fake = MagicMock()
        fake.startup_diagnostic.return_value = {"process_started": True}
        with patch("scripts.jev_startup_triage.JevMcpClient", return_value=fake):
            result = check_mcp("node", Path("package/dist/cli.js"), {})
        self.assertEqual(result["status"], "PASS")
        fake.classify.assert_not_called()


if __name__ == "__main__":
    unittest.main()
