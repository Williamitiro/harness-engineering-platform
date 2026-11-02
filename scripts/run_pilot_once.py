#!/usr/bin/env python3
"""Trusted Windows supervisor: one N<=3 run, 180 s hard limit, no retries.

Run outside MXC. Produces JSON and Markdown automatically, including on failure.
Never prints private logs or reads credential values. No process survives timeout.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.paired_executor import save_receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', default='gpt-6.1-sol')
    args = parser.parse_args()
    output = args.output.absolute()
    if os.name != 'nt' or any(p.exists() for p in (output, output.with_suffix('.md'))):
        parser.error('Windows and a new output path required')
    if ROOT in output.parents:
        parser.error('Output must be outside checkout')
    infisical = shutil.which('infisical')
    if not infisical:
        parser.error('Existing Infisical CLI required')
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [infisical, 'run', '--env=dev', '--', sys.executable,
               str(ROOT / 'scripts/paired_executor.py'), 'pilot', '--max-tasks', '3',
               '--model', args.model, '--output', str(output)]
    started = time.monotonic()
    process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    output.with_suffix('.invocation.json').write_text(json.dumps({
        'pid': process.pid, 'supervisor_pid': os.getpid(), 'command': command,
        'timeout_s': 180, 'max_tasks': 3, 'retries': 0}, indent=2), encoding='utf-8')
    timed_out = False
    try:
        stdout, _ = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Exact PID is this supervisor's child, never a name-wide process kill.
        subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/taskkill.exe'),
                        '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
        process.kill()
        stdout, _ = process.communicate(timeout=5)
    # Only public JSON reports are retained from the child's stdout. Infisical
    # banners and all arbitrary stderr are excluded from the public artifacts.
    text = stdout.decode('utf-8', errors='replace')
    native_report = None
    begin = text.find('{')
    if begin >= 0:
        try:
            native_report, _ = json.JSONDecoder().raw_decode(text[begin:])
        except ValueError:
            pass
    if output.exists():
        try:
            receipt = json.loads(output.read_text(encoding='utf-8'))
        except ValueError:
            receipt = {'status': 'ABORTED', 'records': []}
    else:
        receipt = {'status': 'ABORTED', 'records': [], 'logical_calls': {},
                   'error': {'stage': 'supervised_process', 'code': 'NO_PILOT_RECEIPT'}}
    if timed_out:
        receipt.update(status='ABORTED', error={'stage': 'supervised_process', 'code': 'WALL_TIMEOUT_180S'})
    if native_report is not None:
        receipt['native_preflight'] = native_report
    receipt.update(supervisor_exit_code=process.returncode, total_wall_ms=round((time.monotonic() - started) * 1000, 2))
    save_receipt(output, receipt)
    print(json.dumps({'status': receipt['status'], 'result': str(output),
                      'report': str(output.with_suffix('.md')), 'logical_calls': receipt.get('logical_calls'),
                      'error': receipt.get('error')}))
    return 0 if receipt['status'] == 'COMPLETED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
