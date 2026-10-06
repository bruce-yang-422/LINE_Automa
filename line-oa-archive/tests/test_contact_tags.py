import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from oa_fixture import CHANNEL, add_account, register_oa, use_oa
import admin_server
import recipients

USER1 = "U" + "1" * 32
USER2 = "U" + "2" * 32
GROUP1 = "C" + "3" * 32

class ContactTagTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="line-tags-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "instance").mkdir()
        (self.root / "schema.sql").write_bytes((app.BASE_DIR / "schema.sql").read_bytes())
        for target, value in (("BASE_DIR", self.root), ("DATABASE_PATH", self.root / "test.db")):
            p = patch.object(app, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.dict(os.environ, {"PUBLIC_BASE_URL": "https://reports.example.test"}, clear=True)
        p.start()
        self.addCleanup(p.stop)
        app.initialize_database()
        register_oa()
        use_oa(self)
        add_account('boss@test.com', 'org_admin', 'A', 'Boss')

        with app.database_connection() as conn:
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, active, organization_id) VALUES (current_channel(), ?, 'user', 'Alice', 1, 'A')",
                (USER1,)
            )
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, active, organization_id) VALUES (current_channel(), ?, 'user', 'Bob', 1, 'A')",
                (USER2,)
            )
            conn.execute(
                "INSERT INTO recipients (channel_id, recipient_id, kind, display_name, active, organization_id) VALUES (current_channel(), ?, 'group', 'Sales Team', 1, 'A')",
                (GROUP1,)
            )

    def test_tag_crud_and_listing(self):
        with app.database_connection() as conn:
            t1_id = recipients.save_tag(conn, name="VIP 客戶", color="#007AFF")
            t2_id = recipients.save_tag(conn, name="合作夥伴", color="#34C759")
            self.assertTrue(t1_id.startswith("tag_"))
            self.assertTrue(t2_id.startswith("tag_"))

            tags = recipients.list_tags(conn)
            self.assertEqual(len(tags), 2)
            self.assertEqual({t["name"] for t in tags}, {"VIP 客戶", "合作夥伴"})

            # Update tag
            updated_id = recipients.save_tag(conn, name="重要 VIP", color="#FF9500", tag_id=t1_id)
            self.assertEqual(updated_id, t1_id)
            tags_updated = recipients.list_tags(conn)
            t1_row = next(t for t in tags_updated if t["tag_id"] == t1_id)
            self.assertEqual(t1_row["name"], "重要 VIP")
            self.assertEqual(t1_row["color"], "#FF9500")

            # Delete tag
            recipients.delete_tag(conn, t2_id)
            tags_after = recipients.list_tags(conn)
            self.assertEqual(len(tags_after), 1)
            self.assertEqual(tags_after[0]["tag_id"], t1_id)

    def test_contact_notes_and_custom_name(self):
        with app.database_connection() as conn:
            recipients.update_contact(
                conn, USER1, custom_name="小艾 (Alice)",
                notes="每週二需確認報表"
            )
            contacts = recipients.list_contacts(conn)
            c1 = next(c for c in contacts if c["recipient_id"] == USER1)
            self.assertEqual(c1["custom_name"], "小艾 (Alice)")
            self.assertEqual(c1["custom_name"], "小艾 (Alice)")
            self.assertEqual(c1["notes"], "每週二需確認報表")

    def test_contact_tags_assignment_and_cascade(self):
        with app.database_connection() as conn:
            t1_id = recipients.save_tag(conn, name="VIP", color="#007AFF")
            t2_id = recipients.save_tag(conn, name="北部", color="#AF52DE")

            # Assign tags to USER1
            recipients.set_contact_tags(conn, USER1, [t1_id, t2_id])
            # Assign tag to USER2
            recipients.set_contact_tags(conn, USER2, [t1_id])

            contacts = recipients.list_contacts(conn)
            c1 = next(c for c in contacts if c["recipient_id"] == USER1)
            c2 = next(c for c in contacts if c["recipient_id"] == USER2)
            self.assertEqual(len(c1["tags"]), 2)
            self.assertEqual({t["name"] for t in c1["tags"]}, {"VIP", "北部"})
            self.assertEqual(len(c2["tags"]), 1)
            self.assertEqual(c2["tags"][0]["name"], "VIP")

            # Delete tag t1 and verify cascade removal
            recipients.delete_tag(conn, t1_id)
            contacts_after = recipients.list_contacts(conn)
            c1_after = next(c for c in contacts_after if c["recipient_id"] == USER1)
            c2_after = next(c for c in contacts_after if c["recipient_id"] == USER2)
            self.assertEqual(len(c1_after["tags"]), 1)
            self.assertEqual(c1_after["tags"][0]["name"], "北部")
            self.assertEqual(len(c2_after["tags"]), 0)

    def test_bulk_tag_operations(self):
        with app.database_connection() as conn:
            t1_id = recipients.save_tag(conn, name="2026專案", color="#FF3B30")
            t2_id = recipients.save_tag(conn, name="內部同仁", color="#30B0C7")

            # Bulk add t1 to USER1, USER2, GROUP1
            recipients.bulk_update_tags(conn, [USER1, USER2, GROUP1], [t1_id], action="add")

            contacts = recipients.list_contacts(conn)
            for c in contacts:
                self.assertTrue(any(t["id"] == t1_id for t in c["tags"]))

            # Bulk add t2 to USER1 only
            recipients.bulk_update_tags(conn, [USER1], [t2_id], action="add")

            # Bulk remove t1 from USER1 and USER2
            recipients.bulk_update_tags(conn, [USER1, USER2], [t1_id], action="remove")

            contacts_after = recipients.list_contacts(conn)
            c1 = next(c for c in contacts_after if c["recipient_id"] == USER1)
            c2 = next(c for c in contacts_after if c["recipient_id"] == USER2)
            cg = next(c for c in contacts_after if c["recipient_id"] == GROUP1)

            self.assertEqual([t["name"] for t in c1["tags"]], ["內部同仁"])
            self.assertEqual(len(c2["tags"]), 0)
            self.assertEqual([t["name"] for t in cg["tags"]], ["2026專案"])

    def test_http_api_tag_endpoints_and_bulk(self):
        from urllib.request import Request, urlopen
        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok:
                    handler.user = {"email": "boss@test.com", "role": "org_admin", "organization_id": "A", "display_name": "Boss"}
                    handler.identity = handler.user["email"]
                return ok
        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}

        # 1. Create tag via POST /api/tags/save
        req = Request(f"{base}/api/tags/save", data=json.dumps({"name": "VIP特約", "color": "#FF9500"}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))
            tag_id = data["tag"]["id"]
            self.assertEqual(data["tag"]["name"], "VIP特約")

        # 2. Get tags via GET /api/tags
        req = Request(f"{base}/api/tags", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(len(data["tags"]), 1)
            self.assertEqual(data["tags"][0]["id"], tag_id)

        # 3. Update contact with notes and tag via POST /api/contact
        payload = {"id": USER1, "custom_name": "Alice VIP", "notes": "VIP 專屬客服", "tag_ids": [tag_id]}
        req = Request(f"{base}/api/contact", data=json.dumps(payload).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        # 4. Fetch contacts via GET /api/contacts
        req = Request(f"{base}/api/contacts", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertIn("tags", data)
            self.assertEqual(len(data["tags"]), 1)
            c1 = next(c for c in data["contacts"] if c["recipient_id"] == USER1)
            self.assertEqual(c1["custom_name"], "Alice VIP")
            self.assertEqual(c1["notes"], "VIP 專屬客服")
            self.assertEqual(len(c1["tags"]), 1)
            self.assertEqual(c1["tags"][0]["name"], "VIP特約")

        # 5. Bulk add tags via POST /api/contacts/bulk
        req = Request(f"{base}/api/contacts/bulk", data=json.dumps({"action": "add_tags", "contact_ids": [USER2, GROUP1], "tag_ids": [tag_id]}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        req = Request(f"{base}/api/contacts", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            for c in data["contacts"]:
                self.assertEqual(len(c["tags"]), 1)

        # 6. Delete tag via POST /api/tags/delete
        req = Request(f"{base}/api/tags/delete", data=json.dumps({"id": tag_id}).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        req = Request(f"{base}/api/tags", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertEqual(len(data["tags"]), 0)

    def test_work_department_is_independent_and_validated(self):
        with app.database_connection() as conn:
            conn.execute('UPDATE recipients SET department=? WHERE recipient_id=?', ('北區客戶',USER1))
            recipients.update_contact(conn,USER1,'王經理',contact_type='person_business',work_department=' 採購部 ')
            row=next(c for c in recipients.list_contacts(conn) if c['recipient_id']==USER1)
            self.assertEqual((row['department'],row['work_department']),('北區客戶','採購部'))
            recipients.update_contact(conn,USER1,'新備註',contact_type='person_business')
            self.assertEqual(conn.execute('SELECT work_department FROM recipients WHERE recipient_id=?',(USER1,)).fetchone()[0],'採購部')
            with self.assertRaises(ValueError):
                recipients.update_contact(conn,USER1,'',contact_type='person_business',work_department='部'*61)
            recipients.update_contact(conn,USER1,'',contact_type='person_private')
            self.assertEqual(conn.execute('SELECT work_department FROM recipients WHERE recipient_id=?',(USER1,)).fetchone()[0],'')

    def test_existing_v2_adds_work_department_without_changing_group(self):
        with app.database_connection() as conn:
            conn.execute('UPDATE recipients SET department=? WHERE recipient_id=?',('網路部',USER1))
            conn.execute('ALTER TABLE recipients DROP COLUMN work_department')
        app.initialize_database()
        app.initialize_database()
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT department,work_department FROM recipients WHERE recipient_id=?',(USER1,)).fetchone(),('網路部',''))

    def test_contact_type_and_info_fields_persistence(self):
        with app.database_connection() as conn:
            recipients.update_contact(
                conn, USER1, custom_name="王經理",
                contact_type="person_business",
                phone="+886 912-345-678",
                email="wang@private.com",
                postal_code="100",
                address="台北市中正區忠孝西路一段1號",
                organization_name="ABC 廣告公司",
                job_title="業務經理",
                work_phone="02-2345-6789",
                work_phone_ext="888",
                work_email="wang@abc-ad.com",
                notes="長期合作窗口"
            )
            contacts = recipients.list_contacts(conn)
            c1 = next(c for c in contacts if c["recipient_id"] == USER1)
            self.assertEqual(c1["contact_type"], "person_business")
            self.assertEqual(c1["phone"], "+886 912-345-678")
            self.assertEqual(c1["email"], "wang@private.com")
            self.assertEqual(c1["postal_code"], "100")
            self.assertEqual(c1["address"], "台北市中正區忠孝西路一段1號")
            self.assertEqual(c1["organization_name"], "ABC 廣告公司")
            self.assertEqual(c1["job_title"], "業務經理")
            self.assertEqual(c1["work_phone"], "02-2345-6789")
            self.assertEqual(c1["work_phone_ext"], "888")
            self.assertEqual(c1["work_email"], "wang@abc-ad.com")
            self.assertEqual(c1["notes"], "長期合作窗口")

    def test_contact_type_switch_field_cleanup_rules(self):
        with app.database_connection() as conn:
            # 1. Set as person_business
            recipients.update_contact(
                conn, USER1, custom_name="王經理",
                contact_type="person_business",
                phone="0912345678",
                email="wang@private.com",
                postal_code="100",
                address="台北市中正區忠孝西路一段1號",
                organization_name="ABC 廣告公司",
                job_title="經理",
                work_phone="02-23456789",
                work_phone_ext="123",
                work_email="wang@abc.com"
            )

            # 2. Switch to organization: job_title and work_* fields should be cleared
            recipients.update_contact(
                conn, USER1, custom_name="ABC 廣告公司",
                contact_type="organization",
                phone="02-23456789",
                email="contact@abc.com",
                postal_code="100",
                address="台北市中正區忠孝西路一段1號",
                organization_name="ABC 廣告公司",
                job_title="經理",
                work_phone="02-23456789",
                work_phone_ext="123",
                work_email="wang@abc.com"
            )
            contacts = recipients.list_contacts(conn)
            c1 = next(c for c in contacts if c["recipient_id"] == USER1)
            self.assertEqual(c1["contact_type"], "organization")
            self.assertEqual(c1["organization_name"], "ABC 廣告公司")
            self.assertEqual(c1["job_title"], "")
            self.assertEqual(c1["work_phone"], "")
            self.assertEqual(c1["work_phone_ext"], "")
            self.assertEqual(c1["work_email"], "")

            # 3. Switch to person_private: organization_name and work_* fields should be cleared
            recipients.update_contact(
                conn, USER1, custom_name="王小明",
                contact_type="person_private",
                phone="0912345678",
                email="wang@private.com",
                postal_code="100",
                address="台北市中正區忠孝西路一段1號",
                organization_name="ABC 廣告公司"
            )
            contacts = recipients.list_contacts(conn)
            c1 = next(c for c in contacts if c["recipient_id"] == USER1)
            self.assertEqual(c1["contact_type"], "person_private")
            self.assertEqual(c1["organization_name"], "")
            self.assertEqual(c1["phone"], "0912345678")
            self.assertEqual(c1["email"], "wang@private.com")

    def test_http_api_contact_type_and_info_fields(self):
        from urllib.request import Request, urlopen
        class TestHandler(admin_server.AdminHandler):
            def authorized(handler, require_token=True):
                ok = super().authorized(require_token)
                if ok:
                    handler.user = {"email": "boss@test.com", "role": "org_admin", "organization_id": "A", "display_name": "Boss"}
                    handler.identity = handler.user["email"]
                return ok
        server = admin_server.AdminServer(0)
        server.RequestHandlerClass = TestHandler
        server.start()
        self.addCleanup(server.close)
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"Content-Type": "application/json", "Authorization": "Bearer " + server.token, "X-Line-Channel": CHANNEL}

        payload = {
            "id": USER1,
            "custom_name": "陳副理",
            "contact_type": "person_business",
            "phone": "0988-111-222",
            "email": "chen@private.com",
            "postal_code": "800",
            "address": "高雄市新興區中正三路100號",
            "organization_name": "南區經銷商",
            "job_title": "副理",
            "work_phone": "07-1234567",
            "work_phone_ext": "99",
            "work_email": "chen@south-dealer.com",
            "notes": "南部主要聯絡人"
        }
        req = Request(f"{base}/api/contact", data=json.dumps(payload).encode(), headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            self.assertTrue(data.get("ok"))

        req = Request(f"{base}/api/contacts", headers=headers)
        with urlopen(req) as resp:
            data = json.load(resp)
            c1 = next(c for c in data["contacts"] if c["recipient_id"] == USER1)
            self.assertEqual(c1["custom_name"], "陳副理")
            self.assertEqual(c1["contact_type"], "person_business")
            self.assertEqual(c1["organization_name"], "南區經銷商")
            self.assertEqual(c1["job_title"], "副理")
            self.assertEqual(c1["work_phone"], "07-1234567")
            self.assertEqual(c1["work_phone_ext"], "99")
            self.assertEqual(c1["work_email"], "chen@south-dealer.com")
            self.assertEqual(c1["notes"], "南部主要聯絡人")

