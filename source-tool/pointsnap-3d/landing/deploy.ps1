# Đưa landing page lên Vercel (production). Chạy: .\deploy.ps1
# Deploy từ một bản sao ngoài repo git: Vercel gói Hobby chặn deploy khi commit gần nhất
# của repo là của người khác (thành viên nhóm), dù người chạy lệnh là chủ project.
$dst = Join-Path $env:TEMP 'pointsnap-landing-deploy'
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
robocopy $PSScriptRoot $dst /E /XF .env.local .env README.md deploy.ps1 /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Error "Không chép được thư mục landing (robocopy $LASTEXITCODE)"; exit 1 }
# Font IBM Plex dùng chung với giao diện PointSnap (/static/fonts/), không tải từ Google.
$fonts = Join-Path $PSScriptRoot '..\pointsnap\web\static\fonts'
robocopy $fonts (Join-Path $dst 'static\fonts') /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Error "Không chép được font (robocopy $LASTEXITCODE)"; exit 1 }
Push-Location $dst
try { cmd /c "npx --yes vercel@63.1.2 deploy --prod --yes 2>&1" } finally { Pop-Location }
