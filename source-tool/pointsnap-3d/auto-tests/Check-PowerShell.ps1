$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $toolRoot
try {
    $tracked = @(& git ls-files -- '*.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }
    $scripts = @($tracked | ForEach-Object { Join-Path $toolRoot $_ })
    $scripts += @(Get-ChildItem -LiteralPath $PSScriptRoot -Filter '*.ps1' | ForEach-Object { $_.FullName })
    $scripts = @($scripts | Sort-Object -Unique)
    $invalid = 0
    foreach ($scriptPath in $scripts) {
        $tokens = $null
        $parseErrors = $null
        $null = [System.Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$parseErrors)
        if ($parseErrors.Count -gt 0) {
            $invalid++
            Write-Output ($scriptPath + ': ' + ($parseErrors.Message -join '; '))
        }
    }
    Write-Output ('PowerShell scripts: ' + $scripts.Count + '; invalid: ' + $invalid)
    if ($invalid -gt 0) { exit 1 }
} finally {
    Pop-Location
}
