#!/usr/bin/env python3
"""다음 달 시트 생성: 가장 최근 월 시트(YY-MM)를 복사해 새 시트를 만든다 (xlsx XML 직접 조작, 다른 시트/그림 보존).

규칙
- A열 날짜를 새 달 1일~말일로 바꾼다.
- 3~34행 B~AL 칸(P열 수식 제외)은 비운다. 단
  - 회색(테마6) 고정지출 칸은 유지. '○월관리비' → 전달 월로 바꾸고 금액은 '?'.
  - 사유에 '(n/m)' 할부 표기가 있고 n<m 이면 회차를 n+1로 올리고 금액과 함께 유지. n==m 이면 끝난 할부라 비운다.
- I37/I38 포인트 누적은 0으로 초기화.
- 35행 이후 합계 수식/수입 칸은 그대로 복사.

사용: python3 newmonth.py <입력.xlsx> <출력.xlsx> [새시트명]
"""
import calendar
import datetime
import re
import sys
import uuid
import zipfile
from xml.sax.saxutils import escape

SRC, DST = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(SRC)
files = {i.filename: zin.read(i.filename) for i in zin.infolist()}
infos = zin.infolist()

wb = files["xl/workbook.xml"].decode()
rels = files["xl/_rels/workbook.xml.rels"].decode()
sheets = re.findall(r'<sheet [^>]*name="([^"]+)"[^>]*sheetId="(\d+)"[^>]*r:id="(rId\d+)"', wb)
months = [s for s in sheets if re.fullmatch(r"\d\d-\d\d", s[0])]
src_name, _, src_rid = max(months, key=lambda s: s[0])
yy, mm = map(int, src_name.split("-"))
ny, nm = (yy + 1, 1) if mm == 12 else (yy, mm + 1)
new_name = sys.argv[3] if len(sys.argv) > 3 else f"{ny:02d}-{nm:02d}"
if any(s[0] == new_name for s in sheets):
    raise SystemExit(f"이미 있음: {new_name}")
src_part = "xl/" + re.search(r'Id="%s"[^>]*Target="([^"]+)"' % src_rid, rels).group(1).lstrip("/").removeprefix("xl/")

# --- shared strings ---
sst = files["xl/sharedStrings.xml"].decode()
strings = []
for si in re.findall(r"<si>(.*?)</si>", sst, re.S):
    strings.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))

# --- styles: 회색(테마6) 채우기 스타일 ---
st = files["xl/styles.xml"].decode()
fills = re.findall(r"<fill>(.*?)</fill>", re.search(r"<fills[^>]*>(.*?)</fills>", st, re.S).group(1), re.S)
gray_fill = {i for i, f in enumerate(fills) if re.search(r'<fgColor theme="6"', f)}
xfs = re.findall(r"<xf [^>]*?(?:/>|>.*?</xf>)", re.search(r"<cellXfs[^>]*>(.*?)</cellXfs>", st, re.S).group(1), re.S)
gray_style = {i for i, x in enumerate(xfs) if int((re.search(r'fillId="(\d+)"', x) or [0, 0])[1]) in gray_fill}


def col_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n


def cell_text(c):
    v = re.search(r"<v>(.*?)</v>", c)
    if 't="s"' in c and v:
        return strings[int(v.group(1))]
    t = re.search(r"<t[^>]*>(.*?)</t>", c, re.S)
    if t:
        return t.group(1)
    return v.group(1) if v else None


def empty(ref, s):
    return f'<c r="{ref}"' + (f' s="{s}"' if s else "") + "/>"


def text_cell(ref, s, text):
    return f'<c r="{ref}"' + (f' s="{s}"' if s else "") + f' t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>'


xml = files[src_part].decode()
cell_re = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
cells = {(m.group(1), int(m.group(2))): m for m in cell_re.finditer(xml)}

days = calendar.monthrange(2000 + ny, nm)[1]
prev_month_label = f"{mm}월"
keep = {}      # (col,row) -> new xml
install_rows = set()

# 1) 할부 사유 찾기
for (col, row), m in cells.items():
    if not (3 <= row <= 34) or col == "P":
        continue
    txt = cell_text(m.group(0)) or ""
    s = (re.search(r's="(\d+)"', m.group(3)) or [None, None])[1]
    if s and int(s) in gray_style:
        continue
    im = re.search(r"\((\d+)/(\d+)\)", txt)
    if im and col_idx(col) > 1:
        n, tot = int(im.group(1)), int(im.group(2))
        amt_col = re.sub(r"\d", "", __import__("openpyxl").utils.get_column_letter(col_idx(col) - 1))
        if n < tot:
            keep[(col, row)] = text_cell(f"{col}{row}", s, txt.replace(im.group(0), f"({n + 1}/{tot})"))
            am = cells.get((amt_col, row))
            if am:
                keep[(amt_col, row)] = am.group(0)
        install_rows.add((col, row))


