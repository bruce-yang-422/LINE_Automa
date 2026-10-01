"""Chat system for LINE Official Account Manager integration.

Follows small-team-first and single-PC architecture.
Centralized limits, SQLite persistence, and multi-OA channel isolation.
"""

import json
from pathlib import Path
import re
import time
import uuid
from datetime import datetime, timezone
import app
import channels
import line_api

MEDIA_CACHE_DIR = app.BASE_DIR / "data" / "media_cache"

LIMITS = {
    "canned_replies_per_oa": 100,
    "scheduled_messages_per_oa": 50,
    "messages_page_size": 50,
    "rooms_page_size": 50,
    "text_max_length": 5000,
}


def _parse_ts(val):
    if not val:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return 0.0


def list_chat_rooms(conn, status=None, query=None, limit=50, offset=0):
    """List chat rooms for the current channel with unread count and latest message preview."""
    limit = min(max(1, int(limit or 50)), 100)
    offset = max(0, int(offset or 0))

    # Fetch all recipients in current channel
    recipients_rows = conn.execute(
        """SELECT recipient_id, kind, display_name, alias, notes, active, last_seen
           FROM recipients
           WHERE channel_id=current_channel()"""
    ).fetchall()

    if not recipients_rows:
        return {"rooms": [], "total": 0, "unread_count": 0}

    # Fetch chat states
    state_rows = {
        r[0]: {"status": r[1], "last_read_at": r[2], "last_inbound_at": r[3]}
        for r in conn.execute(
            """SELECT chat_id, status, last_read_at, last_inbound_at
               FROM chat_state
               WHERE channel_id=current_channel()"""
        ).fetchall()
    }

    # Fetch latest message per conversation
    # SQLite subquery for last message
    last_msgs = {}
    msg_rows = conn.execute(
        """SELECT conversation_id, message_id, message_type, text_content, sent_at, received_at, direction, unsent_at
           FROM line_messages
           WHERE channel_id=current_channel()
           ORDER BY COALESCE(sent_at, received_at) DESC"""
    ).fetchall()

    # Track unread count per conversation
    unread_counts = {}
    for r in msg_rows:
        cid = r[0]
        if cid not in last_msgs:
            last_msgs[cid] = {
                "message_id": r[1],
                "message_type": r[2],
                "text_content": r[3],
                "sent_at": r[4] or r[5],
                "direction": r[6] or "inbound",
                "unsent_at": r[7],
            }
        
        # Calculate unread: inbound messages sent after last_read_at
        last_read = state_rows.get(cid, {}).get("last_read_at")
        msg_time = r[4] or r[5]
        if (r[6] or "inbound") == "inbound" and (not last_read or (_parse_ts(msg_time) > _parse_ts(last_read))):
            unread_counts[cid] = unread_counts.get(cid, 0) + 1

    # Fetch tags for contacts
    tags_by_recipient = {}
    try:
        tag_rows = conn.execute(
            """SELECT a.recipient_id, t.tag_id, t.name, t.color
               FROM contact_tag_assignments a
               JOIN contact_tags t ON a.tag_id=t.tag_id AND a.channel_id=t.channel_id
               WHERE a.channel_id=current_channel()"""
        ).fetchall()
        for tr in tag_rows:
            tags_by_recipient.setdefault(tr[0], []).append({
                "id": tr[1], "name": tr[2], "color": tr[3]
            })
    except Exception:
        pass

    rooms = []
    total_unreads = 0

    for r in recipients_rows:
        rid = r[0]
        kind = r[1]
        display_name = r[2]
        alias = r[3]
        notes = r[4]
        active = bool(r[5])
        last_seen = r[6]

        primary_name = alias or display_name or ("個人聊天室" if kind == "user" else "群組聊天室")
        st = state_rows.get(rid, {})
        c_status = st.get("status") or "open"
        unread_cnt = unread_counts.get(rid, 0)
        if unread_cnt > 0:
            total_unreads += unread_cnt

        last_m = last_msgs.get(rid)

        # Filter by status
        if status and status != "all":
            if status == "unread" and unread_cnt == 0:
                continue
            elif status == "pending" and c_status != "pending":
                continue
            elif status == "done" and c_status != "done":
                continue
            elif status == "open" and c_status not in ("open", "pending"):
                continue

        # Filter by search query
        if query:
            q = query.strip().lower()
            match_name = q in primary_name.lower() or q in (display_name or "").lower() or q in rid.lower()
            match_text = last_m and q in (last_m.get("text_content") or "").lower()
            match_tags = any(q in t["name"].lower() for t in tags_by_recipient.get(rid, []))
            if not (match_name or match_text or match_tags):
                continue

        rooms.append({
            "recipient_id": rid,
            "name": primary_name,
            "display_name": display_name,
            "alias": alias,
            "kind": kind,
            "active": active,
            "tags": tags_by_recipient.get(rid, []),
            "status": c_status,
            "unread_count": unread_cnt,
            "last_message": last_m,
            "last_activity_at": (last_m.get("sent_at") if last_m else None) or last_seen,
        })

    # Sort rooms by latest activity DESC
    rooms.sort(key=lambda x: str(x.get("last_activity_at") or ""), reverse=True)
    total_count = len(rooms)
    paginated_rooms = rooms[offset:offset + limit]

    return {
        "rooms": paginated_rooms,
        "total": total_count,
        "unread_count": total_unreads,
    }


