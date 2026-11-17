"""쿠팡 반품·취소 일괄 확인 (Claude 없음).

매달 둘째 주 일요일·말일에 run_daily.ps1이 부른다 (사용자 지시 2026-11-17: 자주 확인하면 토큰 아까움).
쿠팡 주문목록에서 '반품완료'·'취소완료' 상품을 찾아 → 엄마카드 쪽 같은 금액(주문일~+3일) 기록을 가계부에서 지운다.
짝이 여러 개거나 금액이 안 맞으면 지우지 않고 질문으로 남긴다 (collect.py questions).

  python coupang_returns.py          # 날짜 조건 맞을 때만 실행
  python coupang_returns.py --force  # 날짜 상관없이 실행
  python coupang_returns.py --dry    # 지우지 않고 무엇을 지울지만 출력
"""
import datetime, json, os, re, sys

import collect
from collect import book, jload, jsave, tg, NOW, OUT

DONE = "coupang_returns_done.json"
STATUS = ("반품완료", "취소완료")


def due(today):
    second_sunday = today.weekday() == 6 and 8 <= today.day <= 14
    last_day = (today + datetime.timedelta(days=1)).day == 1
    return second_sunday or last_day


def parse(text):
    """주문목록 글자 → [{date, status, item, amount}]"""
    out = []
    parts = re.split(r"(\d{4})\. (\d{1,2})\. (\d{1,2}) 주문\n", text)
    for i in range(1, len(parts) - 3, 4):
        date = f"{parts[i]}-{int(parts[i+1]):02d}-{int(parts[i+2]):02d}"
        lines = [l.strip() for l in parts[i + 3].split("\n") if l.strip()]
        status = next((l for l in lines[:4] if l != "주문 상세보기"), "")
        for j, l in enumerate(lines):
            m = re.fullmatch(r"([\d,]+) 원", l)
            if m and j > 0:
                out.append({"date": date, "status": status, "item": lines[j - 1],
                            "amount": int(m.group(1).replace(",", ""))})
    return out


def main():
    force, dry = "--force" in sys.argv, "--dry" in sys.argv
    if not (force or dry or due(NOW.date())):
        return 0
    cutoff = (NOW.date().replace(day=1) - datetime.timedelta(days=1)).replace(day=1)  # 지난달 1일부터
    import subprocess
    r = subprocess.run(["node", "naver.js", "coupangorders", "3"], cwd=collect.HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    if "COUPANG DENIED" in r.stdout or "COUPANG LOGIN" in r.stdout:
        why = "쿠팡이 접속을 막음 (다음 확인일에 다시)" if "DENIED" in r.stdout else "쿠팡 로그인 필요"
        print(why)
        if not dry:
            tg("쿠팡 반품 확인: " + why)
        return 5
    pages = jload(os.path.join(OUT, "coupang_orders.json"), [])
    orders = [o for p in pages for o in parse(p["text"])]
    if not orders:
        print("주문 못 읽음")
        if dry:
            return 5
        tg("쿠팡 반품 확인: 주문목록을 못 읽음 (쿠팡 로그인 확인 필요)")
        return 5
    done = jload(DONE, [])
    removed, asks = [], []
    for o in orders:
        if o["status"] not in STATUS or o["date"] < cutoff.isoformat():
            continue
        oid = f"{o['date']}|{o['amount']}|{o['item'][:30]}"
        if oid in done:
            continue
        d0 = datetime.date.fromisoformat(o["date"])
        hits = []
        for k in range(4):
            day = (d0 + datetime.timedelta(days=k)).isoformat()
            d = collect.month_data(day)
            if d:
                hits += [(day, e) for e in d["entries"] if e.get("side") == "mom" and e.get("amount") == o["amount"]
                         and (e.get("date") == day or f"({d0.month}.{d0.day + k})" in (e.get("memo") or ""))]
        hits = list({(e["col"], e["row"], day[:7]): (day, e) for day, e in hits}.values())
        if len(hits) == 1:
            day, e = hits[0]
            sheet, col, row = day[2:7], e["col"], e["row"]
            memo_col = book.col_name(book.col_idx(col) + 1)
            line = f"{sheet} {col}{row} {o['amount']:,} {e.get('memo','')} ← {o['status']} {o['item'][:25]}"
            if not dry:
                book.cmd_set(sheet, [f"{col}{row}=", f"{memo_col}{row}="])
                collect._months.pop(sheet, None)
                done.append(oid)
            removed.append(line)
        elif hits:
            asks.append((oid, f"쿠팡 {o['status']} {o['date']} {o['item'][:30]} {o['amount']:,}원 — 같은 금액 기록이 {len(hits)}개라 어느 걸 지울지 모름"))
        else:
            if not dry:
                done.append(oid)  # 가계부에 없던 건 (결제 전 취소 등)
    if dry:
        print("지울 예정:", *removed, sep="\n - ")
        print("물어볼 것:", *[a[1] for a in asks], sep="\n - ")
        return 0
    jsave(DONE, done)
    for oid, q in asks:
        qs = [x for x in jload("questions.json", []) if x["key"] != "cp:" + oid]
        jsave("questions.json", qs + [{"key": "cp:" + oid, "q": q, "at": NOW.strftime("%Y-%m-%d %H:%M")}])
    msg = "쿠팡 반품·취소 확인: " + (f"{len(removed)}건 가계부에서 지움" if removed else "지울 것 없음")
    tg(msg + "".join(f"\n- {r}" for r in removed))
    print(msg, *removed, sep="\n - ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
