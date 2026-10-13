param(
    [string]$Dataset,
    [switch]$LiveCvat,
    [string]$CvatUrl = 'http://localhost:8080',
    [switch]$Evaluate,
    [int]$Rounds = 10,
    [switch]$Docker,
    [switch]$ModelSmoke,
    [string]$ReviewModel
)
$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $toolRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install .[dev], build and wheel first.' }
$testArgs = @((Join-Path $PSScriptRoot 'run_all.py'), '--cvat-url', $CvatUrl, '--rounds', $Rounds)
if ($Dataset) { $testArgs += @('--dataset', $Dataset) }
if ($LiveCvat) { $testArgs += '--live-cvat' }
if ($Evaluate) { $testArgs += '--evaluate' }
if ($Docker) { $testArgs += '--docker' }
if ($ModelSmoke) { $testArgs += '--model-smoke' }
if ($ReviewModel) { $testArgs += @('--review-model', $ReviewModel) }
& $pythonPath @testArgs
exit $LASTEXITCODE
