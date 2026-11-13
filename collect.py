#!/usr/bin/env python3
"""매일 새벽 수집 1단계 — Claude 없이 정해진 일을 모두 처리하고, 판단이 필요한 새 건만 남긴다.

  python collect.py            # 수집 → 자동 처리 → 남은 건을 ~/.config/ledger/collect_todo.json 에
  python collect.py done KEY…  # Claude가 처리한 건을 처리 기록에 넣기 (KEY 예: money:2052… kb:32198 nh:32235 pg:32221 pay:O2026…)
  python collect.py ask KEY…   # 사용자에게 물어본 건 → 답(done) 전까지 매일 Claude를 다시 부르지 않음
  python collect.py --no-fetch # 시험: 이미 받은 naver_out 파일로 판단만 출력 (저장·텔레그램·포인트 없음)

종료 코드: 0 = Claude 필요 없음(텔레그램 보고까지 끝), 10 = Claude가 todo 처리해야 함,
          3 = 네이버 세션 만료, 4 = Aside 연결 실패 (둘 다 텔레그램으로 알림).

자동으로 하는 것: 충전·가승인/취소 쌍·빈 메일·취소된 결제 건너뛰기, 가계부에 이미 같은 날짜·금액이 있는 건 건너뛰기,
I37/I38 포인트 누적, 25일 이후 다음 달 파일 만들기. 분류(어느 칸에 무슨 사유로)는 하지 않는다 → Claude.
"""
import datetime, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_TOOLS = os.path.normpath(os.path.join(HERE, "..", "ledger-web", "tools"))
sys.path.insert(0, WEB_TOOLS)
import book  # noqa: E402
import coupang_parse  # noqa: E402

CFG = os.path.expanduser("~/.config/ledger")
OUT = os.path.join(CFG, "naver_out")
TODO = os.path.join(CFG, "collect_todo.json")
KST = datetime.timezone(datetime.timedelta(hours=9))
DONE = {"money": "naver_done.json", "kb": "kbmail_done.json", "nh": "nhmail_done.json",
        "pg": "coupang_pg_done.json", "pay": "payhist_done.json"}
NOW = datetime.datetime.now(KST)


