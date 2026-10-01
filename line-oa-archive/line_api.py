"""Authenticated LINE requests; never log credentials or raw error responses."""

import json
import os
import ssl
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import truststore
import channels


def request(path, payload=None, *, token=None):
    token = channels.access_token() if token is None else token
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


def get_message_content(message_id: str, *, token=None) -> tuple[bytes, str]:
    """Download binary message content (image, video, audio, file) from LINE api-data endpoint."""
    token = channels.access_token() if token is None else token
    if not token:
        raise ValueError("尚未設定 Channel access token。")
    req = Request(f"https://api-data.line.me/v2/bot/message/{message_id}/content", headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "LINE-Automation/1.0"
    })
    try:
        with urlopen(req, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=25) as response:
            content_type = response.headers.get_content_type() or "application/octet-stream"
            data = response.read(20 * 1024 * 1024)
            return data, content_type
    except HTTPError as error:
        status = error.code
        error.close()
        raise ValueError(f"LINE 媒體內容已過期或無法取得（HTTP {status}）。") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("LINE 媒體伺服器暫時無法連線。") from None
