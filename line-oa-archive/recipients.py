"""Recipient discovery and idempotent self-service weather subscriptions."""

import time
import sqlite3

COMMANDS = {"訂閱天氣", "取消訂閱", "取消訂閱天氣", "我的訂閱", "幫助"}


def migrate_contacts(conn):
    conn.execute("""INSERT OR IGNORE INTO recipients (recipient_id, kind)
                    SELECT conversation_id, conversation_type FROM line_messages
                    GROUP BY conversation_id, conversation_type""")


def handle_event(conn, event, source_type, recipient_id):
    event_type = event.get("type")
    if event_type not in {"message", "follow", "unfollow", "join", "leave"}:
        return None
    stamp = event.get("timestamp")
    stamp = int(stamp) if isinstance(stamp, (int, float)) else int(time.time() * 1000)
    active = int(event_type not in {"unfollow", "leave"})
    conn.execute("""INSERT INTO recipients (recipient_id, kind, active, event_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (recipient_id) DO UPDATE SET
                    active=CASE WHEN excluded.event_at >= event_at THEN excluded.active ELSE active END,
                    weather_subscribed=CASE WHEN excluded.event_at >= event_at AND excluded.active=0
                                            THEN 0 ELSE weather_subscribed END,
                    subscription_at=CASE WHEN excluded.event_at >= event_at AND excluded.active=0
                                         THEN MAX(subscription_at, excluded.event_at) ELSE subscription_at END,
                    event_at=MAX(event_at, excluded.event_at),
                    last_seen=strftime('%Y-%m-%dT%H:%M:%fZ', 'now')""",
                 (recipient_id, source_type, active, stamp))
    message = event.get("message") or {}
    if event_type != "message" or message.get("type") != "text" or not message.get("id"):
        return None
    command = "".join(str(message.get("text", "")).split())
    if command not in COMMANDS:
        return None
    message_id = str(message["id"])
    if conn.execute("SELECT 1 FROM subscription_commands WHERE message_id=?", (message_id,)).fetchone():
        return None
    if source_type != "user":
        response = "群組天氣訂閱由管理員設定。若要個人接收，請私訊我「訂閱天氣」。"
    else:
        if command in {"訂閱天氣", "取消訂閱", "取消訂閱天氣"}:
            conn.execute("""UPDATE recipients SET weather_subscribed=?, subscription_at=?
                            WHERE recipient_id=? AND active=1 AND subscription_at <= ?""",
                         (int(command == "訂閱天氣"), stamp, recipient_id, stamp))
        subscribed = conn.execute("SELECT weather_subscribed FROM recipients WHERE recipient_id=?", (recipient_id,)).fetchone()[0]
        if command == "幫助":
            response = "可用指令：\n訂閱天氣：加入天氣通知名單\n取消訂閱：停止天氣通知\n我的訂閱：查看目前狀態\n目前由管理員發送報告，尚未設定每日自動排程。"
        else:
            response = ("目前已訂閱天氣通知。管理員發送報告時會通知你。\n可傳「取消訂閱」停止通知。"
                        if subscribed else "目前未訂閱天氣通知。可傳「訂閱天氣」加入。")
    conn.execute("INSERT INTO subscription_commands VALUES (?, ?, ?)", (message_id, recipient_id, response))
    token = event.get("replyToken")
    return (token, response) if token else None


def list_contacts(conn):
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(
        "SELECT * FROM recipients ORDER BY kind, COALESCE(NULLIF(alias,''), NULLIF(display_name,''), recipient_id)")]


def update_contact(conn, recipient_id, alias, subscribed):
    if not isinstance(alias, str) or len(alias) > 80 or type(subscribed) is not bool:
        raise ValueError("備註名稱最多 80 字，訂閱設定必須為勾選值。")
    row = conn.execute("SELECT active FROM recipients WHERE recipient_id=?", (recipient_id,)).fetchone()
    if not row:
        raise ValueError("找不到收件者，請先向 Bot 傳送訊息。")
    if subscribed and not row[0]:
        raise ValueError("已封鎖或已離開的聊天室不能加入訂閱。")
    conn.execute("UPDATE recipients SET alias=?, weather_subscribed=?, subscription_at=? WHERE recipient_id=?",
                 (alias.strip(), int(subscribed), int(time.time() * 1000), recipient_id))
