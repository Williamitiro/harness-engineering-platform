import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

# Import collector
spec_collector = importlib.util.spec_from_file_location("jev_collector", ROOT / "scripts" / "jev_collector.py")
collector = importlib.util.module_from_spec(spec_collector)
spec_collector.loader.exec_module(collector)

# Import evaluator
spec_evaluator = importlib.util.spec_from_file_location("jev_evaluator", ROOT / "scripts" / "jev_evaluator.py")
evaluator = importlib.util.module_from_spec(spec_evaluator)
spec_evaluator.loader.exec_module(evaluator)

# Import adapter
spec_adapter = importlib.util.spec_from_file_location("jev_adapter", ROOT / "scripts" / "jev_adapter.py")
adapter = importlib.util.module_from_spec(spec_adapter)
spec_adapter.loader.exec_module(adapter)

# Import sandbox preparer
spec_sandbox = importlib.util.spec_from_file_location("prepare_blind_sandbox", ROOT / "scripts" / "prepare_blind_sandbox.py")
sandbox = importlib.util.module_from_spec(spec_sandbox)
spec_sandbox.loader.exec_module(sandbox)

POLICY = {
    "schema_version": 1,
    "status": "PROPOSED_NOT_APPROVED",
    "allowed_labels": ["tdd-workflow", "verification-loop", "both", "none", "uncertain"],
    "auto_accept_confidence": 0.85,
    "minimum_margin": 0.5,
}

