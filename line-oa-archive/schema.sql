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

CREATE TABLE IF NOT EXISTS recipients (
    recipient_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('user', 'group', 'room')),
    display_name TEXT NOT NULL DEFAULT '',
    alias TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    weather_subscribed INTEGER NOT NULL DEFAULT 0,
    event_at INTEGER NOT NULL DEFAULT 0,
    subscription_at INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS subscription_commands (
    message_id TEXT PRIMARY KEY,
    recipient_id TEXT NOT NULL,
    response TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS send_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    audience TEXT NOT NULL,
    image_path TEXT NOT NULL,
    image_url TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS send_deliveries (
    job_id TEXT NOT NULL REFERENCES send_jobs(job_id),
    recipient_id TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_key TEXT NOT NULL,
    request_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job_id, recipient_id)
);
