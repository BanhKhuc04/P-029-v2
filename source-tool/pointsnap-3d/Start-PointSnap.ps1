param([switch]$NoBrowser, [int]$Port = 8765, [string]$ProjectHome, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be 1..65535.' }
$toolRoot = $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $toolRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Create .venv and install .[dev]; see ../CAI-DAT.md.' }
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
try { $listener.Start() } catch { throw "Port $Port is already in use; choose another port." } finally { $listener.Stop() }
if (-not $ProjectHome) { $ProjectHome = Join-Path $toolRoot 'data/pointsnap-home' }
$outputDir = Join-Path $toolRoot 'out'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$previousHome = $env:POINTSNAP_HOME
$previousPythonPath = $env:PYTHONPATH
try {
    $env:POINTSNAP_HOME = [IO.Path]::GetFullPath($ProjectHome)
    $libraries = Join-Path $toolRoot '.venv/Lib/site-packages'
    $env:PYTHONPATH = $toolRoot
    if ([IO.Path]::GetFullPath($PythonPath) -eq [IO.Path]::GetFullPath((Join-Path $toolRoot '.venv/Scripts/python.exe')) -and (Test-Path -LiteralPath $libraries)) {
        $env:PYTHONPATH = $libraries + [IO.Path]::PathSeparator + $toolRoot
    }
    $arguments = @('-m', 'pointsnap', 'ui', '--port', $Port)
    if ($NoBrowser) { $arguments += '--no-browser' }
    $process = Start-Process -FilePath $PythonPath -ArgumentList $arguments -WorkingDirectory $toolRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $outputDir "ui-$Port.stdout.log") -RedirectStandardError (Join-Path $outputDir "ui-$Port.stderr.log")
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($process.HasExited) { throw "UI exited. Read out/ui-$Port.stderr.log." }
        try {
            $response = Invoke-WebRequest "http://127.0.0.1:$Port/" -UseBasicParsing -TimeoutSec 1
            if ($response.StatusCode -eq 200 -and $response.Content -match 'PointSnap') { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 200
    }
    if (-not $ready) { Stop-Process -Id $process.Id; throw 'UI startup timed out; inspect the log.' }
    Write-Output "PointSnap http://127.0.0.1:$Port | PID=$($process.Id)"
} finally {
    $env:POINTSNAP_HOME = $previousHome
    $env:PYTHONPATH = $previousPythonPath
}
