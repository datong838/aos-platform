"""Current restored content owner distinction, strictly scoped read-only."""
import sys,json,hashlib
from pathlib import Path
import psycopg
sys.path[:0]=['services/aos-api','.evidence/qyh-source-boundary-rehearsal-20261011','.evidence/qyh-full-system-restoration-20261011']
import real_contract as C
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
root=Path('.evidence/qyh-content-queue-unknown-isolation-20261012')
out=root/'current-queue-readback.json';assert not out.exists()
before=C.S.P.M.fingerprint('qyh-restored-pg-20261011');metadata=C.S.D.metadata('qyh-restored-pg-20261011')
reads=[]
for scope in [('org-org','dev-project'),('dev-org','dev-project')]:
 with T.factory() as conn:
  conn.read_only=True;conn.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
  apply_asset_transaction_scope(conn,org_id=scope[0],project_id=scope[1])
  identity=conn.execute("SELECT current_user AS role,current_database() AS db,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation FROM pg_control_system()").fetchone()
  assert identity==dict(role='aos_runtime',db='aos_meta_head',cluster='7695302940039200809',readonly='on',isolation='repeatable read')
  assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
  artifacts=conn.execute("SELECT artifact_type,count(*) AS count FROM public.aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_type IN ('content_draft','ecommerce_content') GROUP BY artifact_type ORDER BY artifact_type",scope).fetchall()
  command=conn.execute('SELECT count(*) AS count FROM public.ecommerce_content_execution_command WHERE org_id=%s AND project_id=%s',scope).fetchone()
  result=conn.execute('SELECT count(*) AS count FROM public.ecommerce_content_execution_result WHERE org_id=%s AND project_id=%s',scope).fetchone()
  runtime=conn.execute("SELECT response->>'state' AS state,count(*) AS count FROM public.ecommerce_growth_runtime_command_receipt WHERE org_id=%s AND project_id=%s AND operation_id='ecommerce_growth_content_generate' GROUP BY response->>'state' ORDER BY state",scope).fetchall()
  reads.append(dict(scope=scope,identity=identity,artifacts=artifacts,commands=command,results=result,runtimeCommandStates=runtime))
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011')==before
assert C.S.D.metadata('qyh-restored-pg-20261011')==metadata
body=dict(authority='AOS-001902',reads=reads,databaseWrites=0,current647DataAndMetadataUnchanged=True,formalRestorationAccepted=False,workerStarted=False,providerInvocations=0,scriptHash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with out.open('x') as f:json.dump(body,f,indent=2);f.write('\n')
print(json.dumps(body))
