"""關鍵字訂閱：聯絡對象在 LINE 傳關鍵字訂閱或取消報告，並輸出名冊給外部 Python 發送腳本。

- 主題、關鍵字與白名單／黑名單定義在 subscribers/topics.json，改檔即生效，不需改程式或重啟。
- 訂閱狀態以資料庫（topic_subscriptions）為準；名冊 subscribers/<主題>.json 只列出
  「已訂閱、目前有資格、未封鎖」的對象，於訂閱變更後與每 60 秒重算。
- 另輸出 subscribers/_contacts.json（所有聯絡對象的 ID、名稱、標籤），方便填寫白名單。

規格見 docs/功能規格/關鍵字訂閱.md。
"""
import json
import os
import re
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import app

EXPORT_INTERVAL = 60  # 名冊定期重算間隔（秒）
KEY_PATTERN = re.compile(r"[a-z0-9_-]{1,40}")
ID_PATTERN = re.compile(r"[UCR][0-9a-fA-F]{32}")

_lock = threading.Lock()
_cache = {"mtime": None, "config": None, "error": ""}
_last_export = 0.0


def folder():
    # 跟著 app.BASE_DIR 走，測試或其他安裝位置不會寫到正式資料夾。
    return app.BASE_DIR / "subscribers"


def normalize(text):
    return "".join(str(text).split())


def _rule(value, where):
    if value is None:
        return {"tags": [], "ids": []}
    if not isinstance(value, dict) or set(value) - {"tags", "ids"}:
        raise ValueError(f"{where} 只能有 tags 與 ids。")
    rule = {}
    for field in ("tags", "ids"):
        items = value.get(field, [])
        if not isinstance(items, list) or any(not isinstance(i, str) or not i.strip() for i in items):
            raise ValueError(f"{where}.{field} 必須是文字陣列。")
        if field == "ids" and any(not ID_PATTERN.fullmatch(i.strip()) for i in items):
            raise ValueError(f"{where}.ids 含有格式不正確的 LINE ID。")
        rule[field] = [i.strip() for i in items]
    return rule


def parse_config(data):
    """檢查 topics.json 內容；格式錯誤時以可讀訊息拋出 ValueError。"""
    if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
        raise ValueError("topics.json 需要 topics 陣列。")
    status = [normalize(k) for k in data.get("status_keywords", ["我的訂閱"])]
    if not all(status):
        raise ValueError("status_keywords 不可有空白關鍵字。")
    seen_keys, seen_words = set(), {w: "status_keywords" for w in status}
    topics = []
    for index, item in enumerate(data["topics"]):
        where = f"topics[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} 必須是物件。")
        key, name = item.get("key"), item.get("name")
        if not isinstance(key, str) or not KEY_PATTERN.fullmatch(key) or key in seen_keys:
            raise ValueError(f"{where}.key 必須是不重複的小寫英數字、- 或 _（最多 40 字）。")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
            raise ValueError(f"{where}.name 必須是 1–40 字。")
        words = {}
        for field in ("subscribe", "unsubscribe"):
            values = item.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not normalize(v) for v in values):
                raise ValueError(f"{where}.{field} 必須是文字陣列。")
            words[field] = [normalize(v) for v in values]
            for word in words[field]:
                if word in seen_words:
                    raise ValueError(f"關鍵字「{word}」重複出現在 {seen_words[word]} 與 {where}。")
                seen_words[word] = where
        if not words["subscribe"]:
            raise ValueError(f"{where}.subscribe 至少要有一個關鍵字。")
        allow = item.get("allow")
        if allow != "all":
            allow = _rule(allow, where + ".allow")
        groups = item.get("groups", False)
        if type(groups) is not bool:
            raise ValueError(f"{where}.groups 必須是 true 或 false。")
        topics.append({"key": key, "name": name.strip(), **words, "allow": allow,
                       "deny": _rule(item.get("deny"), where + ".deny"), "groups": groups})
        seen_keys.add(key)
    return {"status_keywords": status, "topics": topics}


def load_config():
    """回傳最後一份有效設定；檔案改壞時沿用上一份規則，並記錄一次錯誤。"""
    path = folder() / "topics.json"
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        _cache.update(mtime=None, config=None, error="")
        return None
    if mtime != _cache["mtime"]:
        _cache["mtime"] = mtime
        try:
            _cache["config"] = parse_config(json.loads(path.read_text(encoding="utf-8-sig")))
            _cache["error"] = ""
        except (OSError, ValueError) as exc:
            _cache["error"] = str(exc)
            print(f"[subscriptions] topics.json 無效，沿用上一份設定：{exc}", file=sys.stderr)
    return _cache["config"]


