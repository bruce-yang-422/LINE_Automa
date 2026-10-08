"""Folder persistence, safe deletion and real HTTP scope checks."""
import test_forms_permissions as permissions
import unittest
import app
import channels
import forms
from test_roles_and_permissions import COLLABORATOR, ADMIN, ORG_ADMIN, ORG_A

class FormFolderTests(unittest.TestCase):
    setUp = permissions.FormsPermissionsTests.setUp
    server = permissions.FormsPermissionsTests.server
    request = permissions.FormsPermissionsTests.request
    setup_roles_environment = permissions.FormsPermissionsTests.setup_roles_environment
    prepare = permissions.FormsPermissionsTests.prepare
    call = permissions.FormsPermissionsTests.call
    create = permissions.FormsPermissionsTests.create

    def test_move_rename_delete_preserves_form_and_answers(self):
        self.prepare();row=self.create();server=self.server()
        def act(**payload):
            status,data=self.call(server,'/api/forms/folder',payload=payload)
            self.assertEqual(status,200,data);return data
        folder=act(action='create',name='家長')['folder_id']
        act(action='move',form_id=row['form_id'],folder_id=folder)
        act(action='rename',folder_id=folder,name='家長回饋')
        data=self.call(server,'/api/forms')[1]
        self.assertEqual(data['folders'],[{'folder_id':folder,'name':'家長回饋'}])
        self.assertEqual(data['forms'][0]['folder_id'],folder)
        act(action='delete',folder_id=folder)
        data=self.call(server,'/api/forms')[1]
        self.assertEqual(data['folders'],[])
        self.assertEqual(data['forms'][0]['folder_id'],'')
        self.assertEqual(data['forms'][0]['questions'],row['questions'])
        with app.database_connection() as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_events WHERE action LIKE 'forms.folder.%'").fetchone()[0],4)

    def test_invalid_destination_is_atomic_and_names_unique(self):
        self.prepare();row=self.create();server=self.server()
        status,data=self.call(server,'/api/forms/folder',payload={'action':'create','name':'測試'})
        self.assertEqual(status,200);folder=data['folder_id']
        self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':'create','name':'測試'})[0],400)
        self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':'create','name':' '})[0],400)
        self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':'move','form_id':row['form_id'],'folder_id':folder})[0],200)
        self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':'move','form_id':row['form_id'],'folder_id':'missing'})[0],403)
        self.assertEqual(self.call(server,'/api/forms/detail?form_id='+row['form_id'])[1]['form']['folder_id'],folder)
        self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':'move','form_id':row['form_id'],'folder_id':''})[0],200)

    def test_readonly_preview_and_cross_scope_cannot_write(self):
        self.prepare();server=self.server()
        for email in (COLLABORATOR,ADMIN):
            self.assertEqual(self.call(server,'/api/forms/folder',email,{'action':'create','name':'拒絕'})[0],403)
        self.assertEqual(self.call(server,'/api/forms/folder',ADMIN,{'action':'create','name':'拒絕'},view_as=ORG_ADMIN,preview_org=ORG_A)[0],403)
        with app.database_connection() as conn:
            conn.execute("INSERT INTO form_folders VALUES ('foreign',?, 'other', '其他 OA', 'now')",(ORG_A,))
        for action in ('rename','delete','move'):
            self.assertEqual(self.call(server,'/api/forms/folder',payload={'action':action,'folder_id':'foreign','name':'越權','form_id':'missing'})[0],403)
        self.assertEqual(self.call(server,'/api/forms')[1]['folders'],[])

    def test_new_copy_and_restart_keep_folder_and_invalid_create_rolls_back(self):
        self.prepare()
        with channels.use('primary'):
            folder=forms.folder_action(self.user,{'action':'create','name':'活動'})['folder_id']
            row=forms.save(self.user,{'name':'新問卷','folder_id':folder})['form']
            copied=forms.duplicate(self.user,{'form_id':row['form_id']})['form']
            self.assertEqual(copied['folder_id'],folder)
            with self.assertRaises(PermissionError):forms.save(self.user,{'name':'不應建立','folder_id':'missing'})
            app.initialize_database()
            data=forms.listing(self.user)
            self.assertEqual(len(data['forms']),2)
            self.assertTrue(all(r['folder_id']==folder for r in data['forms']))

if __name__=='__main__':unittest.main()
