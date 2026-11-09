#!/usr/bin/env python3
"""가계부(OneDrive xlsx) 읽기/쓰기 도구.

- download: 공유 링크에서 xlsx 다운로드
- show:     월 시트 내용 출력
- set:      셀 값을 XML에서 직접 수정 (서식/회색 고정지출 표시/수식/그림 보존)

시트 구조 (25년 이후 월 시트, 예: '26-11')
  A: 날짜 (3행 = 1일 ... 33행 = 31일), 35행 지출합, 36행 총합
  내 돈:   B 식비 | D,F 데이트(헤더 비어있음) | H 생필품,이동 | J 여가,식비정산
           | L 먼슬리페이(고정지출, 회색) | N 이외          (각 오른쪽 열 = 사유)
  P: 일지출 (수식)
  엄마카드: Q 점심 | S 저녁 | U,W 간식 | Y 생필품 | AA 차량 | AC 여가
           | AE,AG 커피,티 | AI 교육 | AK 이외           (각 오른쪽 열 = 사유)
"""
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from xml.sax.saxutils import escape

DOWNLOAD_URL = (
    "https://my.microsoftpersonalcontent.com/personal/c3ff9e4fac7f997f/"
    "_layouts/15/download.aspx?share=IQB_mX-sT57_IIDDcQAAAAAAAS_yTM5yFv3Y1XCLE-joULs"
)


def download(path):
    with urllib.request.urlopen(DOWNLOAD_URL) as r, open(path, "wb") as f:
        shutil.copyfileobj(r, f)


def sheet_part(zf, name):
    wb = zf.read("xl/workbook.xml").decode()
    m = re.search(r'<sheet [^>]*name="%s"[^>]*r:id="(rId\d+)"' % re.escape(escape(name)), wb)
    if not m:
        raise SystemExit(f"sheet not found: {name}")
    rels = zf.read("xl/_rels/workbook.xml.rels").decode()
    t = re.search(r'Id="%s"[^>]*Target="([^"]+)"' % m.group(1), rels) or \
        re.search(r'Target="([^"]+)"[^>]*Id="%s"' % m.group(1), rels)
    return "xl/" + t.group(1).lstrip("/").removeprefix("xl/")


def _cell_xml(ref, style, value):
    s = f' s="{style}"' if style else ""
    if value is None or value == "":
        return f'<c r="{ref}"{s}/>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"{s}><v>{value}</v></c>'
    return f'<c r="{ref}"{s} t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def set_cells(path, sheet, updates):
    """updates: {"AI14": 12000, "AJ14": "사유"} — 기존 셀 서식(s=)을 유지한 채 값만 교체."""
    with zipfile.ZipFile(path) as zf:
        part = sheet_part(zf, sheet)
        xml = zf.read(part).decode()
        wbxml = zf.read("xl/workbook.xml").decode()
        items = {i.filename: zf.read(i.filename) for i in zf.infolist()}
        infos = zf.infolist()
    for ref, value in updates.items():
        pat = re.compile(r'<c r="%s"(?P<attrs>[^>]*?)(?:/>|>.*?</c>)' % ref, re.S)
        m = pat.search(xml)
        if not m:
            raise SystemExit(f"cell {ref} not pre-formatted in {sheet}; refusing to guess placement")
        st = re.search(r's="(\d+)"', m.group("attrs"))
        xml = xml[:m.start()] + _cell_xml(ref, st.group(1) if st else None, value) + xml[m.end():]
    # 수식 재계산 강제
    if "fullCalcOnLoad" not in wbxml:
        if "<calcPr" in wbxml:
            wbxml = wbxml.replace("<calcPr", '<calcPr fullCalcOnLoad="1"', 1)
        else:
            wbxml = wbxml.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
    items[part] = xml.encode()
    items["xl/workbook.xml"] = wbxml.encode()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx").name
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info in infos:
            out.writestr(info, items[info.filename])
    shutil.move(tmp, path)


def show(path, sheet):
    import openpyxl
    ws = openpyxl.load_workbook(path)[sheet]
    for row in ws.iter_rows(min_row=1, max_row=40):
        cells = [f"{c.coordinate}={c.value!r}" for c in row
                 if c.value is not None and not str(c.value).startswith("=SUM(B")]
        if cells:
            print(" | ".join(cells))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    if cmd == "download":
        download(args[0])
    elif cmd == "show":
        show(args[0], args[1])
    elif cmd == "set":  # set file sheet REF=VALUE ...
        ups = {}
        for a in args[2:]:
            k, v = a.split("=", 1)
            ups[k] = int(v) if re.fullmatch(r"-?\d+", v) else v
        set_cells(args[0], args[1], ups)
    else:
        print(__doc__)
