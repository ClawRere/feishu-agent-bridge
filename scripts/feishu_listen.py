#!/usr/bin/env python3
"""Feishu WebSocket listener template for any AI agent.

- Listens for im.message.receive_v1 on a single WebSocket connection.
- When THIS bot is @mentioned: sticks an OK reaction (visible "received"
  marker), then appends the message to QUEUE_PATH as JSONL for your
  agent (Muse / dot / cue / ...) to consume and reply to.
- When not mentioned: stays silent (logs locally only).

All configuration via environment variables (see README.md).
One APP_ID = one running listener. Never run two.

If your host reaches the internet through a proxy, apply the SDK patch
described in docs/proxy.md first, otherwise the WS connection will fail.
"""
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone

import requests
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as FeishuWSClient

BASE = "https://open.feishu.cn/open-apis"
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
BOT_NAME = os.environ.get("BOT_NAME", "")
BOT_OPEN_ID = os.environ.get("BOT_OPEN_ID", "")
TARGET_CHAT = os.environ.get("TARGET_CHAT", "") or None
QUEUE_PATH = os.environ.get("QUEUE_PATH", "./mention_queue.jsonl")
HEARTBEAT_PATH = os.environ.get("HEARTBEAT_PATH", "./listener_heartbeat.txt")
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "30"))

if not APP_ID or not APP_SECRET:
    sys.exit("FEISHU_APP_ID / FEISHU_APP_SECRET are not set")

SEEN = set()


def _heartbeat():
    while True:
        try:
            with open(HEARTBEAT_PATH, "w") as f:
                f.write(str(time.time()))
        except OSError as e:
            print(f"[listener] heartbeat write failed: {e}", flush=True)
        time.sleep(HEARTBEAT_INTERVAL)


threading.Thread(target=_heartbeat, daemon=True).start()

_tok = {"v": None, "ts": 0.0}


def get_token():
    if _tok["v"] and time.time() - _tok["ts"] < 7000:
        return _tok["v"]
    d = requests.post(
        f"{BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=30,
    ).json()
    if "tenant_access_token" not in d:
        raise RuntimeError(f"token error: {d}")
    _tok["v"], _tok["ts"] = d["tenant_access_token"], time.time()
    return _tok["v"]


def i_am_mentioned(msg):
    """True if this bot itself appears in the message's mentions list."""
    for m in (getattr(msg, "mentions", None) or []):
        mid = getattr(m, "id", None)
        oid = getattr(mid, "open_id", None) if mid is not None else None
        mtype = getattr(m, "mentioned_type", "") or ""
        if mtype in ("bot", "app"):
            if BOT_OPEN_ID and oid == BOT_OPEN_ID:
                return True
            if BOT_NAME and getattr(m, "name", "") == BOT_NAME:
                return True
    return False


def on_message(data):
    ev = data.event
    msg, sender = getattr(ev, "message", None), getattr(ev, "sender", None)
    chat_id = getattr(msg, "chat_id", "") or ""
    if TARGET_CHAT and chat_id != TARGET_CHAT:
        return
    mid = getattr(msg, "message_id", "") or ""
    if not mid or mid in SEEN:
        return
    SEEN.add(mid)

    try:
        text = json.loads(getattr(msg, "content", "") or "{}").get("text", "")
    except Exception:
        text = str(getattr(msg, "content", ""))

    mentioned = i_am_mentioned(msg)
    print(f"[listener] recv chat={chat_id} mentioned={mentioned} text={text[:60]}", flush=True)
    if not mentioned:
        return

    # 1) OK reaction = visible acknowledgement
    try:
        code = requests.post(
            f"{BASE}/im/v1/messages/{mid}/reactions",
            headers={"Authorization": f"Bearer {get_token()}"},
            json={"reaction_type": {"emoji_type": "OK"}},
            timeout=30,
        ).json().get("code")
        print(f"[listener] react code={code}", flush=True)
    except Exception as e:
        print(f"[listener] react error: {e}", flush=True)

    # 2) hand off to your agent via a JSONL queue
    try:
        q = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "chat": chat_id,
            "message_id": mid,
            "sender": getattr(sender, "sender_type", ""),
            "text": text,
        }
        with open(QUEUE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"[listener] queued {mid}", flush=True)
    except OSError as e:
        print(f"[listener] queue write error: {e}", flush=True)


def main():
    handler = (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    client = FeishuWSClient(APP_ID, APP_SECRET, event_handler=handler)
    print(
        f"[listener] WS starting app_id={APP_ID[:8]}... "
        f"target_chat={TARGET_CHAT or 'any'} queue={QUEUE_PATH}",
        flush=True,
    )
    client.start()


if __name__ == "__main__":
    main()