def list_messages(conn, chat_id, limit=50, before_id=None):
    """List messages in a chat room, ordered chronologically for rendering."""
    limit = min(max(1, int(limit or 50)), 100)

    # Fetch recipient info
    rec_row = conn.execute(
        "SELECT kind, display_name, alias, active FROM recipients WHERE channel_id=current_channel() AND recipient_id=?",
        (chat_id,)
    ).fetchone()
    if not rec_row:
        return {"messages": [], "has_more": False}

    kind, display_name, alias, active = rec_row

    # Group members cache
    members_cache = {}
    if kind != "user":
        m_rows = conn.execute(
            "SELECT user_id, display_name, picture_url FROM group_member_cache WHERE channel_id=current_channel() AND group_id=?",
            (chat_id,)
        ).fetchall()
        for mr in m_rows:
            members_cache[mr[0]] = {"name": mr[1], "picture_url": mr[2]}

    query = """SELECT message_id, conversation_type, conversation_id, sender_user_id,
                      message_type, text_content, sent_at, received_at, unsent_at,
                      direction, sent_by, send_method, delivery_status, media_path, reply_token
               FROM line_messages
               WHERE channel_id=current_channel() AND conversation_id=?"""
    params = [chat_id]

    if before_id:
        target_row = conn.execute(
            "SELECT COALESCE(sent_at, received_at) FROM line_messages WHERE channel_id=current_channel() AND message_id=?",
            (before_id,)
        ).fetchone()
        if target_row:
            query += " AND COALESCE(sent_at, received_at) < ?"
            params.append(target_row[0])

    query += " ORDER BY COALESCE(sent_at, received_at) DESC LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(query, tuple(params)).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]

    # Calculate active replyToken if any (within 60s of latest inbound message)
    now_ts = time.time()
    active_reply_token = None
    reply_token_expires_in = 0

    messages = []
    for r in reversed(rows):
        msg_id = r[0]
        c_type = r[1]
        sender_uid = r[3]
        m_type = r[4]
        text = r[5]
        sent_at = r[6]
        recv_at = r[7]
        unsent_at = r[8]
        direction = r[9] or "inbound"
        sent_by = r[10]
        send_method = r[11]
        delivery_status = r[12]
        media_path = r[13]
        reply_token = r[14]

        sender_name = ""
        if direction == "outbound":
            sender_name = sent_by or "管理員"
        elif kind == "user":
            sender_name = alias or display_name or "使用者"
        else:
            sender_name = members_cache.get(sender_uid, {}).get("name") or (f"成員 {sender_uid[:6]}" if sender_uid else "成員")

        msg_time = sent_at or recv_at
        is_unsent = bool(unsent_at)

        # Check reply token validity
        if direction == "inbound" and reply_token and not is_unsent:
            try:
                # Parse sent_at / recv_at ISO to timestamp
                iso_str = sent_at or recv_at
                if iso_str:
                    msg_dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                    diff = now_ts - msg_dt.timestamp()
                    if 0 <= diff < 60:
                        active_reply_token = reply_token
                        reply_token_expires_in = int(60 - diff)
            except Exception:
                pass

        messages.append({
            "message_id": msg_id,
            "direction": direction,
            "sender_user_id": sender_uid,
            "sender_name": sender_name,
            "message_type": m_type,
            "text_content": "[對方已收回訊息]" if is_unsent else text,
            "sent_at": msg_time,
            "is_unsent": is_unsent,
            "sent_by": sent_by,
            "send_method": send_method,
            "delivery_status": delivery_status,
            "media_path": media_path,
        })

    # Fetch chat state
    st_row = conn.execute(
        "SELECT status, last_read_at FROM chat_state WHERE channel_id=current_channel() AND chat_id=?",
        (chat_id,)
    ).fetchone()

    return {
        "messages": messages,
        "has_more": has_more,
        "chat_status": st_row[0] if st_row else "open",
        "last_read_at": st_row[1] if st_row else None,
        "active_reply_token": active_reply_token,
        "reply_token_expires_in": reply_token_expires_in,
    }


