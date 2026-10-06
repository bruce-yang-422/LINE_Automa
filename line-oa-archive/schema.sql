-- LINE 自動化平台資料結構（PRAGMA user_version = 2，由 app.initialize_database() 寫入）。
-- 全新安裝直接建表；同版本僅允許已授權的值日生模組附加欄位。
-- 結構改版須備份並重置；程式僅接受相同 user_version，不提供舊版升級補丁。
-- 業務時間採 UTC ISO 8601；登入與快取期限採 Unix seconds。
-- 所有營運資料都屬於某個 OA：channel_id 為 line_channels.channel_id 或共用範圍 line_channel_shares.share_id。
-- 角色值（權限與角色規格第 2 節）：platform_admin 平台管理員、org_admin 管理員、operator 操作人員、collaborator 協作人員。

-- ============ 平台：組織、帳號與登入 ============

CREATE TABLE IF NOT EXISTS organizations (
    org_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'company'
        CHECK (kind IN ('company', 'unit', 'association', 'club', 'family', 'personal', 'other')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    messaging_enabled INTEGER NOT NULL DEFAULT 1 CHECK (messaging_enabled IN (0, 1)),
    duty_enabled INTEGER NOT NULL DEFAULT 0 CHECK (duty_enabled IN (0, 1)),
    -- 記事政策設定：鎖定政策與標籤政策（對話記事本管理規格 5.2 與 7.2.3）
    note_lock_policy TEXT NOT NULL DEFAULT 'disabled'
        CHECK (note_lock_policy IN ('disabled', 'collaborative', 'strict_admin')),
    note_tag_policy TEXT NOT NULL DEFAULT 'controlled'
        CHECK (note_tag_policy IN ('controlled', 'open'))
);

-- organization_id 為帳號的主要組織；平台管理員為空字串。各組織的等級見 organization_members。
CREATE TABLE IF NOT EXISTS workspace_users (
    email TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('platform_admin', 'org_admin', 'operator', 'collaborator')),
    organization_id TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS organization_members (
    email TEXT NOT NULL REFERENCES workspace_users(email),
    org_id TEXT NOT NULL REFERENCES organizations(org_id),
    role TEXT NOT NULL CHECK (role IN ('org_admin', 'operator', 'collaborator')),
    department TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    duty_manager INTEGER NOT NULL DEFAULT 0 CHECK (duty_manager IN (0, 1)),
    PRIMARY KEY (email, org_id)
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

-- 平台層級事件（組織、OA 設定）的 channel_id 為空字串；organization_id 決定哪個組織看得到。
CREATE TABLE IF NOT EXISTS audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    detail TEXT NOT NULL,
    organization_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    channel_id TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS audit_events_channel_idx ON audit_events(channel_id);
CREATE INDEX IF NOT EXISTS audit_events_organization_idx ON audit_events(organization_id);

-- ============ LINE OA ============

-- OA 歸屬於一個組織，只能由平台管理員移轉。Bot user ID 唯一，防止同一 OA 重複登記。
-- 憑證以 instance/line-credentials.key 加密保存，不寫在 .env。
CREATE TABLE IF NOT EXISTS line_channels (
    channel_id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL REFERENCES organizations(org_id),
    name TEXT NOT NULL,
    bot_user_id TEXT NOT NULL UNIQUE,
    basic_id TEXT NOT NULL DEFAULT '',
    case_prefix TEXT NOT NULL DEFAULT '',
    token_cipher TEXT NOT NULL,
    secret_cipher TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    verified_at TEXT NOT NULL DEFAULT '',
    webhook_seen_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- OA 共用：擁有者組織把使用權授予其他組織。share_id 是獨立資料範圍，
-- 各組織的聯絡對象副本、發送與授權以它區隔；憑證與 Webhook 仍屬擁有者。
CREATE TABLE IF NOT EXISTS line_channel_shares (
    share_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL REFERENCES line_channels(channel_id),
    org_id TEXT NOT NULL REFERENCES organizations(org_id),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (channel_id, org_id)
);

-- 操作人員與協作人員可使用的 OA（管理員固定可使用本組織所有 OA）。
CREATE TABLE IF NOT EXISTS oa_member_access (
    channel_id TEXT NOT NULL REFERENCES line_channels(channel_id) ON DELETE CASCADE,
    email TEXT NOT NULL REFERENCES workspace_users(email) ON DELETE CASCADE,
    org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, email, org_id)
);

-- ============ 訊息與聊天 ============

CREATE TABLE IF NOT EXISTS line_messages (
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    conversation_type TEXT NOT NULL CHECK (conversation_type IN ('user', 'group', 'room')),
    conversation_id TEXT NOT NULL,
    sender_user_id TEXT,
    message_type TEXT NOT NULL,
    text_content TEXT,
    sent_at TEXT,
    received_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f+00:00', 'now')),
    unsent_at TEXT,
    direction TEXT NOT NULL DEFAULT 'inbound' CHECK (direction IN ('inbound', 'outbound')),
    sent_by TEXT NOT NULL DEFAULT '',
    send_method TEXT NOT NULL DEFAULT '',
    delivery_status TEXT NOT NULL DEFAULT '',
    media_path TEXT NOT NULL DEFAULT '',
    reply_token TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (channel_id, message_id)
);
CREATE INDEX IF NOT EXISTS line_messages_conversation_time_idx
    ON line_messages (channel_id, conversation_id, sent_at DESC);

CREATE TABLE IF NOT EXISTS chat_state (
    channel_id TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'pending', 'done')),
    last_inbound_at TEXT,
    last_read_at TEXT,
    updated_by TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, chat_id)
);
CREATE INDEX IF NOT EXISTS chat_state_channel_idx ON chat_state(channel_id, status);

