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
    direction TEXT NOT NULL DEFAULT 'inbound',
    sent_by TEXT NOT NULL DEFAULT '',
    send_method TEXT NOT NULL DEFAULT '',
    delivery_status TEXT NOT NULL DEFAULT '',
    media_path TEXT NOT NULL DEFAULT '',
    reply_token TEXT NOT NULL DEFAULT '',
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
    contact_type TEXT NOT NULL DEFAULT '',
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    organization_name TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    work_phone TEXT NOT NULL DEFAULT '',
    work_phone_ext TEXT NOT NULL DEFAULT '',
    work_email TEXT NOT NULL DEFAULT '',
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
    role TEXT NOT NULL CHECK(role IN ('administrator','company_admin','sender','assistant')),
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
    role TEXT NOT NULL CHECK(role IN ('company_admin','sender','assistant')),
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
    case_prefix TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS oa_member_access (
    channel_id TEXT NOT NULL REFERENCES line_channels(channel_id) ON DELETE CASCADE,
    email TEXT NOT NULL REFERENCES workspace_users(email) ON DELETE CASCADE,
    org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (channel_id, email, org_id)
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
CREATE TABLE IF NOT EXISTS chat_notes (
    note_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL DEFAULT '',
    recipient_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    note_type TEXT NOT NULL DEFAULT '一般',
    tags_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0,
    is_locked INTEGER NOT NULL DEFAULT 0,
    about_member_id TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    is_completed INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS saved_filters (
    filter_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    criteria_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    case_no TEXT NOT NULL UNIQUE,
    channel_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '一般',
    status TEXT NOT NULL CHECK(status IN ('pending','processing','waiting','ready_to_close','closed')) DEFAULT 'pending',
    priority TEXT NOT NULL CHECK(priority IN ('low','medium','high','urgent')) DEFAULT 'medium',
    case_subject_id TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    resolution TEXT NOT NULL DEFAULT '',
    waiting_party TEXT NOT NULL DEFAULT '' CHECK(waiting_party IN ('','internal','case_subject','third_party')),
    waiting_reason TEXT NOT NULL DEFAULT '',
    waiting_since TEXT NOT NULL DEFAULT '',
    ref_no TEXT NOT NULL DEFAULT '',
    continued_from_id TEXT NOT NULL DEFAULT '',
    is_locked INTEGER NOT NULL DEFAULT 0,
    due_date TEXT NOT NULL DEFAULT '',
    source_note_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    closed_at TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS case_activities (
    activity_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL DEFAULT '',
    activity_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    content TEXT NOT NULL,
    source_message_id TEXT NOT NULL DEFAULT '',
    source_snapshot TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS case_number_sequences (
    prefix TEXT NOT NULL,
    period TEXT NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (prefix, period)
);

CREATE TABLE IF NOT EXISTS case_number_aliases (
    case_id TEXT NOT NULL,
    old_case_no TEXT NOT NULL UNIQUE,
    replaced_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (case_id, old_case_no)
);

CREATE TABLE IF NOT EXISTS template_packs (
    pack_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    note_types_json TEXT NOT NULL DEFAULT '[]',
    case_categories_json TEXT NOT NULL DEFAULT '[]',
    is_locked INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS case_templates (
    template_id TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL REFERENCES template_packs(pack_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category_name TEXT NOT NULL DEFAULT '一般',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    defaults_json TEXT NOT NULL DEFAULT '{}',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_locked INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS note_templates (
    template_id TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL REFERENCES template_packs(pack_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category_name TEXT NOT NULL DEFAULT '一般',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    defaults_json TEXT NOT NULL DEFAULT '{}',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_locked INTEGER NOT NULL DEFAULT 0,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS oa_enabled_packs (
    channel_id TEXT NOT NULL,
    pack_key TEXT NOT NULL,
    PRIMARY KEY (channel_id, pack_key)
);

CREATE TABLE IF NOT EXISTS oa_case_categories (
    category_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(channel_id, name)
);

CREATE TABLE IF NOT EXISTS oa_note_categories (
    category_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(channel_id, name)
);

CREATE TABLE IF NOT EXISTS chat_state (
    channel_id TEXT NOT NULL DEFAULT '',
    chat_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'done')),
    last_inbound_at TEXT,
    last_read_at TEXT,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, chat_id)
);

CREATE TABLE IF NOT EXISTS group_member_cache (
    channel_id TEXT NOT NULL DEFAULT '',
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    picture_url TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, group_id, user_id)
);

CREATE TABLE IF NOT EXISTS canned_replies (
    reply_id TEXT NOT NULL,
    channel_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, reply_id)
);

CREATE TABLE IF NOT EXISTS response_hours (
    channel_id TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 0,
    timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
    weekly TEXT NOT NULL DEFAULT '{}',
    holidays TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id)
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
CREATE INDEX IF NOT EXISTS chat_notes_channel_idx ON chat_notes(channel_id, recipient_id);
CREATE INDEX IF NOT EXISTS saved_filters_channel_idx ON saved_filters(channel_id);
CREATE INDEX IF NOT EXISTS cases_channel_idx ON cases(channel_id, status);
CREATE INDEX IF NOT EXISTS cases_subject_idx ON cases(channel_id, case_subject_id);
CREATE INDEX IF NOT EXISTS case_activities_case_idx ON case_activities(case_id, created_at);
CREATE INDEX IF NOT EXISTS chat_state_channel_idx ON chat_state(channel_id, status);
CREATE INDEX IF NOT EXISTS group_member_cache_idx ON group_member_cache(channel_id, group_id);
CREATE INDEX IF NOT EXISTS canned_replies_channel_idx ON canned_replies(channel_id);
CREATE INDEX IF NOT EXISTS case_templates_pack_idx ON case_templates(pack_id);
CREATE INDEX IF NOT EXISTS note_templates_pack_idx ON note_templates(pack_id);


