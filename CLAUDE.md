# 가계부 자동 작성 세션 규칙

> **윈도우 PC로 이전 중**: 실행 환경 안내는 `windows/SETUP.md`. 윈도우에서는 `python3` 대신 `python`, **웹브라우징·네이버 로그인은 Aside 브라우저**(`ASIDE_CDP=http://127.0.0.1:9222`로 naver.js가 Aside에 붙음; 대안 `node naver.js loginlocal`). 아래 '서버 쿠키 가져오기'는 클라우드 전용.

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
- 세션 없음/만료(`NO SESSION`/`SESSION EXPIRED`) → 아래 'PC 쿠키 가져오기'로 재연결 요청.

- **머니카드는 머니 차감액만 기록** (네이버 포인트로 낸 부분은 내 돈이 아니므로 제외). **포인트 적립·해외수수료 환급도 기록하지 않는다** (포인트는 들어오는 것도 쓰는 것도 지출/수입 계산에서 무시).
- 단, **참고용으로** 수입 옆 두 칸에 그 달 누적만 텍스트로 적는다: I37 `N포인트 적립 +4,117`, I38 `N포인트 사용 -9,511` (매일 갱신, 일별 기록 안 함). `node naver.js points 20261101 20261130` → naver_out/points.json (tradeAmount 양수=적립, 음수=사용). 처리한 PAYSEQ는 `~/.config/ledger/naver_done.json`.

## 국민카드 문자 수집 (메일 방식)
- 아이폰 단축어 자동화: 문자에 '국민카드' 포함 → '메일 보내기'(받는 사람 본인 네이버 메일, 제목 `[국민카드 문자]`, 본문=단축어 입력, 작성 시트 끔).
- `node naver.js kbmail` → `~/.config/ledger/naver_out/kbmail.json` (mailSN, time(초), body). **제목이 `[국민카드 문자]`인 메일만** 읽는다 — 다른 메일은 열지 않는다.
- **신한카드 문자도 같은 제목 `[국민카드 문자]`으로 온다** (신한카드도 내 카드 → 내 돈). 본문의 카드사명(KB국민/신한)으로 구분해 보고에 표시.
- 처리한 mailSN은 `~/.config/ledger/kbmail_done.json`. 본문이 빈 메일(수동 시험)은 무시. 취소 문자는 해당 결제를 지운다.
- (OneDrive 파일 방식은 iOS에서 OneDrive 폴더 선택 불가로 폐기)

## 엄마카드(NH) 화면 메일 (뒷면 탭 반자동)
- 사용자가 농협카드 이용내역 화면에서 폰 뒷면 두 번 탭 → 단축어(스크린샷→텍스트 추출→메일, 제목 `[농협카드 화면]`).
- `node naver.js kbmail '[농협카드 화면]' nhmail` → naver_out/nhmail.json. OCR 텍스트에서 가맹점/날짜는 위에, 금액(`12,890원>`)은 아래에 **같은 순서로** 나온다 → 순서대로 짝짓기.
- 이미 가계부에 있는 건(같은 날짜·금액)은 건너뛰고 새 건만 엄마카드 쪽에 기록. 처리한 mailSN은 `~/.config/ledger/nhmail_done.json`.
- 식자재마트·식재료는 간식(U/W) 칸, 사유에 가맹점.

## 쿠팡·쿠팡이츠 (메일, 완전 자동)
- 쿠팡 사이트는 해외 데이터센터 IP를 403으로 차단 → 접속 불가(우회 금지). 메일로 처리.
- **기본 출처 = 결제대행사 영수증**: `node naver.js kbmail '쿠팡(주)' coupang_pg` → `python3 coupang_parse.py pg 202611` (결제시각, 금액, 카드, 상품명). 쿠팡·쿠팡이츠 모든 결제에 한 통씩 옴(NHN KCP '카드종류' / KICC 이지페이 '결제기관' 두 형식).
- 카드가 NH/농협 → 엄마카드, 그 외 → 내 돈.
- 상세 상품 목록이 필요하면 주문 메일: `node naver.js kbmail '주문하신 내역을 확인해주세요' coupang` → `python3 coupang_parse.py 202611` (쿠팡이츠 주문 메일도 같은 제목, `[쿠팡이츠]` 접두).
- 분류: 쿠팡 식품→간식, 생활용품→생필품 등. 쿠팡이츠(음식 배달)는 시간대로 점심(Q)/저녁(S)/간식, 사유 `쿠팡이츠 메뉴명`.
- 농협카드 화면/사진의 '쿠팡 ○원'과 같은 날짜·금액이면 **한 번만** 기록. 처리한 영수증 mailSN은 `~/.config/ledger/coupang_pg_done.json`.
- **쿠팡이츠는 메일이 늦게 온다.** 농협카드 화면 등에서 '쿠팡 ○원'인데 쿠팡 영수증/주문 메일이 없으면 쿠팡이츠로 보고 시간대(점심/저녁/간식) 칸에 `쿠팡이츠 배달주문`으로 먼저 기록하고 `~/.config/ledger/eats_pending.json`에 {sheet, amount_cell, reason_cell, amount, dt} 저장. 이후 같은 금액(·날짜 근처)의 `[쿠팡이츠]` 주문 메일이나 영수증이 오면 사유를 `쿠팡이츠 메뉴명`으로 업데이트하고 pending에서 제거.
- 메일 검색 결과에 다른 메일이 섞일 수 있으니 본문/제목에 '쿠팡(주)' 결제 문구가 있는 것만 사용.