class JevEmpiricalPipelineTests(unittest.TestCase):
    def test_tasks_contain_no_ground_truth_labels(self):
        """Tasks files must be blind and never expose expected or predicted answers."""
        task_files = [
            ROOT / "benchmarks" / "jev" / "tasks" / "tasks_skills.jsonl",
            ROOT / "benchmarks" / "jev" / "tasks" / "tasks_ci_triage.jsonl",
            ROOT / "benchmarks" / "jev" / "tasks" / "tasks_code_review.jsonl",
            ROOT / "benchmarks" / "jev" / "tasks" / "tasks_all.jsonl",
        ]
        for tf in task_files:
            tasks = collector.load_tasks(tf)
            self.assertGreaterEqual(len(tasks), 10)
            for t in tasks:
                self.assertNotIn("expected_label", t)
                self.assertNotIn("expected", t)
                self.assertNotIn("predicted", t)
                self.assertIn("candidate_labels", t)

    def test_ground_truth_files_valid_and_complete(self):
        """Ground truth files must contain valid golden labels and rationales."""
        gt_files = [
            ROOT / "benchmarks" / "jev" / "ground_truth" / "golden_skills.jsonl",
            ROOT / "benchmarks" / "jev" / "ground_truth" / "golden_ci_triage.jsonl",
            ROOT / "benchmarks" / "jev" / "ground_truth" / "golden_code_review.jsonl",
            ROOT / "benchmarks" / "jev" / "ground_truth" / "golden_all.jsonl",
        ]
        for gf in gt_files:
            truths = evaluator.load_ground_truth(gf)
            self.assertGreaterEqual(len(truths), 10)
            for tid, g in truths.items():
                self.assertTrue(g["expected_label"])
                self.assertIn("rationale", g)
                self.assertIn("allow_abstain", g)

    def test_collector_simulation_mode_is_synthetic(self):
        """Simulation mode must explicitly and immutably set evidence_kind=SYNTHETIC."""
        tasks = [
            {
                "task_id": "test-01",
                "domain": "skills",
                "task_type": "standard",
                "input_text": "Write unit tests for authentication",
                "candidate_labels": ["tdd-workflow", "verification-loop", "none"],
            }
        ]
        records = collector.run_collection(
            tasks=tasks,
            condition="CONDITION_J_ADVISORY",
            mode="simulation",
            run_id="test_sim_run",
        )
        self.assertEqual(len(records), 1)
        r = records[0]
        self.assertEqual(r["evidence_kind"], "SYNTHETIC")
        self.assertTrue(r["is_synthetic"])
        self.assertEqual(r["raw_input_sha256"], collector.compute_sha256(r["raw_input"]))
        self.assertEqual(r["raw_output_sha256"], collector.compute_sha256(r["raw_output"]))

    def test_collector_live_blocked_without_isolation(self):
        """Live mode execution must immediately refuse with BLOCKED_G1 without verified isolation."""
        tasks = [{"task_id": "t1", "domain": "skills", "input_text": "x", "candidate_labels": ["a", "b"]}]
        with self.assertRaises(collector.CollectorError) as ctx:
            collector.run_collection(tasks=tasks, condition="CONDITION_J_ADVISORY", mode="live", run_id="live_test")
        self.assertIn("BLOCKED_G1", str(ctx.exception))

    def test_evaluator_marks_synthetic_as_simulation_only(self):
        """Evaluator must refuse to grant empirical validity to synthetic simulation data."""
        records = [{
            "evidence_kind": "SYNTHETIC",
            "is_synthetic": True,
            "run_id": "sim_01",
            "task_id": "t1",
            "domain": "skills",
            "raw_input": '{"task_id": "t1"}',
            "raw_input_sha256": evaluator.compute_sha256('{"task_id": "t1"}'),
            "raw_output": '{"choice": "tdd-workflow"}',
            "raw_output_sha256": evaluator.compute_sha256('{"choice": "tdd-workflow"}'),
            "parsed_decision": {"label": "tdd-workflow", "confidence": 0.95, "margin": 0.8},
            "observed_metrics": {"latency_ms": 180.0, "tokens_in": 200, "tokens_out": 30},
        }]
        ground_truth = {"t1": {"task_id": "t1", "domain": "skills", "expected_label": "tdd-workflow"}}
        res = evaluator.evaluate_run(records, ground_truth, POLICY)
        self.assertEqual(res["evidence_level"], "SYNTHETIC_SIMULATION_ONLY")
        self.assertFalse(res["model_quality_proven"])
        self.assertEqual(res["recommendation"], "NO_EMPIRICAL_EVIDENCE_FOR_ADOPTION")

    def test_evaluator_detects_tampered_output_hash(self):
        """Evaluator must reject records whose raw output does not match its SHA-256."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "tampered.jsonl"
            rec = {
                "task_id": "t1",
                "raw_input": "in",
                "raw_input_sha256": evaluator.compute_sha256("in"),
                "raw_output": "out_tampered",
                "raw_output_sha256": evaluator.compute_sha256("out_original"),
            }
            path.write_text(json.dumps(rec))
            with self.assertRaises(evaluator.EvaluatorError) as ctx:
                evaluator.load_and_verify_run(path)
            self.assertIn("SHA-256 mismatch", str(ctx.exception))

    def test_evaluator_rejects_spoofed_verified_record(self):
        """Changing flags and recalculating hashes cannot establish a live run."""
        record = {
            "evidence_kind": "VERIFIED", "is_synthetic": False,
            "run_id": "made-up-live", "task_id": "t1", "domain": "skills",
            "raw_input": "synthetic input", "raw_output": '{"choice":"tdd-workflow"}',
            "parsed_decision": {"label": "tdd-workflow", "confidence": 1.0, "margin": 1.0},
            "observed_metrics": {"latency_ms": 1, "tokens_in": 1},
        }
        record["raw_input_sha256"] = evaluator.compute_sha256(record["raw_input"])
        record["raw_output_sha256"] = evaluator.compute_sha256(record["raw_output"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "forged.jsonl"
            p.write_text(json.dumps(record))
            with self.assertRaisesRegex(evaluator.EvaluatorError, "UNVERIFIED_PROVENANCE"):
                evaluator.load_and_verify_run(p)
        with self.assertRaisesRegex(evaluator.EvaluatorError, "UNVERIFIED_PROVENANCE"):
            evaluator.evaluate_run([record], {}, POLICY)

    def test_evaluator_rejects_spoofed_observed_record(self):
        record = {"evidence_kind": "OBSERVED", "is_synthetic": False, "task_id": "t1"}
        with self.assertRaisesRegex(evaluator.EvaluatorError, "UNVERIFIED_PROVENANCE"):
            evaluator.evaluate_run([record], {}, POLICY)

    def test_comparison_rejects_unpaired_ids_or_inputs(self):
        def item(tid, cond, sha="same"):
            return {"task_id": tid, "condition": cond, "domain": "skills",
                    "evidence_kind": "SYNTHETIC", "is_synthetic": True,
                    "raw_input_sha256": sha}
        a = item("t1", "CONDITION_A_NATIVE")
        j = item("t1", "CONDITION_J_ADVISORY")
        evaluator.verify_paired_runs([a], [j])
        with self.assertRaisesRegex(evaluator.EvaluatorError, "task IDs differ"):
            evaluator.verify_paired_runs([a], [item("t2", "CONDITION_J_ADVISORY")])
        with self.assertRaisesRegex(evaluator.EvaluatorError, "Input differs"):
            evaluator.verify_paired_runs([a], [item("t1", "CONDITION_J_ADVISORY", "other")])
        with self.assertRaisesRegex(evaluator.EvaluatorError, "one pure A run"):
            evaluator.verify_paired_runs([a], [item("t1", "CONDITION_A_NATIVE")])

    def test_evaluator_rejects_domain_mismatch(self):
        record = {"task_id": "t1", "domain": "skills",
                  "parsed_decision": {"label": "tdd-workflow"}}
        truth = {"t1": {"task_id": "t1", "domain": "ci_triage", "expected_label": "tdd-workflow"}}
        with self.assertRaisesRegex(evaluator.EvaluatorError, "Domain mismatch"):
            evaluator.evaluate_domain([record], truth, POLICY)

    def test_evaluator_calculates_macro_f1_correctly(self):
        """Macro-F1 must be correctly calculated per class rather than simple accuracy."""
        matrix = {
            "a": {"a": 2, "b": 1},
            "b": {"a": 0, "b": 3},
        }
        # class a: TP=2, FP=0, FN=1 -> Prec=1.0, Rec=2/3 (~0.6667), F1=0.8
        # class b: TP=3, FP=1, FN=0 -> Prec=3/4 (0.75), Rec=1.0, F1=6/7 (~0.8571)
        # Macro-F1 = (0.8 + 0.8571) / 2 = ~0.8286
        f1 = evaluator.calculate_macro_f1(matrix, ["a", "b"])
        self.assertAlmostEqual(f1, (0.8 + (6 / 7)) / 2, places=3)

    def test_adapter_attestation_lifecycle_and_tamper_detection(self):
        """Attestation must verify valid records and detect any alteration of payload or digest."""
        task_id = "test-attestation-01"
        raw_in = json.dumps({"question": "Run tests", "choice": ["tdd", "none"]})
        raw_out = json.dumps({"choice": "tdd", "confidence": 0.98})
        
        attestation = adapter.generate_attestation(
            task_id=task_id,
            raw_input=raw_in,
            raw_output=raw_out,
            adapter_name="JevMcpClient",
            provider="typesafe-jev-code",
            model="jev-v0.5.0",
        )
        self.assertEqual(attestation["adapter_name"], "JevMcpClient")
        self.assertEqual(attestation["upstream_version"], "v0.5.0")
        
        record = {
            "task_id": task_id,
            "raw_input": raw_in,
            "raw_input_sha256": adapter.compute_sha256(raw_in),
            "raw_output": raw_out,
            "raw_output_sha256": adapter.compute_sha256(raw_out),
            "adapter_attestation": attestation,
        }
        
        # Valid attestation must pass
        self.assertTrue(adapter.verify_attestation(record))
        
        # Tampered raw_output must fail
        tampered_out = record.copy()
        tampered_out["raw_output"] = '{"choice": "none"}'
        with self.assertRaises(adapter.AttestationError):
            adapter.verify_attestation(tampered_out)
            
        # Tampered digest must fail
        tampered_digest = record.copy()
        tampered_attestation = dict(attestation)
        tampered_attestation["binding_digest"] = "bad" * 16
        tampered_digest["adapter_attestation"] = tampered_attestation
        with self.assertRaises(adapter.AttestationError):
            adapter.verify_attestation(tampered_digest)

    def test_evaluator_evaluates_attested_observed_record(self):
        """Attested OBSERVED records evaluate to OBSERVED_REAL_EXECUTION without premature quality claims."""
        task_id = "skill-01"
        raw_in = json.dumps({"task_id": task_id, "domain": "skills", "input_text": "Write unit tests"})
        raw_out = json.dumps({"choice": "tdd-workflow", "confidence": 0.96, "margin": 0.88})
        
        att = adapter.generate_attestation(
            task_id=task_id,
            raw_input=raw_in,
            raw_output=raw_out,
            adapter_name="JevMcpClient",
            provider="typesafe-jev-code",
            model="jev-v0.5.0",
        )
        
        rec = {
            "evidence_kind": "OBSERVED",
            "is_synthetic": False,
            "run_id": "live_run_01",
            "task_id": task_id,
            "domain": "skills",
            "condition": "CONDITION_J_ADVISORY",
            "raw_input": raw_in,
            "raw_input_sha256": adapter.compute_sha256(raw_in),
            "raw_output": raw_out,
            "raw_output_sha256": adapter.compute_sha256(raw_out),
            "adapter_attestation": att,
            "parsed_decision": {"label": "tdd-workflow", "confidence": 0.96, "margin": 0.88},
            "observed_metrics": {"latency_ms": 190.0, "tokens_in": 120, "tokens_out": 28, "cost_usd": 0.00001},
        }
        
        ground_truth = {task_id: {"task_id": task_id, "domain": "skills", "expected_label": "tdd-workflow"}}
        res = evaluator.evaluate_run([rec], ground_truth, POLICY)
        
        self.assertEqual(res["evidence_level"], "OBSERVED_REAL_EXECUTION")
        self.assertFalse(res["model_quality_proven"]) # Quality not proven until paired comparison in isolated G1
        self.assertEqual(res["status"], "OBSERVED_EXECUTION_EVALUATED")
        self.assertEqual(res["overall"]["micro_accuracy"], 1.0)

    def test_prepare_blind_sandbox_excludes_git_and_ground_truth(self):
        """prepare_blind_sandbox must generate an isolated workspace free from ground truth or git history."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            target = Path(tmp_dir) / "sandbox"
            summary = sandbox.prepare_blind_sandbox(
                tasks_source=ROOT / "benchmarks" / "jev" / "tasks",
                target_dir=target,
                include_runner=True,
            )
            
            self.assertEqual(summary["status"], "SANDBOX_PREPARED")
            self.assertTrue(target.is_dir())
            
            # Tasks exist
            task_files = list((target / "tasks").glob("*.jsonl"))
            self.assertGreaterEqual(len(task_files), 1)
            
            # Ground truth must NOT exist
            for p in target.rglob("*"):
                self.assertNotIn("golden", p.name.lower())
                self.assertNotIn("truth", p.name.lower())
                self.assertNotEqual(p.name, ".git")
                
            # Manifest exists
            manifest_file = target / "sandbox_manifest.json"
            self.assertTrue(manifest_file.is_file())
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            self.assertTrue(manifest["blindness_verified"])
            self.assertTrue(manifest["ground_truth_excluded"])
            
            # Container and canary files exist
            self.assertTrue((target / "Containerfile").is_file())
            self.assertTrue((target / "verify_negative_canaries.sh").is_file())
            self.assertTrue((target / "run_isolated_podman.sh").is_file())

    def test_mcp_client_mock_protocol_and_classification(self):
        """JevMcpClient must speak JSON-RPC 2.0 stdio protocol correctly with an MCP server."""
        mock_server_code = (
            "import sys, json\n"
            "for line in sys.stdin:\n"
            "    line = line.strip()\n"
            "    if not line: continue\n"
            "    msg = json.loads(line)\n"
            "    if msg.get('method') == 'initialize':\n"
            "        resp = {'jsonrpc': '2.0', 'id': msg['id'], 'result': {'serverInfo': {'name': 'mock-jev', 'version': '0.5.0'}, 'capabilities': {'tools': {}}}}\n"
            "        sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()\n"
            "    elif msg.get('method') == 'notifications/initialized':\n"
            "        continue\n"
            "    elif msg.get('method') == 'tools/call':\n"
            "        args = msg['params']['arguments']\n"
            "        choice = args['choice'][0]\n"
            "        content = json.dumps({'choice': choice, 'confidence': 0.95, 'margin': 0.85, 'probabilities': {choice: 0.95}})\n"
            "        resp = {'jsonrpc': '2.0', 'id': msg['id'], 'result': {'content': [{'type': 'text', 'text': content}]}}\n"
            "        sys.stdout.write(json.dumps(resp) + '\\n'); sys.stdout.flush()\n"
        )
        
        cmd = [sys.executable, "-u", "-c", mock_server_code]
        client = adapter.JevMcpClient(command=cmd)
        with client:
            res = client.classify(question="Write unit test for auth", choices=["tdd-workflow", "none"])
            self.assertEqual(res["execution_status"], "SUCCESS")
            self.assertEqual(res["label"], "tdd-workflow")
            self.assertEqual(res["confidence"], 0.95)
            self.assertEqual(res["margin"], 0.85)
            self.assertIn("tdd-workflow", res["probabilities"])
            self.assertGreater(res["latency_ms"], 0)

if __name__ == "__main__":
    unittest.main()
