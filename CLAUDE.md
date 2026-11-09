# 가계부 자동 작성 세션 규칙

가계부: OneDrive xlsx (공유 링크 https://1drv.ms/x/c/c3ff9e4fac7f997f/IQB_mX-sT57_IIDDcQAAAAAAAS_yTM5yFv3Y1XCLE-joULs?e=VhSK0c)
- 다운로드: `python3 ledger.py download <path>` (호스트 my.microsoftpersonalcontent.com)
- 셀 수정: `python3 ledger.py set <path> 26-11 U14=5000 V14=사유` — 기존 셀 서식 유지, XML 직접 수정 (openpyxl 저장은 '현 재정상태' 시트의 잉크 그림을 날리므로 쓰지 말 것)
- xlsx 파일은 저장소에 커밋하지 않는다 (개인 금융정보).

## OneDrive 자동 반영 (기본 방식)
- 원본에 직접 기록: `python3 ledger.py rset 26-11 U14=5000 V14=사유` (Graph Excel API, 셀 단위 PATCH → 서식 유지, 수식 자동 재계산)
- 확인: `python3 ledger.py rget 26-11 Q14:AL14`
- 쓰기 전에 `rget`으로 대상 칸이 비어 있는지 먼저 확인한다(다른 기기에서 바뀌었을 수 있음).
- 토큰: `~/.config/ledger/token.json` (저장소 밖). 없거나 만료되면 `python3 ledger.py login`을 백그라운드로 실행하고, 출력된 코드를 사용자에게 알려 로그인하게 한다.
- 앱 ID: `ledger_config.json`의 `client_id` (비밀값 아님).

## 기록 규칙
- 시트명 `YY-MM` (예: 26-11). 날짜 행 = 일 + 2 (1일 → 3행).
- 사용자가 말하는 지출은 **기본적으로 엄마카드(오른쪽, Q~AL열)**. 사용자가 "내 돈"이라고 언급할 때만 **내 돈(왼쪽, B~O열)**.
- 엄마카드: Q 점심, S 저녁, U/W 간식, Y 생필품, AA 차량, AC 여가, AE/AG 커피·티, AI 교육, AK 이외 (각 오른쪽 열이 사유)
- 내 돈: B 식비, **D/F(헤더 비어있음) = 데이트**, H 생필품·이동, J 여가·식비정산, L 먼슬리페이, N 이외
- **L열(먼슬리페이)과 회색 칸 = 고정지출**. 금액이 '?'인 회색 칸은 실제 금액이 확인되면 채운다(변동사항).
- 한 날짜에 같은 분류 칸이 부족하면 **이미 지난 날짜 중 빈 칸**에 넣고 사유에 `(11.5)`처럼 실제 날짜를 표기.
- P열(일지출), 35~38행(합계)은 수식이므로 건드리지 않는다.
