#!/usr/bin/env python3
"""One CLI: unpaid native G1 preflight, or operator-only bounded A/J pilot."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
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
from scripts.jev_evaluator import load_ground_truth, load_policy, evaluate_domain


def error_code(exc):
    value = getattr(exc, 'diagnostic_code', str(exc) if type(exc).__name__ == 'BrokerError' else type(exc).__name__)
    return value if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', value) else type(exc).__name__


def save_receipt(output, result):
    """Only overwrite this invocation's already-reserved receipt, never another run."""
    staging = output.with_suffix('.pending.json')
    staging.write_text(json.dumps(result, indent=2), encoding='utf-8')
    os.replace(staging, output)
    lines = ['# Piloto HE-JEV — relatório observado', '', 'Estado: ' + result['status'], '',
             'Escopo: classificação de texto, até três casos; sem conclusão para N=30.', '',
             'Invocações lógicas: ' + json.dumps(result.get('logical_calls', {})),
             'Custos/tokens não observados: null. Retries: 0.', '',
             '| Caso | A | J final | Fallback | Erro |', '|---|---|---|---|---|']
    for record in result.get('records', []):
        a, j = record.get('A') or {}, record.get('J') or {}
        failure = record.get('error') or {}
        lines.append('| ' + ' | '.join(str(x) for x in (
            record['task_id'], a.get('label'), j.get('label'), j.get('fallback'), failure.get('code', ''))) + ' |')
    if result.get('error'):
        lines += ['', 'Falha: ' + json.dumps(result['error'])]
    if result.get('quality'):
        lines += ['', 'Avaliação aritmética pelo avaliador existente, no supervisor após coleta:',
                  '| Condição | Casos pareados | Acerto | Latência média ms | Custo USD observado |',
                  '|---|---|---|---|---|']
        for condition, quality in result['quality'].items():
            lines.append('| ' + ' | '.join(str(v) for v in (
                condition, quality['count'], quality['micro_accuracy'], quality['mean_latency_ms'], quality['total_cost_usd'])) + ' |')
    if result.get('evaluation_error'):
        lines += ['', 'Avaliação não concluída: ' + result['evaluation_error']]
    lines += ['', 'Funcionou: ' + ('coleta pareada concluída' if result['status'] == 'COMPLETED' else 'ver etapas concluídas e resultados parciais acima'),
              'Não comprovado: ganho econômico, validade estatística e qualidade de programação.',
              'Precisa melhorar: ' + ('diagnosticar a etapa/erro registrado antes de repetir.' if result['status'] != 'COMPLETED' else 'amostra e observabilidade de custos antes de decidir adoção.'),
              'Preservar: política MXC, segregação de credenciais e limites; roteamento JEV se houve resposta observada.',
              'Conclusão de adoção: INCONCLUSIVO; nenhum N=30 autorizado automaticamente.',
              'Próxima decisão: ' + ('comparar acerto e latência; N=3 é apenas piloto.' if result['status'] == 'COMPLETED' else 'corrigir o erro registrado; sem retry automático.')]
    output.with_suffix('.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


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


def run_pairs(tasks, native, jev, model, checkpoint=None):
    """Finite trusted dispatch. No agent controls credentials, RPC or task selection."""
    if not 1 <= len(tasks) <= 3:
        raise ValueError('MAX_TASKS_3')
    calls = {'A': 0, 'J': 0, 'fallback': 0}
    records = []
    result = {'status': 'RUNNING', 'records': records, 'logical_calls': calls, 'retries': 0}
    for raw in tasks:
        task = valid_task(raw)
        record = {'task_id': task['task_id'], 'domain': task['domain'],
                  'evidence_kind': 'OBSERVED', 'externally_attested': False,
                  'A': None, 'J': None}
        records.append(record)
        stage = 'A'
        try:
            calls['A'] += 1
            if checkpoint: checkpoint(result)
            a = native.classify(task, model)
            record['A'] = {key: a.get(key) for key in ('label', 'requested_model', 'latency_ms', 'tokens_in', 'tokens_out', 'cost_usd')}
            if checkpoint: checkpoint(result)
            stage = 'J'
            started = time.monotonic()
            calls['J'] += 1
            if checkpoint: checkpoint(result)
            suggestion = jev.classify(task['input_text'], task['candidate_labels'], timeout_s=30)
            fallback = not auto_accept(suggestion, task['candidate_labels'])
            record['jev_suggestion'] = {k: suggestion.get(k) for k in ('label', 'model', 'execution_status', 'latency_ms', 'tokens_in', 'tokens_out', 'cost_usd')}
            if checkpoint: checkpoint(result)
            final = suggestion
            if fallback:
                stage = 'fallback'
                calls['fallback'] += 1
                if checkpoint: checkpoint(result)
                final = native.classify(task, model)
            record['J'] = {'label': final['label'], 'jev_label': suggestion['label'],
                        'jev_model': suggestion.get('model'), 'fallback': fallback,
                        'fallback_requested_model': model if fallback else None,
                        'latency_ms': round((time.monotonic() - started) * 1000, 2),
                        'tokens_in': None, 'tokens_out': None, 'cost_usd': None,
                        'jev_usage': {k: suggestion.get(k) for k in ('tokens_in', 'tokens_out', 'cost_usd')},
                        'fallback_usage': {k: final.get(k) for k in ('tokens_in', 'tokens_out', 'cost_usd')} if fallback else None}
            if checkpoint: checkpoint(result)
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            record['error'] = {'stage': stage, 'code': error_code(exc)}
            result['status'] = 'ABORTED'
            result['error'] = record['error']
            if checkpoint: checkpoint(result)
            return result
    result['status'] = 'COMPLETED'
    if checkpoint: checkpoint(result)
    return result


def score_pairs(result):
    # The evaluator alone opens ground truth, after all model dispatches finish.
    truths = {}
    for source in sorted((ROOT / 'benchmarks/jev/ground_truth').glob('golden_*.jsonl')):
        truths.update(load_ground_truth(source))
    policy = load_policy(ROOT / 'config/jev_multi_domain_policy.json')
    paired = [r for r in result['records'] if r.get('A') and r.get('J')]
    if not paired:
        return None
    quality = {}
    for condition in ('A', 'J'):
        rows = [{'task_id': r['task_id'], 'domain': r['domain'],
                 'parsed_decision': {'label': r[condition]['label']},
                 'observed_metrics': r[condition]} for r in paired]
        quality[condition] = evaluate_domain(rows, truths, policy)
    return quality


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
    if any(p.exists() for p in (output, output.with_suffix('.md'), output.with_suffix('.pending.json'))) or ROOT == output.parent or ROOT in output.parents:
        parser.error('output must be a new file outside the Git checkout')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump({'status': 'PREPARING'}, stream)
    initial = {'status': 'PREPARING', 'records': [], 'logical_calls': {'A': 0, 'J': 0, 'fallback': 0},
               'retries': 0, 'phase': 'credentials_and_package', 'cost_usd': None}
    save_receipt(output, initial)
    # Prepare trusted MCP only; no npx/download and no secret sent to native Codex.
    parent = dict(os.environ)
    parent['JEV_CODE_PROVIDER'] = 'openrouter'
    try:
        jev_env = isolated_child_env(parent)
        entry = verify_package(args.package_entry)
        node = shutil.which('node', path=jev_env.get('PATH'))
        if node is None:
            raise RuntimeError('NODE_MISSING')
        tasks = [valid_task(t) for t in load_tasks(ROOT / 'benchmarks/jev/tasks/tasks_all.jsonl')[:args.max_tasks]]
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        initial.update(status='ABORTED', error={'stage': initial['phase'], 'code': error_code(exc)})
        save_receipt(output, initial)
        print(json.dumps({'status': 'ABORTED', 'error': initial['error'], 'output': str(output)}))
        return 1
    def after_preflight(report, native):
        # Called only by this invocation's successful trusted native G1 launcher.
        initial.update(phase='native_session_prepare', g1_fixture=report['fixture'])
        save_receipt(output, initial)
        result = initial
        try:
            native.prepare(args.model)  # free: no turn/start, no inference
            initial['phase'] = 'jev_initialize'
            save_receipt(output, initial)
            with JevMcpClient([node, str(entry), 'mcp'], jev_env, entry.parent.parent) as jev:
                result = run_pairs(tasks, native, jev, args.model, lambda data: save_receipt(output, data))
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            result.update(status='ABORTED', error={'stage': initial['phase'], 'code': error_code(exc)})
        result.update(scope='CLASSIFICATION_ONLY_NOT_CODE_QUALITY', g1_fixture=report['fixture'])
        if native.diagnostic_file is not None:
            result['private_native_diagnostic_directory'] = str(native.diagnostic_file.parent)
        try:
            result['quality'] = score_pairs(result)
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            result['evaluation_error'] = error_code(exc)
        save_receipt(output, result)
        report['pilot_output'] = str(output)
        report['pilot_report'] = str(output.with_suffix('.md'))
        report['pilot_status'] = result['status']
        report['paid_calls'] = None if any(result['logical_calls'].values()) else 0
        report['logical_calls'] = result['logical_calls']
        if result.get('error'): report['pilot_error'] = result['error']
    code = mxc_g1_preflight.main(['--native-broker', '--diagnose-startup'], after_preflight)
    receipt = json.loads(output.read_text(encoding='utf-8'))
    if code and receipt.get('status') == 'PREPARING':
        receipt.update(status='ABORTED', error={'stage': 'g1_preflight', 'code': 'G1_FAILED'})
        save_receipt(output, receipt)
    return code


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, KeyError):
        print(json.dumps({'status': 'BLOCKED', 'error': 'EXECUTOR_ABORTED_NO_RETRY'}))
        raise SystemExit(1)
