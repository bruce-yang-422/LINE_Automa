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

CREATE TABLE IF NOT EXISTS report_sources (
    report_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    source_path TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE IF NOT EXISTS workspace_users (
    email TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK(role IN ('administrator','company_admin','sender','employee')),
    company TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS organizations (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'company',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    reports_enabled INTEGER NOT NULL DEFAULT 1 CHECK(reports_enabled IN (0,1)),
    messaging_enabled INTEGER NOT NULL DEFAULT 1 CHECK(messaging_enabled IN (0,1)),
    weather_enabled INTEGER NOT NULL DEFAULT 0 CHECK(weather_enabled IN (0,1))
);
CREATE TABLE IF NOT EXISTS organization_members (
    email TEXT NOT NULL,
    org_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('company_admin','sender','employee')),
    department TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    PRIMARY KEY(email,org_id)
);
CREATE TABLE IF NOT EXISTS workspace_migrations (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS upload_assets (
    asset_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE IF NOT EXISTS dispatch_scopes (
 scope_id TEXT PRIMARY KEY, company TEXT NOT NULL, name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('department','project','group')),
 department TEXT NOT NULL DEFAULT '', recipients_json TEXT NOT NULL DEFAULT '[]',
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
CREATE TABLE IF NOT EXISTS sender_grants (
 email TEXT NOT NULL, company TEXT NOT NULL,
 scopes_json TEXT NOT NULL DEFAULT '[]', reports_json TEXT NOT NULL DEFAULT '[]',
 messaging INTEGER NOT NULL DEFAULT 0, reports INTEGER NOT NULL DEFAULT 0, weather INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(email,company)
);
CREATE TABLE IF NOT EXISTS builtin_report_state (
    report_id TEXT PRIMARY KEY,
    removed INTEGER NOT NULL DEFAULT 0 CHECK(removed IN (0,1))
);
