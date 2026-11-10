# 가계부 자동 작성 세션 규칙

가계부: OneDrive xlsx (공유 링크 https://1drv.ms/x/c/c3ff9e4fac7f997f/IQB_mX-sT57_IIDDcQAAAAAAAS_yTM5yFv3Y1XCLE-joULs?e=VhSK0c)
- 다운로드: `python3 ledger.py download <path>` (호스트 my.microsoftpersonalcontent.com)
- 셀 수정: `python3 ledger.py set <path> 26-11 U14=5000 V14=사유` — 기존 셀 서식 유지, XML 직접 수정 (openpyxl 저장은 '현 재정상태' 시트의 잉크 그림을 날리므로 쓰지 말 것)
- xlsx 파일은 저장소에 커밋하지 않는다 (개인 금융정보).

## OneDrive 자동 반영 (기본 방식)
- 원본에 직접 기록: `python3 ledger.py rset 26-11 U14=5000 V14=사유` (Graph Excel API, 셀 단위 PATCH → 서식 유지, 수식 자동 재계산)
- 확인: `python3 ledger.py rget 26-11 Q14:AL14`
- 쓰기 전에 `rget`으로 대상 칸이 비어 있는지 먼저 확인한다(다른 기기에서 바뀌었을 수 있음).
- 토큰: `~/.config/ledger/token.json` (저장소 밖). 없거나 갱신 실패 시 재로그인:
  1. `python3 ledger.py login-url` 로 주소를 사용자에게 준다.
  2. 사용자가 로그인 후 빈 화면 주소창 URL(`...nativeclient?code=...`)을 보내면 `python3 ledger.py login-code '<URL>'`.
- 앱 ID: 기본은 오픈소스 'OneDrive Client for Linux'의 공개 ID (개인 계정은 앱 등록 불가, 사용자가 이 방식에 동의함). `LEDGER_CLIENT_ID` 또는 `ledger_config.json`으로 바꿀 수 있다.

## 네이버페이(머니카드) 자동 수집
- `node naver.js history` → `~/.config/ledger/naver_out/api.json` (`paymoneyList`: PAYDTTM, PAYAMT, FILTER use/charge, TYPE nfc=머니카드·pmuse=페이결제·pmcancel=취소, TITLE=가맹점)
- `charge`(저축 계좌에서 충전)는 지출 아님. 가승인/취소 쌍은 제외.
- 세션 없음/만료(`NO SESSION`/`SESSION EXPIRED`) → 백그라운드로 `node naver.js login` 실행 후 사용자에게 네이버 앱 '일회용 로그인 번호'를 받아 `~/.config/ledger/naver_code`에 기록.

- **머니카드는 머니 차감액만 기록** (네이버 포인트로 낸 부분은 내 돈이 아니므로 제외). 처리한 PAYSEQ는 `~/.config/ledger/naver_done.json`.

## 국민카드 문자 수집
- 아이폰 단축어 자동화가 국민카드 문자를 OneDrive `가계부/sms.txt`에 한 줄씩 추가 → `python3 ledger.py rfile '가계부/sms.txt'`.
- 처리한 줄 수는 `~/.config/ledger/sms_done` (파일 줄 수 기준). 취소 문자는 해당 결제를 지운다.

## 매일 아침 자동 실행 (한국시간 오전 8시 전후)
1. `node naver.js history` → naver_done에 없는 `use` 건만 (nfc/pmuse, 취소 쌍 제외) 처리.
2. `rfile 가계부/sms.txt`의 새 줄 처리.
3. 분류가 확실하면 규칙대로 `rget`으로 빈칸 확인 후 `rset`. 애매하면 기록하지 말고 사용자에게 질문.
4. 무엇을 기록했는지 짧게 보고. 로그인 만료 시 재로그인 요청.

## 기록 규칙
- 시트명 `YY-MM` (예: 26-11). 날짜 행 = 일 + 2 (1일 → 3행).
- 사용자가 말하는 지출은 **기본적으로 엄마카드(오른쪽, Q~AL열)**. 사용자가 "내 돈"이라고 언급할 때만 **내 돈(왼쪽, B~O열)**.
- 엄마카드: Q 점심, S 저녁, U/W 간식, Y 생필품, AA 차량, AC 여가, AE/AG 커피·티, AI 교육, AK 이외 (각 오른쪽 열이 사유)
- 내 돈: B 식비, **D/F(헤더 비어있음) = 데이트**, H 생필품·이동, J 여가·식비정산, L 먼슬리페이, N 이외
- **L열(먼슬리페이)과 회색 칸 = 고정지출**. 금액이 '?'인 회색 칸은 실제 금액이 확인되면 채운다(변동사항).
- 한 날짜에 같은 분류 칸이 부족하면 **그 날짜 이전 중 가장 가까운 날짜의 빈 칸**에 넣고 사유에 `(11.5)`처럼 실제 날짜를 표기 (가장 이른 날짜 아님!).
- 가맹점명 `KICC(서울시현장)` = KTX 열차 내 자판기 → 사유 `KTX자판기`.
- 카드 구분: **NH농협카드(올바른POINT UP 3278, 흰 배경 화면) = 엄마카드**, **국민카드(검은 배경 '타임라인' 화면) = 내 돈**, **네이버페이 머니카드 = 내 돈**. 사용자가 보낸 카드 내역 사진의 금액을 기준으로 기록한다.
- **같은 가맹점 결제만 합친다** (예: 카카오T 택시 2건 → `카카오택시`). 가맹점이 다르면(KICC 등) 따로 적는다. 승인취소 건은 제외.
- 26-11 초반 기록은 다른 AI('피클')가 넣은 것이라 부정확할 수 있다. 카드 내역과 다르면 카드 내역이 우선.
- 차량(AA)의 '쏘카' 결제는 모두의주차장 주차권 구매다 → 사유는 **`주차권`**으로 적는다 (26-11부터 적용).
- P열(일지출), 35~38행(합계)은 수식이므로 건드리지 않는다.
