# HE-JEV-006: one billable classification smoke test on the trusted host.
# This is NOT an agent benchmark, G1 attestation, or production deployment.
# Run from repository root in a trusted PowerShell terminal.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not (Test-Path -LiteralPath ".infisical.yaml")) {
    throw "Run this script from C:\dev\harness-engineering (repository root)."
}
foreach ($exe in @("node", "npm.cmd", "infisical", "python")) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) {
        throw "$exe not found in PATH"
    }
}

# Download/package installation happens with NO TypeSafe key injected.
# Fix upstream to v0.5.0; avoid install lifecycle scripts.
$prefix = Join-Path $env:TEMP "harness-jev-smoke-050"
$pkg = Join-Path $prefix "node_modules\@french-castle\jev-code"
$manifest = Join-Path $pkg "package.json"
$entry = Join-Path $pkg "dist\cli.js"
if (-not ((Test-Path -LiteralPath $manifest) -and (Test-Path -LiteralPath $entry))) {
    & npm.cmd install --prefix $prefix --ignore-scripts --no-audit --no-fund --no-package-lock --save-exact "@french-castle/jev-code@0.5.0"
    if ($LASTEXITCODE -ne 0) { throw "Package preparation failed" }
}
$metadata = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($metadata.name -ne "@french-castle/jev-code" -or $metadata.version -ne "0.5.0") {
    throw "Unpinned or invalid Jev package detected"
}
if (-not (Test-Path -LiteralPath $entry)) { throw "Jev entry point missing" }

Write-Output "HE-JEV-006: pinned package is prepared; invoking one fixed public classification."
Write-Output "Expected: one TypeSafe call; no raw result or credentials saved to disk."
# Infisical injects the single key only into the trusted Python runner;
# its MCP subprocess receives an explicit minimal environment allowlist.
& infisical run --env=dev -- python scripts/jev_live_smoke.py --package-entry $entry --execute-one-call
if ($LASTEXITCODE -ne 0) { throw "JEV live smoke test failed (see sanitized status above)" }