def repl(m):
    col, row = m.group(1), int(m.group(2))
    attrs = m.group(3)
    ref = f"{col}{row}"
    s = (re.search(r's="(\d+)"', attrs) or [None, None])[1]
    if col == "A" and 3 <= row <= 33:
        d = row - 2
        if d <= days:
            serial = (datetime.date(2000 + ny, nm, d) - datetime.date(1899, 12, 30)).days
            return f'<c r="{ref}"' + (f' s="{s}"' if s else "") + f"><v>{serial}</v></c>"
        return empty(ref, s)
    if col == "I" and row in (37, 38):
        return text_cell(ref, s, "N포인트 적립 +0" if row == 37 else "N포인트 사용 -0")
    if not (3 <= row <= 34) or col == "P" or col_idx(col) < 2 or col_idx(col) > 38:
        return m.group(0)
    if (col, row) in keep:
        return keep[(col, row)]
    if s and int(s) in gray_style:
        txt = cell_text(m.group(0)) or ""
        if "관리비" in txt:
            return text_cell(ref, s, re.sub(r"\d+월관리비", f"{prev_month_label}관리비", txt))
        # 관리비 금액 칸 → '?'
        right = cells.get((__import__("openpyxl").utils.get_column_letter(col_idx(col) + 1), row))
        if right is not None and "관리비" in (cell_text(right.group(0)) or ""):
            return text_cell(ref, s, "?")
        return m.group(0)
    return empty(ref, s)


new_xml = cell_re.sub(repl, xml)
# A33 등 원본에 없던 날짜 칸 보충
for d in range(1, days + 1):
    row = d + 2
    if ("A", row) not in cells:
        serial = (datetime.date(2000 + ny, nm, d) - datetime.date(1899, 12, 30)).days
        a32 = cells.get(("A", 32))
        s = (re.search(r's="(\d+)"', a32.group(3)) or [None, None])[1] if a32 else None
        new_xml = re.sub(r'(<row r="%d"[^>]*>)' % row,
                         lambda mm_: mm_.group(1) + f'<c r="A{row}"' + (f' s="{s}"' if s else "") + f"><v>{serial}</v></c>",
                         new_xml, count=1)
new_xml = new_xml.replace(' tabSelected="1"', "")
new_xml = re.sub(r'xr:uid="\{[^}]+\}"', 'xr:uid="{%s}"' % str(uuid.uuid4()).upper(), new_xml, count=1)
new_xml = re.sub(r'(<pageSetup[^>]*?) r:id="rId\d+"', r"\1", new_xml)
new_xml = re.sub(r"<drawing [^>]*/>|<legacyDrawing [^>]*/>", "", new_xml)

# --- 새 시트 등록 ---
nums = [int(x) for x in re.findall(r"worksheets/sheet(\d+)\.xml", " ".join(files))]
part_name = f"xl/worksheets/sheet{max(nums) + 1}.xml"
files[part_name] = new_xml.encode()
rid_nums = [int(x) for x in re.findall(r'Id="rId(\d+)"', rels)]
new_rid = f"rId{max(rid_nums) + 1}"
rels = rels.replace("</Relationships>",
                    f'<Relationship Id="{new_rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="{part_name[3:]}"/></Relationships>')
new_sheet_id = max(int(s[1]) for s in sheets) + 1
wb = wb.replace("</sheets>", f'<sheet name="{new_name}" sheetId="{new_sheet_id}" r:id="{new_rid}"/></sheets>')
# 새 시트를 활성 탭으로
idx = len(sheets)
wb = re.sub(r'activeTab="\d+"', f'activeTab="{idx}"', wb)
for k in list(files):
    if re.match(r"xl/worksheets/sheet\d+\.xml$", k) and k != part_name:
        files[k] = files[k].replace(b' tabSelected="1"', b"")
files[part_name] = files[part_name].replace(b"<sheetView ", b'<sheetView tabSelected="1" ', 1)
# calcChain 제거 (Excel이 다시 만든다)
if "xl/calcChain.xml" in files:
    del files["xl/calcChain.xml"]
    rels = re.sub(r'<Relationship [^>]*Target="calcChain.xml"/>', "", rels)
ct = files["[Content_Types].xml"].decode()
ct = re.sub(r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "", ct)
ct = ct.replace("</Types>", f'<Override PartName="/{part_name}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
files["[Content_Types].xml"] = ct.encode()
files["xl/_rels/workbook.xml.rels"] = rels.encode()
if "fullCalcOnLoad" not in wb:
    wb = re.sub(r"<calcPr([^>]*)/>", r'<calcPr\1 fullCalcOnLoad="1"/>', wb) if "<calcPr" in wb else wb
files["xl/workbook.xml"] = wb.encode()

with zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED) as zo:
    for info in infos:
        if info.filename in files:
            zo.writestr(info, files[info.filename])
    zo.writestr(part_name, files[part_name])
print(f"{src_name} -> {new_name} ({part_name}), 할부 {len(install_rows)}건 처리")
