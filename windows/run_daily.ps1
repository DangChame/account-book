# 매일 새벽 가계부 자동 수집 (작업 스케줄러가 실행)
# 1단계 collect.py(Claude 없음): 수집·중복 확인·포인트·새 달 → 판단이 필요한 새 건이 있을 때만 2단계 Claude
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = "$HOME\.config\ledger\daily.log"
# 윈도우 기본 인코딩(cp949)으로 한글 json/출력이 깨지지 않게
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)  # claude 출력(UTF-8)을 daily.log에 그대로
if (-not $env:ASIDE_CDP) { $env:ASIDE_CDP = "http://127.0.0.1:9222" }
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
python collect.py 2>&1 | Out-File -Append -Encoding utf8 $log
$rc = $LASTEXITCODE
$web = Join-Path (Split-Path (Get-Location) -Parent) "ledger-web"
if ($rc -eq 10) {
  "---- Claude (새 건 분류) $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
  $prompt = Get-Content -Raw -Encoding UTF8 "windows\routine_prompt.txt"
  # 사용자 PC에서 무인 실행 → 이 저장소 작업에 필요한 도구만 허용. 분류는 가벼운 일이라 sonnet.
  claude -p $prompt --model sonnet --add-dir $web --allowedTools "Bash,Read,Edit,Write,Glob,Grep" 2>&1 | Out-File -Append -Encoding utf8 $log
} elseif ($rc -ne 0 -and $rc -ne 3 -and $rc -ne 4) {
  python tg.py "가계부 새벽 수집 오류 (코드 $rc) - daily.log 확인 필요" 2>&1 | Out-File -Append -Encoding utf8 $log
}
# 가계부 원본(ledger-web/data/*.json)이 바뀌었으면 GitHub에 올림. 엑셀은 2주마다 따로.
$pub = Join-Path $web "tools\publish.ps1"
if (Test-Path $pub) {
  "---- 웹 올리기 $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
  powershell -NoProfile -ExecutionPolicy Bypass -File $pub 2>&1 | Out-File -Append -Encoding utf8 $log
}
