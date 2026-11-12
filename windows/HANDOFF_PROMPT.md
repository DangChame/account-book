# 윈도우 Claude Code 새 세션에 붙여넣을 메시지

아래 ``` 안의 내용을 통째로 복사해서, 윈도우에서 새로 연 Claude Code 세션에 붙여넣으면 된다.
(Claude Code는 빈 폴더, 예: `C:\Users\<이름>\work` 에서 실행)

```
너는 지금부터 내 가계부 자동 기록 담당이다. 클라우드 세션에서 하던 일을 이 윈도우 PC로 옮긴다. 아래 순서대로 진행하고, 내가 직접 해야 하는 단계(로그인 등)만 나에게 짧게 요청해라.

1. 저장소 받기: git clone https://github.com/DangChame/account-book 후 그 폴더에서 git checkout claude/dazzling-mendel-irk4x8. (git이 없으면 winget install -e --id Git.Git 로 설치. 비공개 저장소 로그인 창이 뜨면 나에게 로그인하라고 말해라.) 이후 모든 작업은 이 폴더에서.
2. CLAUDE.md와 windows\SETUP.md를 끝까지 읽고 그 규칙을 따른다. 윈도우에서는 python3 대신 python 을 쓴다.
3. powershell -ExecutionPolicy Bypass -File windows\setup.ps1 실행 (Node, Python, Playwright, openpyxl 설치).
4. OneDrive 연결: python ledger.py login-url 로 나온 주소를 나에게 주고, 내가 로그인 후 보내는 nativeclient?code=... 주소로 python ledger.py login-code "<주소>" 실행. python ledger.py rget 26-11 A3:A3 로 확인.
5. 처리 기록 옮기기: OneDrive 가계부/migrate/ledger_state.json 을 python 으로 읽어(ledger.remote_text) 각 키 이름 그대로 %USERPROFILE%\.config\ledger\ 에 json 파일로 저장. 끝나면 OneDrive의 migrate 폴더는 지운다.
6. 네이버 로그인: node naver.js loginlocal 실행 → 뜨는 브라우저 창에서 내가 직접 로그인('로그인 상태 유지' 체크, 'IP 보안' 끔). 그다음 node naver.js history 로 확인.
7. 텔레그램: 내가 봇 토큰을 알려줄 테니 %USERPROFILE%\.config\ledger\telegram.json 에 {"token": "...", "chat_id": null} 로 저장하고 python tg.py "윈도우 PC 연결 완료" 로 시험 (chat_id는 tg.py가 자동으로 찾는다). 토큰은 절대 커밋하지 마라.
8. 시험 실행: windows\routine_prompt.txt 의 절차를 지금 한 번 직접 수행하고 결과를 보여줘.
9. 작업 스케줄러 등록: powershell -ExecutionPolicy Bypass -File windows\register_task.ps1 (매일 05:15, 절전 중이면 깨워서 실행). 등록 후 Start-ScheduledTask -TaskName "가계부 새벽 자동 수집" 으로 한 번 돌려 %USERPROFILE%\.config\ledger\daily.log 확인.
10. 다 되면 나에게 "클라우드 세션의 자동 실행을 끄라고 말하세요" 라고 알려줘 (중복 기록 방지).
```
