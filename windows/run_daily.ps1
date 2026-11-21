# 매일 새벽 가계부 자동 수집 (작업 스케줄러가 실행)
# 1단계 collect.py(Claude 없음): 수집·중복 확인·포인트·새 달 → 판단이 필요한 새 건이 있을 때만 2단계 Claude
Set-Location (Split-Path $PSScriptRoot -Parent)
$log = "$HOME\.config\ledger\daily.log"
# 윈도우 기본 인코딩(cp949)으로 한글 json/출력이 깨지지 않게
$env:PYTHONUTF8 = "1"; $env:PYTHONIOENCODING = "utf-8"
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)  # claude 출력(UTF-8)을 daily.log에 그대로
if (-not $env:ASIDE_CDP) { $env:ASIDE_CDP = "http://127.0.0.1:9222" }
"==== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
# Aside가 업데이트 등으로 디버깅 포트 없이 다시 켜져 있으면 포트를 붙여 다시 켠다 (2026-11-19: 이것 때문에 수집 실패)
try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "$env:ASIDE_CDP/json/version" | Out-Null } catch {
  "Aside 디버깅 포트 없음 → 다시 켬" | Out-File -Append -Encoding utf8 $log
  Get-Process aside -ErrorAction SilentlyContinue | ? { $_.Path -like '*Program Files*' } | Stop-Process -Force
  Start-Sleep 3
  Start-Process "C:\Program Files\Aside\Application\Aside.exe" "--remote-debugging-port=9222"
  Start-Sleep 15
}
python collect.py 2>&1 | Out-File -Append -Encoding utf8 $log
$rc = $LASTEXITCODE
$web = Join-Path (Split-Path (Get-Location) -Parent) "ledger-web"
if ($rc -eq 10) {
  "---- Claude (새 건 분류) $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
  $prompt = Get-Content -Raw -Encoding UTF8 "windows\routine_prompt.txt"
  # 사용자 PC에서 무인 실행 → 이 저장소 작업에 필요한 도구만 허용. 분류는 가벼운 일이라 sonnet.
  $out = claude -p $prompt --model sonnet --add-dir $web --allowedTools "Bash,Read,Edit,Write,Glob,Grep" 2>&1 | Out-String
  $out | Out-File -Append -Encoding utf8 $log
  # Claude가 tg.py를 안 부르는 일이 있어(2026-11-22 확인) 보고는 스크립트가 직접 보낸다
  $msg = "가계부 새벽 수집 완료`n" + $out.Trim()
  if ($msg.Length -gt 3500) { $msg = $msg.Substring(0, 3500) + " …" }
  if ($LASTEXITCODE -ne 0 -or -not $out.Trim()) { $msg = "가계부 새벽 수집: Claude 분류 단계 실패 - daily.log 확인 필요`n" + $out.Trim() }
  $mf = "$HOME\.config\ledger\tg_msg.txt"
  [IO.File]::WriteAllText($mf, $msg, [Text.UTF8Encoding]::new($false))
  python tg.py --file $mf 2>&1 | Out-File -Append -Encoding utf8 $log
} elseif ($rc -ne 0 -and $rc -ne 3 -and $rc -ne 4) {
  python tg.py "가계부 새벽 수집 오류 (코드 $rc) - daily.log 확인 필요" 2>&1 | Out-File -Append -Encoding utf8 $log
}
# 쿠팡 반품·취소 확인: 매달 둘째 주 일요일·말일에만 (날짜 판단은 스크립트 안에서, Claude 없음)
"---- 쿠팡 반품 확인 $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
python coupang_returns.py 2>&1 | Out-File -Append -Encoding utf8 $log
# 가계부 원본(ledger-web/data/*.json)이 바뀌었으면 GitHub에 올림. 엑셀은 2주마다 따로.
$pub = Join-Path $web "tools\publish.ps1"
if (Test-Path $pub) {
  "---- 웹 올리기 $(Get-Date -Format 'HH:mm:ss')" | Out-File -Append -Encoding utf8 $log
  powershell -NoProfile -ExecutionPolicy Bypass -File $pub 2>&1 | Out-File -Append -Encoding utf8 $log
}