## 결제대행사 영수증 (가맹점 무관, 완전 자동) — 요기요 등
- 쿠팡 외 온라인 결제(요기요=주식회사 위대한상상 등)도 결제대행사 영수증 메일이 결제 직후 온다.
- 수집: `node naver.js kbmail '쿠팡(주)' coupang_pg` + `node naver.js kbmail 'NHN KCP' pg_kcp` + `node naver.js kbmail '결제하신 내역' pg_kicc` → `python3 coupang_parse.py pg YYYYMM` (세 파일을 합쳐 mailSN 중복 제거; 결제시각·금액·카드·가맹점·상품명).
- 카드 NH/농협 → 엄마카드, 그 외 → 내 돈. 요기요 등 배달은 쿠팡이츠와 같은 시간대 규칙(점심/저녁/간식), 사유 `요기요 메뉴명`. '포인트 + 일시불'이면 결제금액(카드분)만 기록.
- 처리한 mailSN은 `~/.config/ledger/coupang_pg_done.json`(모든 영수증 공용).

## 네이버쇼핑/네이버페이 결제 상품명
- `node naver.js payhist 2` → naver_out/payhist.json (id, date(ms), merchant, product, price, rest, method CREDIT_CARD 등, status).
- CREDIT_CARD 결제는 농협카드 화면의 '네이버파이낸셜 ○원' 또는 국민카드 문자 '네이버페이 ○원'과 날짜·금액으로 짝지어 카드 구분(짝 없으면 엄마카드로 보고 보고서에 표시). 머니 결제는 paymoneyList에서 이미 처리.
- **status가 `취소완료`·`결제취소`인 건은 무조건 제외.** `부분취소`는 실제 금액을 확인하고 애매하면 사용자에게 묻는다. (다른 출처도 마찬가지로 취소/승인취소 건을 반드시 걸러낸다)
- 이미 기록된 건이면 사유만 상품명으로 보강. 처리한 id는 `~/.config/ledger/payhist_done.json`.

## 다음 달 시트 자동 생성
- 매달 25일 이후 새벽 실행에서 `python3 newmonth_remote.py` (다음 달 시트 없으면: 백업→newmonth.py로 복사→If-Match 업로드). 회색 고정지출 유지, '○월관리비' 갱신+금액 '?', 할부 (n/m) 회차+1(끝난 건 제외), 나머지 비움, I37/I38 초기화.
- 백업은 OneDrive `가계부/백업/`.

## 매일 새벽 자동 실행 (한국시간 05:15)
0. `~/.config/ledger/pending_writes.json`(엑셀 장애 등으로 못 쓴 기록, [{sheet, cells, expect, source}])이 있으면 먼저 처리: `rget`으로 대상 칸이 비어 있거나 `expect` 값('?' 등)일 때만 `rset`, 다르면 쓰지 말고 보고. 성공한 항목은 파일에서 지운다. 엑셀이 계속 안 되면 그대로 두고 다음 실행에 다시 시도.
1. `node naver.js history` + `node naver.js points <월초> <월말>` (I37/I38 월 누적 갱신) → naver_done에 없는 `use` 건만 (nfc/pmuse, 취소 쌍 제외) 처리.
2. `node naver.js kbmail`의 새 메일 처리 + 결제대행사 영수증(`coupang_pg`·`pg_kcp`·`pg_kicc`) 처리 + `node naver.js kbmail '[농협카드 화면]' nhmail`의 새 메일 처리.
2-1. `node naver.js payhist 2`로 네이버쇼핑 상품명 처리. 25일 이후면 `python3 newmonth_remote.py`.
3. 분류가 확실하면 규칙대로 `rget`으로 빈칸 확인 후 `rset`. 애매하면 기록하지 말고 사용자에게 질문.
4. 무엇을 기록했는지 짧게 보고(텔레그램 `tg.py`로도 전송). 로그인 만료 시 재로그인 요청.
5. (자동, Claude 아님) `run_daily.ps1`이 끝에 `..\ledger-web\tools\sync.ps1`을 돌려 엑셀 26-08 이후 시트를 `ledger-web/data/*.json`으로 바꾸고, 바뀌었으면 GitHub(DangChame/ledger-web, 공개)에 push → https://dangchame.github.io/ledger-web/

