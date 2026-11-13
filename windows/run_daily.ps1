# 매일 새벽 가계부 자동 수집 (작업 스케줄러가 실행)
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = "$HOME\.config\ledger\daily.log"
# 윈도우 기본 인코딩(cp949)으로 한글 json/출력이 깨지지 않게
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)  # claude 출력(UTF-8)을 daily.log에 그대로
if (-not $env:ASIDE_CDP) { $env:ASIDE_CDP = "http://127.0.0.1:9222" }
$prompt = Get-Content -Raw -Encoding UTF8 "windows\routine_prompt.txt"
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
# 사용자 PC에서 무인 실행 → 이 저장소 작업에 필요한 도구만 허용
$web = Join-Path (Split-Path (Get-Location) -Parent) "ledger-web"
claude -p $prompt --add-dir $web --allowedTools "Bash,Read,Edit,Write,Glob,Grep" 2>&1 | Out-File -Append -Encoding utf8 $log
# 가계부 원본(ledger-web/data/*.json)이 바뀌었으면 GitHub에 올림 (토큰 안 씀). 엑셀은 2주마다 따로.
$pub = Join-Path (Split-Path (Get-Location) -Parent) "ledger-web\tools\publish.ps1"
if (Test-Path $pub) {
  "---- 웹 올리기 $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
  powershell -NoProfile -ExecutionPolicy Bypass -File $pub 2>&1 | Out-File -Append -Encoding utf8 $log
}
