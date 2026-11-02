#!/usr/bin/env python3
"""MCP stdio adapter for jev-code v0.5.0 (upstream contract, offline testable).

The SHA-256 digest produced below is a LOCAL INTEGRITY CHECK, not a signed
attestation or a proof that any model was called. Real execution remains blocked
by the collector until an independent isolation/attestation mechanism exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any

UPSTREAM_REPO = "https://github.com/FrancoisChastel/jev-code"
UPSTREAM_VERSION = "v0.5.0"
UPSTREAM_COMMIT = "74a4569bfe8bb4ad0cc1ba74fa5867f09e267300"
ADAPTER_VERSION = "1.1.0"


class JevAdapterError(RuntimeError):
    pass


class AttestationError(ValueError):
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
    """Legacy-compatible local checksum; NEVER an authenticity attestation."""
    in_sha = compute_sha256(raw_input)
    out_sha = compute_sha256(raw_output)
    payload = f"{task_id}:{in_sha}:{out_sha}:{adapter_name}:{provider}:{model}:{upstream_version}:{upstream_commit}"
    return {
        "integrity_only": True,
        "attestation_status": "UNTRUSTED_LOCAL_DIGEST",
        "adapter_name": adapter_name,
        "adapter_version": ADAPTER_VERSION,
        "upstream_version": upstream_version,
        "upstream_commit": upstream_commit,
        "provider": provider,
        "model": model,
        "timestamp_iso": datetime.now(timezone.utc).isoformat(),
        "raw_input_sha256": in_sha,
        "raw_output_sha256": out_sha,
        "binding_digest": compute_sha256(payload),
    }


def verify_attestation(record: dict[str, Any]) -> bool:
    """Check local consistency only; never promote a run to OBSERVED/VERIFIED."""
    att = record.get("adapter_attestation")
    if not isinstance(att, dict) or att.get("integrity_only") is not True:
        raise AttestationError("Expected an explicitly untrusted local checksum")
    for field in ("raw_input", "raw_output"):
        raw = record.get(field)
        if not isinstance(raw, str):
            raise AttestationError(f"{field} must be a string")
        if compute_sha256(raw) != record.get(f"{field}_sha256"):
            raise AttestationError(f"{field} SHA mismatch")
        if att.get(f"{field}_sha256") != record.get(f"{field}_sha256"):
            raise AttestationError(f"{field} attested SHA mismatch")
    payload = ":".join([
        str(record.get("task_id", "")),
        str(record["raw_input_sha256"]),
        str(record["raw_output_sha256"]),
        str(att.get("adapter_name", "")),
        str(att.get("provider", "")),
        str(att.get("model", "")),
        str(att.get("upstream_version", "")),
        str(att.get("upstream_commit", "")),
    ])
    if compute_sha256(payload) != att.get("binding_digest"):
        raise AttestationError("Local digest mismatch")
    return True


class JevMcpClient:
    """Bounded JSON-RPC stdio client compatible with jev-code v0.5.0.

    A daemon reader prevents blocking readline from disabling the timeout.
    JSON-RPC response ids must match requests; notifications and stderr are
    never mistaken for successful tool responses.
    """

    def __init__(
        self,
        command: list[str] | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        npx_bin = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
        self.command = command or [npx_bin, "-y", "@french-castle/jev-code@0.5.0", "mcp"]
        self.env = dict(os.environ)
        if env:
            self.env.update(env)
        self.cwd = cwd
        self.process: subprocess.Popen[bytes] | None = None
        self._next_id = 1
        self._messages: queue.Queue[dict | None] = queue.Queue()
        self._stderr_tail: list[str] = []

    def _stdout_reader(self) -> None:
        assert self.process is not None and self.process.stdout is not None
        try:
            for raw in self.process.stdout:
                try:
                    msg = json.loads(raw.decode("utf-8"))
                    if isinstance(msg, dict):
                        self._messages.put(msg)
                except (ValueError, UnicodeError):
                    continue
        finally:
            self._messages.put(None)

    def _stderr_reader(self) -> None:
        assert self.process is not None and self.process.stderr is not None
        for raw in self.process.stderr:
            # Redact stderr from user-facing messages: providers can echo secrets.
            if len(self._stderr_tail) < 3:
                self._stderr_tail.append("stderr available (redacted)")

    def start(self, timeout_s: float = 20.0) -> None:
        if self.process is not None:
            return
        try:
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=str(self.cwd) if self.cwd else None, env=self.env,
            )
        except OSError as exc:
            raise JevAdapterError(f"MCP server could not start: {exc}") from exc
        threading.Thread(target=self._stdout_reader, daemon=True).start()
        threading.Thread(target=self._stderr_reader, daemon=True).start()
        try:
            response = self._send_and_receive({
                "jsonrpc": "2.0", "id": self._get_next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "harness-jev-adapter", "version": ADAPTER_VERSION},
                },
            }, timeout_s)
            if "error" in response or not isinstance(response.get("result"), dict):
                raise JevAdapterError("MCP initialize rejected")
            self._send_notification({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except BaseException:
            self.close()
            raise

    def _get_next_id(self) -> int:
        result = self._next_id
        self._next_id += 1
        return result

    def _send_notification(self, message: dict[str, Any]) -> None:
        self._write(message)

    def _write(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise JevAdapterError("MCP server unavailable")
        try:
            self.process.stdin.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
            self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError) as exc:
            raise JevAdapterError("MCP process input closed") from exc

    def _send_and_receive(self, payload: dict[str, Any], timeout_s: float = 30.0) -> dict[str, Any]:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise JevAdapterError("Invalid timeout")
        expected_id = payload["id"]
        self._write(payload)
        deadline = time.monotonic() + timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JevAdapterError("MCP response timed out")
            try:
                response = self._messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise JevAdapterError("MCP response timed out") from exc
            if response is None:
                raise JevAdapterError("MCP server closed stdout before responding")
            if response.get("id") != expected_id:
                # A wrong-id response cannot satisfy this request.
                continue
            if response.get("jsonrpc") != "2.0":
                continue
            if "result" in response or "error" in response:
                return response

    def classify(self, question: str, choices: list[str], timeout_s: float = 30.0,
                 class_descriptions: dict[str, str] | None = None) -> dict[str, Any]:
        if not isinstance(question, str) or not question.strip():
            raise JevAdapterError("Question is required")
        if len(choices) < 2 or len(set(choices)) != len(choices) or not all(
            isinstance(c, str) and c for c in choices
        ):
            raise JevAdapterError("At least two distinct class ids required")
        if class_descriptions is not None and set(class_descriptions) != set(choices):
            raise JevAdapterError("Class descriptions must match choices exactly")
        if self.process is None:
            self.start(timeout_s)
        descriptions = class_descriptions or {
            key: f"Classify when the request matches category {key!r}; do not force a match."
            for key in choices
        }
        request = {
            "jsonrpc": "2.0", "id": self._get_next_id(), "method": "tools/call",
            "params": {"name": "jev_classify", "arguments": {
                "instructions": "Select the best category for the given request. Use 'none' when not applicable.",
                "items": [{"id": "task", "text": question}],
                "classes": descriptions,
                "auto_accept": 0.85, "min_margin": 0.5,
            }},
        }
        start = time.perf_counter()
        response = self._send_and_receive(request, timeout_s)
        elapsed = round((time.perf_counter() - start) * 1000.0, 2)
        if "error" in response:
            raise JevAdapterError("MCP JSON-RPC tool call failed")
        result = response.get("result")
        if not isinstance(result, dict) or result.get("isError") is True:
            raise JevAdapterError("jev_classify tool reported an error")
        content = result.get("content")
        if not isinstance(content, list):
            raise JevAdapterError("MCP result has no content array")
        text_content = [x.get("text") for x in content
                        if isinstance(x, dict) and x.get("type") == "text"]
        if len(text_content) != 1 or not isinstance(text_content[0], str):
            raise JevAdapterError("MCP result missing single JSON content block")
        try:
            payload = json.loads(text_content[0])
        except ValueError as exc:
            raise JevAdapterError("MCP tool output is not valid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise JevAdapterError("jev_classify output missing results list")
        matches = [x for x in payload["results"] if isinstance(x, dict) and x.get("id") == "task"]
        if len(matches) != 1:
            raise JevAdapterError("jev_classify output has missing or duplicate task id")
        item = matches[0]
        label = item.get("label")
        if label is not None and label not in choices:
            raise JevAdapterError("jev_classify returned label outside allowlist")
        if item.get("status") in ("refused", "invalid_response"):
            raise JevAdapterError("jev_classify refused or returned an invalid response")
        numbers = {}
        for name in ("probability", "margin", "confidence"):
            value = item.get(name)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not math.isfinite(value) or not 0 <= value <= 1):
                raise JevAdapterError(f"Invalid {name} from upstream")
            numbers[name] = value
        probs = item.get("probabilities")
        if not isinstance(probs, dict):
            probs = None
        elif any(k not in choices or isinstance(v, bool) or
                 not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1
                 for k, v in probs.items()):
            raise JevAdapterError("Invalid probability distribution")
        decision = item.get("decision")
        if decision not in ("auto", "review"):
            raise JevAdapterError("Unknown upstream decision")
        if decision == "review" or label is None:
            label = "uncertain"
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        def tokens(key: str) -> int | None:
            value = usage.get(key)
            return value if type(value) is int and value >= 0 else None
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            model = "UNKNOWN"
        return {
            "label": label,
            "confidence": numbers["probability"],
            "margin": numbers["margin"],
            "model_confidence": numbers["confidence"],
            "probabilities": probs,
            "raw_output": text_content[0],
            "latency_ms": elapsed,
            "tokens_in": tokens("input_tokens"),
            "tokens_out": tokens("output_tokens"),
            "cost_usd": None,
            "provider": "jev-code-mcp",
            "model": model,
            "execution_status": "SUCCESS" if decision == "auto" else "REVIEW",
        }

    def close(self) -> None:
        if self.process is None:
            return
        process, self.process = self.process, None
        try:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        finally:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()

    def __enter__(self) -> "JevMcpClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