## 네이버 로그인 = PC 쿠키 가져오기 (기본 방식)
- **서버에서 아이디·비밀번호 로그인 금지**: 해외 데이터센터 IP라 보안문자 반복 → 2026-11-12 아이디 보호(잠금)까지 걸렸다. `loginpw`는 쓰지 않는다. 일회용 번호 로그인은 '상태 유지'가 없어 1.5일이면 만료.
- 세션 만료 시: 사용자에게 PC 크롬에서 '로그인 상태 유지' 켜고 'IP 보안' 끈 채 로그인 → F12 → 애플리케이션 → 쿠키 → https://www.naver.com → NID_AUT, NID_SES 값을 OneDrive `가계부/naver_cookie.txt`(1줄 NID_AUT, 2줄 NID_SES)에 저장해 달라고 요청. PC 크롬에서는 로그아웃하지 말 것.
- 받으면 `~/.config/ledger/naver_state.json`에 두 쿠키(.naver.com, secure, httpOnly)로 저장 → `node naver.js history`로 확인 → OneDrive 파일 삭제. 매 실행 후 storageState 저장으로 쿠키가 갱신된다.
- 보안확인 사진 등 사용자에게 보여줄 이미지는 Claude 대화창으로(텔레그램 금지).

## 텔레그램 보고
- 봇 @autoekdcoal_bot. 설정 `~/.config/ledger/telegram.json` {token, chat_id} (저장소 밖, 권한 600). 토큰은 절대 커밋하지 않는다.
- 새벽 실행 결과는 `python3 tg.py "메시지"`로도 보낸다. chat_id가 없으면 tg.py가 getUpdates로 찾는다(사용자가 봇에게 먼저 말을 걸어야 함).

## 기록 규칙
- 시트명 `YY-MM` (예: 26-11). 날짜 행 = 일 + 2 (1일 → 3행).
- 사용자가 말하는 지출은 **기본적으로 엄마카드(오른쪽, Q~AL열)**. 사용자가 "내 돈"이라고 언급할 때만 **내 돈(왼쪽, B~O열)**.
- 엄마카드: Q 점심, S 저녁, U/W 간식, Y 생필품, AA 차량, AC 여가, AE/AG 커피·티, AI 교육, AK 이외 (각 오른쪽 열이 사유)
- 내 돈: B 식비, **D/F(헤더 비어있음) = 데이트**, H 생필품·이동, J 여가·식비정산, L 먼슬리페이, N 이외
- **L열(먼슬리페이)과 회색 칸 = 고정지출**. 금액이 '?'인 회색 칸은 실제 금액이 확인되면 채운다(변동사항).
- 한 날짜에 같은 분류 칸이 부족하면 **그 날짜 이전 중 가장 가까운 날짜의 빈 칸**에 넣고 사유에 `(11.5)`처럼 실제 날짜를 표기 (가장 이른 날짜 아님!).
- 가맹점명 `KICC(서울시현장)` = KTX 열차 내 자판기 → 사유 `KTX자판기`.
- 카드 구분: **NH농협카드(올바른POINT UP 3278, 흰 배경 화면) = 엄마카드**, **국민카드(검은 배경 '타임라인' 화면) = 내 돈**, **네이버페이 머니카드 = 내 돈**, **신한카드 = 내 돈**. 사용자가 보낸 카드 내역 사진의 금액을 기준으로 기록한다.
- **같은 가맹점 결제만 합친다** (예: 카카오T 택시 2건 → `카카오택시`). 가맹점이 다르면(KICC 등) 따로 적는다. 승인취소 건은 제외.
- 26-11 초반 기록은 다른 AI('피클')가 넣은 것이라 부정확할 수 있다. 카드 내역과 다르면 카드 내역이 우선.
- 여자친구 선물(꽃 등)은 내 돈 **데이트(D/F)** 칸. 꾸까(kukka) = 꽃 구독/구매.
- 차량(AA)의 '쏘카' 결제는 모두의주차장 주차권 구매다 → 사유는 **`주차권`**으로 적는다 (26-11부터 적용).
- P열(일지출), 35~38행(합계)은 수식이므로 건드리지 않는다.
