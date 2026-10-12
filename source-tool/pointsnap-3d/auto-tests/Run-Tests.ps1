param([switch]$Online, [switch]$LiveCvat, [int]$JobId = 1, [string]$Dataset)
$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $toolRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install .[dev] first; see README.md.' }
$testArgs = @((Join-Path $PSScriptRoot 'run.py'), '--job', $JobId)
if ($Online) { $testArgs += '--online' }
if ($LiveCvat) { $testArgs += '--live-cvat' }
if ($Dataset) { $testArgs += @('--dataset', $Dataset) }
& $pythonPath @testArgs
exit $LASTEXITCODE
