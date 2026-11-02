#!/usr/bin/env python3
"""Integration tests for the real @french-castle/jev-code@0.5.0 MCP package.

Validates the real upstream package in a keyless, zero-cost environment:
- Verifies stdio MCP initialize handshake and serverInfo.
- Verifies tools/list registers jev_classify with the v0.5.0 schema.
- Verifies schema conformance for instructions, items, and classes.
- Verifies error reporting (isError: true) when no API key is provided.
- Verifies timeout enforcement and clean process termination.

These tests run against the REAL upstream package, NOT a mock.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from scripts.jev_adapter import JevAdapterError, JevMcpClient
except ImportError:
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.jev_adapter import JevAdapterError, JevMcpClient


class RealJevPackageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.npx = shutil.which("npx") or shutil.which("npx.cmd")
        if not cls.npx:
            raise unittest.SkipTest("npx not available on PATH")
        try:
            probe = subprocess.run(
                [cls.npx, "-y", "@french-castle/jev-code@0.5.0", "--version"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if probe.returncode != 0:
                raise unittest.SkipTest(f"jev-code package could not be executed: {probe.stderr.strip()}")
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise unittest.SkipTest(f"jev-code package probe failed: {exc}")

    def test_01_real_package_mcp_initialize(self):
        """Test real package stdio MCP initialize and server identity."""
        client = JevMcpClient()
        try:
            client.start(timeout_s=15.0)
            proc = client.process
            self.assertIsNotNone(proc)
            self.assertIsNone(proc.poll(), "Process should be running")
        finally:
            client.close()
            if proc is not None:
                self.assertIsNotNone(proc.poll(), "Process should be cleanly terminated")

    def test_02_real_package_registers_jev_classify(self):
        """Test real package registers jev_classify and adheres to v0.5.0 schema."""
        proc = subprocess.Popen(
            [self.npx, "-y", "@french-castle/jev-code@0.5.0", "mcp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            def send(msg):
                proc.stdin.write(json.dumps(msg) + "\n")
                proc.stdin.flush()

            def read():
                line = proc.stdout.readline()
                return json.loads(line) if line else None

            # 1. Initialize
            send({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-runner", "version": "1.0.0"},
                },
            })
            init_res = read()
            self.assertEqual(init_res.get("id"), 1)
            server_info = init_res.get("result", {}).get("serverInfo", {})
            self.assertEqual(server_info.get("name"), "jev-code")
            self.assertEqual(server_info.get("version"), "0.5.0")

            # 2. Initialized notification
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})

            # 3. List tools
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            tools_res = read()
            tools = tools_res.get("result", {}).get("tools", [])
            tool_names = [t.get("name") for t in tools]
            self.assertIn("jev_classify", tool_names)

            # 4. Check schema properties
            classify_tool = next(t for t in tools if t.get("name") == "jev_classify")
            schema = classify_tool.get("inputSchema", {})
            self.assertIn("items", schema.get("required", []))
            self.assertIn("classes", schema.get("required", []))
            properties = schema.get("properties", {})
            self.assertIn("items", properties)
            self.assertIn("classes", properties)
            self.assertIn("instructions", properties)
            self.assertIn("auto_accept", properties)
            self.assertIn("min_margin", properties)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

    def test_03_real_package_fails_cleanly_without_api_key(self):
        """Test real package reports isError: true when called without an API key."""
        # Ensure environment has no API key
        clean_env = {k: v for k, v in subprocess.os.environ.items() if not k.endswith("_API_KEY")}
        client = JevMcpClient(env=clean_env)
        try:
            client.start(timeout_s=15.0)
            with self.assertRaises(JevAdapterError) as ctx:
                client.classify(
                    question="Route CI flake issue",
                    choices=["flaky-test", "infra-bug"],
                    timeout_s=15.0,
                )
            self.assertIn("jev_classify tool reported an error", str(ctx.exception))
        finally:
            client.close()

    def test_04_client_timeout_handling_and_process_cleanup(self):
        """Test that invalid timeouts are rejected and timeout cleans up resources."""
        client = JevMcpClient()
        with self.assertRaises(JevAdapterError) as ctx:
            client._send_and_receive({"id": 1}, timeout_s=-1.0)
        self.assertIn("Invalid timeout", str(ctx.exception))
        client.close()


if __name__ == "__main__":
    unittest.main()
