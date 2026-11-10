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


if __name__ == "__main__":
    send(" ".join(sys.argv[1:]) or sys.stdin.read())
