import base64
import copy
import io
import unittest

from PIL import Image
import app, channels, forms, forms_validation as validation, form_content, reports
import test_forms_permissions as permissions
from test_roles_and_permissions import COLLABORATOR


class ContentTests(unittest.TestCase):
    setUp = permissions.FormsPermissionsTests.setUp
    setup_roles_environment = permissions.FormsPermissionsTests.setup_roles_environment
    prepare = permissions.FormsPermissionsTests.prepare
    create = permissions.FormsPermissionsTests.create

    def test_youtube_known_hosts_and_single_video(self):
        for url in ('https://youtu.be/abcdefghijk', 'https://www.youtube.com/watch?v=abcdefghijk&t=30',
                    'https://www.youtube.com/embed/abcdefghijk', 'https://www.youtube.com/shorts/abcdefghijk'):
            self.assertEqual(validation.youtube_id(url), 'abcdefghijk')
        for url in ('javascript:alert(1)', 'https://youtube.com.evil.test/watch?v=abcdefghijk',
                    'https://user@youtube.com/watch?v=abcdefghijk', 'https://youtube.com:444/watch?v=abcdefghijk',
                    'https://youtu.be/abc', 'https://youtube.com/watch?v=abcdefghijk&v=lmnopqrstuv'):
            with self.assertRaises(ValueError): validation.youtube_id(url)

    def test_content_never_accepts_answers_or_required(self):
        q = forms.question('notice', '閱讀說明', 'content')
        q['content'] = {'kind': 'video', 'youtube_url': 'https://youtu.be/abcdefghijk'}
        normalized = validation.validate_questions([q])
        self.assertEqual(normalized[0]['content']['video_id'], 'abcdefghijk')
        self.assertNotIn('video_id', q['content'])
        self.assertEqual(validation.validate_answers(normalized, {}), {})
        self.assertIn('_form', validation.validate_answers(normalized, {'notice': '偽造答案'}))
        for patch in ({'required': True}, {'validation': {'enabled': True}}, {'page_break': True}):
            invalid = copy.deepcopy(q);invalid.update(patch)
            with self.assertRaises(validation.DefinitionError): validation.validate_questions([invalid])
        q.update(title='', description='');q['content']={'kind': 'text'}
        with self.assertRaises(validation.DefinitionError):validation.validate_questions([q])

    def test_image_scope_readonly_upload_and_public_reference(self):
        self.prepare();row = self.create(template='')
        output=io.BytesIO();Image.new('RGB',(10,10),'green').save(output,'PNG')
        payload={'form_id':row['form_id'],'name':'說明.PNG','data':base64.b64encode(output.getvalue()).decode()}
        with channels.use('primary'):
            with self.assertRaises(PermissionError):form_content.upload(reports.account(COLLABORATOR),payload)
            asset=form_content.upload(self.user,payload)
            q=forms.question('picture','','content');q['content']={'kind':'image','image_id':asset['asset_id']}
            row=forms.save_design(self.user,{'form_id':row['form_id'],'questions':[q,forms.question('name','姓名')],'expected_updated_at':row['updated_at']})['form']
            self.assertTrue(form_content.admin_read(reports.account(COLLABORATOR),row['form_id'],asset['asset_id']).startswith(b'\x89PNG'))
            with app.database_connection() as conn:
                scoped=forms._find(conn,self.user,row['form_id'])
                self.assertTrue(form_content.public_read(conn,scoped,asset['asset_id']).startswith(b'\x89PNG'))
                with self.assertRaises(ValueError):form_content.public_read(conn,scoped,'0'*32)
                wrong=dict(scoped);wrong['channel_id']='different-oa'
                with self.assertRaises(ValueError):form_content.image(conn,wrong,asset['asset_id'])
            with self.assertRaises(PermissionError):form_content.upload(self.user,payload,preview=True)

    def test_content_only_cannot_publish(self):
        self.prepare();row=self.create(template='')
        q=forms.question('intro','只有說明','content');q['content']={'kind':'text'}
        with channels.use('primary'):
            forms.save_design(self.user,{'form_id':row['form_id'],'questions':[q],'expected_updated_at':row['updated_at']})
            with self.assertRaises(ValueError):forms.transition(self.user,{'form_id':row['form_id'],'status':'collecting'})
