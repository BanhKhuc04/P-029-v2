param(
    [ValidateRange(1, 2147483647)][int]$JobId = 1,
    [ValidateSet('json', 'html', 'csv')][string]$Format = 'html',
    [string]$OutFile,
    [string]$ApiUrl = 'http://localhost:8080'
)

$ErrorActionPreference = 'Stop'
$reportToken = $env:CVAT_TOKEN
if ([string]::IsNullOrWhiteSpace($reportToken)) {
    $reportEnvFile = Join-Path $PSScriptRoot '.env'
    $tokenLine = if (Test-Path -LiteralPath $reportEnvFile) {
        Get-Content -LiteralPath $reportEnvFile |
            Where-Object { $_ -match '^CVAT_TOKEN\s*=' } | Select-Object -Last 1
    }
    if ($tokenLine) { $reportToken = ($tokenLine -split '=', 2)[1].Trim().Trim('"').Trim("'") }
}
if ([string]::IsNullOrWhiteSpace($reportToken)) { throw 'Điền CVAT_TOKEN vào .env trước khi lấy báo cáo.' }
if (-not $OutFile) { $OutFile = Join-Path $PSScriptRoot "out/report_job_${JobId}_api.$Format" }
$reportPath = [System.IO.Path]::GetFullPath($OutFile)
New-Item -ItemType Directory -Path (Split-Path -Parent $reportPath) -Force | Out-Null
$reportBaseUri = [uri]$ApiUrl
if ($reportBaseUri.Scheme -notin @('http', 'https') -or $reportBaseUri.UserInfo -or $reportBaseUri.Query -or $reportBaseUri.Fragment) {
    throw 'ApiUrl phải là HTTP(S), không chứa thông tin đăng nhập, query hoặc fragment.'
}
$reportUrl = $ApiUrl.TrimEnd('/') + "/pointsnap/jobs/$JobId/report?format=$Format"
Invoke-WebRequest -Uri $reportUrl -Headers @{ Authorization = "Bearer $reportToken" } `
    -UseBasicParsing -TimeoutSec 150 -OutFile $reportPath
Get-Item -LiteralPath $reportPath | Select-Object FullName, Length