def mark_chat_read(conn, chat_id):
    """Mark a chat room as read for the team."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO chat_state (channel_id, chat_id, status, last_read_at, updated_at)
           VALUES (current_channel(), ?, 'open', ?, ?)
           ON CONFLICT(channel_id, chat_id) DO UPDATE
           SET last_read_at=excluded.last_read_at, updated_at=excluded.updated_at""",
        (chat_id, now_iso, now_iso)
    )
    return {"ok": True, "read_at": now_iso}


def set_chat_status(conn, chat_id, status, actor):
    """Update chat status: 'open', 'pending', 'done'."""
    if status not in ("open", "pending", "done"):
        raise ValueError("聊天狀態無效，僅支援 open, pending, done。")

    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO chat_state (channel_id, chat_id, status, updated_by, updated_at)
           VALUES (current_channel(), ?, ?, ?, ?)
           ON CONFLICT(channel_id, chat_id) DO UPDATE
           SET status=excluded.status, updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
        (chat_id, status, actor, now_iso)
    )
    return {"ok": True, "status": status, "updated_at": now_iso}


def send_chat_message(conn, chat_id, text, actor, use_reply_token=True):
    """Send a reply or push text message to a chat room and record in line_messages."""
    text = (text or "").strip()
    if not text:
        raise ValueError("訊息內容不可為空。")
    if len(text) > LIMITS["text_max_length"]:
        raise ValueError(f"文字訊息超過上限 {LIMITS['text_max_length']} 字。")

    # Verify recipient exists and is active
    rec_row = conn.execute(
        "SELECT kind, active FROM recipients WHERE channel_id=current_channel() AND recipient_id=?",
        (chat_id,)
    ).fetchone()
    if not rec_row:
        raise ValueError("找不到指定的聊天室。")
    if not rec_row[1]:
        raise ValueError("此聊天室已封鎖或已離開，無法傳送訊息。")

    kind = rec_row[0]

    # Check for valid reply_token
    chosen_token = None
    if use_reply_token:
        # Find latest inbound message with non-empty reply_token within 60s
        token_row = conn.execute(
            """SELECT message_id, reply_token, COALESCE(sent_at, received_at)
               FROM line_messages
               WHERE channel_id=current_channel() AND conversation_id=? AND direction='inbound' AND reply_token != ''
               ORDER BY COALESCE(sent_at, received_at) DESC LIMIT 1""",
            (chat_id,)
        ).fetchone()
        if token_row:
            token_msg_id, token_val, msg_time = token_row
            try:
                msg_dt = datetime.fromisoformat(msg_time.replace("Z", "+00:00"))
                if time.time() - msg_dt.timestamp() < 55:  # Buffer of 5s
                    chosen_token = token_val
            except Exception:
                pass

    import line_api
    send_method = "push"
    message_id = "out_" + uuid.uuid4().hex[:16]
    now_iso = datetime.now(timezone.utc).isoformat()

    if chosen_token:
        try:
            line_api.request(
                "message/reply",
                {"replyToken": chosen_token, "messages": [{"type": "text", "text": text}]}
            )
            send_method = "reply"
            # Clear used reply_token from database to prevent reuse
            conn.execute(
                "UPDATE line_messages SET reply_token='' WHERE channel_id=current_channel() AND reply_token=?",
                (chosen_token,)
            )
        except Exception as exc:
            # If reply fails, do not automatically push; bubble up error
            raise ValueError(f"免費回覆失敗（Token 可能已過期或已使用）：{exc}")
    else:
        # Push message
        line_api.request(
            "message/push",
            {"to": chat_id, "messages": [{"type": "text", "text": text}]}
        )
        send_method = "push"

    # Record outbound message in line_messages
    conn.execute(
        """INSERT INTO line_messages
           (channel_id, message_id, conversation_type, conversation_id,
            message_type, text_content, sent_at, received_at,
            direction, sent_by, send_method, delivery_status)
           VALUES (current_channel(), ?, ?, ?, 'text', ?, ?, ?, 'outbound', ?, ?, 'sent')""",
        (message_id, kind, chat_id, text, now_iso, now_iso, actor, send_method)
    )

    # Mark as read
    conn.execute(
        """INSERT INTO chat_state (channel_id, chat_id, status, last_read_at, updated_at)
           VALUES (current_channel(), ?, 'open', ?, ?)
           ON CONFLICT(channel_id, chat_id) DO UPDATE
           SET last_read_at=excluded.last_read_at, updated_at=excluded.updated_at""",
        (chat_id, now_iso, now_iso)
    )

    return {
        "ok": True,
        "message_id": message_id,
        "send_method": send_method,
        "sent_at": now_iso,
        "text": text,
    }


