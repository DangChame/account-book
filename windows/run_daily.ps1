# 매일 새벽 가계부 자동 수집 (작업 스케줄러가 실행)
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = "$HOME\.config\ledger\daily.log"
$prompt = Get-Content -Raw -Encoding UTF8 "windows\routine_prompt.txt"
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
# 사용자 PC에서 무인 실행 → 이 저장소 작업에 필요한 도구만 허용
claude -p $prompt --allowedTools "Bash,Read,Edit,Write,Glob,Grep" 2>&1 | Out-File -Append -Encoding utf8 $log
