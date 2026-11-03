import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest
from unittest.mock import Mock, patch

from scripts.codex_native_broker import NativeBroker, BrokerError
from scripts.jev_adapter import JevMcpClient, JevAdapterError
from scripts.paired_executor import auto_accept, run_pairs, valid_task, save_receipt, score_pairs
from scripts import mxc_g1_preflight

TASK = {'task_id': 'artificial', 'domain': 'test', 'input_text': 'ARTIFICIAL',
        'candidate_labels': ['a', 'b']}


class PairedExecutorTests(unittest.TestCase):
    def test_jev_spawn_failure_is_a_specific_safe_code(self):
        with patch('scripts.jev_adapter.subprocess.Popen', side_effect=FileNotFoundError('private-path')):
            client = JevMcpClient(command=['artificial-command'], env={'PATH': 'artificial'})
            with self.assertRaises(JevAdapterError) as raised:
                client.start()
        self.assertEqual(raised.exception.diagnostic_code, 'MCP_SPAWN_FAILED')
        self.assertNotIn('private-path', str(raised.exception))
        self.assertFalse(client.startup_diagnostic()['process_started'])

    def test_jev_eof_and_timeout_provide_distinct_safe_codes(self):
        import queue
        for sentinel, code in ((True, 'MCP_STDOUT_CLOSED'), (False, 'MCP_RESPONSE_TIMEOUT')):
            client = JevMcpClient(command=['never-run'], env={})
            client.process = Mock()
            if sentinel:
                client._messages.put(None)
            else:
                client._messages.get = Mock(side_effect=queue.Empty)
            with self.assertRaises(JevAdapterError) as raised:
                client._send_and_receive({'id': 1, 'jsonrpc': '2.0', 'method': 'initialize'}, timeout_s=.1)
            self.assertEqual(raised.exception.diagnostic_code, code)

    def test_jev_diagnostic_is_closed_schema_without_raw_stderr(self):
        client = JevMcpClient(command=['never-run'], env={'OPENROUTER_API_KEY': 'artificial-secret'})
        client._started_once = True
        client._last_exit_code = 12
        client._stderr_tail.append('stderr available (redacted)')
        client._stderr_categories.add('NODE_MODULE_MISSING')
        result = client.startup_diagnostic()
        self.assertEqual(result['exit_code'], 12)
        self.assertEqual(result['stderr_categories'], ['NODE_MODULE_MISSING'])
        self.assertNotIn('artificial-secret', json.dumps(result))

    def test_pilot_cost_is_unknown_if_any_fallback_cost_is_missing(self):
        # The old evaluator sums partial known costs, misleadingly labelled total.
        records = []
        for i, amount in enumerate((0.000018858, None, None)):
            records.append({
                'task_id': f'skill-0{i + 1}', 'domain': 'skills',
                'A': {'label': 'a', 'cost_usd': None, 'latency_ms': 5},
                'J': {'label': 'a', 'cost_usd': amount, 'latency_ms': 4},
            })
        mocked_evaluation = {'count': 3, 'micro_accuracy': 1.0,
                             'mean_latency_ms': 4, 'total_cost_usd': 0.000018858}
        with patch('scripts.paired_executor.load_ground_truth', return_value={}), \
             patch('scripts.paired_executor.load_policy', return_value={}), \
             patch('scripts.paired_executor.evaluate_domain', return_value=mocked_evaluation):
            quality = score_pairs({'records': records})
        self.assertIsNone(quality['A']['total_cost_usd'])
        self.assertEqual(quality['A']['cost_observed_count'], 0)
        self.assertIsNone(quality['J']['total_cost_usd'])
        self.assertEqual(quality['J']['known_cost_subtotal_usd'], 0.000018858)
        self.assertEqual(quality['J']['cost_observed_count'], 1)
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'pilot.json'
            save_receipt(output, {'status': 'COMPLETED', 'records': records,
                                  'logical_calls': {'A': 3, 'J': 3, 'fallback': 2},
                                  'quality': quality})
            markdown = output.with_suffix('.md').read_text()
            self.assertIn('1/3', markdown)
            self.assertIn('Subtotal USD conhecido', markdown)

    def test_native_final_response_and_observed_usage(self):
        native = NativeBroker(Path('codex.exe'), [], {}, Path.cwd())
        native.prepare = Mock(return_value='artificial-thread')
        def reply(method, params, timeout_s):
            native.notifications.extend([
                {'method': 'item/completed', 'params': {'threadId': 'artificial-thread',
                    'item': {'type': 'agentMessage', 'text': '{"label":"a","reasoning":"artificial"}'}}},
                {'method': 'thread/tokenUsage/updated', 'params': {'threadId': 'artificial-thread',
                    'tokenUsage': {'last': {'inputTokens': 8, 'outputTokens': 4}}}},
                {'method': 'turn/completed', 'params': {'threadId': 'artificial-thread',
                    'turn': {'status': 'completed'}}},
            ])
            return {}
        native.rpc = Mock(side_effect=reply)
        result = native.classify(TASK, 'model')
        self.assertEqual((result['label'], result['tokens_in'], result['tokens_out']), ('a', 8, 4))
        self.assertIsNone(result['cost_usd'])

    @unittest.skipUnless(os.name == 'nt', 'Windows supervisor')
    def test_supervisor_timeout_kills_only_its_child_tree_and_reports_failure(self):
        from scripts import run_pilot_once
        process = Mock(pid=12345, returncode=-9)
        process.communicate.side_effect = [subprocess.TimeoutExpired('artificial', 180), (b'', b'')]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            with patch.object(sys, 'argv', ['run_pilot_once.py', '--output', str(path)]), \
                 patch.object(run_pilot_once.shutil, 'which', return_value='infisical.exe'), \
                 patch.object(run_pilot_once.subprocess, 'Popen', return_value=process), \
                 patch.object(run_pilot_once.subprocess, 'run') as kill, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_pilot_once.main(), 1)
            self.assertEqual(json.loads(path.read_text())['error']['code'], 'WALL_TIMEOUT_180S')
            self.assertIn('12345', kill.call_args.args[0])
            self.assertNotIn('/IM', kill.call_args.args[0])
    def test_native_bootstrap_accepts_only_exact_standing_policy(self):
        native = NativeBroker(Path('codex.exe'), [], {}, Path.cwd())
        native.rpc = Mock(return_value={'thread': {'id': 'artificial'},
            'instructionSources': [str(Path.home() / '.codex' / 'AGENTS.md')]})
        self.assertEqual(native.prepare('model'), 'artificial')
        self.assertEqual(native.turns, 0)
        native.rpc.return_value = {'thread': {'id': 'artificial'},
            'instructionSources': [str(Path.home() / '.codex' / 'auth.json')]}
        with self.assertRaisesRegex(BrokerError, 'UNEXPECTED_INSTRUCTIONS'):
            native.prepare('model')

    def test_error_preserves_completed_A_and_aborts_without_retry(self):
        native, jev = Mock(), Mock()
        native.classify.return_value = {'label': 'a', 'latency_ms': 12, 'tokens_in': 42}
        jev.classify.side_effect = BrokerError('ARTIFICIAL_FAILURE')
        checkpoint = Mock()
        result = run_pairs([TASK] * 3, native, jev, 'model', checkpoint)
        self.assertEqual(result['status'], 'ABORTED')
        self.assertEqual(result['logical_calls'], {'A': 1, 'J': 1, 'fallback': 0})
        self.assertEqual(result['records'][0]['A']['tokens_in'], 42)
        self.assertEqual(result['error'], {'stage': 'J', 'code': 'ARTIFICIAL_FAILURE'})
        self.assertEqual(native.classify.call_count, 1)
        self.assertTrue(checkpoint.called)

    def test_receipt_includes_error_and_partial_results_without_raw_provider_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            save_receipt(path, {'status': 'ABORTED', 'records': [],
                               'error': {'stage': 'A', 'code': 'ARTIFICIAL_FAILURE'}})
            self.assertEqual(json.loads(path.read_text())['status'], 'ABORTED')
            self.assertIn('ARTIFICIAL_FAILURE', path.with_suffix('.md').read_text())

    def test_native_shutdown_never_closes_pipe_owned_by_reader(self):
        native = NativeBroker(Path('codex.exe'), [], {}, Path.cwd())
        process = native.process = Mock()
        native.close()
        process.stdout.close.assert_not_called()
        process.stderr.close.assert_not_called()
        self.assertIsNone(native.process)
    def test_policy_edges_and_invalid_confidence_fail_closed(self):
        base = {'label': 'a', 'execution_status': 'SUCCESS', 'confidence': .85, 'margin': .5}
        self.assertTrue(auto_accept(base, ['a', 'b']))
        for override in ({'confidence': .849}, {'margin': .499}, {'label': 'uncertain'},
                         {'execution_status': 'REVIEW'}, {'confidence': True}, {'margin': float('nan')}):
            self.assertFalse(auto_accept({**base, **override}, ['a', 'b']))

    def test_same_native_model_for_fallback_and_logical_call_ceiling(self):
        native, jev = Mock(), Mock()
        native.classify.return_value = {'label': 'b', 'cost_usd': None}
        jev.classify.return_value = {'label': 'uncertain', 'execution_status': 'REVIEW'}
        result = run_pairs([TASK] * 3, native, jev, 'explicit-model')
        self.assertEqual(result['logical_calls'], {'A': 3, 'J': 3, 'fallback': 3})
        self.assertEqual(native.classify.call_count, 6)
        self.assertTrue(all(c.args == (TASK, 'explicit-model') for c in native.classify.call_args_list))
        self.assertIsNone(result['records'][0]['J']['cost_usd'])
        with self.assertRaisesRegex(ValueError, 'MAX_TASKS_3'):
            run_pairs([TASK] * 4, native, jev, 'explicit-model')

    def test_reject_contamination_before_dispatch(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_BLIND_TASK'):
            valid_task({**TASK, 'ground_truth': 'do-not-read'})

    def test_native_does_not_accept_jev_secret_environment(self):
        with self.assertRaisesRegex(BrokerError, 'NATIVE_ENV_NOT_OPERATIONAL'):
            NativeBroker(Path('codex.exe'), [], {'OPENROUTER_API_KEY': 'artificial'}, Path.cwd())

    def test_native_protocol_and_profile_not_arbitrary_agent_rpc(self):
        native = NativeBroker(Path('codex.exe'), [], {'SystemDrive': 'C:'}, Path.cwd())
        native._write = Mock()
        native._messages.put({'method': 'notice', 'params': {}})
        native._messages.put({'id': 1, 'result': {'exitCode': 0}})
        self.assertEqual(native.canaries(['artificial'])['exitCode'], 0)
        request = native._write.call_args.args[0]
        self.assertEqual(request['method'], 'command/exec')
        self.assertEqual(request['params']['permissionProfile'], 'he-jev-g1')
        self.assertNotIn('sandboxPolicy', request['params'])
        self.assertNotIn('OPENROUTER_API_KEY', ' '.join(native.command))

    def test_escalation_request_is_denied_not_approved(self):
        native = NativeBroker(Path('codex.exe'), [], {}, Path.cwd())
        native._write = Mock()
        native._messages.put({'id': 99, 'method': 'item/permissions/requestApproval'})
        with self.assertRaisesRegex(BrokerError, 'DENIED'):
            native.receive(__import__('time').monotonic() + 1)
        self.assertIn('error', native._write.call_args.args[0])

    @unittest.skipUnless(os.name == 'nt' and os.environ.get('HE_NATIVE_G1') == '1',
                         'Native free MXC integration is explicitly opt-in')
    def test_native_free_command_boundary(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = mxc_g1_preflight.main(['--native-broker', '--diagnose-startup'])
        report = json.loads(output.getvalue())
        self.assertEqual(code, 0, report)
        self.assertTrue(report['broker_verified'])
        self.assertTrue(report['canaries_passed'])
        self.assertEqual(report['paid_calls'], 0)


if __name__ == '__main__':
    unittest.main()