def list_canned_replies(conn, category=None, search=None):
    """List canned reply templates for the current channel."""
    query = "SELECT reply_id, title, category, content, created_by, updated_at FROM canned_replies WHERE channel_id=current_channel()"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if search:
        query += " AND (title LIKE ? OR content LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY category, title"
    rows = conn.execute(query, tuple(params)).fetchall()

    return {
        "replies": [
            {
                "id": r[0],
                "title": r[1],
                "category": r[2],
                "content": r[3],
                "created_by": r[4],
                "updated_at": r[5],
            }
            for r in rows
        ],
        "count": len(rows),
        "limit": LIMITS["canned_replies_per_oa"],
    }


def save_canned_reply(conn, data, actor):
    """Save or create a canned reply template."""
    reply_id = (data.get("id") or data.get("reply_id") or "").strip()
    title = (data.get("title") or "").strip()
    category = (data.get("category") or "").strip()
    content = (data.get("content") or data.get("text") or "").strip()

    if not title or len(title) > 40:
        raise ValueError("預設訊息標題請填寫 1 至 40 字。")
    if not content or len(content) > LIMITS["text_max_length"]:
        raise ValueError(f"預設訊息內容請填寫 1 至 {LIMITS['text_max_length']} 字。")
    if len(category) > 20:
        raise ValueError("分類名稱請限制在 20 字以內。")

    now_iso = datetime.now(timezone.utc).isoformat()

    if reply_id:
        row = conn.execute(
            "SELECT reply_id FROM canned_replies WHERE channel_id=current_channel() AND reply_id=?",
            (reply_id,)
        ).fetchone()
        if not row:
            raise ValueError("找不到此預設訊息。")
        conn.execute(
            """UPDATE canned_replies
               SET title=?, category=?, content=?, updated_by=?, updated_at=?
               WHERE channel_id=current_channel() AND reply_id=?""",
            (title, category, content, actor, now_iso, reply_id)
        )
        return {"id": reply_id, "title": title, "category": category, "content": content}
    else:
        count = conn.execute(
            "SELECT COUNT(*) FROM canned_replies WHERE channel_id=current_channel()"
        ).fetchone()[0]
        if count >= LIMITS["canned_replies_per_oa"]:
            raise ValueError(f"每個 LINE OA 最多建立 {LIMITS['canned_replies_per_oa']} 則預設訊息。")

        new_id = "canned_" + uuid.uuid4().hex[:12]
        conn.execute(
            """INSERT INTO canned_replies
               (channel_id, reply_id, title, category, content, created_by, updated_by, created_at, updated_at)
               VALUES (current_channel(), ?, ?, ?, ?, ?, ?, ?, ?)""",
            (new_id, title, category, content, actor, actor, now_iso, now_iso)
        )
        return {"id": new_id, "title": title, "category": category, "content": content}


