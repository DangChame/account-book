# 가계부 자동화 - 윈도우 설치 스크립트 (저장소 폴더에서 PowerShell로 실행)
#   powershell -ExecutionPolicy Bypass -File windows\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Need($cmd, $wingetId) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "설치: $wingetId"
    winget install -e --id $wingetId --accept-source-agreements --accept-package-agreements
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
  }
}
Need node "OpenJS.NodeJS.LTS"
Need python "Python.Python.3.12"

if (-not (Test-Path package.json)) { npm init -y | Out-Null }
npm install playwright@1.48.2
npx playwright install chromium
python -m pip install --upgrade pip openpyxl

New-Item -ItemType Directory -Force "$HOME\.config\ledger" | Out-Null
Write-Host "설치 완료. 다음: OneDrive 로그인, 네이버 로그인, 텔레그램 설정 (windows\SETUP.md 참고)"
