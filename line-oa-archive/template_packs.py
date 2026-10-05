"""Template Packs & Category Sets management according to 案件管理流程規格.md (Section 17)"""

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone, timedelta
import channels
import limits

PRESET_PACKS = {
    'universal': {
        'pack_id': 'universal',
        'key': 'universal',
        'name': '通用',
        'description': '適用於各類諮詢、問題處理、聯絡備忘與日常工作流程（新 OA 預設）',
        'is_preset': True,
        'note_types': ['一般備忘', '待辦', '備忘', '重點提醒', '交接事項'],
        'case_categories': ['一般備忘', '諮詢', '申請', '報修', '反映', '售後'],
        'case_templates': [
            {
                'template_id': 'preset_u_case_1',
                'name': '一般諮詢',
                'category_name': '諮詢',
                'title': '{聯絡對象} - 諮詢事項',
                'body': '### 1. 諮詢確認\n- [ ] 詢問對象基本需求與現況\n- [ ] 確認回覆方式與期限\n\n### 2. 處置措施\n* **優先等級**：重要處理\n* **處理窗口**：\n* **備註說明**：',
                'defaults': {'priority': 'medium', 'due_days': 2, 'ref_prompt': ''}
            },
            {
                'template_id': 'preset_u_case_2',
                'name': '申請處理',
                'category_name': '申請',
                'title': '{聯絡對象} - 申請處理',
                'body': '### 1. 申請資料\n* **申請項目**：\n* **申請日期**：{今天}\n\n### 2. 檢核項目\n- [ ] 證件與必要文件核對\n- [ ] 案件建檔與派案\n- [ ] 主動通知申請人進度',
                'defaults': {'priority': 'medium', 'due_days': 5, 'ref_prompt': '申請編號'}
            },
            {
                'template_id': 'preset_u_case_3',
                'name': '問題與報修',
                'category_name': '報修',
                'title': '{聯絡對象} - 問題報修',
                'body': '### 1. 狀況描述\n* **品項/設備**：\n* **故障或問題現象**：\n* **發生時間**：\n\n### 2. 處置進度\n- [ ] 照片或事證留存\n- [ ] 安排專人聯絡處理\n- [ ] 完工/結案確認',
                'defaults': {'priority': 'high', 'due_days': 3, 'ref_prompt': '設備或產品編號'}
            },
            {
                'template_id': 'preset_u_case_4',
                'name': '客戶反映',
                'category_name': '反映',
                'title': '{聯絡對象} - 客戶反映',
                'body': '### 1. 反映事項\n* **發生時間與地點**：\n* **事件緣由**：\n\n### 2. 處置與回覆\n- [ ] 釐清狀況與原因\n- [ ] 研擬處置或改善方案\n- [ ] 專人回覆客戶說明',
                'defaults': {'priority': 'high', 'due_days': 2, 'ref_prompt': ''}
            },
            {
                'template_id': 'preset_u_case_5',
                'name': '退換補寄與售後',
                'category_name': '售後',
                'title': '{聯絡對象} - 訂單售後/退換補寄處理',
                'body': '### 1. 訂單與售後類別\n* **訂單編號 / 平台**：\n* **購買品項與數量**：\n* **申請類別**：\n  - [ ] 缺貨通知 / 換款 / 差額退款\n  - [ ] 數量短缺 / 漏發補寄\n  - [ ] 瑕疵破損 / 新品換貨\n  - [ ] 售後維修 / 保固送修（購買後維修）\n  - [ ] 鑑賞期退貨退款\n\n### 2. 狀況說明與佐證\n* **問題狀況描述**：\n* **照片/影片佐證**：\n  - [ ] 外包裝完整度照片\n  - [ ] 寄件託運單照片\n  - [ ] 瑕疵/損壞處特寫照片\n\n### 3. SOP 處理檢核清單\n- [ ] 1. 系統核對訂單與購買紀錄\n- [ ] 2. 判定責任歸屬（商品瑕疵／物流毀損／缺件）\n- [ ] 3. 與顧客確認處置方案（補寄／換貨／退款／維修）\n- [ ] 4. 派案物流收回或補寄新品（填寫單號）\n- [ ] 5. 倉庫驗退 / 維修檢測完成\n- [ ] 6. 財務退款或完修寄回通知',
                'defaults': {'priority': 'high', 'due_days': 3, 'ref_prompt': '訂單編號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_u_note_1',
                'name': '聯絡紀錄',
                'category_name': '一般備忘',
                'title': '聯絡紀錄 - {今天}',
                'body': '### 溝通大綱\n* **對話對象**：{聯絡對象}\n* **溝通重點**：\n\n### 後續追蹤\n- [ ] 待回覆項目\n- [ ] 預計跟進日期：',
                'defaults': {'tags': ['聯絡紀錄']}
            },
            {
                'template_id': 'preset_u_note_2',
                'name': '待辦事項',
                'category_name': '待辦',
                'title': '待辦事項 - {聯絡對象}',
                'body': '### 事項清單\n- [ ] 待辦內容：\n- [ ] 預定完成日：\n- [ ] 協同負責人：',
                'defaults': {'tags': ['待辦']}
            },
            {
                'template_id': 'preset_u_note_3',
                'name': '交接備忘',
                'category_name': '交接事項',
                'title': '交接備忘 - {今天}',
                'body': '### 交接重點\n* **目前進度**：\n* **注意事項**：\n\n### 待辦清單\n- [ ] 需交接事項 1\n- [ ] 需交接事項 2',
                'defaults': {'tags': ['交接']}
            }
        ]
    }
}


# Six reusable workflows share the same four categories as the notebook.
# Retain stable IDs so saved selections and edited preset overrides still work.
_universal = PRESET_PACKS['universal']
_universal['note_types'] = ['一般備忘', '商務往來', '問題處理', '待辦交接']
_universal['case_categories'] = list(_universal['note_types'])
_universal['case_templates'] = [t for t in _universal['case_templates']
                               if t['template_id'] in {'preset_u_case_1', 'preset_u_case_3', 'preset_u_case_5'}]
for _template, _category in zip(_universal['case_templates'], ['商務往來', '問題處理', '問題處理']):
    _template['category_name'] = _category
for _template, _category, _tags in zip(_universal['note_templates'],
                                     ['一般備忘', '待辦交接', '待辦交接'],
                                     [['待追蹤'], ['待確認'], []]):
    _template['category_name'] = _category
    _template['defaults']['tags'] = _tags


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_oa_default_categories(conn: sqlite3.Connection, channel_id: str):
    """Ensure OA has at least '一般備忘' in categories and 'universal' enabled by default."""
    # Check enabled packs
    row = conn.execute("SELECT 1 FROM oa_enabled_packs WHERE channel_id=?", (channel_id,)).fetchone()
    if not row:
        conn.execute("INSERT OR IGNORE INTO oa_enabled_packs (channel_id, pack_key) VALUES (?, 'universal')", (channel_id,))

    # A single note category catalogue is shared by notes and templates.
    import chat_notes
    chat_notes.ensure_default_categories(conn, channel_id)

    # Case categories
    c_row = conn.execute("SELECT 1 FROM oa_case_categories WHERE channel_id=?", (channel_id,)).fetchone()
    if not c_row:
        for idx, name in enumerate(PRESET_PACKS['universal']['case_categories']):
            cid = uuid.uuid4().hex
            conn.execute(
                "INSERT OR IGNORE INTO oa_case_categories (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)",
                (cid, channel_id, name, idx)
            )


def list_oa_categories(conn: sqlite3.Connection, channel_id: str = None) -> dict:
    if not channel_id:
        channel_id = channels.current_id()
    ensure_oa_default_categories(conn, channel_id)

    conn.row_factory = sqlite3.Row
    # Note categories
    note_cats = conn.execute(
        """SELECT nc.category_id, nc.name, nc.sort_order,
                  (SELECT COUNT(*) FROM chat_notes n WHERE n.channel_id=nc.channel_id AND n.note_type=nc.name AND (n.deleted_at='' OR n.deleted_at IS NULL)) as usage_count
        FROM chat_note_categories nc
        WHERE nc.channel_id=?
        ORDER BY nc.sort_order ASC, nc.name ASC""",
        (channel_id,)
    ).fetchall()

    # Case categories
    case_cats = conn.execute(
        """SELECT cc.category_id, cc.name, cc.sort_order,
                  (SELECT COUNT(*) FROM cases c WHERE c.channel_id=cc.channel_id AND c.category=cc.name) as usage_count
        FROM oa_case_categories cc
        WHERE cc.channel_id=?
        ORDER BY cc.sort_order ASC, cc.name ASC""",
        (channel_id,)
    ).fetchall()

    return {
        'note_categories': [dict(r) for r in note_cats],
        'case_categories': [dict(r) for r in case_cats]
    }


def get_deleted_preset_ids(conn: sqlite3.Connection, workspace_id: str = None) -> set:
    try:
        if workspace_id:
            rows = conn.execute("SELECT template_id FROM deleted_preset_templates WHERE workspace_id=?", (workspace_id,)).fetchall()
        else:
            rows = conn.execute("SELECT template_id FROM deleted_preset_templates").fetchall()
        return set(r[0] for r in rows)
    except sqlite3.OperationalError:
        return set()


def list_all_packs(conn: sqlite3.Connection, workspace_id: str = None, channel_id: str = None) -> list:
    if not channel_id:
        channel_id = channels.current_id()
    ensure_oa_default_categories(conn, channel_id)

    # Get enabled packs for current channel
    enabled_keys = set(
        r[0] for r in conn.execute(
            "SELECT pack_key FROM oa_enabled_packs WHERE channel_id=?",
            (channel_id,)
        ).fetchall()
    )

    deleted_preset_ids = get_deleted_preset_ids(conn, workspace_id)

    packs = []
    # 1. Preset packs (filtered by deleted_preset_ids)
    for k, p in PRESET_PACKS.items():
        pack_copy = dict(p)
        pack_copy['is_enabled'] = (k in enabled_keys)
        pack_copy['case_templates'] = [t for t in p.get('case_templates', []) if t['template_id'] not in deleted_preset_ids]
        pack_copy['note_templates'] = [t for t in p.get('note_templates', []) if t['template_id'] not in deleted_preset_ids]
        packs.append(pack_copy)

    # 2. Custom packs
    if workspace_id:
        conn.row_factory = sqlite3.Row
        custom_rows = conn.execute(
            "SELECT * FROM template_packs WHERE workspace_id=? ORDER BY created_at ASC",
            (workspace_id,)
        ).fetchall()
        for cr in custom_rows:
            cd = dict(cr)
            cd['is_preset'] = False
            cd['is_enabled'] = (cd['pack_id'] in enabled_keys)
            cd['note_types'] = json.loads(cd.get('note_types_json') or '[]')
            cd['case_categories'] = json.loads(cd.get('case_categories_json') or '[]')
            
            # Fetch templates
            ct_rows = conn.execute("SELECT * FROM case_templates WHERE pack_id=? ORDER BY sort_order ASC", (cd['pack_id'],)).fetchall()
            cd['case_templates'] = []
            for t in ct_rows:
                td = dict(t)
                td['defaults'] = json.loads(td.get('defaults_json') or '{}')
                cd['case_templates'].append(td)
                
            nt_rows = conn.execute("SELECT * FROM note_templates WHERE pack_id=? ORDER BY sort_order ASC", (cd['pack_id'],)).fetchall()
            cd['note_templates'] = []
            for t in nt_rows:
                td = dict(t)
                td['defaults'] = json.loads(td.get('defaults_json') or '{}')
                cd['note_templates'].append(td)

            packs.append(cd)

    return packs


def toggle_oa_pack(conn: sqlite3.Connection, channel_id: str, pack_key: str, enabled: bool) -> bool:
    if enabled:
        conn.execute(
            "INSERT OR IGNORE INTO oa_enabled_packs (channel_id, pack_key) VALUES (?, ?)",
            (channel_id, pack_key)
        )
    else:
        conn.execute(
            "DELETE FROM oa_enabled_packs WHERE channel_id=? AND pack_key=?",
            (channel_id, pack_key)
        )
    return True


def preview_apply_category_set(conn: sqlite3.Connection, channel_id: str, pack_key_or_id: str, mode: str) -> dict:
    """Preview category set application (Replace vs Merge)."""
    # 1. Get pack target items
    pack = None
    if pack_key_or_id in PRESET_PACKS:
        pack = PRESET_PACKS[pack_key_or_id]
    else:
        row = conn.execute("SELECT * FROM template_packs WHERE pack_id=?", (pack_key_or_id,)).fetchone()
        if row:
            pack = {
                'name': row[2],
                'note_types': json.loads(row[4] or '[]'),
                'case_categories': json.loads(row[5] or '[]')
            }
    if not pack:
        raise ValueError('找不到指定的範本包。')

    target_notes = pack.get('note_types', ['一般備忘'])
    if '一般備忘' not in target_notes:
        target_notes.insert(0, '一般備忘')
        
    target_cases = pack.get('case_categories', ['一般備忘'])
    if '一般備忘' not in target_cases:
        target_cases.insert(0, '一般備忘')

    current_data = list_oa_categories(conn, channel_id)
    curr_notes = {c['name']: c for c in current_data['note_categories']}
    curr_cases = {c['name']: c for c in current_data['case_categories']}

    def calc_diff(target_list, current_dict):
        result_items = []
        # Target items
        for item in target_list:
            item_clean = item.strip()
            if item_clean in current_dict:
                result_items.append({'name': item_clean, 'action': 'keep', 'usage': current_dict[item_clean]['usage_count']})
            else:
                result_items.append({'name': item_clean, 'action': 'add', 'usage': 0})
        
        # Non-target existing items
        for name, info in current_dict.items():
            if name not in [x['name'] for x in result_items]:
                if mode == 'merge' or name == '一般備忘' or info['usage_count'] > 0:
                    result_items.append({'name': name, 'action': 'keep', 'usage': info['usage_count']})
                else:
                    result_items.append({'name': name, 'action': 'remove', 'usage': 0})

        # 每個 OA 的分類上限
        final_list = []
        for idx, it in enumerate(result_items):
            if it['action'] != 'remove':
                if len([x for x in final_list if x['action'] != 'remove']) >= limits.CATEGORIES_PER_OA:
                    it['action'] = 'exceeded'
            final_list.append(it)
        return final_list

    return {
        'pack_name': pack['name'],
        'mode': mode,
        'note_types': calc_diff(target_notes, curr_notes),
        'case_categories': calc_diff(target_cases, curr_cases)
    }


def apply_category_set(conn: sqlite3.Connection, channel_id: str, pack_key_or_id: str, mode: str, actor: str) -> dict:
    preview = preview_apply_category_set(conn, channel_id, pack_key_or_id, mode)

    # 1. Update Note Categories
    final_notes = [x for x in preview['note_types'] if x['action'] in ('keep', 'add')]
    removed_notes = [x['name'] for x in preview['note_types'] if x['action'] == 'remove']

    # Reassign removed notes to '一般備忘'
    for rm in removed_notes:
        conn.execute(
            "UPDATE chat_notes SET note_type='一般備忘', category_id=COALESCE((SELECT category_id FROM chat_note_categories WHERE channel_id=? AND name='一般備忘'), '') WHERE channel_id=? AND note_type=?",
            (channel_id, channel_id, rm)
        )
    conn.execute("DELETE FROM chat_note_categories WHERE channel_id=?", (channel_id,))
    for idx, it in enumerate(final_notes):
        cid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO chat_note_categories (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (cid, channel_id, it['name'], idx)
        )

    conn.execute("""UPDATE chat_notes SET category_id=COALESCE(
        (SELECT category_id FROM chat_note_categories c WHERE c.channel_id=chat_notes.channel_id AND c.name=chat_notes.note_type), '')
        WHERE channel_id=?""", (channel_id,))

    # 2. Update Case Categories
    final_cases = [x for x in preview['case_categories'] if x['action'] in ('keep', 'add')]
    removed_cases = [x['name'] for x in preview['case_categories'] if x['action'] == 'remove']

    for rm in removed_cases:
        conn.execute(
            "UPDATE cases SET category='一般備忘' WHERE channel_id=? AND category=?",
            (channel_id, rm)
        )
    conn.execute("DELETE FROM oa_case_categories WHERE channel_id=?", (channel_id,))
    for idx, it in enumerate(final_cases):
        cid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO oa_case_categories (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (cid, channel_id, it['name'], idx)
        )

    import reports
    reports.audit(
        conn, actor, "category.apply", preview['pack_name'],
        f"套用分類組合「{preview['pack_name']}」（方式：{'取代' if mode=='replace' else '合併'}）"
    )

    return list_oa_categories(conn, channel_id)


def substitute_template(template_str: str, contact_name: str, oa_name: str) -> str:
    tz_taipei = timezone(timedelta(hours=8))
    today_str = datetime.now(tz_taipei).strftime('%Y-%m-%d')
    res = template_str.replace('{聯絡對象}', contact_name or '')
    res = res.replace('{今天}', today_str)
    res = res.replace('{OA}', oa_name or '')
    return res


def get_oa_enabled_templates(conn: sqlite3.Connection, channel_id: str, contact_name: str = '') -> dict:
    """Returns grouped case and note templates from all enabled packs for current OA."""
    ensure_oa_default_categories(conn, channel_id)
    enabled_rows = conn.execute("SELECT pack_key FROM oa_enabled_packs WHERE channel_id=?", (channel_id,)).fetchall()
    enabled_keys = [r[0] for r in enabled_rows]

    oa_row = conn.execute("SELECT name, org_id FROM line_channels WHERE channel_id=?", (channel_id,)).fetchone()
    oa_name = oa_row[0] if oa_row else ""
    workspace_id = oa_row[1] if oa_row else ""

    deleted_preset_ids = get_deleted_preset_ids(conn, workspace_id)

    case_groups = []
    note_groups = []

    for k in enabled_keys:
        if k in PRESET_PACKS:
            p = PRESET_PACKS[k]
            # Case templates
            cts = []
            for t in p.get('case_templates', []):
                if t['template_id'] in deleted_preset_ids:
                    continue
                t_copy = dict(t)
                t_copy['rendered_title'] = substitute_template(t.get('title', ''), contact_name, oa_name)
                t_copy['rendered_body'] = substitute_template(t.get('body', ''), contact_name, oa_name)
                cts.append(t_copy)
            if cts:
                case_groups.append({'pack_name': p['name'], 'pack_key': k, 'templates': cts})

            # Note templates
            nts = []
            for t in p.get('note_templates', []):
                if t['template_id'] in deleted_preset_ids:
                    continue
                t_copy = dict(t)
                t_copy['rendered_title'] = substitute_template(t.get('title', ''), contact_name, oa_name)
                t_copy['rendered_body'] = substitute_template(t.get('body', ''), contact_name, oa_name)
                nts.append(t_copy)
            if nts:
                note_groups.append({'pack_name': p['name'], 'pack_key': k, 'templates': nts})
        else:
            # Custom pack
            conn.row_factory = sqlite3.Row
            pack_row = conn.execute("SELECT * FROM template_packs WHERE pack_id=?", (k,)).fetchone()
            if pack_row:
                pname = pack_row['name']
                # Case templates
                cts = []
                for t in conn.execute("SELECT * FROM case_templates WHERE pack_id=? ORDER BY sort_order ASC", (k,)).fetchall():
                    td = dict(t)
                    td['defaults'] = json.loads(td.get('defaults_json') or '{}')
                    td['rendered_title'] = substitute_template(td.get('title', ''), contact_name, oa_name)
                    td['rendered_body'] = substitute_template(td.get('body', ''), contact_name, oa_name)
                    cts.append(td)
                if cts:
                    case_groups.append({'pack_name': pname, 'pack_key': k, 'templates': cts})

                # Note templates
                nts = []
                for t in conn.execute("SELECT * FROM note_templates WHERE pack_id=? ORDER BY sort_order ASC", (k,)).fetchall():
                    td = dict(t)
                    td['defaults'] = json.loads(td.get('defaults_json') or '{}')
                    td['rendered_title'] = substitute_template(td.get('title', ''), contact_name, oa_name)
                    td['rendered_body'] = substitute_template(td.get('body', ''), contact_name, oa_name)
                    nts.append(td)
                if nts:
                    note_groups.append({'pack_name': pname, 'pack_key': k, 'templates': nts})

    return {
        'case_template_groups': case_groups,
        'note_template_groups': note_groups
    }


# ==========================================
# 自訂範本包與範本管理 (Section 17.2 - 17.4)
# ==========================================

def save_custom_pack(conn: sqlite3.Connection, workspace_id: str, payload: dict, actor: str) -> dict:
    name = str(payload.get('name', '')).strip()
    if not name or len(name) > 30:
        raise ValueError('範本包名稱需在 1 至 30 字以內。')
    desc = str(payload.get('description', '')).strip()
    if len(desc) > 100:
        raise ValueError('範本包說明請在 100 字以內。')

    note_types = payload.get('note_types', ['一般備忘'])
    if not isinstance(note_types, list) or len(note_types) > limits.CATEGORIES_PER_OA:
        raise ValueError(f'記事類型最多 {limits.CATEGORIES_PER_OA} 項。')
    if '一般備忘' not in note_types:
        note_types.insert(0, '一般備忘')

    case_categories = payload.get('case_categories', ['一般備忘'])
    if not isinstance(case_categories, list) or len(case_categories) > limits.CATEGORIES_PER_OA:
        raise ValueError(f'案件類別最多 {limits.CATEGORIES_PER_OA} 項。')
    if '一般備忘' not in case_categories:
        case_categories.insert(0, '一般備忘')

    pack_id = payload.get('pack_id')
    now = now_iso()

    if pack_id:
        row = conn.execute("SELECT * FROM template_packs WHERE pack_id=? AND workspace_id=?", (pack_id, workspace_id)).fetchone()
        if not row:
            raise ValueError('找不到要修改的範本包。')
        if row[6] == 1 and not payload.get('unlock'):  # is_locked
            raise ValueError('範本包已鎖定，請先解鎖後再修改。')
        
        # Check duplicate name in workspace
        dup = conn.execute("SELECT 1 FROM template_packs WHERE workspace_id=? AND name=? AND pack_id!=?", (workspace_id, name, pack_id)).fetchone()
        if dup:
            raise ValueError('同工作區已有同名的範本包。')

        conn.execute(
            """UPDATE template_packs SET name=?, description=?, note_types_json=?, case_categories_json=?, updated_by=?, updated_at=?
               WHERE pack_id=? AND workspace_id=?""",
            (name, desc, json.dumps(note_types, ensure_ascii=False), json.dumps(case_categories, ensure_ascii=False), actor, now, pack_id, workspace_id)
        )
    else:
        # 每個工作區的自訂範本包上限
        cnt = conn.execute("SELECT COUNT(*) FROM template_packs WHERE workspace_id=?", (workspace_id,)).fetchone()[0]
        if cnt >= limits.CUSTOM_PACKS_PER_WORKSPACE:
            raise ValueError(f'每個工作區最多建立 {limits.CUSTOM_PACKS_PER_WORKSPACE} 個自訂範本包。')
        dup = conn.execute("SELECT 1 FROM template_packs WHERE workspace_id=? AND name=?", (workspace_id, name)).fetchone()
        if dup:
            raise ValueError('同工作區已有同名的範本包。')

        pack_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO template_packs (pack_id, workspace_id, name, description, note_types_json, case_categories_json, is_locked, created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (pack_id, workspace_id, name, desc, json.dumps(note_types, ensure_ascii=False), json.dumps(case_categories, ensure_ascii=False), actor, actor, now, now)
        )

    import reports
    reports.audit(conn, actor, 'template_pack.save', pack_id, f"儲存自訂範本包「{name}」")
    return {'pack_id': pack_id, 'name': name}


def delete_custom_pack(conn: sqlite3.Connection, workspace_id: str, pack_id: str, actor: str) -> bool:
    if pack_id in PRESET_PACKS:
        raise ValueError('預設範本包不可刪除。')
    row = conn.execute("SELECT name, is_locked FROM template_packs WHERE pack_id=? AND workspace_id=?", (pack_id, workspace_id)).fetchone()
    if not row:
        raise ValueError('找不到範本包。')
    if row[1] == 1:
        raise ValueError('範本包已鎖定，請先解鎖後再刪除。')

    name = row[0]
    conn.execute("DELETE FROM case_templates WHERE pack_id=?", (pack_id,))
    conn.execute("DELETE FROM note_templates WHERE pack_id=?", (pack_id,))
    conn.execute("DELETE FROM oa_enabled_packs WHERE pack_key=?", (pack_id,))
    conn.execute("DELETE FROM template_packs WHERE pack_id=? AND workspace_id=?", (pack_id, workspace_id))

    import reports
    reports.audit(conn, actor, 'template_pack.delete', pack_id, f"刪除自訂範本包「{name}」")
    return True


def copy_pack(conn: sqlite3.Connection, workspace_id: str, source_pack_key: str, new_name: str, actor: str) -> dict:
    new_name = new_name.strip()
    if not new_name or len(new_name) > 30:
        raise ValueError('新範本包名稱需在 1 至 30 字以內。')
    
    cnt = conn.execute("SELECT COUNT(*) FROM template_packs WHERE workspace_id=?", (workspace_id,)).fetchone()[0]
    if cnt >= limits.CUSTOM_PACKS_PER_WORKSPACE:
        raise ValueError(f'每個工作區最多建立 {limits.CUSTOM_PACKS_PER_WORKSPACE} 個自訂範本包。')
    dup = conn.execute("SELECT 1 FROM template_packs WHERE workspace_id=? AND name=?", (workspace_id, new_name)).fetchone()
    if dup:
        raise ValueError('同工作區已有同名的範本包。')

    now = now_iso()
    new_pack_id = uuid.uuid4().hex

    if source_pack_key in PRESET_PACKS:
        src = PRESET_PACKS[source_pack_key]
        desc = src.get('description', '')
        note_types = src.get('note_types', ['一般備忘'])
        case_cats = src.get('case_categories', ['一般備忘'])
        case_tmpls = src.get('case_templates', [])
        note_tmpls = src.get('note_templates', [])
    else:
        conn.row_factory = sqlite3.Row
        src_row = conn.execute("SELECT * FROM template_packs WHERE pack_id=?", (source_pack_key,)).fetchone()
        if not src_row:
            raise ValueError('找不到來源範本包。')
        desc = src_row['description']
        note_types = json.loads(src_row['note_types_json'] or '[]')
        case_cats = json.loads(src_row['case_categories_json'] or '[]')
        case_tmpls = [dict(r) for r in conn.execute("SELECT * FROM case_templates WHERE pack_id=?", (source_pack_key,)).fetchall()]
        note_tmpls = [dict(r) for r in conn.execute("SELECT * FROM note_templates WHERE pack_id=?", (source_pack_key,)).fetchall()]

    conn.execute(
        """INSERT INTO template_packs (pack_id, workspace_id, name, description, note_types_json, case_categories_json, is_locked, created_by, updated_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (new_pack_id, workspace_id, new_name, desc, json.dumps(note_types, ensure_ascii=False), json.dumps(case_cats, ensure_ascii=False), actor, actor, now, now)
    )

    for idx, ct in enumerate(case_tmpls):
        tid = uuid.uuid4().hex
        d_json = json.dumps(ct.get('defaults', {}) if isinstance(ct.get('defaults'), dict) else json.loads(ct.get('defaults_json') or '{}'), ensure_ascii=False)
        conn.execute(
            """INSERT INTO case_templates (template_id, pack_id, name, category_name, title, body, defaults_json, sort_order, is_locked, created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (tid, new_pack_id, ct.get('name', ''), ct.get('category_name', '一般備忘'), ct.get('title', ''), ct.get('body', ''), d_json, idx, actor, actor, now, now)
        )

    for idx, nt in enumerate(note_tmpls):
        tid = uuid.uuid4().hex
        d_json = json.dumps(nt.get('defaults', {}) if isinstance(nt.get('defaults'), dict) else json.loads(nt.get('defaults_json') or '{}'), ensure_ascii=False)
        conn.execute(
            """INSERT INTO note_templates (template_id, pack_id, name, category_name, title, body, defaults_json, sort_order, is_locked, created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (tid, new_pack_id, nt.get('name', ''), nt.get('category_name', '一般備忘'), nt.get('title', ''), nt.get('body', ''), d_json, idx, actor, actor, now, now)
        )

    import reports
    reports.audit(conn, actor, 'template_pack.copy', new_pack_id, f"複製範本包為「{new_name}」")
    return {'pack_id': new_pack_id, 'name': new_name}


def toggle_pack_lock(conn: sqlite3.Connection, workspace_id: str, pack_id: str, is_locked: bool, actor: str) -> bool:
    if pack_id in PRESET_PACKS:
        raise ValueError('預設範本包不可修改鎖定狀態。')
    row = conn.execute("SELECT name FROM template_packs WHERE pack_id=? AND workspace_id=?", (pack_id, workspace_id)).fetchone()
    if not row:
        raise ValueError('找不到範本包。')
    conn.execute("UPDATE template_packs SET is_locked=?, updated_by=?, updated_at=? WHERE pack_id=?", (1 if is_locked else 0, actor, now_iso(), pack_id))
    import reports
    reports.audit(conn, actor, 'template_pack.lock', pack_id, f"{'鎖定' if is_locked else '解鎖'}範本包「{row[0]}」")
    return True


# ==========================================
# 範本 CRUD 與存成範本
# ==========================================

def save_template(conn: sqlite3.Connection, workspace_id: str, template_type: str, payload: dict, actor: str) -> dict:
    if template_type not in ('case', 'note'):
        raise ValueError('範本類型不正確。')
    table = 'case_templates' if template_type == 'case' else 'note_templates'
    
    pack_id = payload.get('pack_id')
    template_id = payload.get('template_id')
    is_preset_source = bool(template_id and (template_id.startswith('preset_') or any(
        any(t.get('template_id') == template_id for t in p.get('case_templates', []) + p.get('note_templates', []))
        for p in PRESET_PACKS.values()
    )))

    if not pack_id or pack_id in PRESET_PACKS or pack_id == 'universal':
        # Find first custom pack for this workspace or auto-create one
        custom_pack = conn.execute("SELECT pack_id FROM template_packs WHERE workspace_id=? AND is_locked=0 ORDER BY created_at ASC", (workspace_id,)).fetchone()
        if custom_pack:
            pack_id = custom_pack[0]
        else:
            pack_id = uuid.uuid4().hex
            now = now_iso()
            conn.execute(
                """INSERT INTO template_packs (pack_id, workspace_id, name, description, note_types_json, case_categories_json, is_locked, created_by, updated_by, created_at, updated_at)
                   VALUES (?, ?, '自訂範本庫', '主要業務自訂範本庫', '["一般"]', '["一般"]', 0, ?, ?, ?, ?)""",
                (pack_id, workspace_id, actor, actor, now, now)
            )
            ch = channels.current_id()
            if ch:
                conn.execute("INSERT OR IGNORE INTO oa_enabled_packs (channel_id, pack_key) VALUES (?, ?)", (ch, pack_id))

    if is_preset_source:
        # Mark preset template as deleted so it is replaced by this custom edit
        conn.execute("""CREATE TABLE IF NOT EXISTS deleted_preset_templates (
            workspace_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, template_id)
        )""")
        conn.execute(
            "INSERT OR REPLACE INTO deleted_preset_templates (workspace_id, template_id, deleted_at) VALUES (?, ?, ?)",
            (workspace_id or '', template_id, now_iso())
        )
        template_id = None  # Insert as new custom template
    
    pack = conn.execute("SELECT is_locked FROM template_packs WHERE pack_id=? AND workspace_id=?", (pack_id, workspace_id)).fetchone()
    if not pack:
        raise ValueError('找不到所屬範本包。')
    if pack[0] == 1 and not payload.get('unlock'):
        raise ValueError('範本包已鎖定，無法新增或修改範本。')

    name = str(payload.get('name', '')).strip()
    if not name or len(name) > 30:
        raise ValueError('範本名稱需在 1 至 30 字以內。')
    
    title = str(payload.get('title', '')).strip()
    body = str(payload.get('body', '')).strip()
    if len(body) > 1000:
        raise ValueError('內容骨架請在 1,000 字以內。')
    category_name = str(payload.get('category_name', '一般備忘')).strip() or '一般備忘'
    defaults = payload.get('defaults', {})
    if not isinstance(defaults, dict):
        defaults = {}

    now = now_iso()

    if template_id:
        row = conn.execute(f"SELECT is_locked, pack_id FROM {table} WHERE template_id=?", (template_id,)).fetchone()
        if not row:
            raise ValueError('找不到要修改的範本。')
        if row[0] == 1 and not payload.get('unlock'):
            raise ValueError('範本已鎖定，請先解鎖後再修改。')
        
        dup = conn.execute(f"SELECT 1 FROM {table} WHERE pack_id=? AND name=? AND template_id!=?", (pack_id, name, template_id)).fetchone()
        if dup:
            raise ValueError('同範本包內已有同名範本。')

        conn.execute(
            f"""UPDATE {table} SET name=?, category_name=?, title=?, body=?, defaults_json=?, updated_by=?, updated_at=?
                WHERE template_id=?""",
            (name, category_name, title, body, json.dumps(defaults, ensure_ascii=False), actor, now, template_id)
        )
    else:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pack_id=?", (pack_id,)).fetchone()[0]
        if cnt >= limits.TEMPLATES_PER_PACK:
            raise ValueError(f'每個範本包最多建立 {limits.TEMPLATES_PER_PACK} 個{"案件" if template_type=="case" else "記事"}範本。')
        dup = conn.execute(f"SELECT 1 FROM {table} WHERE pack_id=? AND name=?", (pack_id, name)).fetchone()
        if dup:
            raise ValueError('同範本包內已有同名範本。')

        template_id = uuid.uuid4().hex
        sort_order = cnt
        conn.execute(
            f"""INSERT INTO {table} (template_id, pack_id, name, category_name, title, body, defaults_json, sort_order, is_locked, created_by, updated_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (template_id, pack_id, name, category_name, title, body, json.dumps(defaults, ensure_ascii=False), sort_order, actor, actor, now, now)
        )

    import reports
    reports.audit(conn, actor, f'template_{template_type}.save', template_id, f"儲存{'案件' if template_type=='case' else '記事'}範本「{name}」")
    return {'template_id': template_id, 'name': name}


def delete_template(conn: sqlite3.Connection, workspace_id: str, template_type: str, template_id: str, actor: str) -> bool:
    if not template_id:
        raise ValueError('缺少範本 ID。')

    # Check if this is a preset template
    is_preset = False
    preset_name = ""
    for p in PRESET_PACKS.values():
        key = 'case_templates' if template_type == 'case' else 'note_templates'
        for item in p.get(key, []):
            if item.get('template_id') == template_id:
                is_preset = True
                preset_name = item.get('name', '預設範本')
                break
        if is_preset:
            break

    if is_preset or template_id.startswith('preset_'):
        conn.execute("""CREATE TABLE IF NOT EXISTS deleted_preset_templates (
            workspace_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            deleted_at TEXT NOT NULL,
            PRIMARY KEY (workspace_id, template_id)
        )""")
        now = now_iso()
        conn.execute(
            "INSERT OR REPLACE INTO deleted_preset_templates (workspace_id, template_id, deleted_at) VALUES (?, ?, ?)",
            (workspace_id or '', template_id, now)
        )
        import reports
        reports.audit(conn, actor, f'template_{template_type}.delete', template_id, f"刪除內建{'案件' if template_type=='case' else '記事'}範本「{preset_name or template_id}」")
        return True

    table = 'case_templates' if template_type == 'case' else 'note_templates'
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"""SELECT t.*, p.workspace_id, p.is_locked as pack_locked 
                           FROM {table} t JOIN template_packs p ON t.pack_id=p.pack_id
                           WHERE t.template_id=?""", (template_id,)).fetchone()
    if not row or (workspace_id and row['workspace_id'] != workspace_id):
        raise ValueError('找不到範本。')
    if row['is_locked'] == 1 or row['pack_locked'] == 1:
        raise ValueError('範本或所屬範本包已鎖定，無法刪除。')

    conn.execute(f"DELETE FROM {table} WHERE template_id=?", (template_id,))
    import reports
    reports.audit(conn, actor, f'template_{template_type}.delete', template_id, f"刪除{'案件' if template_type=='case' else '記事'}範本「{row['name']}」")
    return True


def batch_delete_templates(conn: sqlite3.Connection, workspace_id: str, items: list, actor: str) -> int:
    deleted = 0
    for it in items:
        tmpl_id = it.get('template_id')
        tmpl_type = it.get('template_type', 'case')
        if not tmpl_id:
            continue
        try:
            delete_template(conn, workspace_id, tmpl_type, tmpl_id, actor)
            deleted += 1
        except Exception:
            pass
    return deleted


def copy_template(conn: sqlite3.Connection, workspace_id: str, template_type: str, source_id: str, target_pack_id: str, new_name: str, actor: str) -> dict:
    table = 'case_templates' if template_type == 'case' else 'note_templates'
    new_name = new_name.strip()
    if not new_name or len(new_name) > 30:
        raise ValueError('新範本名稱需在 1 至 30 字以內。')

    pack = conn.execute("SELECT is_locked FROM template_packs WHERE pack_id=? AND workspace_id=?", (target_pack_id, workspace_id)).fetchone()
    if not pack:
        raise ValueError('目標範本包不存在。')
    if pack[0] == 1:
        raise ValueError('目標範本包已鎖定，無法新增範本。')

    cnt = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pack_id=?", (target_pack_id,)).fetchone()[0]
    if cnt >= limits.TEMPLATES_PER_PACK:
        raise ValueError(f'目標範本包已達 {limits.TEMPLATES_PER_PACK} 個{"案件" if template_type=="case" else "記事"}範本上限。')
    dup = conn.execute(f"SELECT 1 FROM {table} WHERE pack_id=? AND name=?", (target_pack_id, new_name)).fetchone()
    if dup:
        raise ValueError('目標範本包已有同名範本。')

    # Source can be preset or custom
    src_tmpl = None
    if source_id.startswith('preset_'):
        for p in PRESET_PACKS.values():
            key = 'case_templates' if template_type == 'case' else 'note_templates'
            for item in p.get(key, []):
                if item['template_id'] == source_id:
                    src_tmpl = dict(item)
                    break
            if src_tmpl:
                break
    else:
        conn.row_factory = sqlite3.Row
        r = conn.execute(f"SELECT * FROM {table} WHERE template_id=?", (source_id,)).fetchone()
        if r:
            src_tmpl = dict(r)
            src_tmpl['defaults'] = json.loads(src_tmpl.get('defaults_json') or '{}')

    if not src_tmpl:
        raise ValueError('找不到來源範本。')

    now = now_iso()
    new_id = uuid.uuid4().hex
    conn.execute(
        f"""INSERT INTO {table} (template_id, pack_id, name, category_name, title, body, defaults_json, sort_order, is_locked, created_by, updated_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (new_id, target_pack_id, new_name, src_tmpl.get('category_name', '一般備忘'), src_tmpl.get('title', ''), src_tmpl.get('body', ''),
         json.dumps(src_tmpl.get('defaults', {}), ensure_ascii=False), cnt, actor, actor, now, now)
    )

    import reports
    reports.audit(conn, actor, f'template_{template_type}.copy', new_id, f"複製{'案件' if template_type=='case' else '記事'}範本為「{new_name}」")
    return {'template_id': new_id, 'name': new_name}


def move_template(conn: sqlite3.Connection, workspace_id: str, template_type: str, template_id: str, target_pack_id: str, actor: str) -> bool:
    table = 'case_templates' if template_type == 'case' else 'note_templates'
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"""SELECT t.*, p.workspace_id, p.is_locked as pack_locked 
                           FROM {table} t JOIN template_packs p ON t.pack_id=p.pack_id
                           WHERE t.template_id=?""", (template_id,)).fetchone()
    if not row or row['workspace_id'] != workspace_id:
        raise ValueError('找不到範本。')
    if row['is_locked'] == 1 or row['pack_locked'] == 1:
        raise ValueError('範本已鎖定，無法搬移。')

    target_pack = conn.execute("SELECT is_locked FROM template_packs WHERE pack_id=? AND workspace_id=?", (target_pack_id, workspace_id)).fetchone()
    if not target_pack:
        raise ValueError('目標範本包不存在。')
    if target_pack[0] == 1:
        raise ValueError('目標範本包已鎖定，無法搬入。')

    cnt = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE pack_id=?", (target_pack_id,)).fetchone()[0]
    if cnt >= limits.TEMPLATES_PER_PACK:
        raise ValueError(f'目標範本包已達 {limits.TEMPLATES_PER_PACK} 個{"案件" if template_type=="case" else "記事"}範本上限。')
    dup = conn.execute(f"SELECT 1 FROM {table} WHERE pack_id=? AND name=?", (target_pack_id, row['name'])).fetchone()
    if dup:
        raise ValueError('目標範本包已有同名範本。')

    conn.execute(f"UPDATE {table} SET pack_id=?, sort_order=?, updated_by=?, updated_at=? WHERE template_id=?", (target_pack_id, cnt, actor, now_iso(), template_id))
    import reports
    reports.audit(conn, actor, f'template_{template_type}.move', template_id, f"搬移{'案件' if template_type=='case' else '記事'}範本「{row['name']}」")
    return True


def toggle_template_lock(conn: sqlite3.Connection, workspace_id: str, template_type: str, template_id: str, is_locked: bool, actor: str) -> bool:
    table = 'case_templates' if template_type == 'case' else 'note_templates'
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"""SELECT t.*, p.workspace_id 
                           FROM {table} t JOIN template_packs p ON t.pack_id=p.pack_id
                           WHERE t.template_id=?""", (template_id,)).fetchone()
    if not row or row['workspace_id'] != workspace_id:
        raise ValueError('找不到範本。')

    conn.execute(f"UPDATE {table} SET is_locked=?, updated_by=?, updated_at=? WHERE template_id=?", (1 if is_locked else 0, actor, now_iso(), template_id))
    import reports
    reports.audit(conn, actor, f'template_{template_type}.lock', template_id, f"{'鎖定' if is_locked else '解鎖'}{'案件' if template_type=='case' else '記事'}範本「{row['name']}」")
    return True


def create_template_from_source(conn: sqlite3.Connection, workspace_id: str, source_type: str, source_id: str, target_pack_id: str, template_name: str, actor: str) -> dict:
    """Creates a custom case/note template from an existing case or chat note according to Section 17.4."""
    if source_type not in ('case', 'note'):
        raise ValueError('來源類型不正確。')

    template_name = template_name.strip()
    if not template_name or len(template_name) > 30:
        raise ValueError('範本名稱需在 1 至 30 字以內。')

    conn.row_factory = sqlite3.Row
    if source_type == 'case':
        case_row = conn.execute("SELECT * FROM cases WHERE case_id=?", (source_id,)).fetchone()
        if not case_row:
            raise ValueError('找不到指定的來源案件。')
        category = case_row['category'] or '一般備忘'
        title = case_row['title'] or ''
        body = case_row['description'] or ''
        defaults = {'priority': case_row['priority'] or 'medium'}
        return save_template(conn, workspace_id, 'case', {
            'pack_id': target_pack_id,
            'name': template_name,
            'category_name': category,
            'title': title,
            'body': body,
            'defaults': defaults
        }, actor)
    else:
        note_row = conn.execute("SELECT * FROM chat_notes WHERE note_id=?", (source_id,)).fetchone()
        if not note_row:
            raise ValueError('找不到指定的來源記事。')
        category = note_row['note_type'] or '一般備忘'
        title = note_row['title'] or ''
        body = note_row['content'] or ''
        tags = json.loads(note_row['tags_json'] or '[]')
        defaults = {'tags': tags}
        return save_template(conn, workspace_id, 'note', {
            'pack_id': target_pack_id,
            'name': template_name,
            'category_name': category,
            'title': title,
            'body': body,
            'defaults': defaults
        }, actor)


# ==========================================
# 分類單項管理 (Section 17 條款 2)
# ==========================================

def save_single_category(conn: sqlite3.Connection, channel_id: str, category_type: str, name: str, old_name: str = '', actor: str = '') -> dict:
    if category_type not in ('case', 'note'):
        raise ValueError('分類類型不正確。')
    table = 'oa_case_categories' if category_type == 'case' else 'chat_note_categories'
    name = str(name).strip()
    if not name or len(name) > 20:
        raise ValueError('分類名稱需在 1 至 20 字以內。')

    ensure_oa_default_categories(conn, channel_id)

    if old_name and old_name != name:
        if old_name == '一般備忘':
            raise ValueError('「一般備忘」為系統保留項目，不可改名。')
        dup = conn.execute(f"SELECT 1 FROM {table} WHERE channel_id=? AND name=?", (channel_id, name)).fetchone()
        if dup:
            raise ValueError('已有相同名稱的分類。')
        conn.execute(f"UPDATE {table} SET name=? WHERE channel_id=? AND name=?", (name, channel_id, old_name))
        if category_type == 'case':
            conn.execute("UPDATE cases SET category=? WHERE channel_id=? AND category=?", (name, channel_id, old_name))
        else:
            conn.execute("UPDATE chat_notes SET note_type=? WHERE channel_id=? AND note_type=?", (name, channel_id, old_name))
        import reports
        reports.audit(conn, actor, f'category_{category_type}.rename', channel_id, f"將{'案件類別' if category_type=='case' else '記事類型'}「{old_name}」改名為「{name}」")
    elif not old_name:
        cnt = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE channel_id=?", (channel_id,)).fetchone()[0]
        if cnt >= limits.CATEGORIES_PER_OA:
            raise ValueError(f'{"案件類別" if category_type=="case" else "記事類型"}最多 {limits.CATEGORIES_PER_OA} 項。')
        dup = conn.execute(f"SELECT 1 FROM {table} WHERE channel_id=? AND name=?", (channel_id, name)).fetchone()
        if dup:
            raise ValueError('已有相同名稱的分類。')
        cid = uuid.uuid4().hex
        conn.execute(f"INSERT INTO {table} (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)", (cid, channel_id, name, cnt))
        import reports
        reports.audit(conn, actor, f'category_{category_type}.add', channel_id, f"新增{'案件類別' if category_type=='case' else '記事類型'}「{name}」")

    return list_oa_categories(conn, channel_id)


def delete_single_category(conn: sqlite3.Connection, channel_id: str, category_type: str, name: str, actor: str) -> dict:
    if category_type not in ('case', 'note'):
        raise ValueError('分類類型不正確。')
    if name == '一般備忘':
        raise ValueError('「一般備忘」為系統保留項目，不可刪除。')
    table = 'oa_case_categories' if category_type == 'case' else 'chat_note_categories'
    
    conn.execute(f"DELETE FROM {table} WHERE channel_id=? AND name=?", (channel_id, name))
    if category_type == 'case':
        conn.execute("UPDATE cases SET category='一般備忘' WHERE channel_id=? AND category=?", (channel_id, name))
    else:
        conn.execute("UPDATE chat_notes SET note_type='一般備忘', category_id=COALESCE((SELECT category_id FROM chat_note_categories WHERE channel_id=? AND name='一般備忘'), '') WHERE channel_id=? AND note_type=?", (channel_id, channel_id, name))

    import reports
    reports.audit(conn, actor, f'category_{category_type}.delete', channel_id, f"刪除{'案件類別' if category_type=='case' else '記事類型'}「{name}」（既有項目已轉為一般備忘）")
    return list_oa_categories(conn, channel_id)


def reorder_categories(conn: sqlite3.Connection, channel_id: str, category_type: str, names: list, actor: str) -> dict:
    if category_type not in ('case', 'note'):
        raise ValueError('分類類型不正確。')
    table = 'oa_case_categories' if category_type == 'case' else 'chat_note_categories'
    for idx, name in enumerate(names):
        conn.execute(f"UPDATE {table} SET sort_order=? WHERE channel_id=? AND name=?", (idx, channel_id, name))
    return list_oa_categories(conn, channel_id)

