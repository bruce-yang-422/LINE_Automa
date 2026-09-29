-- 時間以 UTC ISO 8601 文字格式儲存。
CREATE TABLE IF NOT EXISTS line_messages (
    message_id TEXT PRIMARY KEY NOT NULL,
    conversation_type TEXT NOT NULL CHECK (conversation_type IN ('user', 'group', 'room')),
    conversation_id TEXT NOT NULL,
    sender_user_id TEXT,
    message_type TEXT NOT NULL,
    text_content TEXT,
    sent_at TEXT,
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    unsent_at TEXT
);

CREATE INDEX IF NOT EXISTS line_messages_conversation_time_idx
    ON line_messages (conversation_type, conversation_id, sent_at DESC);
