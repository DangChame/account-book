#!/usr/bin/env python3
"""OneDrive 가계부에 다음 달 시트가 없으면 만든다 (매달 25일 이후 새벽 실행에서 호출).

1) Graph로 현재 파일과 eTag를 받는다
2) 다음 달 시트가 이미 있으면 종료
3) 백업을 OneDrive '가계부/백업/'에 올린다
4) newmonth.py로 새 시트를 추가한 파일을 If-Match(eTag)로 업로드 — 그 사이 누가 고쳤으면 실패하고 아무것도 덮어쓰지 않는다
"""
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402

p = ledger.item_path()
it = ledger.graph("GET", p)
etag = it["eTag"]
data = urllib.request.urlopen(it["@microsoft.graph.downloadUrl"]).read()
tmp = tempfile.mkdtemp()
src, dst = os.path.join(tmp, "src.xlsx"), os.path.join(tmp, "dst.xlsx")
open(src, "wb").write(data)

names = re.findall(r'<sheet [^>]*name="(\d\d-\d\d)"', zipfile.ZipFile(src).read("xl/workbook.xml").decode())
latest = max(names)
yy, mm = map(int, latest.split("-"))
today = datetime.date.today()
if (2000 + yy, mm) > (today.year, today.month):
    print("이미 있음:", latest)
    sys.exit(0)


def put(url, body, extra=None):
    req = urllib.request.Request(url, body, method="PUT", headers={
        "Authorization": "Bearer " + ledger.access_token(),
        "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", **(extra or {})})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
put(ledger.GRAPH + "/me/drive/root:/" + urllib.parse.quote(f"가계부/백업/{it['name'][:-5]}_{stamp}.xlsx") + ":/content", data)
out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "newmonth.py"), src, dst],
                     capture_output=True, text=True, check=True).stdout.strip()
r = put(ledger.GRAPH + p + "/content", open(dst, "rb").read(), {"If-Match": etag})
print(out, "| 업로드", r["lastModifiedDateTime"])
