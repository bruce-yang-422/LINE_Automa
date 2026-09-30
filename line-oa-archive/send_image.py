"""Publish a PNG snapshot and push it to one explicitly selected LINE chat."""

import argparse
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import truststore

from control_runtime import load_settings

ROOT = Path(__file__).resolve().parent
MAX_IMAGE_BYTES = 1_000_000  # Same PNG serves as original and preview; preview limit is 1 MB.


def chat_ids(kind):
    path = Path(os.environ.get("DATABASE_PATH", "data/line_archive.db"))
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        return [row[0] for row in connection.execute(
            "SELECT DISTINCT conversation_id FROM line_messages WHERE conversation_type=? ORDER BY conversation_id", (kind,))]


def select_recipient(kind):
    configured = os.environ.get("LINE_PUSH_USER_ID" if kind == "user" else "LINE_PUSH_GROUP_ID", "").strip()
    candidates = [configured] if configured else chat_ids(kind)
    if len(candidates) != 1:
        raise ValueError("找不到唯一收件者：請先向 Bot 傳送測試訊息；多位收件者請使用控制台的「收件者與發送」，或 --target subscribers。")
    prefix = "U" if kind == "user" else "C"
    if not re.fullmatch(prefix + r"[0-9a-fA-F]{32}", candidates[0]):
        raise ValueError("收件者 ID 格式不正確；請使用 Webhook 的 userId 或 groupId。")
    return candidates[0]


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
        raise ValueError(f"LINE 拒絕請求（HTTP {status}）：請檢查 access token、收件者與訊息額度。不會自動重送。") from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("LINE 請求連線中斷，送達狀態不明；請先確認聊天室，不會自動重送。") from None


def send_to_subscribers(image):
    access_file = ROOT / "instance" / "admin-access.json"
    if not access_file.exists():
        raise ValueError("請先啟動 LINE 服務，訂閱名單由本機管理服務發送。")
    access = json.loads(access_file.read_text(encoding="utf-8"))
    base = f"http://127.0.0.1:{int(access['port'])}"
    headers = {"Authorization": "Bearer " + access["token"], "Content-Type": "application/json"}
    job_id = str(uuid4())
    payload = {"job_id": job_id, "audience": "subscribers", "ids": [], "image_path": str(image.resolve())}
    try:
        with urlopen(Request(base + "/api/send", data=json.dumps(payload).encode(), headers=headers), timeout=30) as response:
            job = json.load(response)
        print("已建立天氣訂閱發送工作：" + job_id, flush=True)
        deadline = time.monotonic() + 300
        while job["status"] in {"queued", "running"}:
            if time.monotonic() > deadline:
                raise ValueError("發送工作仍在進行，請到管理頁查看，不要重複執行。")
            time.sleep(1)
            with urlopen(Request(base + "/api/jobs/" + job_id, headers=headers), timeout=10) as response:
                job = json.load(response)["jobs"][0]
        for row in job["deliveries"]:
            print(row["label"] + "：" + row["status"])
        if job["status"] != "finished" or any(row["status"] not in {"accepted", "cancelled"} for row in job["deliveries"]):
            raise ValueError("部分發送未完成，請查看管理頁紀錄；不要整批重送。")
    except HTTPError as error:
        try:
            message = json.load(error).get("error", "本機管理服務未接受請求。")
        except (ValueError, AttributeError):
            message = "本機管理服務未接受請求。"
        finally:
            error.close()
        raise ValueError(message) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("本機管理連線中斷，請先查看管理頁發送紀錄，避免重複發送。") from None
    return 0


def main():
    parser = argparse.ArgumentParser(description="將一張 PNG 傳給 LINE 個人或群組；一次只傳一個目標。")
    parser.add_argument("image", type=Path, nargs="?")
    parser.add_argument("--target", choices=("user", "group", "both", "subscribers"))
    parser.add_argument("--list-targets", action="store_true", help="列出已收到訊息的聊天室 ID，不發送")
    parser.add_argument("--prepare-only", action="store_true", help="只發布並檢查圖片網址，不向 LINE 發送")
    args = parser.parse_args()
    load_settings()
    if args.list_targets:
        for kind in ("user", "group"):
            ids = chat_ids(kind)
            print(kind + ": " + (", ".join(ids) if ids else "尚未收到訊息"))
        return 0
    if args.image is None or (not args.prepare_only and args.target is None):
        parser.error("請指定圖片與 --target user/group/both/subscribers；也可用 --prepare-only 測試圖片連線。")
    if args.target == "subscribers" and not args.prepare_only:
        return send_to_subscribers(args.image)
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    recipients = []
    if not args.prepare_only:
        if not token:
            raise ValueError("請先在 line-oa-archive/.env 填入 LINE_CHANNEL_ACCESS_TOKEN；Channel secret 不能代替它。")
        targets = ("user", "group") if args.target == "both" else (args.target,)
        # Resolve every recipient first, so a missing group cannot cause a partial send.
        recipients = [(kind, select_recipient(kind)) for kind in targets]
    modified = datetime.fromtimestamp(args.image.stat().st_mtime).astimezone()
    print("圖片最後修改時間：" + modified.isoformat(timespec="seconds"))
    url, data = publish_image(args.image, os.environ.get("PUBLIC_BASE_URL", "https://reports.stack-base.com"))
    verify_public_image(url, data)
    print("圖片公開連線正常：" + url)
    if args.prepare_only:
        print("只完成圖片準備，未發送 LINE 訊息。")
        return 0
    for kind, recipient in recipients:
        try:
            request_id = send_push(token, recipient, url)
        except ValueError:
            print(f"發送在 {kind} 中止；若前面的聊天室已接受請求，請勿整批重送。", file=sys.stderr)
            raise
        print(f"LINE 已接受圖片發送請求（{kind}）。請在聊天室確認圖片；request ID：{request_id}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except (ValueError, OSError, sqlite3.Error) as error:
        # ValueError messages above are controlled; other errors may contain local details.
        print(str(error) if isinstance(error, ValueError) else "讀取檔案或資料庫失敗，請確認圖片路徑、設定與權限。", file=sys.stderr)
        raise SystemExit(1)