CREATE TABLE IF NOT EXISTS group_member_cache (
    channel_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    picture_url TEXT NOT NULL DEFAULT '',
    fetched_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, group_id, user_id)
);

-- Durable leases and retry backoff for member names, scoped to each OA and conversation.
CREATE TABLE IF NOT EXISTS member_profile_jobs (
    channel_id TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    next_at INTEGER NOT NULL DEFAULT 0,
    failures INTEGER NOT NULL DEFAULT 0,
    lease_until INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (channel_id, conversation_id, user_id)
);

CREATE TABLE IF NOT EXISTS canned_replies (
    channel_id TEXT NOT NULL,
    reply_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, reply_id)
);

-- 回應時間只控制瀏覽器通知（聊天規格 12.4）；weekly 為 {"0".."6": {"start","end"}}。
CREATE TABLE IF NOT EXISTS response_hours (
    channel_id TEXT PRIMARY KEY,
    sticker_reply_enabled INTEGER NOT NULL DEFAULT 0 CHECK (sticker_reply_enabled IN (0, 1)),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
    timezone TEXT NOT NULL DEFAULT 'Asia/Taipei',
    weekly TEXT NOT NULL DEFAULT '{}',
    holidays TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- ============ 聯絡對象 ============

-- organization_id 為系統組織（決定報表與發送範圍）；organization_name 為對方組織（只供辨識）。
CREATE TABLE IF NOT EXISTS recipients (
    channel_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('user', 'group', 'room')),
    display_name TEXT NOT NULL DEFAULT '',
    custom_name TEXT NOT NULL DEFAULT '',
    picture_url TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    contact_type TEXT NOT NULL DEFAULT ''
        CHECK (contact_type IN ('', 'organization', 'person_business', 'person_private')),
    phone TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    postal_code TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    organization_name TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    work_department TEXT NOT NULL DEFAULT '',
    work_phone TEXT NOT NULL DEFAULT '',
    work_phone_ext TEXT NOT NULL DEFAULT '',
    work_email TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    event_at INTEGER NOT NULL DEFAULT 0,
    organization_id TEXT NOT NULL DEFAULT '',
    department TEXT NOT NULL DEFAULT '',
    profile_checked_at INTEGER NOT NULL DEFAULT 0,
    profile_next_at INTEGER NOT NULL DEFAULT 0,
    profile_failures INTEGER NOT NULL DEFAULT 0,
    profile_lease_until INTEGER NOT NULL DEFAULT 0,
    last_seen TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, recipient_id)
);

CREATE TABLE IF NOT EXISTS contact_tags (
    tag_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#7C916C',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (channel_id, name)
);

