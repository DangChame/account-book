#!/usr/bin/env python3
"""쿠팡 주문 확인 메일(naver_out/coupang.json) → 주문 목록.

출력: 주문시각(KST), 총 결제금액, 결제수단, 상품 목록
사용: python3 coupang_parse.py [YYYYMM]
"""
import datetime
import json
import os
import re
import sys

KST = datetime.timezone(datetime.timedelta(hours=9))
SRC = os.path.expanduser("~/.config/ledger/naver_out/coupang.json")


def parse(body):
    t = re.sub(r"\s+", " ", body.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&"))
    total = re.search(r"총 결제금액 ([\d,]+)원", t)
    pay = re.search(r"배송비 [\d,]+원 (.+?) / ", t)
    sec = re.search(r"판매자 (.+?) 결제 정보", t)
    items = []
    if sec:
        # "상품명, 옵션, 1개 4,300원 1 4,300원 판매자" 반복
        body = re.sub(r"로켓배송 상품 \d+ .*?구매금액 판매자 |\S+배송 상품 \d+ .*?구매금액 판매자 ", "", sec.group(1))
        for m in re.finditer(r"(.+?) ([\d,]+)원 (\d+) ([\d,]+)원 (\S+)(?= |$)", body + " "):
            items.append({"name": m.group(1).strip(), "qty": int(m.group(3)),
                          "amount": int(m.group(4).replace(",", ""))})
    return {
        "total": int(total.group(1).replace(",", "")) if total else None,
        "pay": pay.group(1).strip() if pay else "",
        "items": items,
    }


def orders(month=None):
    out = []
    for m in json.load(open(SRC, encoding="utf-8")):
        dt = datetime.datetime.fromtimestamp(m["time"], KST)
        if month and dt.strftime("%Y%m") != month:
            continue
        o = parse(m["body"])
        o.update(mailSN=m["mailSN"], dt=dt.strftime("%Y-%m-%d %H:%M"))
        out.append(o)
    return sorted(out, key=lambda o: o["dt"])


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "pg":
    pass
elif __name__ == "__main__":
    for o in orders(sys.argv[1] if len(sys.argv) > 1 else None):
        names = " / ".join(i["name"] for i in o["items"])
        print(f'{o["dt"]} {o["total"]:>8} [{o["pay"]}] {names}')


# ---- 결제대행사 영수증 메일 (NHN KCP / KICC 이지페이): 쿠팡·쿠팡이츠 모든 결제에 한 통씩 온다 ----
# 영수증 메일 모음: 쿠팡(주) 검색분 + 모든 NHN KCP + 모든 KICC 이지페이 (가맹점 무관)
PG_SRCS = [os.path.expanduser(f"~/.config/ledger/naver_out/{n}.json") for n in ("coupang_pg", "pg_kcp", "pg_kicc")]


def parse_pg(body):
    t = re.sub(r"\s+", " ", body)
    if "카드종류" in t:  # NHN KCP
        dt = re.search(r"결제일시 (\d{4})년 (\d\d)월 (\d\d)일 (\d\d)시 (\d\d)분", t)
        amt = re.search(r"결제금액 ([\d,]+) ?원", t)
        card = re.search(r"카드종류 (\S+)", t)
        item = re.search(r"주문상품명 (.+?) 사이트주소", t)
        shop = re.search(r"구매상점명 (.+?) 주문상품명", t)
    else:  # KICC 이지페이
        dt = re.search(r"결제일시 (\d{4})/(\d\d)/(\d\d) (\d\d):(\d\d)", t)
        amt = re.search(r"상품금액 ([\d,]+)원", t)
        card = re.search(r"결제기관 (\S+)", t)
        item = re.search(r"상품명 (.+?) 결제일시", t)
        shop = re.search(r"상호 (.+?) 사이트", t)
    if not (dt and amt):
        return None
    c = card.group(1) if card else ""
    appr = re.search(r"승인번호 (\d+)", t)
    # 취소 영수증: "…에서 …취소하신 내역은" / "취소요청일시" — 결제일시·금액은 원 결제와 같다
    cancel = "취소하신 내역" in t or "취소요청일시" in t
    return {"dt": "{}-{}-{} {}:{}".format(*dt.groups()), "amount": int(amt.group(1).replace(",", "")),
            "card": c, "mom": ("NH" in c or "농협" in c), "item": item.group(1).strip() if item else "",
            "shop": shop.group(1).strip() if shop else "", "appr": appr.group(1) if appr else "",
            "cancel": cancel, "partial_text": "부분취소" in t}


def _pg_key(r):
    return r["appr"] or (r["dt"], r["amount"])


def receipts(month=None, include_cancelled=False):
    """결제 영수증 목록. 전액 취소(같은 승인번호·같은 금액)면 취소 영수증과 원 결제를 뺀다.
    부분취소(금액이 다르거나 본문에 '부분취소')면 원 결제를 남기고 'partial'=True를 달아
    사용자에게 실제 금액을 묻게 한다 (CLAUDE.md 규칙).
    include_cancelled=True면 취소 영수증·취소된 원 결제도 'cancel'/'cancelled' 표시를 달아 포함."""
    out, seen = [], set()
    mails = [m for f in PG_SRCS if os.path.exists(f) for m in json.load(open(f, encoding="utf-8"))]
    for m in mails:
        if m["mailSN"] in seen:
            continue
        seen.add(m["mailSN"])
        r = parse_pg(m["body"])
        if r and (not month or r["dt"].replace("-", "").startswith(month)):
            r["mailSN"] = m["mailSN"]
            out.append(r)
    cancels = {}
    for r in out:
        if r["cancel"]:
            cancels.setdefault(_pg_key(r), []).append(r)
    for r in out:
        cs = [] if r["cancel"] else cancels.get(_pg_key(r), [])
        full = any(c["amount"] == r["amount"] and not c["partial_text"] for c in cs)
        r["cancelled"] = full
        r["partial"] = bool(cs) and not full
        if r["partial"]:
            r["cancel_amount"] = sum(c["amount"] for c in cs)
    partial_keys = {_pg_key(r) for r in out if r["partial"]}
    if not include_cancelled:
        # 부분취소의 취소 영수증은 원 결제에 cancel_amount로 붙였으니 목록에서는 뺀다
        out = [r for r in out if not (r["cancel"] or r["cancelled"])]
    else:
        for r in out:
            if r["cancel"]:
                r["partial"] = _pg_key(r) in partial_keys
    return sorted(out, key=lambda r: r["dt"])


def main_pg(month):
    for r in receipts(month, include_cancelled=True):
        if r["cancel"]:
            tag = " [부분취소 영수증]" if r["partial"] else " [취소]"
        elif r["partial"]:
            tag = f" [부분취소 {r['cancel_amount']:,}원 — 실제 금액 확인 필요]"
        else:
            tag = " [취소됨]" if r["cancelled"] else ""
        print(f'{r["dt"]} {r["amount"]:>8} [{"엄마카드" if r["mom"] else "내돈:" + r["card"]}]{tag} {r["item"][:50]}')


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "pg":
    main_pg(sys.argv[2] if len(sys.argv) > 2 else None)
