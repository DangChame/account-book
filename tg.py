#!/usr/bin/env python3
"""텔레그램 보고 전송.  python3 tg.py "메시지"   (설정: ~/.config/ledger/telegram.json {token, chat_id})"""
import json
import os
import sys
import urllib.parse
import urllib.request

CFG = os.path.expanduser("~/.config/ledger/telegram.json")


def api(cfg, method, **params):
    url = f"https://api.telegram.org/bot{cfg['token']}/{method}"
    data = urllib.parse.urlencode(params).encode() if params else None
    return json.load(urllib.request.urlopen(url, data))


def load():
    cfg = json.load(open(CFG))
    if not cfg.get("chat_id"):  # 봇에게 처음 말을 건 사람의 chat_id를 찾아 저장
        for u in api(cfg, "getUpdates")["result"]:
            msg = u.get("message") or {}
            if msg.get("chat", {}).get("id"):
                cfg["chat_id"] = msg["chat"]["id"]
        if cfg.get("chat_id"):
            fd = os.open(CFG, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0o600)
            with os.fdopen(fd, "w") as f:
                json.dump(cfg, f)
    return cfg


def send(text):
    cfg = load()
    if not cfg.get("chat_id"):
        raise SystemExit("chat_id 없음: 텔레그램에서 봇에게 아무 메시지나 먼저 보내 주세요")
    for i in range(0, len(text), 4000):
        api(cfg, "sendMessage", chat_id=cfg["chat_id"], text=text[i:i + 4000])
    print("SENT")


def send_photo(path, caption=""):
    import uuid
    cfg = load()
    b = uuid.uuid4().hex
    body = (f'--{b}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{cfg["chat_id"]}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="p.png"\r\nContent-Type: image/png\r\n\r\n').encode() \
        + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{cfg['token']}/sendPhoto", body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    json.load(urllib.request.urlopen(req))
    print("PHOTO SENT")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--photo":
        send_photo(sys.argv[2], " ".join(sys.argv[3:]))
    else:
        send(" ".join(sys.argv[1:]) or sys.stdin.read())
