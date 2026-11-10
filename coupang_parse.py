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
    for m in json.load(open(SRC)):
        dt = datetime.datetime.fromtimestamp(m["time"], KST)
        if month and dt.strftime("%Y%m") != month:
            continue
        o = parse(m["body"])
        o.update(mailSN=m["mailSN"], dt=dt.strftime("%Y-%m-%d %H:%M"))
        out.append(o)
    return sorted(out, key=lambda o: o["dt"])


if __name__ == "__main__":
    for o in orders(sys.argv[1] if len(sys.argv) > 1 else None):
        names = " / ".join(i["name"] for i in o["items"])
        print(f'{o["dt"]} {o["total"]:>8} [{o["pay"]}] {names}')
