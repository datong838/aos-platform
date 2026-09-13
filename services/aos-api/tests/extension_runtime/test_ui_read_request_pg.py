import importlib.util
from datetime import datetime,timedelta,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import hashlib
import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest
from test_generation_attempts_pg import attempt_case, database, TOKEN, HASH, SCOPE, pytestmark
from aos_api.extension_runtime.generation_attempts import PostgresRuntimeAttemptStore

@pytest.fixture
def queue(attempt_case):
    conn,installation,generation,role,schema=attempt_case
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_031_runtime_ui_read_request.py'
    spec=importlib.util.spec_from_file_location('ui_queue_migration',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.op=SimpleNamespace(execute=lambda q:conn.execute(q.replace('SET search_path=pg_catalog,public,pg_temp',f'SET search_path=pg_catalog,{schema},pg_temp')))
    import ast
    source=Path(__file__).resolve().parents[2]/'alembic/versions/228asset0_evidence_snapshot.py'
    canonical=next(n.value for n in ast.walk(ast.parse(source.read_text())) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.strip().startswith('CREATE OR REPLACE FUNCTION canonical_asset_registry_jsonb'))
    conn.execute(canonical)
    module.upgrade()
    return conn,installation,generation,role


def insert(queue,**changes):
    conn,installation,generation,_=queue
    target=dict(installationId=str(installation),installationRevision=1,generation=str(generation),executionEpoch=1,bindingRevision=1,route='/workshop/analyst',resourceHash=HASH)
    target.update(changes)
    request=uuid4()
    from aos_api.asset_registry.canonical_json import canonical_json
    body=dict(schemaVersion='aos.runtime-ui-read-request/v1',operationId='analyst_workspace_view_v1',moduleId='ecommerce.analyst',target=target,caseLimit=20,runLimit=5)
    request_hash='sha256:'+hashlib.sha256(canonical_json(dict(tenant=dict(orgId='org-org',projectId='dev-project'),subject='reader',request=body))).hexdigest()
    conn.execute('''INSERT INTO extension_runtime_ui_read_request(org_id,project_id,request_id,subject,idempotency_key,request_hash,
      installation_id,generation,execution_epoch,operation_id,module_id,target_json,case_limit,run_limit,state,deadline)
      VALUES('org-org','dev-project',%s,'reader',%s,%s,%s,%s,1,'analyst_workspace_view_v1','ecommerce.analyst',%s,20,5,'requested',clock_timestamp()+interval '1 minute')''',
      (request,str(request),request_hash,installation,generation,Jsonb(target)))
    return request


def test_queue_rls_and_runtime_has_no_enqueue_privilege(queue):
    conn,_,_,role=queue
    insert(queue)
    conn.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(role)))
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()[0]==1
    conn.execute("SELECT set_config('aos.org_id','dev-org',false)")
    assert conn.execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()[0]==0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):insert(queue)


@pytest.mark.parametrize('changes',[{'resourceHash':None},{'installationRevision':'1'},{'executionEpoch':True},{'route':'/workshop/other'},{'approved':True},{'bindingRevision':2},{'installationRevision':2}])
def test_queue_rejects_ambiguous_target(queue,changes):
    with pytest.raises(psycopg.Error):insert(queue,**changes)
    assert queue[0].execute('SELECT count(*) FROM extension_runtime_ui_read_request').fetchone()[0]==0


def test_request_identity_and_terminal_history_are_immutable(queue):
    conn,*_=queue;request=insert(queue)
    with pytest.raises(psycopg.Error):conn.execute("UPDATE extension_runtime_ui_read_request SET subject='other',revision=2")
    conn.execute("UPDATE extension_runtime_ui_read_request SET state='denied',failure_code='ACCESS_DENIED',completed_at=clock_timestamp(),revision=2")
    with pytest.raises(psycopg.Error):conn.execute("UPDATE extension_runtime_ui_read_request SET state='requested',failure_code=NULL,completed_at=NULL,revision=3")
    with pytest.raises(psycopg.Error):conn.execute('DELETE FROM extension_runtime_ui_read_request')
    assert conn.execute('SELECT request_id,state FROM extension_runtime_ui_read_request').fetchone()==(request,'denied')


def test_success_requires_exact_existing_attempt_and_its_terminal_state(queue):
    conn,installation,generation,_=queue;request=insert(queue)
    store=PostgresRuntimeAttemptStore()
    with conn.transaction():
        attempt=store.begin(conn,**SCOPE,installation_id=installation,generation=generation,execution_epoch=1,
            operation_kind='signed_read',operation_key='ui-read:'+str(request),idempotency_key=str(request),request_hash=HASH,
            owner_token=TOKEN,lease_until=datetime.now(timezone.utc)+timedelta(minutes=1))
    owner_hash='sha256:'+hashlib.sha256(TOKEN.encode()).hexdigest()
    conn.execute('''UPDATE extension_runtime_ui_read_request SET state='claimed',revision=2,claimed_at=clock_timestamp(),
       attempt_id=%s,owner_token_hash=%s,snapshot_hash=%s,attempt_request_hash=%s''',(attempt.attempt_id,owner_hash,HASH,HASH))
    terminal="UPDATE extension_runtime_ui_read_request SET state='succeeded',revision=3,completed_at=clock_timestamp(),result_json='{}',result_hash=%s"
    with pytest.raises(psycopg.Error,match='execution attempt'):conn.execute(terminal,('sha256:'+hashlib.sha256(b'{}').hexdigest(),))
    with conn.transaction():store.settle(conn,**SCOPE,attempt_id=attempt.attempt_id,expected_revision=1,owner_token=TOKEN,state='succeeded')
    with pytest.raises(psycopg.Error):conn.execute(terminal,(HASH,))
    conn.execute(terminal,('sha256:'+hashlib.sha256(b'{}').hexdigest(),))
    assert conn.execute('SELECT state FROM extension_runtime_ui_read_request').fetchone()[0]=='succeeded'