CREATE TABLE IF NOT EXISTS contact_tag_assignments (
    channel_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    tag_id TEXT NOT NULL REFERENCES contact_tags(tag_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (channel_id, recipient_id, tag_id)
);

CREATE TABLE IF NOT EXISTS saved_filters (
    filter_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    criteria_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- 關鍵字訂閱（主題定義在 subscribers/topics.json；名冊另輸出為 subscribers/<主題>.json 供外部腳本讀取）。
CREATE TABLE IF NOT EXISTS topic_subscriptions (
    channel_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    subscribed INTEGER NOT NULL DEFAULT 0 CHECK (subscribed IN (0, 1)),
    updated_at INTEGER NOT NULL DEFAULT 0,  -- LINE 事件時間（毫秒），防止亂序重送覆蓋較新的選擇
    PRIMARY KEY (channel_id, recipient_id, topic)
);

-- 已處理的關鍵字訊息；LINE 重送同一則訊息時不重複切換或回覆。
CREATE TABLE IF NOT EXISTS subscription_commands (
    channel_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    response TEXT NOT NULL,
    PRIMARY KEY (channel_id, message_id)
);

-- ============ 對話記事本 ============

CREATE TABLE IF NOT EXISTS chat_notes (
    note_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    target_user_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    note_type TEXT NOT NULL DEFAULT '一般',
    category_id TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    content TEXT NOT NULL,
    is_pinned INTEGER NOT NULL DEFAULT 0 CHECK (is_pinned IN (0, 1)),
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    about_member_id TEXT NOT NULL DEFAULT '',
    due_date TEXT NOT NULL DEFAULT '',
    is_completed INTEGER NOT NULL DEFAULT 0 CHECK (is_completed IN (0, 1)),
    source_message_id TEXT NOT NULL DEFAULT '',
    linked_case_id TEXT NOT NULL DEFAULT '',
    deleted_at TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS chat_notes_channel_idx ON chat_notes(channel_id, recipient_id);
CREATE INDEX IF NOT EXISTS idx_chat_notes_lookup ON chat_notes(channel_id, recipient_id, deleted_at, is_pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_notes_global ON chat_notes(channel_id, deleted_at, is_completed, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_notes_case ON chat_notes(channel_id, linked_case_id) WHERE linked_case_id != '';

-- 記事分類主表 (預設 4 個通用分類，乙丙級可自訂增刪改)
CREATE TABLE IF NOT EXISTS chat_note_categories (
    category_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#007AFF',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(channel_id, name)
);

-- 記事標準標籤主表 (預設 8 大通用標籤，乙丙級可自訂增刪改)
CREATE TABLE IF NOT EXISTS chat_note_tags (
    tag_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    color TEXT NOT NULL DEFAULT '#007AFF',
    category TEXT NOT NULL DEFAULT 'general',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE(channel_id, name)
);

-- 記事標籤僅儲存於 chat_notes.tags_json，避免雙份同步。
-- ============ 案件 ============

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    case_no TEXT NOT NULL UNIQUE,
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '一般',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'waiting', 'ready_to_close', 'closed')),
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    case_subject_id TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    resolution TEXT NOT NULL DEFAULT '',
    waiting_party TEXT NOT NULL DEFAULT '' CHECK (waiting_party IN ('', 'internal', 'case_subject', 'third_party')),
    waiting_reason TEXT NOT NULL DEFAULT '',
    waiting_since TEXT NOT NULL DEFAULT '',
    ref_no TEXT NOT NULL DEFAULT '',
    continued_from_id TEXT NOT NULL DEFAULT '',
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    due_date TEXT NOT NULL DEFAULT '',
    source_note_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    closed_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS cases_channel_idx ON cases(channel_id, status);
CREATE INDEX IF NOT EXISTS cases_subject_idx ON cases(channel_id, case_subject_id);

CREATE TABLE IF NOT EXISTS case_activities (
    activity_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    channel_id TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    content TEXT NOT NULL,
    source_message_id TEXT NOT NULL DEFAULT '',
    source_snapshot TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS case_activities_case_idx ON case_activities(case_id, created_at);

-- 案件編號 {前綴}-{YYYYMM}-{流水號}：流水號每月重新起算，前綴全平台唯一（案件規格 14）。
CREATE TABLE IF NOT EXISTS case_number_sequences (
    prefix TEXT NOT NULL,
    period TEXT NOT NULL,
    last_number INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (prefix, period)
);

-- 覆蓋既有編號時，舊編號保留為別名可搜尋。
CREATE TABLE IF NOT EXISTS case_number_aliases (
    case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    old_case_no TEXT NOT NULL UNIQUE,
    replaced_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (case_id, old_case_no)
);

-- ============ 範本包與分類（案件規格 17） ============

-- 自訂範本包屬於工作區（workspace_id 為組織 ID）；內建範本包定義於程式，不存資料表。
CREATE TABLE IF NOT EXISTS template_packs (
    pack_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    note_types_json TEXT NOT NULL DEFAULT '[]',
    case_categories_json TEXT NOT NULL DEFAULT '[]',
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
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
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS case_templates_pack_idx ON case_templates(pack_id);

CREATE TABLE IF NOT EXISTS note_templates (
    template_id TEXT PRIMARY KEY,
    pack_id TEXT NOT NULL REFERENCES template_packs(pack_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    category_name TEXT NOT NULL DEFAULT '一般',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    defaults_json TEXT NOT NULL DEFAULT '{}',
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    created_by TEXT NOT NULL DEFAULT '',
    updated_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS note_templates_pack_idx ON note_templates(pack_id);

-- 每個 OA 啟用的範本包（內建範本包以 key、自訂範本包以 pack_id 表示）。
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
    UNIQUE (channel_id, name)
);

-- ============ 發送 ============

CREATE TABLE IF NOT EXISTS upload_assets (
    asset_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    name TEXT NOT NULL,
    organization_id TEXT NOT NULL DEFAULT '',
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS upload_assets_channel_idx ON upload_assets(channel_id);

CREATE TABLE IF NOT EXISTS send_jobs (
    job_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('scheduled', 'queued', 'running', 'finished', 'cancelled', 'missed', 'interrupted')),
    audience TEXT NOT NULL CHECK (audience = 'selected'),
    image_path TEXT NOT NULL,
    image_url TEXT NOT NULL DEFAULT '',
    actor TEXT NOT NULL DEFAULT '',
    report_title TEXT NOT NULL DEFAULT '',  -- 發送紀錄顯示的標題
    scheduled_at TEXT NOT NULL DEFAULT '',
    message_text TEXT NOT NULL DEFAULT '',
    organization_id TEXT NOT NULL DEFAULT '',
    messages_json TEXT NOT NULL DEFAULT '[]',
    error TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS send_jobs_channel_idx ON send_jobs(channel_id, status);

CREATE TABLE IF NOT EXISTS send_deliveries (
    job_id TEXT NOT NULL REFERENCES send_jobs(job_id),
    recipient_id TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'sending', 'accepted', 'failed', 'unknown', 'cancelled')),
    retry_key TEXT NOT NULL,
    request_id TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (job_id, recipient_id)
);

CREATE TABLE IF NOT EXISTS chat_room_preferences (
 channel_id TEXT NOT NULL, actor TEXT NOT NULL, recipient_id TEXT NOT NULL,
 is_pinned INTEGER NOT NULL DEFAULT 0 CHECK(is_pinned IN (0,1)),
 marker TEXT NOT NULL DEFAULT '' CHECK(marker IN ('','star','flag')),
 PRIMARY KEY(channel_id,actor,recipient_id)
);

-- ============ 值日生第二階段（可在既有 v2 資料庫建立） ============
CREATE TABLE IF NOT EXISTS duty_people (
 person_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id),
 full_name TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '', department TEXT NOT NULL DEFAULT '', floor TEXT NOT NULL DEFAULT '',
 active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)), deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)),
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duty_positions (
 position_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id), code TEXT NOT NULL,
 sort_order INTEGER NOT NULL, vacant INTEGER NOT NULL DEFAULT 1 CHECK(vacant IN (0,1)), UNIQUE(org_id,code)
);
CREATE TABLE IF NOT EXISTS duty_position_members (
 membership_id TEXT PRIMARY KEY, position_id TEXT NOT NULL REFERENCES duty_positions(position_id),
 person_id TEXT NOT NULL REFERENCES duty_people(person_id), effective_from TEXT NOT NULL, effective_to TEXT,
 CHECK(effective_to IS NULL OR effective_to>=effective_from)
);
CREATE INDEX IF NOT EXISTS duty_members_period ON duty_position_members(position_id,effective_from,effective_to);
CREATE TABLE IF NOT EXISTS duty_person_bindings (
 org_id TEXT NOT NULL REFERENCES organizations(org_id), person_id TEXT NOT NULL REFERENCES duty_people(person_id),
 channel_id TEXT NOT NULL, recipient_id TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(org_id,person_id,channel_id), UNIQUE(org_id,channel_id,recipient_id)
);
CREATE TABLE IF NOT EXISTS duty_tasks (
 task_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id), active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
 deleted INTEGER NOT NULL DEFAULT 0 CHECK(deleted IN (0,1)), sort_order INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duty_task_versions (
 version_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES duty_tasks(task_id), version INTEGER NOT NULL,
 effective_from TEXT NOT NULL, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', area TEXT NOT NULL DEFAULT '',
 kind TEXT NOT NULL CHECK(kind IN ('normal','rest','blank')), rotation TEXT NOT NULL CHECK(rotation IN ('year','month','week','fixed')),
 allow_multiple INTEGER NOT NULL DEFAULT 0 CHECK(allow_multiple IN (0,1)), created_at TEXT NOT NULL,
 UNIQUE(task_id,version)
);
CREATE TABLE IF NOT EXISTS duty_task_items (
 item_id TEXT PRIMARY KEY, version_id TEXT NOT NULL REFERENCES duty_task_versions(version_id), content TEXT NOT NULL,
 frequency TEXT NOT NULL CHECK(frequency IN ('daily','weekly','monthly','annual')),
 weekdays TEXT NOT NULL DEFAULT '[]', day_start INTEGER NOT NULL DEFAULT 1, day_end INTEGER NOT NULL DEFAULT 31,
 annual_date TEXT NOT NULL DEFAULT '', excluded_dates TEXT NOT NULL DEFAULT '[]', reminder_time TEXT NOT NULL DEFAULT '',
 reminder_enabled INTEGER NOT NULL DEFAULT 0 CHECK(reminder_enabled IN (0,1)), sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS duty_rosters (
 roster_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id), name TEXT NOT NULL,
 period_type TEXT NOT NULL CHECK(period_type IN ('week','month','year')), date_from TEXT NOT NULL, date_to TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published','replaced','cancelled')),
 version INTEGER NOT NULL DEFAULT 0, published_by TEXT NOT NULL DEFAULT '', published_at TEXT NOT NULL DEFAULT '',
 reason TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL, CHECK(date_to>=date_from)
);
CREATE UNIQUE INDEX IF NOT EXISTS duty_one_draft ON duty_rosters(org_id,date_from,date_to) WHERE status='draft';
CREATE UNIQUE INDEX IF NOT EXISTS duty_one_published ON duty_rosters(org_id,date_from,date_to) WHERE status='published';
CREATE TABLE IF NOT EXISTS duty_assignments (
 assignment_id TEXT PRIMARY KEY, roster_id TEXT NOT NULL REFERENCES duty_rosters(roster_id), task_id TEXT NOT NULL REFERENCES duty_tasks(task_id),
 person_ids TEXT NOT NULL DEFAULT '[]', note TEXT NOT NULL DEFAULT '', snapshot TEXT NOT NULL DEFAULT '{}', UNIQUE(roster_id,task_id)
);
CREATE TABLE IF NOT EXISTS duty_substitutions (
 substitution_id TEXT PRIMARY KEY, assignment_id TEXT NOT NULL REFERENCES duty_assignments(assignment_id),
 original_person_id TEXT NOT NULL REFERENCES duty_people(person_id), substitute_person_id TEXT NOT NULL REFERENCES duty_people(person_id),
 date_from TEXT NOT NULL, date_to TEXT NOT NULL, CHECK(date_to>=date_from)
);