def _contact(conn, channel_id, recipient_id):
    row = conn.execute("SELECT kind,active FROM recipients WHERE channel_id=? AND recipient_id=?",
                       (channel_id, recipient_id)).fetchone()
    tags = {r[0] for r in conn.execute("""SELECT t.name FROM contact_tag_assignments a
        JOIN contact_tags t ON t.tag_id=a.tag_id AND t.channel_id=a.channel_id
        WHERE a.channel_id=? AND a.recipient_id=?""", (channel_id, recipient_id))}
    return (row[0] if row else "user"), bool(row and row[1]), tags


def _matches(rule, recipient_id, tags):
    return recipient_id in rule["ids"] or bool(tags & set(rule["tags"]))


def eligible(topic, recipient_id, kind, tags):
    """黑名單優先於白名單；群組與多人聊天室需 groups=true；沒有 allow 時沒有人能訂閱。"""
    if kind != "user" and not topic["groups"]:
        return False
    if _matches(topic["deny"], recipient_id, tags):
        return False
    return topic["allow"] == "all" or _matches(topic["allow"], recipient_id, tags)


def handle_event(conn, event, source_type, recipient_id):
    """處理封鎖／離開與關鍵字訊息；需要回覆時傳回 (replyToken, 文字)，否則傳回 None。"""
    import channels
    channel_id = channels.current_id()
    stamp = event.get("timestamp")
    stamp = int(stamp) if isinstance(stamp, (int, float)) else int(time.time() * 1000)
    if event.get("type") in {"unfollow", "leave"}:
        conn.execute("""UPDATE topic_subscriptions SET subscribed=0,updated_at=?
            WHERE channel_id=? AND recipient_id=? AND updated_at<=?""", (stamp, channel_id, recipient_id, stamp))
        return None
    message = event.get("message") or {}
    if event.get("type") != "message" or message.get("type") != "text" or not message.get("id"):
        return None
    config = load_config()
    if not config:
        return None
    word = normalize(message.get("text", ""))
    topic = next((t for t in config["topics"] if word in t["subscribe"] or word in t["unsubscribe"]), None)
    if topic is None and word not in config["status_keywords"]:
        return None
    message_id = str(message["id"])
    if conn.execute("SELECT 1 FROM subscription_commands WHERE channel_id=? AND message_id=?",
                    (channel_id, message_id)).fetchone():
        return None  # LINE 重送的同一則訊息：已處理並回覆過。
    kind, _active, tags = _contact(conn, channel_id, recipient_id)
    kind = source_type if source_type in {"group", "room"} else kind
    if topic is None:
        reply = status_reply(conn, config, channel_id, recipient_id, kind, tags)
    elif word in topic["subscribe"]:
        if eligible(topic, recipient_id, kind, tags):
            _set(conn, channel_id, recipient_id, topic["key"], 1, stamp)
            reply = f"已訂閱「{topic['name']}」。" + (f"取消請傳「{topic['unsubscribe'][0]}」。" if topic["unsubscribe"] else "")
        elif kind != "user" and not topic["groups"]:
            reply = f"「{topic['name']}」只開放個人訂閱，請私訊我「{topic['subscribe'][0]}」。"
        else:
            reply = f"你沒有訂閱「{topic['name']}」的權限，如有需要請聯絡管理員。"
    else:
        _set(conn, channel_id, recipient_id, topic["key"], 0, stamp)
        reply = f"已取消訂閱「{topic['name']}」。"
    conn.execute("INSERT INTO subscription_commands(channel_id,message_id,recipient_id,response) VALUES (?,?,?,?)",
                 (channel_id, message_id, recipient_id, reply))
    token = event.get("replyToken")
    return (token, reply) if token else None


def _set(conn, channel_id, recipient_id, key, subscribed, stamp):
    # 亂序到達的舊事件不會蓋掉較新的選擇。
    conn.execute("""INSERT INTO topic_subscriptions(channel_id,recipient_id,topic,subscribed,updated_at)
        VALUES (?,?,?,?,?) ON CONFLICT(channel_id,recipient_id,topic) DO UPDATE SET
        subscribed=excluded.subscribed,updated_at=excluded.updated_at
        WHERE excluded.updated_at>=topic_subscriptions.updated_at""", (channel_id, recipient_id, key, subscribed, stamp))


