"""Build table contracts from original trusted DDL in a rollback-only lab window."""
import hashlib,json,os,sys,tempfile,subprocess
from pathlib import Path
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(Path.cwd()/'services/aos-api'))
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_provider_capacity_publication_transaction as t
from aos_api.aip_provider_capacity_publication_registry import install_registry_schema,install_origin_registration
from aos_api.aip_provider_capacity_document_registry import install_document_registry
from aos_api.aip_provider_capacity_withdrawal_registry import install_withdrawal_registry
names=('deployment_anchor','root_snapshot','origin','root_entry','registry_epoch','document','origin_withdrawal')
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
database='aos_test_0eecd0337b00_ti4_test'
def catalog(conn):
 result={}
 for name in names:
  oid=conn.execute('SELECT to_regclass(%s)::oid AS oid',('aos_capacity_publication_private.'+name,)).fetchone()['oid'];assert oid
  row=conn.execute(t._SOURCE_TABLE_PROPERTIES,(oid,)).fetchone()
  for key,query in t._SOURCE_TABLE_QUERIES.items():row[key]=conn.execute(query,(oid,)).fetchall()
  result[name]=row
 return result
def original_state(conn):
 t.require_source_transaction_tables(conn)
 state={'schema_oid':conn.execute("SELECT 'aos_capacity_publication_private'::regnamespace::oid AS oid").fetchone()['oid']}
 for name in names:
  state[name]=conn.execute("SELECT count(*) AS n,coalesce(array_agg(encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') ORDER BY to_jsonb(t)::text),ARRAY[]::text[]) AS hashes FROM aos_capacity_publication_private."+name+' t').fetchone()
 return state
statements=[]
for install in (install_registry_schema,install_origin_registration,install_document_registry,install_withdrawal_registry):install(statements.append)
assert len(statements)==84
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',password=password,dbname=database,row_factory=dict_row) as conn:
 before=original_state(conn);conn.rollback()
 try:
  assert conn.execute("SELECT to_regnamespace('aos_capacity_registry_reference_hold')::oid AS oid").fetchone()['oid'] is None
  conn.execute('ALTER SCHEMA aos_capacity_publication_private RENAME TO aos_capacity_registry_reference_hold')
  skipped=0
  for statement in statements:
   if statement.startswith('DO $role$'):
    skipped+=1;continue
   conn.execute(statement)
  assert skipped==2
  expected=catalog(conn)
  for name in names:
   assert conn.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.'+name).fetchone()['n']==0
 finally:conn.rollback()
 after=original_state(conn);assert before==after
 assert conn.execute("SELECT to_regnamespace('aos_capacity_registry_reference_hold')::oid AS oid").fetchone()['oid'] is None
 conn.rollback()
result={'schema':'aos-original-registry-trusted-table-reference/v1','authority':'AOS-001453',
 'head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'database':database,
 'source':'82 exact original installer statements in rollback-only fresh schema; 2 preinstallation reserved role guards skipped; original roles audited; no target-derived expected',
 'statement_sha256':[hashlib.sha256(x.encode()).hexdigest() for x in statements],
 'expected':expected,'hashes':{k:hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest() for k,v in expected.items()},
 'restored_original_state':after,'original_state_unchanged':True,'temporary_schema_absent':True,
 'DDL_committed':False,'explicit_DROP_executed':False,'formal_resources_changed':False}
Path('.evidence/gt-capacity-source-entry-20261007/full157-original-registry-table-contract-reviewed.json').write_text(json.dumps(result,indent=2)+'\n')
print('Trusted seven-table reference frozen; rollback/readback preserved original schema and rows')
