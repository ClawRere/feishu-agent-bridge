#!/usr/bin/env python3
"""Send a Feishu text message as your Feishu app (bot identity).

Credentials come from environment variables ONLY:
    FEISHU_APP_ID, FEISHU_APP_SECRET

Usage:
    python3 feishu_send.py --chat oc_xxx --text "..."

Prints "Sent to <chat>: <message_id>" on success; exits non-zero on failure.
"""
import argparse
import json
import os
import sys
import time

import requests

BASE = "https://open.feishu.cn/open-apis"
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")

_tok = {"v": None, "ts": 0.0}


def get_token():
    if not APP_ID or not APP_SECRET:
        raise RuntimeError("FEISHU_APP_ID / FEISHU_APP_SECRET are not set")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat", required=True, help="target chat_id (oc_...)")
    ap.add_argument("--text", required=True, help="message text")
    a = ap.parse_args()

    r = requests.post(
        f"{BASE}/im/v1/messages?receive_id_type=chat_id",
        headers={"Authorization": f"Bearer {get_token()}"},
        json={
            "receive_id": a.chat,
            "msg_type": "text",
            "content": json.dumps({"text": a.text}, ensure_ascii=False),
        },
        timeout=30,
    ).json()

    if r.get("code") == 0:
        print(f"Sent to {a.chat}: {r['data']['message_id']}")
    else:
        print(f"SEND-FAIL code={r.get('code')} msg={r.get('msg')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