def delete_canned_reply(conn, reply_id):
    """Delete a canned reply template."""
    conn.execute(
        "DELETE FROM canned_replies WHERE channel_id=current_channel() AND reply_id=?",
        (reply_id,)
    )
    return {"ok": True}


def get_response_hours(conn):
    """Get response hours configuration for the current channel."""
    row = conn.execute(
        "SELECT enabled, timezone, weekly, holidays FROM response_hours WHERE channel_id=current_channel()"
    ).fetchone()
    if not row:
        return {
            "enabled": False,
            "timezone": "Asia/Taipei",
            "weekly": {},
            "holidays": [],
        }
    return {
        "enabled": bool(row[0]),
        "timezone": row[1] or "Asia/Taipei",
        "weekly": json.loads(row[2] or "{}"),
        "holidays": json.loads(row[3] or "[]"),
    }


def save_response_hours(conn, data):
    """Save response hours configuration."""
    enabled = int(bool(data.get("enabled")))
    tz = (data.get("timezone") or "Asia/Taipei").strip()
    weekly = json.dumps(data.get("weekly") or {})
    holidays = json.dumps(data.get("holidays") or [])
    now_iso = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT INTO response_hours (channel_id, enabled, timezone, weekly, holidays, updated_at)
           VALUES (current_channel(), ?, ?, ?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE
           SET enabled=excluded.enabled, timezone=excluded.timezone, weekly=excluded.weekly,
               holidays=excluded.holidays, updated_at=excluded.updated_at""",
        (enabled, tz, weekly, holidays, now_iso)
    )
    return {"ok": True}


def cache_group_member(conn, group_id, user_id, display_name, picture_url=""):
    """Cache group member name and picture."""
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO group_member_cache (channel_id, group_id, user_id, display_name, picture_url, fetched_at)
           VALUES (current_channel(), ?, ?, ?, ?, ?)
           ON CONFLICT(channel_id, group_id, user_id) DO UPDATE
           SET display_name=excluded.display_name, picture_url=excluded.picture_url, fetched_at=excluded.fetched_at""",
        (group_id, user_id, display_name, picture_url or "", now_iso)
    )


def get_chat_media(conn, message_id: str) -> tuple[bytes, str]:
    """Get binary media data and mime type for a message (from local cache or LINE Content API)."""
    channel_id = channels.current_id()
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = MEDIA_CACHE_DIR / f"{channel_id}_{message_id}.bin"
    meta_file = MEDIA_CACHE_DIR / f"{channel_id}_{message_id}.json"

    if cache_file.exists() and meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            return cache_file.read_bytes(), meta.get("content_type", "application/octet-stream")
        except Exception:
            pass

    # Download from LINE API
    data, content_type = line_api.get_message_content(message_id)
    try:
        cache_file.write_bytes(data)
        meta_file.write_text(
            json.dumps({"content_type": content_type, "cached_at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8"
        )
    except Exception:
        pass
    return data, content_type
