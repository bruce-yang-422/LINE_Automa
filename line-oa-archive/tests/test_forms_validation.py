"""Phase two A9/A10/A11/A12, shared vectors and authorized HTTP designer/preview."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app
import channels
import forms
import forms_validation as validation
import limits
import reports
import test_forms_permissions as permissions
from test_roles_and_permissions import ADMIN, ORG_ADMIN, SENDER, COLLABORATOR, ORG_A

VECTORS = json.loads(Path(__file__).with_name('form_validation_vectors.json').read_text(encoding='utf-8'))


class FormValidationTests(unittest.TestCase):
    def test_page_break_is_section_only_and_boolean(self):
        section = forms.question('section', '第二頁', 'section')
        section['page_break'] = True
        self.assertEqual(validation.validate_questions([section])[0]['page_break'], True)
        for value in ('true', 1, None):
            section['page_break'] = value
            with self.assertRaises(ValueError):
                validation.validate_questions([section])
        question = forms.question('text', '姓名')
        question['page_break'] = False
        with self.assertRaises(ValueError):
            validation.validate_questions([question])

    def test_shared_python_vectors_and_no_answer_coercion(self):
        for vector in VECTORS:
            with self.subTest(vector=vector['name']):
                validation.validate_questions(vector['questions'])
                original = copy.deepcopy(vector['answers'])
                expected = {key: next(q for q in vector['questions'] if q['id']==key)['validation']['message'] if code=='custom' else validation.RULES['messages'][code] for key,code in vector['expected'].items()}
                self.assertEqual(validation.validate_answers(vector['questions'], vector['answers']), expected)
                self.assertEqual(vector['answers'], original)

    def test_shared_javascript_vectors(self):
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp)/'config.json'
            config.write_text(json.dumps(validation.configuration()), encoding='utf-8')
            result = subprocess.run(['node','tests/forms_validation_checks.cjs',str(config)], cwd=root, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_definition_contradictions_and_unsupported_rules(self):
        q = forms.question('q', '題目')
        cases = [('short_text', {'enabled':True,'min_length':3,'max_length':2}),
                 ('short_text', {'enabled':False,'min_length':3,'max_length':2}),
                 ('short_text', {'enabled':True,'format':'unknown'}),
                 ('short_text', {'enabled':True,'format':[]}),
                 ('short_text', {'enabled':True,'max_length':limits.FORM_TEXT_MAX+1}),
                 ('paragraph', {'enabled':True,'format':'email'}),
                 ('number', {'enabled':True,'min':5,'max':2}),
                 ('number', {'enabled':True,'integer':True,'min':1.2,'max':1.8}),
                 ('number', {'enabled':True,'integer':1}),
                 ('multiple_choice', {'enabled':True,'count_min':3}),
                 ('multiple_choice', {'enabled':True,'count_min':2,'count_max':1}),
                 ('multiple_choice', {'enabled':True,'count_exact':2,'count_max':1}),
                 ('date', {'enabled':True,'date_min':'2026-02-30'}),
                 ('date', {'enabled':True,'date_min':'2027-01-01','date_max':'2026-01-01'}),
                 ('time', {'enabled':True})]
        for kind, conditions in cases:
            with self.subTest(kind=kind,conditions=conditions):
                value = {**copy.deepcopy(q),'type':kind,'validation':conditions}
                if kind=='multiple_choice':value['options']=[{'id':'a','label':'A'},{'id':'b','label':'B'}]
                with self.assertRaises(validation.DefinitionError):validation.validate_questions([value])

    def test_ids_types_options_and_platform_caps(self):
        q = forms.question('q', '題目')
        invalid = [[q,q], [{**q,'id':'__other__'}], [{**q,'id':'bad/id'}], [{**q,'title':' '}], [{**q,'required':1}], [{**q,'type':'unknown'}], [{**q,'type':'section','required':True}], [{**q,'type':'dropdown','allow_other':True}], [{**q,'type':'single_choice'}]]
        for questions in invalid:
            with self.subTest(questions=questions):
                with self.assertRaises(validation.DefinitionError):validation.validate_questions(questions)
        for identifier in validation.RULES['reserved_ids']:
            with self.subTest(identifier=identifier):
                with self.assertRaises(validation.DefinitionError):validation.validate_questions([{**q,'id':identifier}])
        value = forms.question('q','選項','single_choice',['A','B'])
        value['options'][1]['id']=value['options'][0]['id']
        with self.assertRaises(validation.DefinitionError):validation.validate_questions([value])
        with patch.object(limits,'FORM_QUESTIONS_MAX',0):
            with self.assertRaises(validation.DefinitionError):validation.validate_questions([q])
        with patch.object(limits,'FORM_OPTIONS_MAX',1):
            with self.assertRaises(validation.DefinitionError):validation.validate_questions([forms.question('q','選項','single_choice',['A','B'])])

    def test_rating_and_attachment_structure(self):
        rating = forms.question('q','評分','rating')
        for limits_value in [{'min':5,'max':1},{'min':1.5,'max':5},{'min':True,'max':5}]:
            with self.assertRaises(validation.DefinitionError):validation.validate_questions([{**rating,'rating':limits_value}])
        attachment = copy.deepcopy(next(v['questions'][0] for v in VECTORS if v['name']=='attachment-optional'))
        for ext in ['webp','gif','heic','webm','m4a','exe']:
            value = copy.deepcopy(attachment);value['attachment']['extensions']=[ext]
            with self.assertRaises(validation.DefinitionError):validation.validate_questions([value])
        for key, maximum in [('max_files', limits.FORM_ATTACHMENTS_PER_QUESTION),('max_file_bytes',limits.FORM_ATTACHMENT_MAX_BYTES),('max_total_bytes',limits.FORM_ATTACHMENT_TOTAL_MAX_BYTES)]:
            value=copy.deepcopy(attachment);value['attachment'][key]=maximum+1
            with self.assertRaises(validation.DefinitionError):validation.validate_questions([value])


class FormDesignerApiTests(unittest.TestCase):
    setUp = permissions.FormsPermissionsTests.setUp
    server = permissions.FormsPermissionsTests.server
    request = permissions.FormsPermissionsTests.request
    setup_roles_environment = permissions.FormsPermissionsTests.setup_roles_environment
    prepare = permissions.FormsPermissionsTests.prepare
    call = permissions.FormsPermissionsTests.call
    create = permissions.FormsPermissionsTests.create

    def test_fixed_ids_survive_rename_order_and_invalid_update_is_atomic(self):
        self.prepare();row=self.create();server=self.server()
        questions=copy.deepcopy(row['questions']);questions.reverse();questions[0]['title']='新名稱'
        questions[-2]['options'].reverse()
        payload={'form_id':row['form_id'],'questions':questions,'expected_updated_at':row['updated_at']}
        status,data=self.call(server,'/api/forms/design',SENDER,payload)
        self.assertEqual(status,200)
        self.assertEqual(data['form']['questions'],questions)
        self.assertEqual({q['id'] for q in data['form']['questions']},{q['id'] for q in row['questions']})
        self.assertEqual({o['id'] for q in data['form']['questions'] for o in q['options']},{o['id'] for q in row['questions'] for o in q['options']})
        payload['expected_updated_at']=data['form']['updated_at'];payload['questions'][0]['title']=' '
        status,error=self.call(server,'/api/forms/design',SENDER,payload)
        self.assertEqual(status,400);self.assertIn(questions[0]['id'],error['errors'])
        self.assertEqual(self.call(server,'/api/forms/detail?form_id='+row['form_id'])[1]['form']['questions'],data['form']['questions'])
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action='forms.design'").fetchone()[0],1)

    def test_stale_design_is_rejected_without_losing_saved_questions(self):
        self.prepare();row=self.create();server=self.server()
        payload={'form_id':row['form_id'],'questions':row['questions'],'expected_updated_at':row['updated_at']}
        self.assertEqual(self.call(server,'/api/forms/design',payload=payload)[0],200)
        payload['questions']=[]
        status,data=self.call(server,'/api/forms/design',payload=payload)
        self.assertEqual(status,400);self.assertIn('其他人更新',data['error'])
        self.assertEqual(len(self.call(server,'/api/forms/detail?form_id='+row['form_id'])[1]['form']['questions']),4)

    def test_preview_uses_server_validation_preserves_phone_and_never_saves(self):
        self.prepare();row=self.create();server=self.server()
        for vector in VECTORS:
            with self.subTest(vector=vector['name']):
                status,data=self.call(server,'/api/forms/preview',payload={'form_id':row['form_id'],'questions':vector['questions'],'answers':vector['answers']})
                attachment_input=any(q['type']=='attachment' and vector['answers'].get(q['id']) for q in vector['questions']) if isinstance(vector['answers'],dict) else False
                self.assertEqual(status,200);self.assertEqual(data['valid'],not vector['expected'] and not attachment_input)
                if data['valid']:self.assertEqual(data['answers'],vector['answers'])
        with app.database_connection() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM forms').fetchone()[0],1)
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action='forms.design'").fetchone()[0],0)
            self.assertEqual(conn.execute("SELECT count(*) FROM form_submissions").fetchone()[0],0)

    def test_readonly_preview_allowed_design_and_cross_oa_rejected(self):
        self.prepare();row=self.create();server=self.server()
        payload={'form_id':row['form_id'],'questions':row['questions'],'answers':{},'expected_updated_at':row['updated_at']}
        self.assertEqual(self.call(server,'/api/forms/preview',COLLABORATOR,payload)[0],200)
        self.assertEqual(self.call(server,'/api/forms/design',COLLABORATOR,payload)[0],403)
        self.assertEqual(self.call(server,'/api/forms/preview',ADMIN,payload,view_as=ORG_ADMIN,preview_org=ORG_A)[0],200)
        self.assertEqual(self.call(server,'/api/forms/design',ADMIN,payload,view_as=ORG_ADMIN,preview_org=ORG_A)[0],403)
        payload['form_id']='unavailable'
        self.assertEqual(self.call(server,'/api/forms/preview',payload=payload)[0],403)

    def test_existing_response_changes_require_explicit_confirmation(self):
        self.prepare();row=self.create()
        payload={'form_id':row['form_id'],'questions':row['questions'][1:],'expected_updated_at':row['updated_at']}
        with channels.use('primary'),patch.object(forms,'_counts',return_value={'notifications':1,'responses':1}):
            with self.assertRaises(ValueError):forms.save_design(self.user,payload)
            payload['confirm_response_impact']=True
            self.assertEqual(len(forms.save_design(self.user,payload)['form']['questions']),3)

    def test_section_only_form_cannot_publish(self):
        self.prepare();row=self.create()
        with channels.use('primary'):
            forms.save_design(self.user,{'form_id':row['form_id'],'questions':[forms.question('section','分區','section')],'expected_updated_at':row['updated_at']})
            with self.assertRaises(ValueError):forms.transition(self.user,{'form_id':row['form_id'],'status':'collecting'})


if __name__=='__main__':unittest.main()