CREATE TABLE IF NOT EXISTS duty_notice_settings (
 org_id TEXT PRIMARY KEY REFERENCES organizations(org_id), channel_id TEXT NOT NULL DEFAULT '',
 config TEXT NOT NULL DEFAULT '{}', revision INTEGER NOT NULL DEFAULT 1, actor TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duty_notice_jobs (
 job_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id), event_key TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL, roster_ids TEXT NOT NULL, scheduled_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 channel_id TEXT NOT NULL, settings_revision INTEGER NOT NULL, actor TEXT NOT NULL,
 missing TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS duty_notice_deliveries (
 delivery_id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES duty_notice_jobs(job_id), recipient_id TEXT NOT NULL,
 person_id TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL, label TEXT NOT NULL, task_ids TEXT NOT NULL,
 message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','accepted','failed','cancelled','unknown')),
 retry_key TEXT NOT NULL, request_id TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '', attempts TEXT NOT NULL DEFAULT '[]',
 UNIQUE(job_id,recipient_id)
);
CREATE INDEX IF NOT EXISTS duty_notice_due ON duty_notice_jobs(scheduled_at,org_id);
CREATE TABLE IF NOT EXISTS duty_subscriptions (
 org_id TEXT NOT NULL REFERENCES organizations(org_id), channel_id TEXT NOT NULL, person_id TEXT NOT NULL REFERENCES duty_people(person_id),
 recipient_id TEXT NOT NULL, subscribed INTEGER NOT NULL DEFAULT 0 CHECK(subscribed IN (0,1)), updated_at TEXT NOT NULL,
 PRIMARY KEY(org_id,channel_id,person_id)
);
CREATE TABLE IF NOT EXISTS duty_rotation_versions (
 rule_version_id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(org_id), period_type TEXT NOT NULL CHECK(period_type IN ('week','month','year')),
 version INTEGER NOT NULL, effective_from TEXT NOT NULL, config TEXT NOT NULL, automatic INTEGER NOT NULL DEFAULT 0,
 actor TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(org_id,period_type,version)
);
CREATE TABLE IF NOT EXISTS duty_rotation_runs (
 rule_version_id TEXT NOT NULL REFERENCES duty_rotation_versions(rule_version_id), date_from TEXT NOT NULL,
 roster_id TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
 PRIMARY KEY(rule_version_id,date_from)
);
