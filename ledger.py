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


# ---------------------------------------------------------------------------
# OneDrive 직접 수정 (Microsoft Graph, Excel REST API)
#   셀 단위로 PATCH 하므로 서식/회색/그림이 그대로이고, 수식은 Excel이 재계산하며,
#   폰/PC에서 동시에 열어둬도 파일 전체를 덮어쓰지 않는다.
# ---------------------------------------------------------------------------
import base64
import json
import os
import time
import urllib.error
import urllib.parse

SHARE_URL = "https://1drv.ms/x/c/c3ff9e4fac7f997f/IQB_mX-sT57_IIDDcQAAAAAAAS_yTM5yFv3Y1XCLE-joULs?e=VhSK0c"
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.expanduser("~/.config/ledger")
TOKEN_PATH = os.path.join(STATE_DIR, "token.json")
AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0"
SCOPE = "Files.ReadWrite offline_access"
DEFAULT_CLIENT_ID = "d50ca740-c83f-4d1b-b616-12c519384f0c"
REDIRECT = "https://login.microsoftonline.com/common/oauth2/nativeclient"
GRAPH = "https://graph.microsoft.com/v1.0"


def client_id():
    cid = os.environ.get("LEDGER_CLIENT_ID")
    cfg = os.path.join(HERE, "ledger_config.json")
    if not cid and os.path.exists(cfg):
        cid = json.load(open(cfg)).get("client_id")
    # 기본값: 오픈소스 'OneDrive Client for Linux'(abraunegg/onedrive)의 공개 앱 ID.
    # 개인 계정은 Entra에서 앱 등록이 막혀 있어, 사용자 동의하에 이 공개 클라이언트로 로그인한다.
    return cid or DEFAULT_CLIENT_ID


def _post_form(url, data):
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode())
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def _save_token(tok):
    os.makedirs(STATE_DIR, exist_ok=True)
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 120
    fd = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(tok, f)


def login():
    """디바이스 코드 로그인: 코드를 출력하고, 사용자가 로그인할 때까지 기다린다."""
    dc = _post_form(f"{AUTH}/devicecode", {"client_id": client_id(), "scope": SCOPE})
    if "device_code" not in dc:
        raise SystemExit(f"devicecode 실패: {dc}")
    print(f"LOGIN {dc['verification_uri']} CODE {dc['user_code']}", flush=True)
    deadline = time.time() + int(dc.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(int(dc.get("interval", 5)))
        tok = _post_form(f"{AUTH}/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": client_id(), "device_code": dc["device_code"]})
        if "access_token" in tok:
            _save_token(tok)
            print("LOGIN OK", flush=True)
            return
        if tok.get("error") not in ("authorization_pending", "slow_down"):
            raise SystemExit(f"로그인 실패: {tok.get('error')}: {tok.get('error_description')}")
    raise SystemExit("로그인 시간 초과")


def login_url():
    """브라우저 로그인 주소. 로그인 후 빈 화면의 주소창 URL(code= 포함)을 login-code 로 넘긴다."""
    return f"{AUTH}/authorize?" + urllib.parse.urlencode({
        "client_id": client_id(), "scope": SCOPE, "response_type": "code",
        "redirect_uri": REDIRECT, "prompt": "select_account"})


def login_code(redirected):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(redirected.strip()).query)
    code = q.get("code", [redirected.strip()])[0]
    tok = _post_form(f"{AUTH}/token", {
        "grant_type": "authorization_code", "client_id": client_id(), "code": code,
        "redirect_uri": REDIRECT, "scope": SCOPE})
    if "access_token" not in tok:
        raise SystemExit(f"로그인 실패: {tok.get('error')}: {tok.get('error_description')}")
    _save_token(tok)
    print("LOGIN OK")


