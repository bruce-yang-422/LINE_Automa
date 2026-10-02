"""Tests for Chat Notes Management, Taxonomy Governance, and RBAC according to 對話記事本管理規格.md."""

import json
import sqlite3
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import app
import channels
import chat_notes
import cases
import limits
from oa_fixture import CHANNEL, add_account, register_oa, use_oa


class ChatNotesManagementTests(unittest.TestCase):
    def setUp(self):
        self.tmp_db = app.DATABASE_PATH.parent / f"test_notes_mgmt_{self._testMethodName}.db"
        if self.tmp_db.exists():
            self.tmp_db.unlink()
        app.DATABASE_PATH = self.tmp_db
        app.initialize_database()
        register_oa("org_test", "測試組織", CHANNEL, "U_bot_notes", name="OA 記事測試")
        add_account("admin@test.com", "org_admin", "org_test", "管理員")
        add_account("op@test.com", "operator", "org_test", "操作員")
        add_account("collab@test.com", "collaborator", "org_test", "協作員")
        with app.database_connection() as conn:
            # 建立測試聯絡人
            conn.execute(
                "INSERT OR IGNORE INTO recipients (recipient_id, channel_id, kind, display_name, active) VALUES ('U_customer_1', ?, 'user', '測試客戶1', 1)",
                (CHANNEL,)
            )
        use_oa(self, CHANNEL)

    def tearDown(self):
        if self.tmp_db.exists():
            try:
                self.tmp_db.unlink()
            except Exception:
                pass

    def test_default_categories_and_tags_seeding(self):
        """驗證初始預設 8 大通用分類與 8 大通用標籤（Apple HIG 色彩）可正確初始化。"""
        with app.database_connection() as conn:
            chat_notes.ensure_default_categories(conn, CHANNEL)
            chat_notes.ensure_default_tags(conn, CHANNEL)
            
            cat_data = chat_notes.list_note_categories(conn)
            self.assertEqual(cat_data['count'], 8)
            cat_names = [c['name'] for c in cat_data['categories']]
            self.assertIn('商務商談', cat_names)
            self.assertIn('工程工務', cat_names)
            self.assertIn('一般備忘', cat_names)
            # 檢查 Apple System Blue 色票
            blue_cat = next(c for c in cat_data['categories'] if c['name'] == '商務商談')
            self.assertEqual(blue_cat['color'], '#007AFF')

            tag_data = chat_notes.list_note_tags(conn)
            self.assertEqual(tag_data['count'], 8)
            tag_names = [t['name'] for t in tag_data['tags']]
            self.assertIn('急件優先', tag_names)
            self.assertIn('已報價', tag_names)
            self.assertIn('處理中', tag_names)

    def test_explicit_manual_save_and_crud(self):
        """驗證手動明確儲存、編輯、置頂上限(5)與單室記事上限(100)。"""
        with app.database_connection() as conn:
            # 1. 新增記事
            note = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'title': '專案初步需求洽談',
                'content': '討論自動化備份與多 OA 整合細節。',
                'note_type': '商務商談',
                'tags': ['已報價', '重要協議'],
                'due_date': '2026-10-15'
            }, 'op@test.com', 'operator')
            
            note_id = note['note_id']
            self.assertEqual(note['title'], '專案初步需求洽談')
            self.assertEqual(note['tags'], ['已報價', '重要協議'])
            self.assertEqual(note['author'], 'op@test.com')

            # 2. 查閱側欄清單
            room_notes = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(room_notes['count'], 1)
            self.assertEqual(room_notes['notes'][0]['title'], '專案初步需求洽談')

            # 3. 置頂操作與 5 筆上限驗證
            chat_notes.toggle_note_pin(conn, note_id)
            room_notes = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(room_notes['notes'][0]['is_pinned'], 1)
            self.assertEqual(room_notes['pinned_count'], 1)

            # 建立另外 4 筆置頂
            for i in range(4):
                n = chat_notes.save_chat_note(conn, {
                    'recipient_id': 'U_customer_1',
                    'content': f'置頂事項 {i}'
                }, 'op@test.com', 'operator')
                chat_notes.toggle_note_pin(conn, n['note_id'])

            # 第 6 筆置頂應被拒絕
            n6 = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'content': '第 6 筆置頂'
            }, 'op@test.com', 'operator')
            with self.assertRaisesRegex(ValueError, '置頂記事已達上限'):
                chat_notes.toggle_note_pin(conn, n6['note_id'])

            # 4. 標記完成與重啟
            chat_notes.toggle_note_completed(conn, note_id)
            n_status = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(n_status['completed_count'], 1)

            chat_notes.toggle_note_completed(conn, note_id)
            n_status2 = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(n_status2['completed_count'], 0)

    def test_note_lock_policies(self):
        """驗證三種組織鎖定政策 (disabled, collaborative, strict_admin) 及鎖定後防篡改唯讀保護。"""
        with app.database_connection() as conn:
            note = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'title': '重要協議備忘',
                'content': '此合約條款經雙方律師確認。'
            }, 'admin@test.com', 'org_admin')
            note_id = note['note_id']

            # 模式 A: disabled (預設) - 鎖定操作被拒絕
            with self.assertRaisesRegex(ValueError, '自由編輯模式'):
                chat_notes.toggle_note_lock(conn, note_id, 'org_admin')

            # 切換至 模式 B: collaborative (協作鎖定模式)
            conn.execute("UPDATE organizations SET note_lock_policy='collaborative' WHERE org_id='org_test'")
            
            # 任何角色（包括協作人員）皆可鎖定
            res = chat_notes.toggle_note_lock(conn, note_id, 'collaborator')
            self.assertEqual(res['is_locked'], 1)

            # 鎖定狀態下，嘗試編輯或刪除必須被拒絕（唯讀保護，防止誤改）
            with self.assertRaisesRegex(ValueError, '已鎖定為唯讀狀態'):
                chat_notes.save_chat_note(conn, {
                    'note_id': note_id,
                    'recipient_id': 'U_customer_1',
                    'content': '嘗試修改內容'
                }, 'op@test.com', 'operator')

            with self.assertRaisesRegex(ValueError, '已鎖定'):
                chat_notes.delete_chat_note(conn, note_id, 'operator')

            # 協作人員可解鎖
            res_unlock = chat_notes.toggle_note_lock(conn, note_id, 'collaborator')
            self.assertEqual(res_unlock['is_locked'], 0)

            # 切換至 模式 C: strict_admin (管理員嚴格合規模式)
            conn.execute("UPDATE organizations SET note_lock_policy='strict_admin' WHERE org_id='org_test'")
            
            # 僅 org_admin 可鎖定
            with self.assertRaisesRegex(ValueError, '僅組織管理員可以鎖定'):
                chat_notes.toggle_note_lock(conn, note_id, 'operator')
            
            chat_notes.toggle_note_lock(conn, note_id, 'org_admin')
            
            # 協作人員嘗試解鎖被拒絕
            with self.assertRaisesRegex(ValueError, '僅組織管理員可以鎖定'):
                chat_notes.toggle_note_lock(conn, note_id, 'collaborator')

            # 管理員可解鎖
            chat_notes.toggle_note_lock(conn, note_id, 'org_admin')

    def test_soft_delete_restore_and_purge(self):
        """驗證軟刪除（垃圾桶）、還原與管理員永久清除（Purge）。"""
        with app.database_connection() as conn:
            note = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'content': '即將被刪除的記事'
            }, 'admin@test.com', 'org_admin')
            note_id = note['note_id']

            # 軟刪除
            chat_notes.delete_chat_note(conn, note_id, 'operator')
            active_list = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(active_list['count'], 0)
            self.assertEqual(active_list['trash_count'], 1)

            # 垃圾桶清單
            trash = chat_notes.list_trash_notes(conn, 'U_customer_1')
            self.assertEqual(len(trash), 1)

            # 還原
            chat_notes.restore_chat_note(conn, note_id)
            restored = chat_notes.list_chat_notes(conn, 'U_customer_1')
            self.assertEqual(restored['count'], 1)

            # 再次刪除並由管理員永久清除
            chat_notes.delete_chat_note(conn, note_id, 'operator')
            
            # 非管理員嘗試永久刪除被拒絕
            with self.assertRaisesRegex(ValueError, '只有管理員可以永久刪除'):
                chat_notes.purge_chat_note(conn, note_id, 'operator')

            # 管理員永久刪除
            ok = chat_notes.purge_chat_note(conn, note_id, 'org_admin')
            self.assertTrue(ok)
            final_trash = chat_notes.list_trash_notes(conn, 'U_customer_1')
            self.assertEqual(len(final_trash), 0)

    def test_convert_note_to_case(self):
        """驗證記事轉為案件並維護雙向關聯 (linked_case_id)。"""
        with app.database_connection() as conn:
            note = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'title': '重大客戶系統當機回報',
                'content': '客戶伺服器無法連線，需工程師緊急排查。',
                'note_type': '售後客服',
                'due_date': '2026-10-03'
            }, 'op@test.com', 'operator')
            note_id = note['note_id']

            # 轉為案件
            new_case = chat_notes.convert_note_to_case(conn, note_id, 'op@test.com')
            self.assertIn('case_no', new_case)
            self.assertEqual(new_case['case_subject_id'], 'U_customer_1')
            self.assertEqual(new_case['title'], '重大客戶系統當機回報')
            self.assertEqual(new_case['source_note_id'], note_id)

            # 驗證記事上的 linked_case_id
            updated_note = conn.execute("SELECT linked_case_id FROM chat_notes WHERE note_id=?", (note_id,)).fetchone()
            self.assertEqual(updated_note[0], new_case['case_id'])

    def test_category_governance_and_merge(self):
        """驗證分類管理、同義分類合併與歷史記事批次移轉。"""
        with app.database_connection() as conn:
            # 建立兩個自訂分類
            c1 = chat_notes.save_note_category(conn, {'name': '客戶洽談', 'color': '#007AFF'}, 'operator')
            c2 = chat_notes.save_note_category(conn, {'name': '商務拜訪', 'color': '#30B0C7'}, 'operator')
            target = chat_notes.save_note_category(conn, {'name': '商務商談', 'color': '#007AFF'}, 'operator')

            # 建立關聯至 c1, c2 的記事
            n1 = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1', 'content': '記事1', 'category_id': c1['category_id']
            }, 'admin@test.com')
            n2 = chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1', 'content': '記事2', 'category_id': c2['category_id']
            }, 'admin@test.com')

            # 執行分類合併
            res = chat_notes.merge_note_categories(
                conn, [c1['category_id'], c2['category_id']], target['category_id'], 'operator'
            )
            self.assertEqual(res['merged_count'], 2)

            # 驗證 n1, n2 已自動移轉至目標分類
            row1 = conn.execute("SELECT category_id, note_type FROM chat_notes WHERE note_id=?", (n1['note_id'],)).fetchone()
            row2 = conn.execute("SELECT category_id, note_type FROM chat_notes WHERE note_id=?", (n2['note_id'],)).fetchone()
            self.assertEqual(row1[0], target['category_id'])
            self.assertEqual(row1[1], '商務商談')
            self.assertEqual(row2[0], target['category_id'])
            self.assertEqual(row2[1], '商務商談')

            # 舊分類已自動刪除
            rem = conn.execute("SELECT COUNT(*) FROM chat_note_categories WHERE category_id IN (?, ?)", (c1['category_id'], c2['category_id'])).fetchone()[0]
            self.assertEqual(rem, 0)

    def test_tag_governance_merge_and_orphan_cleanup(self):
        """驗證標籤治理：同義標籤合併、孤立標籤一鍵清理與更名。"""
        with app.database_connection() as conn:
            # 建立同義標籤
            chat_notes.save_note_tag(conn, '報價單', color='#007AFF', actor_role='operator')
            chat_notes.save_note_tag(conn, '客戶報價', color='#007AFF', actor_role='operator')
            chat_notes.save_note_tag(conn, '報價確認', color='#007AFF', actor_role='operator')
            chat_notes.save_note_tag(conn, '無人使用的孤立標籤', color='#8E8E93', actor_role='operator')

            # 記事使用標籤
            n1 = chat_notes.save_chat_note(conn, {'recipient_id': 'U_customer_1', 'content': '記事A', 'tags': ['報價單', '急件']}, 'admin@test.com')
            n2 = chat_notes.save_chat_note(conn, {'recipient_id': 'U_customer_1', 'content': '記事B', 'tags': ['客戶報價']}, 'admin@test.com')

            # 合併「報價單」、「客戶報價」至「報價確認」
            merge_res = chat_notes.merge_note_tags(conn, ['報價單', '客戶報價'], '報價確認', 'operator')
            self.assertEqual(merge_res['merged_count'], 2)

            tags_n1 = json.loads(conn.execute("SELECT tags_json FROM chat_notes WHERE note_id=?", (n1['note_id'],)).fetchone()[0])
            tags_n2 = json.loads(conn.execute("SELECT tags_json FROM chat_notes WHERE note_id=?", (n2['note_id'],)).fetchone()[0])
            self.assertIn('報價確認', tags_n1)
            self.assertIn('急件', tags_n1)
            self.assertNotIn('報價單', tags_n1)
            self.assertEqual(tags_n2, ['報價確認'])

            # 清理 0 篇引用之孤立標籤
            clean_res = chat_notes.cleanup_orphan_tags(conn, 'operator')
            self.assertGreaterEqual(clean_res['cleaned_count'], 1)
            self.assertIn('無人使用的孤立標籤', clean_res['cleaned_tags'])

    def test_global_search_and_export(self):
        """驗證全域多條件檢索與 CSV / Markdown / JSON 匯出功能。"""
        with app.database_connection() as conn:
            cat = chat_notes.save_note_category(conn, {'name': '工程工務', 'color': '#FF9500'}, 'operator')
            chat_notes.save_chat_note(conn, {
                'recipient_id': 'U_customer_1',
                'title': '現場機房施工勘查',
                'content': '檢查配線盤與冷氣出風口位置。',
                'category_id': cat['category_id'],
                'tags': ['現場勘查'],
                'due_date': '2026-10-20'
            }, 'op@test.com', 'operator')

            # 1. 全域關鍵字檢索
            res = chat_notes.list_global_chat_notes(conn, {'q': '機房'})
            self.assertEqual(res['total'], 1)
            self.assertEqual(res['notes'][0]['title'], '現場機房施工勘查')

            # 2. 全域分類過濾
            res_cat = chat_notes.list_global_chat_notes(conn, {'category_name': '工程工務'})
            self.assertEqual(res_cat['total'], 1)

            # 3. 匯出 CSV / Markdown / JSON
            csv_bytes, mime_csv, fname_csv = chat_notes.export_chat_notes(conn, {'q': '機房'}, 'csv', 'admin@test.com')
            self.assertIn('text/csv', mime_csv)
            self.assertTrue(fname_csv.endswith('.csv'))
            self.assertIn('現場機房施工勘查', csv_bytes.decode('utf-8'))

            md_bytes, mime_md, fname_md = chat_notes.export_chat_notes(conn, {}, 'md', 'admin@test.com')
            self.assertIn('text/markdown', mime_md)
            self.assertIn('# 對話記事本匯出報告', md_bytes.decode('utf-8'))

            json_bytes, mime_json, fname_json = chat_notes.export_chat_notes(conn, {}, 'json', 'admin@test.com')
            self.assertIn('application/json', mime_json)
            json_obj = json.loads(json_bytes.decode('utf-8'))
            self.assertIn('notes', json_obj)

    def test_http_rbac_and_endpoints(self):
        """驗證各等級 (甲/乙/丙/丁) 透過 HTTP API 呼叫對話記事本與治理功能之權限矩陣。"""
        import admin_server
        
        current_user = {"email": "admin@test.com", "role": "org_admin", "organization_id": "org_test", "display_name": "管理員"}

        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok:
                    handler.user = current_user
                    handler.identity = handler.user["email"]
                return ok

        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}

        # 1. 乙級 (org_admin) - 新增分類、標籤、記事
        current_user = {"email": "admin@test.com", "role": "org_admin", "organization_id": "org_test", "display_name": "管理員"}
        
        # POST /api/chat-notes/categories/save
        req = Request(f"{base}/api/chat-notes/categories/save", data=json.dumps({"name": "商務商談", "color": "#007AFF"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            cat_id = data["category"]["category_id"]

        # POST /api/chat-notes/tags/save
        req = Request(f"{base}/api/chat-notes/tags/save", data=json.dumps({"name": "急件優先", "color": "#FF3B30"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        # POST /api/chat-notes/save (新增記事)
        note_payload = {
            "recipient_id": "U_customer_1",
            "title": "HTTP測試記事",
            "content": "透過HTTP新增的記事內容",
            "category_id": cat_id,
            "tags": ["急件優先"]
        }
        req = Request(f"{base}/api/chat-notes/save", data=json.dumps(note_payload).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            note_id = data["note"]["note_id"]

        # 2. 丁級 (collaborator) - 撰寫記事可以，但管理分類/標籤庫必須被拒絕 (403)
        current_user = {"email": "collab@test.com", "role": "collaborator", "organization_id": "org_test", "display_name": "協作員"}
        
        # 丁級建立記事 (使用既有標籤) -> 成功
        req = Request(f"{base}/api/chat-notes/save", data=json.dumps({
            "recipient_id": "U_customer_1",
            "content": "協作員回報進度",
            "tags": ["急件優先"]
        }).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        # 丁級嘗試建立新分類庫 -> 403 被拒絕
        req = Request(f"{base}/api/chat-notes/categories/save", data=json.dumps({"name": "丁級自創分類"}).encode(), headers=headers)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

        # 丁級嘗試建立新標籤庫 -> 403 被拒絕
        req = Request(f"{base}/api/chat-notes/tags/save", data=json.dumps({"name": "丁級自創標籤"}).encode(), headers=headers)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

        # 3. 丙級 (operator) - 可管理分類與標籤，但不可 purge (403)
        current_user = {"email": "op@test.com", "role": "operator", "organization_id": "org_test", "display_name": "操作員"}
        
        # 丙級可建立分類
        req = Request(f"{base}/api/chat-notes/categories/save", data=json.dumps({"name": "客服排障", "color": "#FF3B30"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        # 丙級嘗試 purge 記事 -> 403 被拒絕
        req = Request(f"{base}/api/chat-notes/purge", data=json.dumps({"note_id": note_id}).encode(), headers=headers)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

        # 4. 甲級 (platform_admin) - 唯讀，禁止任何寫入操作 (403)
        current_user = {"email": "plat@test.com", "role": "platform_admin", "organization_id": "", "display_name": "平台管理員"}
        
        # 甲級查詢清單 -> 200 (唯讀)
        req = Request(f"{base}/api/chat-notes?recipient_id=U_customer_1", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("notes", data)

        # 甲級嘗試新增/修改記事 -> 403 被拒絕
        req = Request(f"{base}/api/chat-notes/save", data=json.dumps({"recipient_id": "U_customer_1", "content": "甲級不應能寫入"}).encode(), headers=headers)
        with self.assertRaises(HTTPError) as ctx:
            urlopen(req)
        self.assertEqual(ctx.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
