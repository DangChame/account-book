# 작업 스케줄러에 '매일 05:15 가계부 수집' 등록 (절전 중이면 깨워서 실행)
#   powershell -ExecutionPolicy Bypass -File windows\register_task.ps1
$repo = Split-Path $PSScriptRoot -Parent
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$repo\windows\run_daily.ps1`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -Daily -At 05:15
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName "가계부 새벽 자동 수집" -Action $action -Trigger $trigger -Settings $settings `
  -Description "account-book 저장소: 네이버페이/카드문자/영수증 → OneDrive 가계부 기록, 텔레그램 보고" -Force
Write-Host "등록 완료. 지금 시험 실행: Start-ScheduledTask -TaskName '가계부 새벽 자동 수집'"