# ---------- 공통 ----------
def jload(name, default):
    p = os.path.join(CFG, name) if not os.path.isabs(name) else name
    try:
        return json.load(open(p, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def jsave(name, data):
    with open(os.path.join(CFG, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_done():
    return {k: jload(f, []) for k, f in DONE.items()}


def save_done(done):
    for k, f in DONE.items():
        jsave(f, done[k])


def mark(done, kind, key):
    # 처리 기록 파일마다 원래 쓰던 형식(문자열/숫자)을 그대로 따른다
    key = int(key) if kind in ("kb", "nh", "pg") else str(key)
    if key not in done[kind]:
        done[kind].append(key)


def tg(msg):
    subprocess.run([sys.executable, os.path.join(HERE, "tg.py"), msg], cwd=HERE)


_months = {}


def month_data(date):
    sheet = date[2:7]
    if sheet not in _months:
        try:
            _months[sheet] = book.load(sheet)
        except SystemExit:
            _months[sheet] = None
    return _months[sheet]


def recorded(date, amount, side=None):
    """가계부에 같은 날짜(또는 사유의 실제 날짜)·같은 금액이 이미 있으면 그 칸 주소."""
    d = month_data(date)
    for e in (d or {}).get("entries", []):
        if e.get("amount") == amount and (e.get("date") == date or e.get("realDate") == date) \
                and (side is None or e["side"] == side):
            return f"{d['sheet']} {e['col']}{e['row']}"
    return None


# ---------- 수집 ----------
def fetch(cmds):
    for args in cmds:
        r = subprocess.run(["node", "naver.js", *args], cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        if "SESSION EXPIRED" in out or "NO SESSION" in out:
            tg("가계부 새벽 수집: Aside에서 네이버 재로그인 필요")
            raise SystemExit(3)
        if r.returncode != 0:
            if re.search(r"connectOverCDP|ECONNREFUSED|9222", out):
                tg("가계부 새벽 수집: Aside를 디버깅 포트로 켜 주세요")
                raise SystemExit(4)
            raise SystemExit(f"naver.js {' '.join(args)} 실패: {out.strip()[-300:]}")


# ---------- 출처별 새 건 ----------
def money(done, todo, auto):
    try:
        api = jload(os.path.join(OUT, "api.json"), [])
        rows = next(x["body"]["response"]["list"] for x in api if "paymoneyList" in x["url"])
    except StopIteration:
        raise SystemExit("네이버페이 내역(paymoneyList)을 못 읽음")
    new = [r for r in rows if r["PAYSEQ"] not in done["money"]]
    cancels = [r for r in new if r["TYPE"] == "pmcancel"]
    for r in new:
        if r["FILTER"] != "use":  # 충전 등
            mark(done, "money", r["PAYSEQ"])
    for c in cancels:  # 가승인/취소 쌍
        pair = next((r for r in new if r["TYPE"] != "pmcancel" and r["TITLE"] == c["TITLE"]
                     and r["PAYAMT"] == -c["PAYAMT"] and r["PAYSEQ"] not in done["money"]), None)
        mark(done, "money", c["PAYSEQ"])
        if pair:
            mark(done, "money", pair["PAYSEQ"])
            auto.append(f"취소 쌍 건너뜀: {c['TITLE']} {c['PAYAMT']:,}")
        else:
            todo.append({"key": f"money:{c['PAYSEQ']}", "src": "네이버페이 머니 취소", "side": "me",
                         "dt": dt14(c["PAYDTTM"]), "amount": c["PAYAMT"], "merchant": c["TITLE"],
                         "note": "짝 결제가 이번 목록에 없음 → 이미 기록된 결제라면 지우기"})
    for r in new:
        if r["PAYSEQ"] in done["money"] or r["FILTER"] != "use" or r["PAYAMT"] >= 0:
            continue
        dt, amt = dt14(r["PAYDTTM"]), -r["PAYAMT"]
        hit = recorded(dt[:10], amt, "me")
        if hit:
            mark(done, "money", r["PAYSEQ"])
            auto.append(f"이미 있음: {r['TITLE']} {amt:,} ({hit})")
        else:
            todo.append({"key": f"money:{r['PAYSEQ']}", "src": "네이버페이 머니카드" if r["TYPE"] == "nfc" else "네이버페이 결제",
                         "side": "me", "dt": dt, "amount": amt, "merchant": r["TITLE"]})


def dt14(s):
    return f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[8:10]}:{s[10:12]}"


def ts(sec):
    return datetime.datetime.fromtimestamp(sec, KST).strftime("%Y-%m-%d %H:%M")


def kbmail(done, todo, auto):
    for m in jload(os.path.join(OUT, "kbmail.json"), []):
        if m["mailSN"] in done["kb"]:
            continue
        body = m["body"].strip()
        a = re.search(r"([\d,]{3,})\s*원", body)
        if not body:
            mark(done, "kb", m["mailSN"])
            continue
        dt = ts(m["time"])
        if a and "취소" not in body:
            hit = recorded(dt[:10], int(a.group(1).replace(",", "")), "me")
            if hit:
                mark(done, "kb", m["mailSN"])
                auto.append(f"이미 있음: 카드 문자 {a.group(1)}원 ({hit})")
                continue
        todo.append({"key": f"kb:{m['mailSN']}", "src": "카드 문자(국민·신한, 내 돈)", "side": "me",
                     "dt": dt, "body": body[:300]})


DATE_LINE = re.compile(r"^(\d{4})\.(\d\d)\.(\d\d) (\d\d):(\d\d)$")
AMT_LINE = re.compile(r"^([\d,]+)\s*원")


def nh_items(body):
    lines = [x.strip() for x in body.replace("&gt;", ">").replace("&lt;", "<").split("\n") if x.strip()]
    heads = [(lines[i - 1], "{}-{}-{} {}:{}".format(*DATE_LINE.match(x).groups()))
             for i, x in enumerate(lines) if DATE_LINE.match(x) and i > 0]
    amts = [int(AMT_LINE.match(x).group(1).replace(",", "")) for x in lines if AMT_LINE.match(x)]
    if not heads or len(heads) != len(amts):
        return None
    return [{"merchant": h[0], "dt": h[1], "amount": a} for h, a in zip(heads, amts)]


def nhmail(done, todo, auto):
    for m in jload(os.path.join(OUT, "nhmail.json"), []):
        if m["mailSN"] in done["nh"]:
            continue
        items = nh_items(m["body"])
        if items is None:
            todo.append({"key": f"nh:{m['mailSN']}", "src": "농협카드 화면(엄마카드) — 짝짓기 실패, 원문 확인",
                         "side": "mom", "dt": ts(m["time"]), "body": m["body"][:800]})
            continue
        left = [i for i in items if not recorded(i["dt"][:10], i["amount"], "mom")]
        if not left:
            mark(done, "nh", m["mailSN"])
            auto.append(f"농협카드 화면 {len(items)}건 모두 이미 있음")
            continue
        todo.append({"key": f"nh:{m['mailSN']}", "src": "농협카드 화면(엄마카드)", "side": "mom",
                     "items": left, "note": f"화면의 나머지 {len(items) - len(left)}건은 이미 기록됨"})


def pg(done, todo, auto):
    since = (NOW - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
    rs = [r for r in coupang_parse.receipts(None, include_cancelled=True) if r["dt"] >= since]
    by_key = {}
    for r in rs:
        by_key.setdefault(r["appr"] or (r["dt"], r["amount"]), []).append(r)
    for r in rs:
        if r["mailSN"] in done["pg"]:
            continue
        side = "mom" if r["mom"] else "me"
        base = {"key": f"pg:{r['mailSN']}", "side": side, "dt": r["dt"], "amount": r["amount"],
                "card": r["card"], "shop": r["shop"], "item": r["item"][:80]}
        if r["cancel"]:
            orig = [o for o in by_key.get(r["appr"] or (r["dt"], r["amount"]), []) if not o["cancel"]]
            if r["partial"]:
                todo.append({**base, "src": "결제대행사 부분취소 영수증", "note": "실제 금액 확인 필요 — 애매하면 질문"})
            elif any(o["mailSN"] in done["pg"] for o in orig):
                hit = recorded(r["dt"][:10], r["amount"], side)
                todo.append({**base, "src": "결제대행사 취소 영수증",
                             "note": f"이미 기록된 결제가 전액 취소됨 → 그 칸 지우기 ({hit or '칸 못 찾음'})"})
            else:
                mark(done, "pg", r["mailSN"])
            continue
        if r["cancelled"]:
            mark(done, "pg", r["mailSN"])
            auto.append(f"취소된 결제 건너뜀: {r['shop'] or r['item'][:20]} {r['amount']:,}")
            continue
        if r["partial"]:
            todo.append({**base, "src": "결제대행사 영수증(부분취소됨)",
                         "note": f"부분취소 {r['cancel_amount']:,}원 — 실제 금액 확인, 애매하면 질문"})
            continue
        hit = recorded(r["dt"][:10], r["amount"], side)
        if hit:
            mark(done, "pg", r["mailSN"])
            auto.append(f"이미 있음: {r['shop'] or '영수증'} {r['amount']:,} ({hit})")
        else:
            todo.append({**base, "src": "결제대행사 영수증(쿠팡·쿠팡이츠·요기요 등)"})


def payhist(done, todo, auto):
    for r in jload(os.path.join(OUT, "payhist.json"), []):
        if r["id"] in done["pay"]:
            continue
        st = r.get("status") or ""
        dt = datetime.datetime.fromtimestamp(r["date"] / 1000, KST).strftime("%Y-%m-%d %H:%M")
        if st in ("취소완료", "결제취소"):
            mark(done, "pay", r["id"])
            auto.append(f"취소 건너뜀: 네이버쇼핑 {r['merchant']} {r['price']:,}")
            continue
        base = {"key": f"pay:{r['id']}", "dt": dt, "amount": r.get("rest") or r["price"],
                "merchant": r["merchant"], "product": (r.get("product") or "")[:80], "status": st}
        if "부분취소" in st:
            todo.append({**base, "src": "네이버쇼핑 부분취소", "note": "실제 금액 확인, 애매하면 질문"})
            continue
        if r.get("method") != "CREDIT_CARD":
            # 머니 결제는 네이버페이 머니 내역에서 처리 → 같은 날 같은 가맹점 새 건이 있으면 상품명만 붙여 준다
            for t in todo:
                if t["key"].startswith("money:") and t["dt"][:10] == dt[:10] and t.get("merchant") == r["merchant"]:
                    t["product"] = base["product"]
            mark(done, "pay", r["id"])
            continue
        hit = recorded(dt[:10], base["amount"])
        if hit:
            mark(done, "pay", r["id"])
            auto.append(f"이미 있음: 네이버쇼핑 {r['merchant']} {base['amount']:,} ({hit})")
        else:
            todo.append({**base, "src": "네이버쇼핑 카드결제",
                         "note": "농협카드 화면 '네이버파이낸셜'이나 카드 문자 '네이버페이'와 날짜·금액으로 짝지어 카드 구분, 짝 없으면 엄마카드로 보고 보고에 표시"})


def eats(todo):
    pend = jload("eats_pending.json", [])
    if not pend:
        return False
    orders = [o for o in coupang_parse.orders() if o["items"]]
    for p in pend:
        hits = [o for o in orders if o["total"] == p.get("amount")]
        if hits:
            todo.append({"key": "eats", "src": "쿠팡이츠 대기(eats_pending)", "pending": p,
                         "orders": [{"dt": o["dt"], "total": o["total"], "items": [i["name"] for i in o["items"]][:5]} for o in hits[-3:]],
                         "note": "맞는 주문이면 사유를 '쿠팡이츠 메뉴명'으로 고치고 eats_pending.json에서 빼기"})
    return True


def points(month_first, auto):
    """I37/I38: 그 달 포인트 적립·사용 누적 (참고용 텍스트)."""
    y, m = month_first.year, month_first.month
    last = (month_first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
    fetch([["points", month_first.strftime("%Y%m%d"), last.strftime("%Y%m%d")]])
    trades = jload(os.path.join(OUT, "points.json"), [])
    plus = sum(t["tradeAmount"] for t in trades if t["tradeAmount"] > 0)
    minus = sum(t["tradeAmount"] for t in trades if t["tradeAmount"] < 0)
    want = {"I37": f"N포인트 적립 +{plus:,}", "I38": f"N포인트 사용 -{-minus:,}"}
    sheet = f"{y % 100:02d}-{m:02d}"
    try:
        d = book.load(sheet)
    except SystemExit:
        return
    have = d.get("extra", {})
    ch = [f"{k}={v}" for k, v in want.items() if have.get(k) != v]
    if ch:
        book.cmd_set(sheet, ch)
        _months.pop(sheet, None)
        auto.append(f"{sheet} 포인트 {want['I37']} / {want['I38']}")


def newmonth(auto):
    if NOW.day < 25:
        return
    nxt = (NOW.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    if os.path.exists(book.path_of(nxt.strftime("%Y-%m"))):
        return
    try:
        book.cmd_newmonth()
        auto.append(f"다음 달 {nxt:%y-%m} 파일 만듦")
    except SystemExit as e:
        auto.append(f"다음 달 파일 만들기 실패: {e}")


# ---------- 실행 ----------
def run(do_fetch=True):
    done, todo, auto = load_done(), [], []
    if do_fetch:
        fetch([["history"], ["kbmail"], ["kbmail", "[농협카드 화면]", "nhmail"],
               ["kbmail", "쿠팡(주)", "coupang_pg"], ["kbmail", "NHN KCP", "pg_kcp"],
               ["kbmail", "결제하신 내역", "pg_kicc"], ["payhist", "2"]])
        if jload("eats_pending.json", []):
            fetch([["kbmail", "주문하신 내역을 확인해주세요", "coupang"]])
    first = NOW.date().replace(day=1)
    if do_fetch:
        points(first, auto)
        if NOW.day <= 3:  # 지난달 마지막 날 포인트까지 반영
            points((first - datetime.timedelta(days=1)).replace(day=1), auto)
    if do_fetch:
        newmonth(auto)
    money(done, todo, auto)
    kbmail(done, todo, auto)
    nhmail(done, todo, auto)
    pg(done, todo, auto)
    payhist(done, todo, auto)
    eats(todo)
    asked = jload("collect_asked.json", [])  # 사용자에게 이미 물어본 건은 답이 올 때까지 Claude를 다시 부르지 않는다
    waiting = [t for t in todo if t["key"] in asked]
    todo = [t for t in todo if t["key"] not in asked]
    if waiting:
        auto.append(f"답 기다리는 질문 {len(waiting)}건 ({', '.join(t['key'] for t in waiting)})")
    print(f"자동 처리 {len(auto)}건, Claude 판단 필요 {len(todo)}건")
    for a in auto:
        print(" -", a)
    for t in todo:
        print(" ?", json.dumps(t, ensure_ascii=False)[:200])
    if not do_fetch:  # 시험: 아무것도 저장·전송하지 않음
        return 0
    save_done(done)
    jsave("collect_todo.json", {"at": NOW.strftime("%Y-%m-%d %H:%M"), "items": todo, "auto": auto})
    if not todo:
        tg("가계부 새벽 수집: 새 내역 없음" + ("\n" + "\n".join(f"- {a}" for a in auto if not a.startswith("이미 있음")) if auto else ""))
        return 0
    return 10


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "done":
        dn = load_done()
        for k in sys.argv[2:]:
            kind, key = k.split(":", 1)
            if kind in DONE:
                mark(dn, kind, key)
        save_done(dn)
        asked = [k for k in jload("collect_asked.json", []) if k not in sys.argv[2:]]
        jsave("collect_asked.json", asked)
        print("처리 기록:", " ".join(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "ask":
        asked = jload("collect_asked.json", [])
        jsave("collect_asked.json", asked + [k for k in sys.argv[2:] if k not in asked])
        print("질문으로 남김:", " ".join(sys.argv[2:]))
    else:
        sys.exit(run(do_fetch="--no-fetch" not in sys.argv))
