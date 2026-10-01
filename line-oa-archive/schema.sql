-- 全新安裝的完整 schema；啟動只執行此檔，不搬移或修補舊版資料。
-- IF NOT EXISTS 只用於重啟時保留本版資料，不代表支援舊版 schema。
-- 業務時間採 UTC ISO 8601；登入與快取期限採 Unix seconds。
CREATE TABLE IF NOT EXISTS line_messages (
    message_id TEXT NOT NULL,
    conversation_type TEXT NOT NULL CHECK (conversation_type IN ('user', 'group', 'room')),
    conversation_id TEXT NOT NULL,
    sender_user_id TEXT,
    message_type TEXT NOT NULL,
    text_content TEXT,
    sent_at TEXT,
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    unsent_at TEXT,
    channel_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(channel_id,message_id)
);

CREATE INDEX IF NOT EXISTS line_messages_conversation_time_idx
    ON line_messages (conversation_type, conversation_id, sent_at DESC);

CREATE TABLE IF NOT EXISTS recipients (
    recipient_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('user', 'group', 'room')),
    display_name TEXT NOT NULL DEFAULT '',
    alias TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    weather_subscribed INTEGER NOT NULL DEFAULT 0,
    event_at INTEGER NOT NULL DEFAULT 0,
    subscription_at INTEGER NOT NULL DEFAULT 0,
    company TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    profile_checked_at INTEGER NOT NULL DEFAULT 0,
    profile_next_at INTEGER NOT NULL DEFAULT 0,
    profile_failures INTEGER NOT NULL DEFAULT 0,
    profile_lease_until INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(channel_id,recipient_id)
);
CREATE TABLE IF NOT EXISTS subscription_commands (
    message_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    response TEXT NOT NULL,
    channel_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(channel_id,message_id)
);
CREATE TABLE IF NOT EXISTS send_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'queued',
    audience TEXT NOT NULL,
    image_path TEXT NOT NULL,
    image_url TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    report_title TEXT NOT NULL DEFAULT '',
    report_id TEXT NOT NULL DEFAULT '',
    scheduled_at TEXT NOT NULL DEFAULT '',
    message_text TEXT NOT NULL DEFAULT '',
    company TEXT NOT NULL DEFAULT '',
    messages_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT ''
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
    company TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT 'company',
    owner_email TEXT NOT NULL DEFAULT '',
    owner_recipient_id TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS workspace_users (
    email TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK(role IN ('administrator','company_admin','sender')),
    company TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);
-- 登入資料只存密碼雜湊與 Token 雜湊。
CREATE TABLE IF NOT EXISTS site_credentials (
    email TEXT PRIMARY KEY REFERENCES workspace_users(email),
    password_hash TEXT NOT NULL,
    changed_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS site_sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL REFERENCES workspace_users(email),
    created_at INTEGER NOT NULL,
    last_seen INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    idle_seconds INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS site_sessions_email ON site_sessions(email);
CREATE TABLE IF NOT EXISTS site_activation (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL REFERENCES workspace_users(email),
    expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS site_login_limits (
    bucket TEXT PRIMARY KEY,
    started_at INTEGER NOT NULL,
    attempts INTEGER NOT NULL
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
    role TEXT NOT NULL CHECK(role IN ('company_admin','sender')),
    department TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    PRIMARY KEY(email,org_id)
);
CREATE TABLE IF NOT EXISTS upload_assets (
    asset_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    company TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    channel_id TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dispatch_scopes (
 scope_id TEXT PRIMARY KEY, company TEXT NOT NULL, name TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('department','project','group')),
 department TEXT NOT NULL DEFAULT '', recipients_json TEXT NOT NULL DEFAULT '[]',
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    channel_id TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sender_grants (
 email TEXT NOT NULL, company TEXT NOT NULL,
 scopes_json TEXT NOT NULL DEFAULT '[]', reports_json TEXT NOT NULL DEFAULT '[]',
 messaging INTEGER NOT NULL DEFAULT 0, reports INTEGER NOT NULL DEFAULT 0, weather INTEGER NOT NULL DEFAULT 0,
 channel_id TEXT NOT NULL DEFAULT '',
 PRIMARY KEY(channel_id,email,company)
);
CREATE TABLE IF NOT EXISTS builtin_report_state (
    report_id TEXT NOT NULL,
    removed INTEGER NOT NULL DEFAULT 0 CHECK(removed IN (0,1)),
    channel_id TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(channel_id,report_id)
);

-- OA 歸屬於一個個人或組織工作區，只能由平台管理員移轉。Bot user ID 唯一，防止同一 OA 重複登記。
CREATE TABLE IF NOT EXISTS line_channels (
    channel_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL DEFAULT '',
    owner_email TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    bot_user_id TEXT NOT NULL UNIQUE,
    basic_id TEXT NOT NULL DEFAULT '',
    token_cipher TEXT NOT NULL,
    secret_cipher TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    legacy_webhook INTEGER NOT NULL DEFAULT 0 CHECK(legacy_webhook IN (0,1)),
    verified_at TEXT NOT NULL DEFAULT '',
    webhook_seen_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((org_id<>'' AND owner_email='') OR (org_id='' AND owner_email<>''))
);
CREATE UNIQUE INDEX IF NOT EXISTS line_channels_legacy ON line_channels(legacy_webhook) WHERE legacy_webhook=1;
-- OA 共用：擁有者工作區把使用權授予其他工作區。share_id 是獨立資料範圍，
-- 各工作區的收件者副本、報告、發送與授權以它區隔；憑證與 Webhook 仍屬擁有者。
CREATE TABLE IF NOT EXISTS line_channel_shares (
    share_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES line_channels(channel_id),
    org_id TEXT NOT NULL DEFAULT '',
    owner_email TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    CHECK ((org_id<>'' AND owner_email='') OR (org_id='' AND owner_email<>'')),
    UNIQUE(channel_id, org_id, owner_email)
);

CREATE TABLE IF NOT EXISTS contact_tags (
    tag_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#7C916C',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contact_tag_assignments (
    channel_id TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL,
    tag_id TEXT NOT NULL REFERENCES contact_tags(tag_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, recipient_id, tag_id)
);
CREATE INDEX IF NOT EXISTS audit_events_channel_idx ON audit_events(channel_id);
CREATE INDEX IF NOT EXISTS builtin_report_state_channel_idx ON builtin_report_state(channel_id);
CREATE INDEX IF NOT EXISTS dispatch_scopes_channel_idx ON dispatch_scopes(channel_id);
CREATE INDEX IF NOT EXISTS line_messages_channel_idx ON line_messages(channel_id);
CREATE INDEX IF NOT EXISTS contact_tags_channel_idx ON contact_tags(channel_id);
CREATE INDEX IF NOT EXISTS contact_tag_assignments_channel_idx ON contact_tag_assignments(channel_id);
CREATE INDEX IF NOT EXISTS recipients_channel_idx ON recipients(channel_id);
CREATE INDEX IF NOT EXISTS report_sources_channel_idx ON report_sources(channel_id);
CREATE INDEX IF NOT EXISTS send_jobs_channel_idx ON send_jobs(channel_id);
CREATE INDEX IF NOT EXISTS sender_grants_channel_idx ON sender_grants(channel_id);
CREATE INDEX IF NOT EXISTS subscription_commands_channel_idx ON subscription_commands(channel_id);
CREATE INDEX IF NOT EXISTS upload_assets_channel_idx ON upload_assets(channel_id);
