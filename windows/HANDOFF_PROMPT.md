# 윈도우 Claude Code 새 세션에 붙여넣을 메시지

아래 ``` 안의 내용을 통째로 복사해서, 윈도우에서 새로 연 Claude Code 세션에 붙여넣으면 된다.

```
클라우드 세션에서 돌리던 내 가계부 자동 기록을 이 PC로 옮긴다. 아래를 순서대로 끝까지 진행하고, 내가 직접 해야 하는 것(로그인, 토큰 입력)만 짧게 요청해라.

1. git clone https://github.com/DangChame/account-book → 그 폴더에서 git checkout claude/dazzling-mendel-irk4x8. 이후 모든 작업은 이 폴더에서. CLAUDE.md와 windows\SETUP.md를 끝까지 읽고 그 규칙을 따른다(윈도우는 python3 대신 python).
2. powershell -ExecutionPolicy Bypass -File windows\setup.ps1 로 설치.
3. OneDrive 연결: python ledger.py login-url 주소를 나에게 주고, 내가 보내는 nativeclient?code=... 주소로 python ledger.py login-code "<주소>". python ledger.py rget 26-11 A3:A3 로 확인.
4. OneDrive 가계부/migrate/ledger_state.json 을 읽어 각 키 이름 그대로 %USERPROFILE%\.config\ledger\ 에 json 파일로 저장하고, migrate 폴더는 OneDrive에서 지운다.
5. 네이버·웹브라우징은 Aside로 한다(네이버는 내가 Aside에서 로그인해 둠). naver.js는 환경변수 ASIDE_CDP 가 있으면 그 주소의 브라우저에 connectOverCDP로 붙는다. Aside를 원격 디버깅 포트로 열고 ASIDE_CDP를 사용자 환경변수로 설정해 작업 스케줄러 실행에도 적용되게 한 뒤, node naver.js history 로 확인. 네이버 비밀번호는 절대 스크립트에 넣지 마라.
6. 텔레그램: 내가 주는 봇 토큰을 %USERPROFILE%\.config\ledger\telegram.json 에 {"token":"...","chat_id":null} 로 저장하고 python tg.py "윈도우 PC 연결 완료" 로 시험. 토큰은 커밋 금지.
7. windows\routine_prompt.txt 절차를 지금 한 번 수행해 결과를 보여줘.
8. powershell -ExecutionPolicy Bypass -File windows\register_task.ps1 로 매일 05:15 작업 등록 → Start-ScheduledTask -TaskName "가계부 새벽 자동 수집" 로 시험 → %USERPROFILE%\.config\ledger\daily.log 확인.
9. 끝나면 "클라우드 세션에서 '클라우드 중지'라고 말하세요"라고 알려줘.
```
