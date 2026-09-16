"""Service commits approval once; lost acknowledgement is resolved by original key."""
from contextlib import contextmanager
from types import SimpleNamespace as NS
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aos_api.auth import Principal,require_principal
from aos_api.errors import register_exception_handlers
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.pipeline_snapshot_schedule_service import PipelineSnapshotScheduleService
from aos_api.routers.pipeline_controls import router
from aos_api.tenant_scope import TenantScope

pytest_plugins=('test_snapshot_group_recovery_owner_pg',)


def service_for(runtime,owner,command):
    return PipelineSnapshotScheduleService(scope=command['scope'],controls=owner._controls,installation_store=PostgresInstallationStore())


def test_context_approval_and_receipt_are_committed_without_execution(recovery_case):
    runtime,owner,command,state=recovery_case
    service=service_for(runtime,owner,command)
    context=service.read_recovery_context(group_id=command['group_id'],actor=command['actor'])
    assert context['inputManifestHash']==command['input_manifest_hash']
    assert context['expectedDefinitionRef']==command['expected_definition_ref']
    assert context['expectedRecoveryRef'] is None
    assert 'parents' not in context and 'outputRows' not in str(context)
    result=service.renew_saved_group(**{k:v for k,v in command.items() if k!='scope'})
    assert result['status']=='approval_recorded' and result['executionStarted'] is False
    assert service.read_recovery_receipt(group_id=command['group_id'],actor=command['actor'],
        idempotency_key=command['idempotency_key'])==result['receipt']
    assert state['calls']==1


def test_unknown_commit_ack_uses_original_receipt_readback(recovery_case,monkeypatch):
    runtime,owner,command,state=recovery_case
    service=service_for(runtime,owner,command)
    original=service._connection
    @contextmanager
    def lost():
        with original() as conn:yield conn
        raise OSError('named committed acknowledgement lost')
    monkeypatch.setattr(service,'_connection',lost)
    with pytest.raises(OSError,match='acknowledgement'):
        service.renew_saved_group(**{k:v for k,v in command.items() if k!='scope'})
    monkeypatch.setattr(service,'_connection',original)
    receipt=service.read_recovery_receipt(group_id=command['group_id'],actor=command['actor'],idempotency_key=command['idempotency_key'])
    assert receipt['idempotencyKey']==command['idempotency_key']
    with runtime._transaction(command['scope']) as conn:
        assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_recovery_receipt').fetchone()['n']==1
        assert conn.execute('SELECT count(*) AS n FROM pipeline_runtime_control_revision').fetchone()['n']==24
    assert state['calls']==1


def test_receipt_read_only_mode_keeps_current_permission_and_tenant(recovery_case):
    runtime,owner,command,state=recovery_case
    service=service_for(runtime,owner,command)
    receipt=service.renew_saved_group(**{k:v for k,v in command.items() if k!='scope'})['receipt']
    read_only=PipelineSnapshotScheduleService(scope=command['scope'],controls=None,installation_store=PostgresInstallationStore())
    kwargs=dict(group_id=command['group_id'],actor=command['actor'],idempotency_key=command['idempotency_key'])
    assert read_only.read_recovery_receipt(**kwargs)==receipt
    with pytest.raises(RuntimeConflict,match='membership'):
        read_only.read_recovery_receipt(**(kwargs|dict(actor='not-current-member')))
    negative=PipelineSnapshotScheduleService(scope=TenantScope('dev-org','dev-project'),controls=None,installation_store=PostgresInstallationStore())
    with pytest.raises(LookupError):negative.read_recovery_receipt(**kwargs)
    assert state['calls']==1


def test_real_http_approval_commits_through_original_service(recovery_case):
    runtime,owner,command,state=recovery_case
    service=service_for(runtime,owner,command)
    def build(scope,*,source_controls):
        assert scope==command['scope']
        return service if source_controls else PipelineSnapshotScheduleService(scope=scope,controls=None,installation_store=PostgresInstallationStore())
    app=FastAPI();register_exception_handlers(app);app.include_router(router)
    app.state.extension_runtime_control_plane=NS(pipeline_control_factory=NS(build_snapshot_schedule=build))
    app.dependency_overrides[require_principal]=lambda:Principal(subject=command['actor'],org_id=command['scope'].org_id,
        project_id=command['scope'].project_id,roles=['admin'],markings=[])
    client=TestClient(app)
    path='/v1/pipelines/snapshot-recoveries/'+command['group_id']
    body=dict(expectedDefinitionRef=command['expected_definition_ref'],expectedRecoveryRef=None,inputManifestHash=command['input_manifest_hash'],
        notBefore=command['not_before'].isoformat(),expiresAt=command['expires_at'].isoformat())
    response=client.post(path+'/renew',json=body,headers={'Idempotency-Key':command['idempotency_key']})
    assert response.status_code==200,response.text
    assert response.json()['executionStarted'] is False
    result=client.get(path+'/receipts/'+command['idempotency_key'])
    assert result.status_code==200,result.text
    assert result.json()==response.json()['receipt']
    context=client.get(path)
    assert context.status_code==200,context.text
    assert context.json()['expectedRecoveryRef']==result.json()['ref']
    assert state['calls']==1


def test_context_without_complete_input_never_rereads_source(runtime_case,monkeypatch):
    runtime,args,state,*_=runtime_case
    original=runtime._ingress._transaction
    @contextmanager
    def unknown(scope):
        with original(scope) as conn:yield conn
        raise RuntimeError('named stop before saved input')
    monkeypatch.setattr(runtime._ingress,'_transaction',unknown)
    with pytest.raises(RuntimeError,match='before saved input'):runtime.execute(**args)
    service=PipelineSnapshotScheduleService(scope=args['scope'],controls=runtime._claims._groups._controls,installation_store=PostgresInstallationStore())
    with pytest.raises(IngressJournalConflict,match='INPUT_REQUIRED'):
        service.read_recovery_context(group_id=args['group_id'],actor=args['actor'])
    assert state['calls']==0
