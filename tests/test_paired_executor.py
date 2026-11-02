import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts.codex_native_broker import NativeBroker, BrokerError
from scripts.paired_executor import auto_accept, run_pairs, valid_task
from scripts import mxc_g1_preflight

TASK = {'task_id': 'artificial', 'domain': 'test', 'input_text': 'ARTIFICIAL',
        'candidate_labels': ['a', 'b']}


class PairedExecutorTests(unittest.TestCase):
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
