"""Independent readback of retained consumer cases and unchanged old contracts."""
import ast,hashlib,json,os,re,subprocess,sys,tempfile,types
from pathlib import Path
os.environ['AOS_DOTENV_DISABLED']='1'
sys.path.insert(0,str(Path.cwd()/'services/aos-api'))
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_provider_capacity_publication_transaction as current
old=types.ModuleType('previous_compiler')
exec(compile(subprocess.check_output(['git','show','HEAD:services/aos-api/aos_api/aip_provider_capacity_publication_transaction.py'],text=True),'previous','exec'),old.__dict__)
assert old.source_public_entry_statements()==current.source_public_entry_statements()
assert old.source_transaction_function_manifest()==current.source_transaction_function_manifest()
assert old.original_registry_function_manifest()==current.original_registry_function_manifest()
assert len(current.source_public_entry_manifest(include_consumer=True))==3
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
logs={};databases=set()
names=('current-source-consumer-red-r1.log','current-source-consumer-green-r1.log',
       'current-source-consumer-green-r2.log','current-source-consumer-green-r3.log',
       'current-source-consumer-expired-auth-r1.log','current-source-consumer-expired-auth-r2.log',
       'current-source-consumer-adjacent-r1.log')
for name in names:
    p=Path('.evidence/gt-capacity-source-publication-20261006')/name
    raw=p.read_text();assert password not in raw
    assert not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',raw)
    summary=re.findall(r'^.*(?:passed|failed),.* in .*s(?: \(.*\))?$',raw,re.M)[-1]
    logs[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'summary':summary}
    databases.update(re.findall(r'Retained isolated test database: (aos_test_\w+_ti4_test)',raw))
assert logs[names[-1]]['summary'].startswith('7 passed,')
outputs=[];sources=0;withdrawn=0
for database in sorted(databases):
    with psycopg.connect(host='127.0.0.1',port=5434,dbname=database,user='aos_app',password=password,row_factory=dict_row) as conn:
        conn.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
        conn.execute('SET LOCAL ROLE aos_capacity_publication_owner')
        rows=conn.execute("""SELECT p.asset_id,p.content_hash,
          p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
          aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
          s.finalized,(v.native_xid=s.native_xid AND v.native_pid=s.native_pid AND v.native_session=s.native_session) AS provenance_ok
          FROM aos_capacity_publication_private.source_publication p
          JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
          JOIN aos_capacity_publication_private.source_provenance v ON v.asset_id=p.asset_id AND v.org_id=p.org_id AND v.project_id=p.project_id
          WHERE p.asset_id LIKE 'consumed-source-%'""").fetchall()
        for row in rows:assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok'))
        clean=conn.execute("""SELECT to_regprocedure('public.prepare_capacity_source(bytea,text,text,jsonb)') IS NULL
          AND to_regprocedure('public.commit_capacity_source(text,bytea,bytea)') IS NULL
          AND to_regprocedure('public.read_current_capacity_source(bytea,jsonb)') IS NULL
          AND to_regprocedure('aos_capacity_publication_private.require_current_source_installation()') IS NULL AS clean""").fetchone()['clean']
        assert clean
        count=conn.execute('SELECT count(*) AS n FROM aos_capacity_publication_private.origin_withdrawal').fetchone()['n']
        if count:
            epoch=conn.execute('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch').fetchone()
            assert epoch=={'epoch':2,'head_origin_hash':None}
            withdrawn+=len(rows)
        outputs.append({'database':database,'sources':rows,'temporary_functions_absent':clean,'actual_origin_withdrawals':count})
        sources+=len(rows);conn.rollback()
assert sources>=10 and withdrawn>=4
def functions(text):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
test='services/aos-api/tests/aip/test_capacity_source_publication_transaction_pg.py'
previous=functions(subprocess.check_output(['git','show','HEAD:'+test],text=True));now=functions(Path(test).read_text())
assert {n for n in previous if previous[n]!=now[n]}=={'registered_database_isolation','exact_public_source_caller'}
result={'schema':'aos-current-source-consumer-verification/v1','head':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
    'logs':logs,'databases':outputs,'durable_sources_verified':sources,'withdrawn_sources_still_signed':withdrawn,
    'default9_statements_unchanged':True,'private41_and_original17_manifests_unchanged':True,
    'old_test_changes':['registered_database_isolation','exact_public_source_caller'],
    'consumer_service_gate_verified':True,'formal_installation':False,'business_runtime_integration':False,
    'final_caller_commit_wallclock_gate':False,'full_source_delivery':False}
serialized=json.dumps(result,ensure_ascii=False,indent=2)+'\n';assert password not in serialized
Path('.evidence/gt-capacity-source-entry-20261007/full157-current-source-consumer-verification.json').write_text(serialized)
print(json.dumps({k:result[k] for k in ['durable_sources_verified','withdrawn_sources_still_signed','default9_statements_unchanged','full_source_delivery']}))
