#!/usr/bin/env python3
"""One-time, fail-closed patch: switch paired_executor J branch from MCP/Node to HTTP.

Run from the repo root on the existing codex/he-jev-007a branch. Does not call API.
"""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'scripts/paired_executor.py'


def once(src, needle, repl):
    if src.count(needle) != 1:
        raise RuntimeError(f'PATCH_REFUSED: expected exactly one match for {needle[:65]!r}')
    return src.replace(needle, repl)


def main():
    import os
    if not TARGET.exists():
        raise RuntimeError('PATCH_REFUSED: paired_executor.py not found')
    state = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no', '--', 'scripts/paired_executor.py'], cwd=ROOT, capture_output=True, text=True)
    if state.returncode != 0 or state.stdout.strip():
        raise RuntimeError('PATCH_REFUSED: executor has existing modifications')
    src = TARGET.read_text(encoding='utf-8')
    src = once(src, 'from scripts.jev_adapter import JevMcpClient', 'from scripts.jev_http import JevHttpClient')
    src = once(src, 'from scripts.jev_live_smoke import isolated_child_env, verify_package\n', '')
    src = once(src, "choices=('preflight', 'diagnose-jev', 'pilot')", "choices=('preflight', 'pilot')")
    src = once(src, "    parser.add_argument('--package-entry', type=Path,\n                        default=Path(tempfile.gettempdir()) / 'harness-jev-smoke-050/node_modules/@french-castle/jev-code/dist/cli.js')\n", '')
    a = src.index("    if args.mode == 'diagnose-jev':")
    b = src.index("    if not args.model or not args.output:", a)
    src = src[:a] + src[b:]
    a = src.index("    # Prepare trusted MCP only; no npx/download and no secret sent to native Codex.")
    b = src.index('    def after_preflight(report, native):', a)
    src = src[:a] + '''    # Direct OpenRouter Decisions HTTP; the key remains only in this supervisor.
    # No Node.js, MCP subprocess, external package or sandbox credential injection.
    try:
        jev_client = JevHttpClient.from_environment(os.environ)
        tasks = [valid_task(t) for t in load_tasks(ROOT / 'benchmarks/jev/tasks/tasks_all.jsonl')[:args.max_tasks]]
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        initial.update(status='ABORTED', error={'stage': 'credentials_and_tasks', 'code': error_code(exc)})
        save_receipt(output, initial)
        print(json.dumps({'status': 'ABORTED', 'error': initial['error'], 'output': str(output)}))
        return 1
''' + src[b:]
    a = src.index('        result = initial\n        jev = None', src.index('    def after_preflight(report, native):'))
    b = src.index('        result.update(scope=', a)
    src = src[:a] + '''        result = initial
        try:
            native.prepare(args.model)  # no model turn yet
            initial['phase'] = 'jev_http_dispatch'
            save_receipt(output, initial)
            result = run_pairs(tasks, native, jev_client, args.model,
                               lambda data: save_receipt(output, data))
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            result.update(status='ABORTED', error={'stage': initial['phase'], 'code': error_code(exc)})
''' + src[b:]
    # Record probability/margin for interpreting Jev's policy without raw provider data.
    src = once(src, "('label', 'model', 'execution_status', 'latency_ms', 'tokens_in', 'tokens_out', 'cost_usd')",
               "('label', 'predicted_label', 'confidence', 'margin', 'model', 'execution_status', 'latency_ms', 'tokens_in', 'tokens_out', 'cost_usd')")
    # When all usage components are observed, sum JEV+fallback; else keep null.
    old = """                        'tokens_in': None, 'tokens_out': None, 'cost_usd': None,
                        'jev_usage':"""
    new = """                        'tokens_in': (suggestion.get('tokens_in') if not fallback else
                                      sum([suggestion['tokens_in'], final['tokens_in']])
                                      if type(suggestion.get('tokens_in')) is int and type(final.get('tokens_in')) is int else None),
                        'tokens_out': (suggestion.get('tokens_out') if not fallback else
                                       sum([suggestion['tokens_out'], final['tokens_out']])
                                       if type(suggestion.get('tokens_out')) is int and type(final.get('tokens_out')) is int else None),
                        'cost_usd': (suggestion.get('cost_usd') if not fallback else
                                     round(suggestion['cost_usd'] + final['cost_usd'], 10)
                                     if type(suggestion.get('cost_usd')) in (int, float) and
                                        type(final.get('cost_usd')) in (int, float) else None),
                        'jev_usage':"""
    src = once(src, old, new)
    compile(src, str(TARGET), 'exec')
    TARGET.write_text(src, encoding='utf-8')
    print('PATCH_APPLIED: paired_executor now uses direct OpenRouter Decisions HTTP; no model called')


if __name__ == '__main__':
    main()
