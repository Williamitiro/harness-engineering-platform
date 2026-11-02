#!/usr/bin/env python3
"""One bounded, unpaid MXC probe. Artificial files only; never enables live."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def private_diagnostic_directory(fixture: Path, env: dict[str, str]) -> Path:
    """Restrict only the diagnostic directory, never the tested file canaries.

    Raw errors are local operator data, excluded from stdout and Git. Refuse
    diagnostic mode if the Windows ACL cannot be applied successfully.
    """
    system32 = Path(env['SystemRoot']) / 'System32'
    identity = subprocess.run(
        [str(system32 / 'whoami.exe'), '/user', '/fo', 'csv', '/nh'],
        env=env, capture_output=True, text=True, check=True, timeout=5,
    )
    sid = next(csv.reader(identity.stdout.splitlines()))[-1].strip()
    if not re.fullmatch(r'S-1-\d+(?:-\d+)+', sid):
        raise ValueError('Unable to resolve operator SID')
    directory = fixture / 'private-diagnostics'
    directory.mkdir()
    subprocess.run(
        [str(system32 / 'icacls.exe'), str(directory), '/inheritance:r',
         '/grant:r', f'*{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'],
        env=env, capture_output=True, check=True, timeout=5,
    )
    return directory

PROBE = r'''
$ErrorActionPreference = 'Stop'
$r = [ordered]@{}
$r.allowed_read = ([IO.File]::ReadAllText((Join-Path $PSScriptRoot 'allowed.txt')) -eq 'ARTIFICIAL')
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'allowed-write.txt'), 'ARTIFICIAL')
$r.allowed_write = $true
$targets = Get-Content (Join-Path $PSScriptRoot 'targets.json') -Raw | ConvertFrom-Json
foreach ($p in $targets.PSObject.Properties) {
    if ($p.Name -eq 'loopback_port') { continue }
    try {
        $f = [IO.File]::Open($p.Value, 'Open', 'Read', 'ReadWrite')
        $f.Dispose()
        $r[$p.Name] = 'LEAKED'
    } catch {
        $e = $_.Exception
        while ($e.InnerException) { $e = $e.InnerException }
        $r[$p.Name] = if (($e.HResult -band 65535) -eq 5) { 'DENIED' } else { 'INCONCLUSIVE' }
    }
}
try {
    [IO.File]::WriteAllText((Join-Path (Split-Path $PSScriptRoot) 'outside-write.txt'), 'ARTIFICIAL')
    $r.outside_write = 'LEAKED'
} catch {
    $e = $_.Exception
    while ($e.InnerException) { $e = $e.InnerException }
    $r.outside_write = if (($e.HResult -band 65535) -eq 5) { 'DENIED' } else { 'INCONCLUSIVE' }
}
$r.credential_environment_absent = (@(Get-ChildItem Env: | Where-Object {
    $_.Name -match '(?i)(API.?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|INFISICAL|G1_SUPERVISOR)'
}).Count -eq 0)
foreach ($endpoint in @(@('external', '1.1.1.1', 443), @('loopback', '127.0.0.1', [int]$targets.loopback_port))) {
    $s = New-Object Net.Sockets.Socket([Net.Sockets.AddressFamily]::InterNetwork, [Net.Sockets.SocketType]::Stream, [Net.Sockets.ProtocolType]::Tcp)
    try {
        $a = $s.BeginConnect($endpoint[1], [int]$endpoint[2], $null, $null)
        if (!$a.AsyncWaitHandle.WaitOne(750)) { $r['network_' + $endpoint[0]] = 'INCONCLUSIVE_TIMEOUT' }
        else {
            try { $s.EndConnect($a); $r['network_' + $endpoint[0]] = 'LEAKED' }
            catch {
                $e = $_.Exception
                while ($e.InnerException) { $e = $e.InnerException }
                $r['network_' + $endpoint[0]] = if ($e.SocketErrorCode -eq 'AccessDenied') { 'DENIED' } else { 'INCONCLUSIVE' }
            }
        }
    } catch { $r['network_' + $endpoint[0]] = 'INCONCLUSIVE' }
    finally { $s.Dispose() }
}
$r | ConvertTo-Json -Compress
'''


def main() -> int:
    import socket

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-exe', type=Path)
    parser.add_argument('--diagnose-startup', action='store_true',
                        help='On failure retain stderr locally under an operator/SYSTEM-only ACL; never print it')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('Native Windows required')
    exe = args.codex_exe
    if exe is None:
        base = Path(os.environ['APPDATA']) / 'npm/node_modules/@openai/codex'
        matches = list(base.glob('node_modules/@openai/codex-win32-*/vendor/*/bin/codex.exe'))
        if len(matches) != 1:
            parser.error('Specify installed codex.exe with --codex-exe')
        exe = matches[0]
    exe = exe.resolve(strict=True)
    fixture = Path(tempfile.mkdtemp(prefix='he-jev-mxc-g1-'))
    workspace = fixture / 'workspace'
    workspace.mkdir()
    protected = fixture / 'protected'
    protected.mkdir()
    (protected / '.git').mkdir()
    paths = {
        'protected_read': protected / 'personal-canary.txt',
        'golden_read': protected / 'golden_canary.jsonl',
        'git_read': protected / '.git/config',
        'workspace_denied_read': workspace / 'denied-canary.txt',
    }
    for path in paths.values():
        path.write_text('ARTIFICIAL', encoding='utf-8')
    (workspace / 'allowed.txt').write_text('ARTIFICIAL', encoding='utf-8')
    (workspace / 'probe.ps1').write_text(PROBE, encoding='utf-8')
    # A host listener supplies a reachable loopback control without external services.
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    targets = {key: str(value) for key, value in paths.items()}
    targets['loopback_port'] = listener.getsockname()[1]
    (workspace / 'targets.json').write_text(json.dumps(targets), encoding='utf-8')
    # No global config writes. Exact denies exist before MXC starts (no glob race).
    fs = {':root': 'deny', ':minimal': 'read', str(workspace): 'write',
          str(ROOT): 'deny', str(Path.home()): 'deny',
          str(protected): 'deny', str(paths['workspace_denied_read']): 'deny'}
    # Codex's executable is trusted supervisor infrastructure, outside the child grants.
    config = [
        '-c', 'windows.sandbox="mxc"',
        '-c', 'permissions.he-jev-g1.filesystem=' + '{' + ','.join(json.dumps(k) + '=' + json.dumps(v) for k, v in fs.items()) + '}',
        '-c', 'permissions.he-jev-g1.network.enabled=false',
    ]
    powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    command = [str(exe), *config, 'sandbox', '--include-managed-config',
               '--permission-profile', 'he-jev-g1', '-C', str(workspace), '--',
               str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive',
               '-File', str(workspace / 'probe.ps1')]
    # MXC requires the operational host SystemDrive variable during preparation.
    keep = ('SystemRoot', 'SystemDrive', 'WINDIR', 'PATH', 'PATHEXT', 'TEMP', 'TMP',
            'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'PROGRAMDATA', 'ProgramFiles')
    env = {key: os.environ[key] for key in keep if key in os.environ}
    report = {'status': 'BLOCKED_G1', 'scope': 'MXC_NEGATIVE_CANARIES_ONLY',
              'fixture': str(fixture), 'paid_calls': 0, 'broker_verified': False,
              'timeout_s': 40, 'max_invocations': 1, 'retries': 0,
              'policy_filesystem': fs, 'network_enabled': False}
    # Record only artificial policy and the exact reproducible command, never env values.
    (fixture / 'command.json').write_text(json.dumps(command, indent=2), encoding='utf-8')
    diagnostic_directory = None
    if args.diagnose_startup:
        try:
            diagnostic_directory = private_diagnostic_directory(fixture, env)
        except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
            listener.close()
            report['error'] = 'PRIVATE_DIAGNOSTIC_ACL_FAILED_NO_MXC_STARTED'
            (fixture / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report, indent=2))
            return 1
    try:
        result = subprocess.run(command, cwd=workspace, env=env, capture_output=True,
                                text=True, timeout=40)
        report['exit_code'] = result.returncode
        # Stdout remains a closed schema. Raw stderr is retained only by the
        # operator's explicit diagnostic option and only under its private ACL.
        try:
            parsed = json.loads(result.stdout.strip())
            expected = {'allowed_read', 'allowed_write', 'outside_write',
                        'credential_environment_absent', 'network_external', 'network_loopback', *paths}
            if set(parsed) != expected:
                raise ValueError('Unexpected probe schema')
            if any(v not in (True, False, 'DENIED', 'LEAKED', 'INCONCLUSIVE', 'INCONCLUSIVE_TIMEOUT') for v in parsed.values()):
                raise ValueError('Unexpected probe value')
            report['probes'] = parsed
            report['canaries_passed'] = result.returncode == 0 and all(
                value is True if key in ('allowed_read', 'allowed_write', 'credential_environment_absent')
                else value == 'DENIED' for key, value in parsed.items())
        except (ValueError, TypeError):
            report['error'] = 'MXC_START_OR_PROBE_FAILED'
            # Stable errors only, no raw logs that could include operator data.
            report['diagnostic'] = ('MXC_POLICY_UNSUPPORTED' if 'unsupported' in result.stderr.lower()
                                    else 'NO_VALID_PROBE_REPORT')
            # Closed vocabulary: enough to distinguish policy parsing from runtime
            # failures without emitting arbitrary stderr, paths or config contents.
            report['diagnostic_terms'] = [term for term in (
                'error parsing', 'invalid type', 'unknown variant', 'unknown field',
                'permission profile', 'not found', 'access is denied',
                'createprocess', 'spawnchild', 'mxc', 'toml', 'filesystem',
                'denied', 'not supported', 'execution policy', 'cannot be loaded',
                'not recognized', 'permissions', 'configuration', 'failed',
            ) if term in result.stderr.lower()]
            report['windows_error_codes'] = re.findall(r'Windows error (\d+)', result.stderr)
            report['stdout_empty'] = not bool(result.stdout.strip())
            if diagnostic_directory is not None:
                diagnostic_file = diagnostic_directory / 'startup-stderr.txt'
                diagnostic_file.write_text(result.stderr, encoding='utf-8')
                report['private_diagnostic_file'] = str(diagnostic_file)
    except subprocess.TimeoutExpired:
        report['error'] = 'MXC_TIMEOUT_NO_RETRY'
    finally:
        listener.close()
    # Even passing canaries alone cannot authenticate the future credential broker.
    output = fixture / 'report.json'
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report.get('canaries_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
