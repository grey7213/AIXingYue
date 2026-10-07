"""Portable backup recovery, isolation and atomic failure tests, using real Store."""
import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

import ai_fengyue_local_server as server
import homer_user_backup as backup


class UserBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = server.Store(Path(self.temp.name)/'state.sqlite3')
        self.addCleanup(self.store.conn.close)
        c = self.store.conn
        for uid in ('alice', 'bob'):
            c.execute('insert into users(id,email,name,password_hash,points,free_points,paid_points,reward_points,is_admin,created_at,updated_at,persona_name,persona_desc) values(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                      (uid,uid+'@example.test',uid,'fixture-secret',100,20,70,10,0,1,1,uid,'persona-'+uid))
        c.commit()
        self.role=self.store.create_user_app('alice', {'name':'故事角色','pre_prompt':'owned prompt','opening_statement':'你好','is_public':False})
        self.other=self.store.create_user_app('bob', {'name':'秘密角色','pre_prompt':'bob private prompt','is_public':False})
        self.store.upsert_conversation('conversation-a','alice',self.role['id'],app_name='故事角色',title='存档')
        self.store.sync_sillytavern_chat('conversation-a','alice',self.role['id'],[
            {'role':'user','content':'问题','created_at':123},
            {'role':'assistant','content':'回复二','swipes':['回复一','回复二'],'swipe_index':1,'created_at':124},
        ])
        c.execute('update conversations set version_id=? where id=?',(self.role['current_version_id'],'conversation-a'))
        c.execute('insert into chat_memories(id,user_id,app_id,conversation_id,title,content,created_at,updated_at) values(?,?,?,?,?,?,?,?)',
                  ('memory-a','alice',self.role['id'],'conversation-a','记忆','完整记忆',1,2))
        c.commit()
        self.doc=backup.export_data(self.store,'alice')

    def restore(self,doc=None,user='alice',persona=False):
        return backup.restore(self.store,user,doc or self.doc,restore_persona=persona,
                              can_play=server.user_can_play_app,normalize_model=server.normalize_user_selected_llm_model,check_role=lambda r:None)

    def test_export_scope_and_no_account_credentials(self):
        raw=backup.encoded(self.doc)
        self.assertNotIn(b'fixture-secret',raw)
        self.assertNotIn(b'bob private prompt',raw)
        self.assertNotIn(b'paid_points',raw)
        self.assertEqual(len(self.doc['payload']['roles']),1)
        self.assertEqual(backup.unpack(backup.pack(self.doc)),self.doc)

    def test_roundtrip_versions_swipes_persona_and_no_overwrite(self):
        c=self.store.conn
        old=dict(c.execute('select * from users where id="alice"').fetchone())
        self.doc['payload']['persona']['name']='恢复的人设'
        result=self.restore(persona=True)
        restored=c.execute('select * from local_apps where id=?',(result['first_role_id'],)).fetchone()
        self.assertEqual(restored['is_public'],0)
        self.assertNotEqual(restored['id'],self.role['id'])
        messages=self.store.list_messages(result['first_conversation_id'],'alice',limit=1000)
        self.assertEqual([m['content'] for m in messages],['问题','回复二'])
        self.assertEqual(messages[-1]['swipe_index'],1)
        self.assertEqual(messages[-1]['swipes'],['回复一','回复二'])
        versions=c.execute('select version_no,snapshot_json from content_versions where entity_id=?',(restored['id'],)).fetchall()
        self.assertEqual(len(versions),1)
        self.assertEqual(json.loads(versions[0]['snapshot_json'])['pre_prompt'],'owned prompt')
        self.assertEqual(self.store.get_persona('alice')['name'],'恢复的人设')
        now=dict(c.execute('select * from users where id="alice"').fetchone())
        for field in ('points','free_points','paid_points','reward_points','password_hash','is_admin'):
            self.assertEqual(old[field],now[field])
        self.assertEqual(self.store.get_local_app(self.role['id'])['pre_prompt'],'owned prompt')

    def test_idempotency_and_account_scoping(self):
        a=self.restore()
        again=self.restore()
        self.assertTrue(again['already_imported'])
        self.assertEqual(a['first_conversation_id'],again['first_conversation_id'])
        b=self.restore(user='bob')
        self.assertNotEqual(a['first_role_id'],b['first_role_id'])
        self.assertIsNone(self.store.get_conversation(a['first_conversation_id'],'bob'))

    def test_private_external_role_is_not_exposed(self):
        doc=copy.deepcopy(self.doc)
        doc['payload']['roles']=[]
        doc['payload']['tables']['conversations'][0]['app_id']=self.other['id']
        doc['payload']['tables']['conversations'][0]['version_id']=self.other['current_version_id']
        result=self.restore(doc)
        self.assertEqual(result['unavailable_roles'],1)
        row=self.store.get_local_app(result['first_role_id'])
        self.assertEqual(row['is_public'],0)
        self.assertNotIn('bob private prompt',str(dict(row)))

    def test_failure_rolls_back_every_content_row(self):
        doc=copy.deepcopy(self.doc)
        # Passes initial shape checks but violates NOT NULL during the last insert.
        doc['payload']['tables']['messages'][-1]['content']=None
        before=self.store.conn.execute('select count(*) from local_apps').fetchone()[0]
        with self.assertRaises(sqlite3.IntegrityError): self.restore(doc)
        self.assertEqual(before,self.store.conn.execute('select count(*) from local_apps').fetchone()[0])
        self.assertEqual(self.store.conn.execute('select count(*) from user_backup_imports').fetchone()[0],0)

    def test_archive_paths_duplicates_corruption_and_size(self):
        for names in (['../backup.json'],['backup.json','backup.json'],['backup.json','secret.txt']):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w') as z:
                for n in names:z.writestr(n,backup.encoded(self.doc))
            with self.assertRaises(backup.BackupError):backup.unpack(out.getvalue())
        with self.assertRaises(backup.BackupError):backup.unpack(b'not a zip')
        with self.assertRaises(backup.BackupError):backup.unpack(b'x'*(backup.MAX_UPLOAD+1))
        with self.assertRaises(backup.BackupError):backup.unpack(b'{"format":"a","format":"b"}')

    def test_invalid_version_and_dangling_message_rejected(self):
        doc=copy.deepcopy(self.doc)
        doc['payload']['roles'][0]['current_version_id']='missing'
        with self.assertRaises(backup.BackupError):self.restore(doc)
        doc=copy.deepcopy(self.doc)
        doc['payload']['tables']['messages'][0]['conversation_id']='bob-conversation'
        with self.assertRaises(backup.BackupError):self.restore(doc)

    def test_secret_fields_are_scrubbed_inside_json(self):
        row=backup.clean_row({'extra_settings':json.dumps({'api_key':'no','nested':{'password':'no','value':'yes'}})},backup.ROLE_FIELDS)
        self.assertEqual(json.loads(row['extra_settings']),{'nested':{'value':'yes'}})

    def test_deleted_roles_are_not_exported_as_live_creations(self):
        self.store.conn.execute("update local_apps set status='deleted' where id=?",(self.role['id'],))
        self.store.conn.commit()
        doc=backup.export_data(self.store,'alice')
        self.assertEqual(doc['payload']['roles'],[])
        self.assertEqual(len(doc['payload']['tables']['conversations']),1)

    def test_export_does_not_truncate_long_chats(self):
        c=self.store.conn
        c.executemany('insert into messages(id,conversation_id,user_id,role,content,created_at) values(?,?,?,?,?,?)',
            [(f'long-{i}','conversation-a','alice','user',f'正文{i}',1000+i) for i in range(1100)])
        c.commit()
        doc=backup.export_data(self.store,'alice')
        self.assertEqual(len(doc['payload']['tables']['messages']),1102)
        result=self.restore(doc)
        self.assertEqual(c.execute('select count(*) from messages where conversation_id=?',(result['first_conversation_id'],)).fetchone()[0],1102)

    def test_runtime_json_database_and_multiple_versions_roundtrip(self):
        c=self.store.conn
        snapshot=dict(self.role); snapshot['pre_prompt']='second version'
        v=server.ContentVersionStore(c,self.store.lock).create_version('character',self.role['id'],server.character_snapshot(snapshot),version_name='v2',created_by='alice')
        c.execute('update local_apps set current_version_id=? where id=?',(v['id'],self.role['id']))
        c.execute('insert into sillytavern_runtime_states(user_id,app_id,conversation_id,variables_json,updated_at) values(?,?,?,?,?)',
                  ('alice',self.role['id'],'conversation-a','{"score":12}',1))
        c.execute('insert into conversation_database_tables(id,conversation_id,user_id,table_key,name,columns_json,created_at,updated_at) values(?,?,?,?,?,?,?,?)',
                  ('table-a','conversation-a','alice','inventory','物品','[]',1,1))
        c.execute('insert into conversation_database_rows(id,table_id,conversation_id,user_id,row_key,data_json,created_at,updated_at) values(?,?,?,?,?,?,?,?)',
                  ('row-a','table-a','conversation-a','alice','key','{"item":"剑"}',1,1))
        c.commit()
        doc=backup.unpack(backup.pack(backup.export_data(self.store,'alice')))
        result=self.restore(doc)
        self.assertEqual(result['versions'],2)
        self.assertEqual(c.execute('select variables_json from sillytavern_runtime_states where conversation_id=?',(result['first_conversation_id'],)).fetchone()[0],'{"score":12}')
        row=c.execute('select * from conversation_database_rows where conversation_id=?',(result['first_conversation_id'],)).fetchone()
        self.assertNotEqual(row['table_id'],'table-a')
        self.assertIsNotNone(c.execute('select id from conversation_database_tables where id=?',(row['table_id'],)).fetchone())

    def test_http_auth_method_origin_and_download_headers(self):
        class Fake:
            command='GET'
            headers={}
            wfile=io.BytesIO()
            def __init__(self,store,user):self.store,self.user,self.sent=store,user,{}
            def authenticated_user(self):return self.user
            def send_response(self,status):self.status=status
            def send_header(self,key,value):self.sent[key]=value
            def end_headers(self):pass
            def send_json(self,status,data):self.status,self.data=status,data
        def go(h,action):backup.handle(h,'/console/api/web/user-backup/'+action,'',can_play=server.user_can_play_app,normalize_model=lambda v:'',check_role=lambda *a:None,public_origin='https://patcher.villainy.top')
        h=Fake(self.store,None);go(h,'download');self.assertEqual(h.status,401)
        h=Fake(self.store,{'id':'alice'});go(h,'download');self.assertEqual(h.status,200)
        self.assertIn('attachment',h.sent['Content-Disposition']);self.assertEqual(h.sent['Cache-Control'],'private, no-store')
        h.command='POST';h.headers={'Origin':'https://evil.invalid','X-Homer-Backup':'1'};go(h,'restore');self.assertEqual(h.status,403)
        h.headers={};go(h,'restore');self.assertEqual(h.status,403)


import sqlite3
if __name__=='__main__':unittest.main()
