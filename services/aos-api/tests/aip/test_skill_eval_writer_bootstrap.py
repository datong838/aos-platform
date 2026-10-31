import importlib.util
from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from psycopg.rows import dict_row
P=Path(__file__).resolve().parents[2]/'aos_api/aip_skill_eval_writer_bootstrap.py'
s=importlib.util.spec_from_file_location('writer_bootstrap',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Fake:
 def __init__(self):
  self.autocommit=False;self.row_factory=dict_row;self.events=[];self.bad=None
 @contextmanager
 def transaction(self):
  self.events.append('savepoint')
  try:yield
  except Exception:self.events.append('rollback');raise
  else:self.events.append('release')
 def execute(self,sql,args=()):
  text=str(sql);self.events.append(text)
  if 'session_user AS login' in text:r={'role':'aos_app','login':'aos_app','database':'test_db','isolation':'serializable'}
  elif 'pg_control_system' in text:r={'id':'123'}
  elif 'version_num' in text:r={'version_num':'a0v_163'}
  elif 'rolcanlogin' in text:r=dict(oid=12,rolcanlogin=False,rolinherit=False,rolsuper=False,rolbypassrls=False,rolcreaterole=False,rolcreatedb=False,rolreplication=False)
  elif 'AS unsafe' in text:r={'unsafe':False}
  elif 'AS present' in text:r={'present':False}
  elif 'relforcerowsecurity' in text:
   rows=[dict(relname=t,owner='aos_app',relrowsecurity=True,relforcerowsecurity=True) for t in m.READ_TABLES]
   if self.bad=='rls':rows[0]['relforcerowsecurity']=False
   return SimpleNamespace(fetchall=lambda:rows)
  else:r={}
  if self.bad=='cluster' and 'id' in r:r['id']='other'
  if self.bad=='context' and 'login' in r:r['role']='aos_runtime'
  if self.bad=='database' and 'database' in r:r['database']='other'
  if self.bad=='schema' and 'version_num' in r:r['version_num']='a0v_165'
  if self.bad=='role' and 'rolcanlogin' in r:r['rolcanlogin']=True
  if self.bad=='wide' and 'unsafe' in r:r['unsafe']=True
  if self.bad=='existing' and 'present' in r:r['present']=True
  if self.bad=='late' and text.startswith('CREATE POLICY'):raise RuntimeError('late SQL failure')
  return SimpleNamespace(fetchone=lambda:r)
class Tests(unittest.TestCase):
 def call(self,c):return m.install_skill_eval_writer_permissions(c,expected_database='test_db',expected_cluster='123')
 def test_exact_permissions_and_no_commit_or_role_creation(self):
  c=Fake();self.call(c);ddl=[x for x in c.events if x.startswith(('GRANT','CREATE POLICY'))]
  self.assertEqual(sum(x.startswith('GRANT SELECT ') for x in ddl),9)
  self.assertEqual(sum(x.startswith('GRANT INSERT ') for x in ddl),3)
  self.assertEqual(sum(' AS RESTRICTIVE ' in x for x in ddl),9)
  self.assertFalse(any('UPDATE' in x or 'CREATE ROLE' in x for x in ddl))
  self.assertEqual(c.events[-1],'release')
 def test_drift_refuses_before_ddl(self):
  for bad in ('database','cluster','context','schema','role','wide','existing','rls'):
   with self.subTest(bad=bad):
    c=Fake();c.bad=bad
    with self.assertRaises(RuntimeError):self.call(c)
    self.assertNotIn('savepoint',c.events)
 def test_wrong_transaction_and_row_factory_refuse_without_sql(self):
  for field,value in [('autocommit',True),('row_factory',None)]:
   c=Fake();setattr(c,field,value)
   with self.assertRaises(RuntimeError):self.call(c)
   self.assertEqual(c.events,[])
 def test_late_error_exits_rollback_savepoint(self):
  c=Fake();c.bad='late'
  with self.assertRaises(RuntimeError):self.call(c)
  self.assertEqual(c.events[-1],'rollback')
if __name__=='__main__':unittest.main()
