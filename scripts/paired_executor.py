#!/usr/bin/env python3
"""One CLI: unpaid native G1 preflight, or operator-only bounded A/J pilot."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.jev_adapter import JevMcpClient
from scripts.jev_collector import load_tasks
from scripts.jev_live_smoke import isolated_child_env, verify_package
from scripts import mxc_g1_preflight


def valid_task(task):
    allowed = {'task_id', 'domain', 'task_type', 'input_text', 'candidate_labels'}
    if set(task) - allowed or not isinstance(task.get('input_text'), str) or len(task['input_text']) > 16000:
        raise ValueError('INVALID_BLIND_TASK')
    labels = task.get('candidate_labels')
    if not isinstance(labels, list) or len(labels) < 2 or len(set(labels)) != len(labels):
        raise ValueError('INVALID_LABELS')
    if any(not isinstance(label, str) or not label or len(label) > 120 for label in labels):
        raise ValueError('INVALID_LABELS')
    return task


def auto_accept(result, labels):
    return (result.get('execution_status') == 'SUCCESS' and result.get('label') in labels
            and result['label'] != 'uncertain' and all(
                type(result.get(key)) in (int, float) and math.isfinite(result[key])
                and threshold <= result[key] <= 1
                for key, threshold in (('confidence', .85), ('margin', .50))))


def run_pairs(tasks, native, jev, model):
    """Finite trusted dispatch. No agent controls credentials, RPC or task selection."""
    if not 1 <= len(tasks) <= 3:
        raise ValueError('MAX_TASKS_3')
    calls = {'A': 0, 'J': 0, 'fallback': 0}
    records = []
    for raw in tasks:
        task = valid_task(raw)
        calls['A'] += 1
        a = native.classify(task, model)
        started = time.monotonic()
        calls['J'] += 1
        suggestion = jev.classify(task['input_text'], task['candidate_labels'], timeout_s=30)
        fallback = not auto_accept(suggestion, task['candidate_labels'])
        final = suggestion
        if fallback:
            calls['fallback'] += 1
            final = native.classify(task, model)
        # No raw provider text, reasoning, account data or authentication logs.
        record = {'task_id': task['task_id'], 'domain': task['domain'],
                  'evidence_kind': 'OBSERVED', 'externally_attested': False,
                  'A': {key: a.get(key) for key in ('label', 'requested_model', 'latency_ms', 'tokens_in', 'tokens_out', 'cost_usd')},
                  'J': {'label': final['label'], 'jev_label': suggestion['label'],
                        'jev_model': suggestion.get('model'), 'fallback': fallback,
                        'fallback_requested_model': model if fallback else None,
                        'latency_ms': round((time.monotonic() - started) * 1000, 2),
                        'tokens_in': None, 'tokens_out': None, 'cost_usd': None,
                        'jev_usage': {k: suggestion.get(k) for k in ('tokens_in', 'tokens_out', 'cost_usd')},
                        'fallback_usage': {k: final.get(k) for k in ('tokens_in', 'tokens_out', 'cost_usd')} if fallback else None}}
        records.append(record)
    return {'records': records, 'logical_calls': calls, 'retries': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'pilot'))
    parser.add_argument('--max-tasks', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--model')
    parser.add_argument('--package-entry', type=Path,
                        default=Path(tempfile.gettempdir()) / 'harness-jev-smoke-050/node_modules/@french-castle/jev-code/dist/cli.js')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'preflight':
        # Explicitly does not instantiate JEV, inject Infisical, or start a model turn.
        return mxc_g1_preflight.main(['--native-broker', '--diagnose-startup'])
    if not args.model or not args.output:
        parser.error('pilot requires explicit --model and a new --output file')
    output = args.output.absolute()
    if output.exists() or ROOT == output.parent or ROOT in output.parents:
        parser.error('output must be a new file outside the Git checkout')
    # Prepare trusted MCP only; no npx/download and no secret sent to native Codex.
    parent = dict(os.environ)
    parent['JEV_CODE_PROVIDER'] = 'openrouter'
    jev_env = isolated_child_env(parent)
    entry = verify_package(args.package_entry)
    node = shutil.which('node', path=jev_env.get('PATH'))
    if node is None:
        parser.error('Node missing')
    tasks = [valid_task(t) for t in load_tasks(ROOT / 'benchmarks/jev/tasks/tasks_all.jsonl')[:args.max_tasks]]
    def after_preflight(report, native):
        # Called only by this invocation's successful trusted native G1 launcher.
        with JevMcpClient([node, str(entry), 'mcp'], jev_env, entry.parent.parent) as jev:
            result = run_pairs(tasks, native, jev, args.model)
        result['scope'] = 'CLASSIFICATION_ONLY_NOT_CODE_QUALITY'
        result['g1_fixture'] = report['fixture']
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2)
        report['pilot_output'] = str(output)
        report['logical_calls'] = result['logical_calls']
    return mxc_g1_preflight.main(['--native-broker', '--diagnose-startup'], after_preflight)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError):
        print(json.dumps({'status': 'BLOCKED', 'error': 'EXECUTOR_ABORTED_NO_RETRY'}))
        raise SystemExit(1)
