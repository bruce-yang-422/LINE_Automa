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
        'description': '適用於多數一般溝通、諮詢與簡易報修情境（新 OA 預設）',
        'is_preset': True,
        'note_types': ['一般', '待辦', '約定事項', '重要提醒', '交接'],
        'case_categories': ['一般', '詢問', '申請', '報修', '反映'],
        'case_templates': [
            {
                'template_id': 'preset_u_case_1',
                'name': '一般詢問',
                'category_name': '詢問',
                'title': '{聯絡對象} - 一般詢問',
                'body': '詢問內容：\n希望回覆方式：',
                'defaults': {'priority': 'medium', 'due_days': 2, 'ref_prompt': ''}
            },
            {
                'template_id': 'preset_u_case_2',
                'name': '申請處理',
                'category_name': '申請',
                'title': '{聯絡對象} - 申請處理',
                'body': '申請項目：\n申請日期：{今天}\n所需文件：',
                'defaults': {'priority': 'medium', 'due_days': 5, 'ref_prompt': '申請編號'}
            },
            {
                'template_id': 'preset_u_case_3',
                'name': '報修處理',
                'category_name': '報修',
                'title': '{聯絡對象} - 報修處理',
                'body': '品項：\n位置：\n狀況描述：\n發生時間：\n方便聯絡時間：',
                'defaults': {'priority': 'high', 'due_days': 3, 'ref_prompt': '設備或產品編號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_u_note_1',
                'name': '聯絡紀錄',
                'category_name': '一般',
                'title': '聯絡紀錄 - {今天}',
                'body': '聯絡對象：{聯絡對象}\n溝通重點：\n後續追蹤：',
                'defaults': {'tags': ['聯絡紀錄']}
            },
            {
                'template_id': 'preset_u_note_2',
                'name': '約定事項',
                'category_name': '約定事項',
                'title': '約定事項',
                'body': '約定事項：\n預計完成日：\n相關窗口：',
                'defaults': {'tags': ['約定事項']}
            },
            {
                'template_id': 'preset_u_note_3',
                'name': '交接紀錄',
                'category_name': '交接',
                'title': '交接紀錄 - {今天}',
                'body': '交接事項：\n目前進度：\n待確認項目：',
                'defaults': {'tags': ['交接']}
            }
        ]
    },
    'school': {
        'pack_id': 'school',
        'key': 'school',
        'name': '學校',
        'description': '適用於學校、班級、補習班與家長聯繫情境',
        'is_preset': True,
        'note_types': ['一般', '學習狀況', '出缺勤', '家長聯繫', '行政事務'],
        'case_categories': ['一般', '請假', '輔導', '設備報修', '家長反映'],
        'case_templates': [
            {
                'template_id': 'preset_sch_case_1',
                'name': '請假申請',
                'category_name': '請假',
                'title': '{聯絡對象} - 請假申請',
                'body': '請假日期：\n節次或時段：\n事由：',
                'defaults': {'priority': 'medium', 'due_days': 1, 'ref_prompt': ''}
            },
            {
                'template_id': 'preset_sch_case_2',
                'name': '設備報修',
                'category_name': '設備報修',
                'title': '{OA} - 設備報修',
                'body': '品項：\n教室/位置：\n狀況描述：\n發生時間：',
                'defaults': {'priority': 'medium', 'due_days': 3, 'ref_prompt': '設備編號'}
            },
            {
                'template_id': 'preset_sch_case_3',
                'name': '家長反映',
                'category_name': '家長反映',
                'title': '{聯絡對象} - 家長反映事項',
                'body': '反映事項：\n發生地點：\n期望處理方式：',
                'defaults': {'priority': 'high', 'due_days': 2, 'ref_prompt': ''}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_sch_note_1',
                'name': '家長聯繫紀錄',
                'category_name': '家長聯繫',
                'title': '家長聯繫 - {聯絡對象}',
                'body': '通話/訊息摘要：\n家長主要回饋：\n導師後續事項：',
                'defaults': {'tags': ['家長聯繫']}
            },
            {
                'template_id': 'preset_sch_note_2',
                'name': '學習狀況觀察',
                'category_name': '學習狀況',
                'title': '學習狀況紀錄',
                'body': '觀察課堂/科目：\n具體表現：\n建議協助事項：',
                'defaults': {'tags': ['學習觀察']}
            }
        ]
    },
    'election': {
        'pack_id': 'election',
        'key': 'election',
        'name': '選舉／服務處',
        'description': '適用於民意代表、候選人服務處與選民服務',
        'is_preset': True,
        'note_types': ['一般', '陳情', '服務案件', '活動', '選務'],
        'case_categories': ['一般', '陳情', '服務申請', '活動', '選務'],
        'case_templates': [
            {
                'template_id': 'preset_elc_case_1',
                'name': '陳情案件',
                'category_name': '陳情',
                'title': '{聯絡對象} - 陳情事項',
                'body': '陳情事由：\n發生地點：\n相關單位：\n期望協助方式：',
                'defaults': {'priority': 'high', 'due_days': 7, 'ref_prompt': '地點或地址'}
            },
            {
                'template_id': 'preset_elc_case_2',
                'name': '服務申請',
                'category_name': '服務申請',
                'title': '{聯絡對象} - 服務申請',
                'body': '申請項目：\n需求說明：\n預計完成期限：',
                'defaults': {'priority': 'medium', 'due_days': 5, 'ref_prompt': '申請編號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_elc_note_1',
                'name': '陳情訪談紀錄',
                'category_name': '陳情',
                'title': '訪談紀錄 - {聯絡對象}',
                'body': '陳情人：{聯絡對象}\n訪談重點：\n承辦窗口：',
                'defaults': {'tags': ['陳情訪談']}
            },
            {
                'template_id': 'preset_elc_note_2',
                'name': '活動聯繫',
                'category_name': '活動',
                'title': '活動聯繫紀錄',
                'body': '活動名稱：\n活動日期：\n出席意向：',
                'defaults': {'tags': ['活動聯繫']}
            }
        ]
    },
    'enterprise': {
        'pack_id': 'enterprise',
        'key': 'enterprise',
        'name': '企業內部',
        'description': '適用於企業內部行政、IT、採購與部門協作',
        'is_preset': True,
        'note_types': ['一般', '交辦', '會議紀錄', '行政', '交接'],
        'case_categories': ['一般', 'IT 報修', '行政申請', '請假', '採購'],
        'case_templates': [
            {
                'template_id': 'preset_ent_case_1',
                'name': 'IT 報修',
                'category_name': 'IT 報修',
                'title': '{聯絡對象} - IT 問題報修',
                'body': '問題系統/設備：\n錯誤訊息/狀況：\n急迫性：',
                'defaults': {'priority': 'high', 'due_days': 1, 'ref_prompt': '設備序號'}
            },
            {
                'template_id': 'preset_ent_case_2',
                'name': '行政申請',
                'category_name': '行政申請',
                'title': '{聯絡對象} - 行政事務申請',
                'body': '申請項目：\n用途說明：\n需求日期：',
                'defaults': {'priority': 'medium', 'due_days': 3, 'ref_prompt': '表單編號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_ent_note_1',
                'name': '會議紀錄',
                'category_name': '會議紀錄',
                'title': '會議紀錄 - {今天}',
                'body': '會議主題：\n出席人員：\n決議事項：\n待辦行動：',
                'defaults': {'tags': ['會議紀錄']}
            },
            {
                'template_id': 'preset_ent_note_2',
                'name': '交辦事項',
                'category_name': '交辦',
                'title': '交辦事項',
                'body': '交辦內容：\n負責人：\n預計完成時間：',
                'defaults': {'tags': ['交辦']}
            }
        ]
    },
    'government': {
        'pack_id': 'government',
        'key': 'government',
        'name': '政府／對外窗口',
        'description': '適用於公務機關、對外服務窗口與民眾查報',
        'is_preset': True,
        'note_types': ['一般', '陳情', '公文往返', '會勘', '追蹤'],
        'case_categories': ['一般', '陳情', '查報', '申請', '會勘'],
        'case_templates': [
            {
                'template_id': 'preset_gov_case_1',
                'name': '民眾查報',
                'category_name': '查報',
                'title': '民眾查報案件',
                'body': '查報項目：\n地點：\n照片/事證：\n發生時間：',
                'defaults': {'priority': 'medium', 'due_days': 5, 'ref_prompt': '地點或地號'}
            },
            {
                'template_id': 'preset_gov_case_2',
                'name': '陳情處理',
                'category_name': '陳情',
                'title': '民眾陳情處理',
                'body': '陳情主旨：\n案由說明：\n主責科室：',
                'defaults': {'priority': 'high', 'due_days': 10, 'ref_prompt': '公文文號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_gov_note_1',
                'name': '會勘紀錄',
                'category_name': '會勘',
                'title': '現場會勘紀錄 - {今天}',
                'body': '會勘地點：\n會勘單位：\n現場結論：',
                'defaults': {'tags': ['會勘']}
            },
            {
                'template_id': 'preset_gov_note_2',
                'name': '公文往返',
                'category_name': '公文往返',
                'title': '公文處理備註',
                'body': '發文字號：\n主旨：\n辦理情形：',
                'defaults': {'tags': ['公文']}
            }
        ]
    },
    'ngo': {
        'pack_id': 'ngo',
        'key': 'ngo',
        'name': '公益團體',
        'description': '適用於非營利組織、基金會、志工與捐款者服務',
        'is_preset': True,
        'note_types': ['一般', '志工', '捐款', '物資', '活動'],
        'case_categories': ['一般', '物資需求', '志工排班', '捐款問題', '反映'],
        'case_templates': [
            {
                'template_id': 'preset_ngo_case_1',
                'name': '物資需求',
                'category_name': '物資需求',
                'title': '{聯絡對象} - 物資需求申請',
                'body': '需求項目與數量：\n需求地點：\n聯絡窗口：',
                'defaults': {'priority': 'medium', 'due_days': 7, 'ref_prompt': ''}
            },
            {
                'template_id': 'preset_ngo_case_2',
                'name': '志工排班',
                'category_name': '志工排班',
                'title': '{聯絡對象} - 志工排班確認',
                'body': '服務日期與時段：\n服務地點：\n當日帶隊人：',
                'defaults': {'priority': 'medium', 'due_days': 3, 'ref_prompt': ''}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_ngo_note_1',
                'name': '志工聯繫',
                'category_name': '志工',
                'title': '志工聯繫紀錄',
                'body': '志工姓名：{聯絡對象}\n聯繫事項：\n出勤意願：',
                'defaults': {'tags': ['志工聯繫']}
            },
            {
                'template_id': 'preset_ngo_note_2',
                'name': '捐款者聯繫',
                'category_name': '捐款',
                'title': '捐款者關懷紀錄',
                'body': '捐款者：{聯絡對象}\n收據需求：\n關懷事項：',
                'defaults': {'tags': ['捐款關懷']}
            }
        ]
    },
    'club': {
        'pack_id': 'club',
        'key': 'club',
        'name': '社團／同好會',
        'description': '適用於社團、學會、協會、同好俱樂部活動與會員服務',
        'is_preset': True,
        'note_types': ['一般', '活動', '會員', '器材', '交接'],
        'case_categories': ['一般', '活動報名', '器材借用', '會員問題', '反映'],
        'case_templates': [
            {
                'template_id': 'preset_clb_case_1',
                'name': '活動報名問題',
                'category_name': '活動報名',
                'title': '{聯絡對象} - 活動報名問題',
                'body': '活動名稱：\n報名序號/場次：\n問題描述：',
                'defaults': {'priority': 'medium', 'due_days': 3, 'ref_prompt': '活動名稱'}
            },
            {
                'template_id': 'preset_clb_case_2',
                'name': '器材借用',
                'category_name': '器材借用',
                'title': '{聯絡對象} - 器材借用申請',
                'body': '借用器材清單：\n借用期間：\n歸還預定日：',
                'defaults': {'priority': 'medium', 'due_days': 2, 'ref_prompt': '器材名稱'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_clb_note_1',
                'name': '活動籌備',
                'category_name': '活動',
                'title': '活動籌備紀錄',
                'body': '活動名稱：\n工作分工：\n目前進度：',
                'defaults': {'tags': ['活動籌備']}
            },
            {
                'template_id': 'preset_clb_note_2',
                'name': '會員聯繫',
                'category_name': '會員',
                'title': '會員聯繫紀錄',
                'body': '會員姓名：{聯絡對象}\n溝通事項：',
                'defaults': {'tags': ['會員聯繫']}
            }
        ]
    },
    'shop': {
        'pack_id': 'shop',
        'key': 'shop',
        'name': '商店／客服',
        'description': '適用於零售門市、電商客服、售後服務與訂單維修',
        'is_preset': True,
        'note_types': ['一般', '訂單', '售後服務', '客訴', '交接'],
        'case_categories': ['一般', '訂單問題', '退換貨', '維修', '客訴'],
        'case_templates': [
            {
                'template_id': 'preset_shp_case_1',
                'name': '訂單問題',
                'category_name': '訂單問題',
                'title': '{聯絡對象} - 訂單諮詢',
                'body': '購買商品：\n問題描述：\n希望處理方式：',
                'defaults': {'priority': 'medium', 'due_days': 2, 'ref_prompt': '訂單編號'}
            },
            {
                'template_id': 'preset_shp_case_2',
                'name': '退換貨處理',
                'category_name': '退換貨',
                'title': '{聯絡對象} - 退換貨申請',
                'body': '商品名稱與型號：\n退換原因：\n收件地址/門市：',
                'defaults': {'priority': 'high', 'due_days': 3, 'ref_prompt': '訂單編號'}
            },
            {
                'template_id': 'preset_shp_case_3',
                'name': '維修處理',
                'category_name': '維修',
                'title': '{聯絡對象} - 產品維修',
                'body': '產品型號：\n故障狀況：\n購買日期/保固狀態：',
                'defaults': {'priority': 'medium', 'due_days': 5, 'ref_prompt': '產品序號'}
            }
        ],
        'note_templates': [
            {
                'template_id': 'preset_shp_note_1',
                'name': '客戶需求追蹤',
                'category_name': '訂單',
                'title': '客戶偏好與需求',
                'body': '客戶偏好：\n詢問商品：\n後續跟進時機：',
                'defaults': {'tags': ['客戶需求']}
            },
            {
                'template_id': 'preset_shp_note_2',
                'name': '售後追蹤',
                'category_name': '售後服務',
                'title': '售後關懷紀錄',
                'body': '關懷事項：\n客戶滿意度：\n其他備註：',
                'defaults': {'tags': ['售後追蹤']}
            }
        ]
    }
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_oa_default_categories(conn: sqlite3.Connection, channel_id: str):
    """Ensure OA has at least '一般' in categories and 'universal' enabled by default."""
    # Check enabled packs
    row = conn.execute("SELECT 1 FROM oa_enabled_packs WHERE channel_id=?", (channel_id,)).fetchone()
    if not row:
        conn.execute("INSERT OR IGNORE INTO oa_enabled_packs (channel_id, pack_key) VALUES (?, 'universal')", (channel_id,))

    # Note categories
    n_row = conn.execute("SELECT 1 FROM oa_note_categories WHERE channel_id=?", (channel_id,)).fetchone()
    if not n_row:
        for idx, name in enumerate(PRESET_PACKS['universal']['note_types']):
            cid = uuid.uuid4().hex
            conn.execute(
                "INSERT OR IGNORE INTO oa_note_categories (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)",
                (cid, channel_id, name, idx)
            )

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
        FROM oa_note_categories nc
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

    packs = []
    # 1. Preset packs
    for k, p in PRESET_PACKS.items():
        pack_copy = dict(p)
        pack_copy['is_enabled'] = (k in enabled_keys)
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

    target_notes = pack.get('note_types', ['一般'])
    if '一般' not in target_notes:
        target_notes.insert(0, '一般')
        
    target_cases = pack.get('case_categories', ['一般'])
    if '一般' not in target_cases:
        target_cases.insert(0, '一般')

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
                if mode == 'merge' or name == '一般' or info['usage_count'] > 0:
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

    # Reassign removed notes to '一般'
    for rm in removed_notes:
        conn.execute(
            "UPDATE chat_notes SET note_type='一般' WHERE channel_id=? AND note_type=?",
            (channel_id, rm)
        )
    conn.execute("DELETE FROM oa_note_categories WHERE channel_id=?", (channel_id,))
    for idx, it in enumerate(final_notes):
        cid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO oa_note_categories (category_id, channel_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (cid, channel_id, it['name'], idx)
        )

    # 2. Update Case Categories
    final_cases = [x for x in preview['case_categories'] if x['action'] in ('keep', 'add')]
    removed_cases = [x['name'] for x in preview['case_categories'] if x['action'] == 'remove']

    for rm in removed_cases:
        conn.execute(
            "UPDATE cases SET category='一般' WHERE channel_id=? AND category=?",
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

    oa_row = conn.execute("SELECT name FROM line_channels WHERE channel_id=?", (channel_id,)).fetchone()
    oa_name = oa_row[0] if oa_row else ""

    case_groups = []
    note_groups = []

    for k in enabled_keys:
        if k in PRESET_PACKS:
            p = PRESET_PACKS[k]
            # Case templates
            cts = []
            for t in p.get('case_templates', []):
                t_copy = dict(t)
                t_copy['rendered_title'] = substitute_template(t.get('title', ''), contact_name, oa_name)
                t_copy['rendered_body'] = substitute_template(t.get('body', ''), contact_name, oa_name)
                cts.append(t_copy)
            if cts:
                case_groups.append({'pack_name': p['name'], 'pack_key': k, 'templates': cts})

            # Note templates
            nts = []
            for t in p.get('note_templates', []):
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

    note_types = payload.get('note_types', ['一般'])
    if not isinstance(note_types, list) or len(note_types) > limits.CATEGORIES_PER_OA:
        raise ValueError(f'記事類型最多 {limits.CATEGORIES_PER_OA} 項。')
    if '一般' not in note_types:
        note_types.insert(0, '一般')

    case_categories = payload.get('case_categories', ['一般'])
    if not isinstance(case_categories, list) or len(case_categories) > limits.CATEGORIES_PER_OA:
        raise ValueError(f'案件類別最多 {limits.CATEGORIES_PER_OA} 項。')
    if '一般' not in case_categories:
        case_categories.insert(0, '一般')

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
        note_types = src.get('note_types', ['一般'])
        case_cats = src.get('case_categories', ['一般'])
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
            (tid, new_pack_id, ct.get('name', ''), ct.get('category_name', '一般'), ct.get('title', ''), ct.get('body', ''), d_json, idx, actor, actor, now, now)
        )

    for idx, nt in enumerate(note_tmpls):
        tid = uuid.uuid4().hex
        d_json = json.dumps(nt.get('defaults', {}) if isinstance(nt.get('defaults'), dict) else json.loads(nt.get('defaults_json') or '{}'), ensure_ascii=False)
        conn.execute(
            """INSERT INTO note_templates (template_id, pack_id, name, category_name, title, body, defaults_json, sort_order, is_locked, created_by, updated_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (tid, new_pack_id, nt.get('name', ''), nt.get('category_name', '一般'), nt.get('title', ''), nt.get('body', ''), d_json, idx, actor, actor, now, now)
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
    if not pack_id or pack_id in PRESET_PACKS:
        raise ValueError('請選擇有效的自訂範本包。')
    
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
    category_name = str(payload.get('category_name', '一般')).strip() or '一般'
    defaults = payload.get('defaults', {})
    if not isinstance(defaults, dict):
        defaults = {}

    template_id = payload.get('template_id')
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
    table = 'case_templates' if template_type == 'case' else 'note_templates'
    conn.row_factory = sqlite3.Row
    row = conn.execute(f"""SELECT t.*, p.workspace_id, p.is_locked as pack_locked 
                           FROM {table} t JOIN template_packs p ON t.pack_id=p.pack_id
                           WHERE t.template_id=?""", (template_id,)).fetchone()
    if not row or row['workspace_id'] != workspace_id:
        raise ValueError('找不到範本。')
    if row['is_locked'] == 1 or row['pack_locked'] == 1:
        raise ValueError('範本或所屬範本包已鎖定，無法刪除。')

    conn.execute(f"DELETE FROM {table} WHERE template_id=?", (template_id,))
    import reports
    reports.audit(conn, actor, f'template_{template_type}.delete', template_id, f"刪除{'案件' if template_type=='case' else '記事'}範本「{row['name']}」")
    return True


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
        (new_id, target_pack_id, new_name, src_tmpl.get('category_name', '一般'), src_tmpl.get('title', ''), src_tmpl.get('body', ''),
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
        category = case_row['category'] or '一般'
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
        category = note_row['note_type'] or '一般'
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
    table = 'oa_case_categories' if category_type == 'case' else 'oa_note_categories'
    name = str(name).strip()
    if not name or len(name) > 20:
        raise ValueError('分類名稱需在 1 至 20 字以內。')

    ensure_oa_default_categories(conn, channel_id)

    if old_name and old_name != name:
        if old_name == '一般':
            raise ValueError('「一般」為系統保留項目，不可改名。')
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
    if name == '一般':
        raise ValueError('「一般」為系統保留項目，不可刪除。')
    table = 'oa_case_categories' if category_type == 'case' else 'oa_note_categories'
    
    conn.execute(f"DELETE FROM {table} WHERE channel_id=? AND name=?", (channel_id, name))
    if category_type == 'case':
        conn.execute("UPDATE cases SET category='一般' WHERE channel_id=? AND category=?", (channel_id, name))
    else:
        conn.execute("UPDATE chat_notes SET note_type='一般' WHERE channel_id=? AND note_type=?", (channel_id, name))

    import reports
    reports.audit(conn, actor, f'category_{category_type}.delete', channel_id, f"刪除{'案件類別' if category_type=='case' else '記事類型'}「{name}」（既有項目已轉為一般）")
    return list_oa_categories(conn, channel_id)


def reorder_categories(conn: sqlite3.Connection, channel_id: str, category_type: str, names: list, actor: str) -> dict:
    if category_type not in ('case', 'note'):
        raise ValueError('分類類型不正確。')
    table = 'oa_case_categories' if category_type == 'case' else 'oa_note_categories'
    for idx, name in enumerate(names):
        conn.execute(f"UPDATE {table} SET sort_order=? WHERE channel_id=? AND name=?", (idx, channel_id, name))
    return list_oa_categories(conn, channel_id)

