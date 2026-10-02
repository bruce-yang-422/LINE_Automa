"""Publish PNG snapshots for LINE and send push messages; used by the admin service dispatcher."""

import json
from pathlib import Path
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import truststore

ROOT = Path(__file__).resolve().parent
MAX_IMAGE_BYTES = 1_000_000  # Same PNG serves as original and preview; preview limit is 1 MB.


def publish_image(source, base_url):
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("PUBLIC_BASE_URL 必須是 HTTPS 網站根網址。")
    with source.open("rb") as stream:
        data = stream.read(MAX_IMAGE_BYTES + 1)
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("圖片必須是 PNG 格式。")
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("本版共用原圖與預覽圖，PNG 必須小於或等於 1 MB；請先縮小圖片。")
    folder = ROOT / "published-images"
    folder.mkdir(exist_ok=True)
    filename = uuid4().hex + ".png"
    temporary = folder / (filename + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(folder / filename)
    return base_url.rstrip("/") + "/images/" + filename, data


def verify_public_image(url, expected):
    try:
        request = Request(url, headers={"User-Agent": "LINE-Automation/1.0"})
        with urlopen(request, timeout=15, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
            if response.headers.get_content_type() != "image/png" or response.read(MAX_IMAGE_BYTES + 1) != expected:
                raise ValueError("公開圖片內容不符，尚未發送。請確認 Tunnel 路由與快取設定。")
    except (HTTPError, URLError, TimeoutError) as error:
        if isinstance(error, HTTPError):
            error.close()
        raise ValueError("公開圖片無法讀取，尚未發送。請先重啟 LINE 服務並確認公開連線。") from None


def send_push(token, recipient, image_url, retry_key=None, text=None, messages=None):
    if messages is None:
        messages = [{"type": "text", "text": text}] if text is not None else [{"type": "image", "originalContentUrl": image_url,
                                                                                "previewImageUrl": image_url}]
    body = json.dumps({"to": recipient, "messages": messages}).encode()
    retry_key = retry_key or str(uuid4())
    request = Request("https://api.line.me/v2/bot/message/push", data=body, headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json", "X-Line-Retry-Key": retry_key,
        "User-Agent": "LINE-Automation/1.0"})
    try:
        with urlopen(request, timeout=20, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
            if response.status != 200:
                raise ValueError("LINE 回應非預期狀態，請先確認聊天室，避免重複發送。")
            return response.headers.get("x-line-request-id", "")
    except HTTPError as error:
        status = error.code
        error.close()
        if status >= 500:
            raise ValueError(f"LINE 暫時異常（HTTP {status}），送達狀態不明；請先確認聊天室，不會自動重送。") from None
        raise ValueError(f"LINE 拒絕請求（HTTP {status}）：請檢查 access token、發送對象與訊息額度。不會自動重送。") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("LINE 請求連線中斷，送達狀態不明；請先確認聊天室，不會自動重送。") from None
