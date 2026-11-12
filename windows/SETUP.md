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
- **웹브라우징·네이버 로그인은 Aside 브라우저**로 한다. 사용자가 Aside에서 네이버에 로그인해 두고, Aside를 `--remote-debugging-port=9222`로 띄운 뒤 환경변수 `ASIDE_CDP=http://127.0.0.1:9222`를 설정하면 `naver.js`가 Aside에 붙어(Playwright connectOverCDP) 그 로그인 세션을 그대로 쓴다. Aside 창은 닫지 않고 스크립트가 연 탭만 닫는다. 비밀번호를 스크립트에 넣지 않는다.
- Aside가 원격 디버깅을 지원하지 않으면 대안: `node naver.js loginlocal`(Playwright 창에서 직접 로그인 → `naver_state.json`).
- run_daily는 Aside가 켜져 있어야 한다(시작프로그램에 디버깅 포트 옵션으로 등록: `HKCU\...\Run` 값 `AsideDebug` = `"C:\Program Files\Aside\Application\Aside.exe" --remote-debugging-port=9222`).
- 작업 스케줄러는 `claude` CLI를 쓰므로 PC에서 `claude` → `/login` 한 번 해 둬야 한다.
- `.ps1` 파일은 UTF-8 **BOM**으로 저장한다(Windows PowerShell 5.1이 BOM 없으면 cp949로 읽어 한글 작업 이름이 깨짐).
- 쿠팡 사이트 직접 접속, 네이버 메일 IMAP(앱 비밀번호)도 가능 — 지금은 메일 웹 방식(naver.js kbmail)을 그대로 쓴다.

## 문제 생기면
- 네이버 세션 만료 → Aside에서 네이버 다시 로그인 (대안 모드면 `node naver.js loginlocal`)
- `ASIDE_CDP` 연결 실패 → Aside가 `--remote-debugging-port=9222`로 켜져 있는지 확인
- OneDrive 만료 → `python ledger.py login-url` → 로그인 → `python ledger.py login-code "<주소>"`
- 작업이 안 돌았는지 → `daily.log` 확인, `Get-ScheduledTaskInfo -TaskName "가계부 새벽 자동 수집"`