def status_reply(conn, config, channel_id, recipient_id, kind, tags):
    current = {r[0] for r in conn.execute("SELECT topic FROM topic_subscriptions WHERE channel_id=? AND recipient_id=? AND subscribed=1",
                                          (channel_id, recipient_id))}
    usable = [t for t in config["topics"] if eligible(t, recipient_id, kind, tags)]
    mine = [t["name"] for t in usable if t["key"] in current]
    lines = ["目前訂閱：" + "、".join(mine) if mine else "目前沒有訂閱。"]
    if usable:
        lines.append("可用指令：")
        lines += [f"{t['name']}：傳「{t['subscribe'][0]}」" + (f"，取消傳「{t['unsubscribe'][0]}」" if t["unsubscribe"] else "") for t in usable]
    return "\n".join(lines)


def _write_json(path, payload, compare_key):
    """以暫存檔加替換寫入；內容沒變時不改寫，讓讀取的腳本看到穩定的檔案。"""
    try:
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get(compare_key) == payload[compare_key] and old.get("name") == payload.get("name"):
            return False
    except (OSError, ValueError):
        pass
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(temp, path)
            return True
        except PermissionError:
            # Windows 上讀取中的程式可能短暫鎖住檔案，稍後重試。
            time.sleep(0.1 * (attempt + 1))
    temp.unlink(missing_ok=True)
    return False


def export():
    """重算每個主題的 subscribers/<主題>.json，並輸出查 ID 與標籤用的 _contacts.json。"""
    global _last_export
    config = load_config()
    with _lock:
        _last_export = time.monotonic()
        target = folder()
        target.mkdir(exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        with app.database_connection() as conn:
            contacts = conn.execute("""SELECT r.channel_id,c.name,c.basic_id,r.recipient_id,r.kind,r.active,
                    COALESCE(NULLIF(r.custom_name,''),NULLIF(r.display_name,''),'') AS label
                FROM recipients r JOIN line_channels c ON c.channel_id=r.channel_id
                WHERE c.active=1 ORDER BY c.name,r.kind,label,r.recipient_id""").fetchall()
            tags = {}
            for channel_id, recipient_id, tag in conn.execute("""SELECT a.channel_id,a.recipient_id,t.name FROM contact_tag_assignments a
                    JOIN contact_tags t ON t.tag_id=a.tag_id AND t.channel_id=a.channel_id ORDER BY t.name"""):
                tags.setdefault((channel_id, recipient_id), []).append(tag)
            subscribed = {}
            for channel_id, recipient_id, topic, updated in conn.execute(
                    "SELECT channel_id,recipient_id,topic,updated_at FROM topic_subscriptions WHERE subscribed=1"):
                subscribed[(channel_id, recipient_id, topic)] = updated
        def entry(row):
            return {"channel_id": row[0], "oa_name": row[1], "oa_basic_id": row[2], "recipient_id": row[3],
                    "kind": row[4], "name": row[6], "tags": tags.get((row[0], row[3]), [])}
        _write_json(target / "_contacts.json", {"generated_at": now, "contacts": [
            {**entry(r), "active": bool(r[5])} for r in contacts]}, "contacts")
        for topic in (config or {}).get("topics", []):
            rows = []
            for r in contacts:
                stamp = subscribed.get((r[0], r[3], topic["key"]))
                if stamp is None or not r[5] or not eligible(topic, r[3], r[4], set(tags.get((r[0], r[3]), []))):
                    continue
                rows.append({**entry(r), "subscribed_at": datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()})
            _write_json(target / f"{topic['key']}.json",
                        {"topic": topic["key"], "name": topic["name"], "generated_at": now, "subscribers": rows}, "subscribers")
        if config:
            # 主題從設定移除後刪掉舊名冊，避免腳本讀到過期名單；只刪本模組產生的名冊檔。
            keys = {t["key"] for t in config["topics"]}
            for path in target.glob("*.json"):
                if path.stem in keys or path.name in {"topics.json", "topics.example.json", "_contacts.json"}:
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if isinstance(data, dict) and data.get("topic") == path.stem and "subscribers" in data:
                    path.unlink(missing_ok=True)


def periodic_export():
    if time.monotonic() - _last_export >= EXPORT_INTERVAL:
        export()