def access_token():
    if not os.path.exists(TOKEN_PATH):
        raise SystemExit("로그인 필요: python3 ledger.py login")
    tok = json.load(open(TOKEN_PATH))
    if time.time() < tok.get("expires_at", 0):
        return tok["access_token"]
    new = _post_form(f"{AUTH}/token", {
        "grant_type": "refresh_token", "client_id": client_id(),
        "refresh_token": tok["refresh_token"], "scope": SCOPE})
    if "access_token" not in new:
        raise SystemExit(f"토큰 갱신 실패(다시 login 필요): {new.get('error')}")
    new.setdefault("refresh_token", tok["refresh_token"])
    _save_token(new)
    return new["access_token"]


def graph(method, path, body=None):
    url = path if path.startswith("http") else GRAPH + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data, method=method, headers={
        "Authorization": "Bearer " + access_token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Graph {method} {path} -> {e.code}: {e.read().decode()[:500]}")


def item_path():
    enc = "u!" + base64.urlsafe_b64encode(SHARE_URL.encode()).decode().rstrip("=")
    it = graph("GET", f"/shares/{enc}/driveItem?$select=id,name,parentReference")
    return f"/drives/{it['parentReference']['driveId']}/items/{it['id']}"


def _ws(sheet):
    return "/workbook/worksheets('%s')" % urllib.parse.quote(sheet.replace("'", "''"))


def remote_get(sheet, address):
    r = graph("GET", item_path() + _ws(sheet) + f"/range(address='{address}')?$select=address,values")
    return r["values"]


def remote_set(sheet, updates):
    """updates: {"U14": 5000, "V14": "사유"} — OneDrive 원본 셀에 직접 기록."""
    base = item_path() + _ws(sheet)
    for ref, value in updates.items():
        graph("PATCH", base + f"/range(address='{ref}')", {"values": [[value]]})
    return {ref: remote_get(sheet, ref)[0][0] for ref in updates}


def remote_text(drive_path):
    """내 OneDrive의 텍스트 파일 내용 (예: '가계부/sms.txt'). 없으면 빈 문자열."""
    url = GRAPH + "/me/drive/root:/" + urllib.parse.quote(drive_path)
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + access_token()})
    try:
        with urllib.request.urlopen(req) as r:
            dl = json.load(r)["@microsoft.graph.downloadUrl"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ""
        raise SystemExit(f"Graph GET {drive_path} -> {e.code}: {e.read().decode()[:300]}")
    # 다운로드 URL은 사전 서명돼 있어 인증 헤더 없이 받는다
    with urllib.request.urlopen(dl) as r:
        return r.read().decode("utf-8", "replace")


def remote_folder_texts(drive_folder):
    """폴더 안 파일들의 (이름, 수정시각, 내용) 목록 — 단축어 '파일 저장'으로 쌓인 카드 문자용."""
    r = graph("GET", "/me/drive/root:/" + urllib.parse.quote(drive_folder)
              + ":/children?$top=999&$orderby=lastModifiedDateTime")
    out = []
    for it in r.get("value", []):
        if "file" not in it:
            continue
        with urllib.request.urlopen(it["@microsoft.graph.downloadUrl"]) as f:
            out.append((it["name"], it["lastModifiedDateTime"], f.read().decode("utf-8", "replace")))
    return out


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
    elif cmd == "login":  # 직접 등록한 앱(공용 클라이언트) 전용 디바이스 코드 로그인
        login()
    elif cmd == "login-url":
        print(login_url())
    elif cmd == "login-code":  # login-code '<리디렉션된 URL>'
        login_code(args[0])
    elif cmd == "rdir":  # rdir '가계부/카드문자'
        for name, ts, text in remote_folder_texts(args[0]):
            print(f"=== {name} | {ts}\n{text}")
    elif cmd == "rfile":  # rfile '가계부/sms.txt'
        print(remote_text(args[0]))
    elif cmd == "rget":  # rget sheet A1:B2
        for row in remote_get(args[0], args[1]):
            print(row)
    elif cmd == "rset":  # rset sheet REF=VALUE ...  (OneDrive 원본 직접 수정)
        ups = {}
        for a in args[1:]:
            k, v = a.split("=", 1)
            ups[k] = int(v) if re.fullmatch(r"-?\d+", v) else v
        print(remote_set(args[0], ups))
    else:
        print(__doc__)
