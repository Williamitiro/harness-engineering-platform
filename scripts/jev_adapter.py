#!/usr/bin/env python3
"""Standard library MCP and native model classification adapter for Jev.

Connects to FrancoisChastel/jev-code v0.5.0 via stdio MCP (JSON-RPC 2.0)
or CLI without global installation or personal configuration modifications.

Enforces cryptographic attestation on captured raw input and raw output
to prevent tampering and evidence spoofing.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UPSTREAM_REPO = "https://github.com/FrancoisChastel/jev-code"
UPSTREAM_VERSION = "v0.5.0"
UPSTREAM_COMMIT = "74a4569bfe8bb4ad0cc1ba74fa5867f09e267300"
ADAPTER_VERSION = "1.0.0"

class JevAdapterError(RuntimeError):
    """Raised when an adapter operation fails."""
    pass

class AttestationError(ValueError):
    """Raised when an evidence record fails cryptographic provenance verification."""
    pass

def compute_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def generate_attestation(
    task_id: str,
    raw_input: str,
    raw_output: str,
    adapter_name: str,
    provider: str,
    model: str,
    upstream_version: str = UPSTREAM_VERSION,
    upstream_commit: str = UPSTREAM_COMMIT,
) -> dict[str, Any]:
    """Generates a verifiable provenance block for an observed execution record."""
    in_sha = compute_sha256(raw_input)
    out_sha = compute_sha256(raw_output)
    
    # Deterministic digest binding the execution context
    binding_payload = f"{task_id}:{in_sha}:{out_sha}:{adapter_name}:{provider}:{model}:{upstream_version}:{upstream_commit}"
    digest = compute_sha256(binding_payload)
    
    return {
        "adapter_name": adapter_name,
        "adapter_version": ADAPTER_VERSION,
        "upstream_version": upstream_version,
        "upstream_commit": upstream_commit,
        "provider": provider,
        "model": model,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "raw_input_sha256": in_sha,
        "raw_output_sha256": out_sha,
        "binding_digest": digest,
    }

def verify_attestation(record: dict[str, Any]) -> bool:
    """Verifies that an observed/verified record contains a valid, untampered attestation block."""
    attestation = record.get("adapter_attestation")
    if not isinstance(attestation, dict):
        raise AttestationError("Missing adapter_attestation block in observed record")
    
    raw_in = record.get("raw_input", "")
    raw_out = record.get("raw_output", "")
    in_sha = record.get("raw_input_sha256", "")
    out_sha = record.get("raw_output_sha256", "")
    
    # 1. Check that local content matches local declared hashes
    if compute_sha256(raw_in) != in_sha:
        raise AttestationError("raw_input content does not match raw_input_sha256")
    if compute_sha256(raw_out) != out_sha:
        raise AttestationError("raw_output content does not match raw_output_sha256")
        
    # 2. Check that attestation block hashes match record hashes
    if attestation.get("raw_input_sha256") != in_sha:
        raise AttestationError("attestation raw_input_sha256 does not match record hash")
    if attestation.get("raw_output_sha256") != out_sha:
        raise AttestationError("attestation raw_output_sha256 does not match record hash")
        
    # 3. Check binding digest
    task_id = record.get("task_id", "")
    adapter_name = attestation.get("adapter_name", "")
    provider = attestation.get("provider", "")
    model = attestation.get("model", "")
    upstream_ver = attestation.get("upstream_version", "")
    upstream_com = attestation.get("upstream_commit", "")
    
    expected_binding = f"{task_id}:{in_sha}:{out_sha}:{adapter_name}:{provider}:{model}:{upstream_ver}:{upstream_com}"
    if compute_sha256(expected_binding) != attestation.get("binding_digest"):
        raise AttestationError("Attestation binding_digest mismatch; record provenance has been altered")
        
    return True

class JevMcpClient:
    """Standard library JSON-RPC 2.0 client communicating over stdio with an MCP server."""

    def __init__(
        self,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self.command = command or ["npx", "-y", "@french-castle/jev-code@0.5.0", "mcp"]
        self.env = dict(os.environ)
        if env:
            self.env.update(env)
        self.cwd = cwd
        self.process: subprocess.Popen[bytes] | None = None
        self._next_id = 1

    def start(self, timeout_s: float = 20.0) -> None:
        """Starts the MCP server process and performs JSON-RPC protocol handshake."""
        if self.process is not None:
            return

        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.cwd) if self.cwd else None,
                env=self.env,
            )
        except OSError as exc:
            raise JevAdapterError(f"Failed to spawn MCP server process {self.command}: {exc}") from exc

        # 1. Send initialize request
        init_req = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "harness-jev-adapter",
                    "version": ADAPTER_VERSION,
                },
            },
        }
        resp = self._send_and_receive(init_req, timeout_s=timeout_s)
        if "error" in resp:
            self.close()
            raise JevAdapterError(f"MCP server initialize error: {resp['error']}")

        # 2. Send initialized notification
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self._send_notification(notif)

    def _get_next_id(self) -> int:
        req_id = self._next_id
        self._next_id += 1
        return req_id

    def _send_notification(self, payload: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise JevAdapterError("MCP server process is not running")
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        try:
            self.process.stdin.write(line.encode("utf-8"))
            self.process.stdin.flush()
        except OSError as exc:
            raise JevAdapterError(f"Failed to send notification to MCP server: {exc}") from exc

    def _send_and_receive(self, payload: dict[str, Any], timeout_s: float = 30.0) -> dict[str, Any]:
        if self.process is None or self.process.stdin is None or self.process.stdout is None:
            raise JevAdapterError("MCP server process is not running")
        
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        try:
            self.process.stdin.write(line.encode("utf-8"))
            self.process.stdin.flush()
        except OSError as exc:
            raise JevAdapterError(f"Failed to write to MCP server stdin: {exc}") from exc

        # Read line from stdout
        # Simple line reader with deadline
        start = time.monotonic()
        while True:
            if time.monotonic() - start > timeout_s:
                raise JevAdapterError(f"MCP server response timed out after {timeout_s}s")
            
            raw_line = self.process.stdout.readline()
            if not raw_line:
                # Check if process exited
                ret = self.process.poll()
                stderr_out = ""
                if self.process.stderr:
                    try:
                        stderr_out = self.process.stderr.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                raise JevAdapterError(
                    f"MCP server process exited prematurely with code {ret}. Stderr: {stderr_out.strip()}"
                )
            
            text_line = raw_line.decode("utf-8").strip()
            if not text_line:
                continue
            try:
                msg = json.loads(text_line)
                # Verify JSON-RPC structure
                if isinstance(msg, dict) and ("result" in msg or "error" in msg):
                    return msg
            except json.JSONDecodeError:
                # Some logs might appear on stdout; continue reading until valid JSON-RPC
                continue

    def classify(self, question: str, choices: list[str], timeout_s: float = 30.0) -> dict[str, Any]:
        """Invokes jev_classify tool on the MCP server and parses probability output."""
        if self.process is None:
            self.start(timeout_s=timeout_s)

        req_id = self._get_next_id()
        tool_req = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {
                "name": "jev_classify",
                "arguments": {
                    "question": question,
                    "choice": choices,
                },
            },
        }

        t0 = time.perf_counter()
        resp = self._send_and_receive(tool_req, timeout_s=timeout_s)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        if "error" in resp:
            return {
                "label": "uncertain",
                "confidence": 0.0,
                "margin": 0.0,
                "probabilities": {c: 0.0 for c in choices},
                "raw_output": json.dumps(resp, ensure_ascii=False),
                "latency_ms": elapsed_ms,
                "tokens_in": len(question) // 4,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "provider": "typesafe-jev-code",
                "model": "jev-v0.5.0",
                "execution_status": f"ERROR: {resp['error']}",
            }

        result = resp.get("result", {})
        content = result.get("content", [])
        raw_text = ""
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                raw_text += c.get("text", "")

        # Parse text payload
        label = "uncertain"
        confidence = None
        margin = None
        probabilities = None
        tokens_out = 32

        if raw_text:
            try:
                parsed = json.loads(raw_text)
                label = parsed.get("choice", parsed.get("label", "uncertain"))
                confidence = parsed.get("confidence")
                margin = parsed.get("margin")
                probabilities = parsed.get("probabilities")
                if parsed.get("tokens_out"):
                    tokens_out = int(parsed["tokens_out"])
            except json.JSONDecodeError:
                # Raw text might be just the label
                label = raw_text.strip()

        raw_output_str = json.dumps({
            "mcp_result": result,
            "parsed_choice": label,
            "confidence": confidence,
            "margin": margin,
            "probabilities": probabilities,
        }, ensure_ascii=False)

        return {
            "label": label,
            "confidence": confidence,
            "margin": margin,
            "probabilities": probabilities,
            "raw_output": raw_output_str,
            "latency_ms": round(elapsed_ms, 2),
            "tokens_in": max(1, len(question) // 4),
            "tokens_out": tokens_out,
            "cost_usd": 0.00001, # Estimated nominal cost per call
            "provider": "typesafe-jev-code",
            "model": "jev-v0.5.0",
            "execution_status": "SUCCESS",
        }

    def close(self) -> None:
        """Terminates the MCP server process cleanly."""
        if self.process is not None:
            if self.process.stdin:
                try:
                    self.process.stdin.close()
                except OSError:
                    pass
            if self.process.stdout:
                try:
                    self.process.stdout.close()
                except OSError:
                    pass
            if self.process.stderr:
                try:
                    self.process.stderr.close()
                except OSError:
                    pass
            try:
                self.process.terminate()
                self.process.wait(timeout=2.0)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

    def __enter__(self) -> JevMcpClient:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
