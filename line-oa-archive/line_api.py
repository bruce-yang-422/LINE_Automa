"""Authenticated LINE requests; never log credentials or raw error responses."""

import json
import os
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import truststore


def request(path, payload=None):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise ValueError("尚未設定 Channel access token。")
    data = None if payload is None else json.dumps(payload).encode()
    req = Request("https://api.line.me/v2/bot/" + path, data=data, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json", "User-Agent": "LINE-Automation/1.0"})
    try:
        with urlopen(req, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=10) as response:
            return json.load(response)
    except HTTPError as error:
        status = error.code
        error.close()
        raise ValueError(f"LINE API 未接受請求（HTTP {status}）。") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("LINE API 暫時無法連線。") from None


def reply(token, text):
    request("message/reply", {"replyToken": token, "messages": [{"type": "text", "text": text}]})
