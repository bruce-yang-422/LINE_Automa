import unittest

import app
import channels
import chat_notes
import cases
import test_recipients as fixtures


class NoteTaskTests(unittest.TestCase):
    setUp = fixtures.RecipientTests.setUp

    def create(self, conn):
        return chat_notes.save_chat_note(conn, {'recipient_id': fixtures.USER, 'title': '待辦',
            'content': '```text\r\n- [ ] 程式範例\r\n```\r\n- [ ] 第一項\r\n  * [X] 第二項'}, 'author')

    def test_check_and_uncheck_preserve_content_and_metadata(self):
        with app.database_connection() as conn:
            note = self.create(conn)
            result = chat_notes.update_note_task(conn, {'note_id': note['note_id'], 'task_index': 0,
                'checked': True, 'expected_content': note['content']}, 'editor')
            self.assertIn('- [ ] 程式範例', result['content'])
            self.assertIn('- [x] 第一項', result['content'])
            second = chat_notes.update_note_task(conn, {'note_id': note['note_id'], 'task_index': 1,
                'checked': False, 'expected_content': result['content']}, 'editor')
            self.assertIn('* [ ] 第二項', second['content'])
            row = conn.execute('SELECT title,author,created_at FROM chat_notes WHERE note_id=?', (note['note_id'],)).fetchone()
            self.assertEqual(row['title'], '待辦')
            self.assertEqual(row['author'], 'author')
            self.assertEqual(row['created_at'], note['created_at'])

    def test_locked_deleted_other_oa_and_concurrent_edits_are_rejected(self):
        with app.database_connection() as conn:
            note = self.create(conn)
            payload = {'note_id': note['note_id'], 'task_index': 0, 'checked': True, 'expected_content': note['content']}
            with channels.use('other-oa'), self.assertRaises(ValueError):
                chat_notes.update_note_task(conn, payload, 'editor')
            conn.execute('UPDATE chat_notes SET is_locked=1 WHERE note_id=?', (note['note_id'],))
            with self.assertRaises(ValueError): chat_notes.update_note_task(conn, payload, 'editor')

            conn.execute("UPDATE chat_notes SET is_locked=0,content='別人修改的內容' WHERE note_id=?", (note['note_id'],))
            with self.assertRaises(ValueError): chat_notes.update_note_task(conn, payload, 'editor')
            self.assertEqual(conn.execute('SELECT content FROM chat_notes WHERE note_id=?', (note['note_id'],)).fetchone()[0], '別人修改的內容')
            conn.execute("UPDATE chat_notes SET deleted_at='deleted' WHERE note_id=?", (note['note_id'],))
            with self.assertRaises(ValueError): chat_notes.update_note_task(conn, payload, 'editor')

    def test_case_tasks_preserve_metadata_and_reject_locked_closed_or_stale_content(self):
        app.save_events([fixtures.RecipientTests.event(self)])
        with app.database_connection() as conn:
            c = cases.create_case(conn, {'case_subject_id': fixtures.USER, 'title': '案件待辦', 'description': '- [ ] 回覆\n- [x] 確認'}, 'author')
            payload = {'case_id': c['case_id'], 'task_index': 0, 'checked': True, 'expected_content': c['description']}
            result = cases.update_case_task(conn, payload, 'editor')
            self.assertEqual(result['description'], '- [x] 回覆\n- [x] 確認')
            self.assertEqual(result['title'], c['title'])
            with self.assertRaises(ValueError): cases.update_case_task(conn, payload, 'editor')
            payload.update(expected_content=result['description'], checked=False)
            result = cases.update_case_task(conn, payload, 'editor')
            self.assertEqual(result['description'], c['description'])
            payload['expected_content'] = result['description']
            conn.execute('UPDATE cases SET is_locked=1 WHERE case_id=?', (c['case_id'],))
            with self.assertRaises(ValueError): cases.update_case_task(conn, payload, 'editor')
            conn.execute("UPDATE cases SET is_locked=0,status='closed' WHERE case_id=?", (c['case_id'],))
            with self.assertRaises(ValueError): cases.update_case_task(conn, payload, 'editor')



if __name__ == '__main__': unittest.main()
