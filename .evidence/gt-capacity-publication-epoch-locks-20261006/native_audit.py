"""Read only the retained isolated fixture; never print connection secrets."""
import json,tempfile
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from aos_api.aip_provider_capacity_publication_lock_boundary import require_publication_lock_boundary
from aos_api.aip_provider_capacity_evidence_fence import _require_boundary
from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
password=(Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass').read_text().strip().split(':')[-1]
kwargs=dict(host='127.0.0.1',port=5434,user='aos_app',password=password,row_factory=dict_row)
with psycopg.connect(dbname='aos_meta',**kwargs) as c:
 c.read_only=True
 database=c.execute("SELECT datname FROM pg_database WHERE datname LIKE 'aos_test_%_ti4_test' ORDER BY oid DESC LIMIT 1").fetchone()['datname']
assert database.startswith('aos_test_') and database.endswith('_ti4_test')
with psycopg.connect(dbname=database,**kwargs) as c:
 c.read_only=True
 require_publication_lock_boundary(c);_require_boundary(c);require_withdrawal_fence(c)
 result={'database':database,'read_only':True,'formal_database_accessed':False,
  'head':c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num'],
  'roles':c.execute("SELECT rolname,rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname IN('aos_capacity_publication_owner','aos_provider_capacity_issuer','aos_provider_capacity_policy_publisher') ORDER BY rolname").fetchall(),
  'original_three_catalog_boundaries':'PASS',
  'entrypoints':c.execute("SELECT to_regprocedure('public.prepare_capacity_source(bytea,text,text,jsonb)') IS NOT NULL AS prepare,to_regprocedure('public.commit_capacity_source(text,bytea,bytea)') IS NOT NULL AS commit").fetchone(),
  'epoch_access':c.execute("SELECT has_function_privilege('aos_capacity_publication_owner','public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)','EXECUTE') AS evidence_lock,has_function_privilege('aos_capacity_publication_owner','public.aos_capacity_withdrawal_epoch_lock(text,text,text)','EXECUTE') AS withdrawal_lock,has_table_privilege('aos_capacity_publication_owner','public.aip_capacity_withdrawal_epoch','SELECT') AS withdrawal_table,has_table_privilege('aos_capacity_publication_owner','public.aip_capacity_evidence_epoch','SELECT') AS evidence_table").fetchone(),
  'temporary_harness_count':c.execute("SELECT count(*) AS n FROM pg_proc WHERE pronamespace='public'::regnamespace AND proname LIKE 'publication_epoch_harness_%'").fetchone()['n'],
  'source_published':False,'full_source_acceptance':'INCOMPLETE'}
assert result['head']=='a0v_156' and not any(result['entrypoints'].values())
assert result['temporary_harness_count']==0 and all(not v for r in result['roles'] for k,v in r.items() if k!='rolname')
assert result['epoch_access']==dict(evidence_lock=True,withdrawal_lock=True,withdrawal_table=False,evidence_table=False)
Path(__file__).with_name('native-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print('Isolated native catalogue readback PASS',database)
