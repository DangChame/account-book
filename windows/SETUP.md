# 윈도우 PC에서 가계부 자동화 돌리기

클라우드(미국 데이터센터)에서는 네이버 로그인 보안문자·계정 잠금, 쿠팡 403, 메일 포트 차단 문제가 있었다.
한국 집 PC에서 돌리면 이 문제들이 없다. PC는 항상 켜 둔다(절전은 괜찮음 — 작업이 깨워서 실행).

## 파일
| 파일 | 역할 |
|---|---|
| `windows/setup.ps1` | Node, Python, Playwright(크로미움), openpyxl 설치 |
| `windows/run_daily.ps1` | 매일 실행: `claude -p`로 `routine_prompt.txt` 절차 수행, 로그 `%USERPROFILE%\.config\ledger\daily.log` |
| `windows/register_task.ps1` | 작업 스케줄러 '가계부 새벽 자동 수집' 등록 (매일 05:15, WakeToRun) |
| `windows/routine_prompt.txt` | 새벽 루틴 지시문 |
| `windows/HANDOFF_PROMPT.md` | 새 세션에 붙여넣을 메시지 |

## 비밀 정보 위치 (전부 `%USERPROFILE%\.config\ledger\`, 저장소에 커밋 금지)
- `token.json` — OneDrive(Microsoft Graph) 토큰
- `naver_state.json` — 네이버 로그인 세션 (`node naver.js loginlocal`로 만듦)
- `telegram.json` — 텔레그램 봇 토큰/chat_id
- `*_done.json`, `eats_pending.json` — 처리 기록 (클라우드에서 옮겨 옴)

## 윈도우에서 달라지는 점
- `python3` → `python`
- 네이버 로그인: 서버용 쿠키 복사 대신 **`node naver.js loginlocal`** (브라우저 창에서 직접 로그인, '로그인 상태 유지' 체크). 비밀번호를 스크립트에 넣지 않는다.
- 쿠팡 사이트 직접 접속, 네이버 메일 IMAP(앱 비밀번호)도 가능 — 지금은 메일 웹 방식(naver.js kbmail)을 그대로 쓴다.

## 문제 생기면
- 네이버 세션 만료 → `node naver.js loginlocal`
- OneDrive 만료 → `python ledger.py login-url` → 로그인 → `python ledger.py login-code "<주소>"`
- 작업이 안 돌았는지 → `daily.log` 확인, `Get-ScheduledTaskInfo -TaskName "가계부 새벽 자동 수집"`
