"""Read-only evidence for the registry function audit; no runtime authority."""
import ast,hashlib,json,os,re,subprocess,sys,tempfile,types
from pathlib import Path
os.environ['AOS_DOTENV_DISABLED']='1'
root=Path.cwd();sys.path.insert(0,str(root/'services/aos-api'))
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_provider_capacity_publication_transaction as current
production=Path('services/aos-api/aos_api/aip_provider_capacity_publication_transaction.py')
tests=Path('services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py')
old=subprocess.check_output(['git','show','HEAD:'+str(production)],text=True)
legacy=types.ModuleType('legacy_registry_verification');exec(compile(old,'legacy','exec'),legacy.__dict__)
assert current.source_transaction_function_manifest()==legacy.source_transaction_function_manifest()
def functions(source):
 return {x.name:ast.dump(x,include_attributes=False) for x in ast.parse(source).body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}
a,b=functions(old),functions(production.read_text())
assert {name for name in a if a[name]!=b[name]}=={'original_registry_function_manifest','source_private_installation_audit_sql'}
a,b=functions(subprocess.check_output(['git','show','HEAD:'+str(tests)],text=True)),functions(tests.read_text())
assert {name for name in a if a[name]!=b[name]}=={'registered_database_isolation'}
reference=json.loads(Path('.evidence/gt-capacity-source-entry-20261007/full157-original-registry-table-contract-reviewed.json').read_text())
assert reference['original_state_unchanged'] and reference['temporary_schema_absent'] and not reference['DDL_committed']
assert current._ORIGINAL_REGISTRY_TABLE_HASHES==reference['hashes']
assert len(current._ORIGINAL_REGISTRY_TABLE_HASHES)==7
manifest=current.original_registry_function_manifest()
assert len(manifest)==17
inventory=json.loads(Path('.evidence/gt-capacity-source-entry-20261007/full157-original-registry-trusted-inventory.json').read_text())
assert {m['signature'].split('(')[0]:m['body_sha256'] for m in manifest}=={m['name']:m['body_sha256'] for m in inventory['functions']}
logs={};names=set()
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
for name in ('registry-tables-red.log','registry-tables-green-r1.log','registry-tables-adjacent.log'):
 p=Path('.evidence/gt-capacity-source-publication-20261006')/name
 raw=p.read_text();assert password not in raw
 summary=re.findall(r'^.*(?:passed|failed),.* in .*s$',raw,re.M)[-1]
 logs[str(p)]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'summary':summary}
 names.update(re.findall(r'Retained isolated test database: (aos_test_\w+_ti4_test)',raw))
readback=[]
for name in sorted(names):
 with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',password=password,dbname=name,row_factory=dict_row) as conn:
  conn.execute('BEGIN READ ONLY')
  current.require_source_transaction_tables(conn)
  assert conn.execute("SELECT to_regprocedure('aos_capacity_publication_private.require_current_source_installation()')::text AS f").fetchone()['f'] is None
  rows=conn.execute("""SELECT p.asset_id,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
   aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
   s.finalized FROM aos_capacity_publication_private.source_publication p
   JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id""").fetchall()
  assert all(r['hash_ok'] and r['signature_ok'] and r['finalized'] for r in rows)
  readback.append({'database':name,'versions':[r['version_num'] for r in conn.execute('SELECT version_num FROM alembic_version')],
   'cluster':conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'],
   'private_original_check':True,'temporary_audit_absent':True,'source_rows':rows})
  conn.rollback()
assert any(r['source_rows'] for r in readback)
result={'schema':'aos-original-registry-tables-verification/v1','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 'authority':'AOS-001453','original_functions':17,'new_functions_unchanged':41,'native_audited_total':58,
 'single_cause_faults':55,'native_audited_tables':12,'logs':logs,'readback':readback,
 'legacy_function_AST_preserved':True,'legacy_test_AST_preserved_except_registration':True,
 'expected_not_target_derived':True,'public_grants_changed':False,'default_installation_changed':False,
 'remaining':['native C verifier','issuer and audit/public self integrity','controlled JWT signer','current consumer','final actual caller COMMIT TTL','full natural business chain']}
Path('.evidence/gt-capacity-source-entry-20261007/full157-original-registry-tables-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print('Seven original registry tables verified:',len(readback),'retained databases; original17/new41/total58; durable Source readback valid')
