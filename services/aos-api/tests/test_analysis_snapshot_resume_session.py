"""Pure session checks with named connection/stage fixtures; not a PG resume."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analysis_data_resume import _AnalysisDataResumeSession
from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession, SNAPSHOT_RESUME_REASON
from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext, _CurrentSnapshotResumeStage
from aos_api.ecommerce_business_investigation_profile_catalog import INITIAL_STORE_PROFILE
from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService
from aos_api.tenant_scope import TenantScope
from tests.test_analysis_snapshot_resume_contracts import command, seal, SCOPE
from tests.test_data_requirement_store import requirement
from tests.test_aip_business_investigation_evidence import runtime


class NamedConnection:
    def __init__(self):
        self.pid, self.xid, self.scope = 123, 456, SCOPE
        self.now = datetime(2026, 9, 15, tzinfo=timezone.utc)

    def execute(self, sql):
        if 'pg_backend_pid()' in sql:
            row = dict(pid=self.pid, xid=self.xid)
        else:
            assert "current_setting('aos.org_id'" in sql
            row = dict(org_id=self.scope.org_id, project_id=self.scope.project_id, now=self.now)
        return SimpleNamespace(fetchone=lambda:row)


@pytest.fixture
def session_case(monkeypatch):
    conn = NamedConnection()
    cmd = command()
    cmd['profileRef'] = INITIAL_STORE_PROFILE.exact_ref.model_dump(mode='json', by_alias=True, exclude_none=True)
    seal(cmd)
    req = requirement().model_copy(update={'purpose_code':'initial_store_analysis'})
    rt = runtime()
    context = object.__new__(AnalysisSnapshotResumeContext)
    context.scope = SCOPE
    state = {}

    def named_current(self, db, *, command, execute):
        assert self is context and db is conn and command == cmd
        # Other authority values are explicitly not exercised in this pure fixture.
        stage = _CurrentSnapshotResumeStage(conn,SCOPE,command,requirement=req,runtime=rt,
            fulfillment=req,bundle=req,readiness=req,deadline=conn.now+timedelta(minutes=5))
        state['stage'] = stage
        stage._active = True
        try:return execute(stage)
        finally:stage._active = False

    monkeypatch.setattr(AnalysisSnapshotResumeContext,'run_current',named_current)
    session = _AnalysisSnapshotResumeSession(context,conn,cmd)
    run = dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,run_id=rt.task_run_ref.resource_id,
        task_id=rt.task_ref.resource_id,version=rt.task_run_ref.version,status='paused',plan_revision_id=rt.plan_ref.resource_id)
    task = dict(org_id=SCOPE.org_id,project_id=SCOPE.project_id,task_id=rt.task_ref.resource_id,
        version=rt.task_ref.version,status='paused')
    args = dict(actor=AnalysisAdvanceHostService.executor_identity,idempotency_key=session.control_key,
        reason=SNAPSHOT_RESUME_REASON,expected_run_version=rt.task_run_ref.version,expected_task_version=rt.task_ref.version)
    return conn,cmd,session,run,task,args,state


def test_exact_session_and_old_type_only_no_public_registry_change(session_case):
    conn,cmd,session,run,task,args,state = session_case
    with pytest.raises(PermissionError):session.authorize_task_resume(conn,SCOPE,run,task,**args)
    assert AipTaskStore(_analysis_resume_session=session)._analysis_resume_session is session
    old = object.__new__(_AnalysisDataResumeSession)
    assert AipTaskStore(_analysis_resume_session=old)._analysis_resume_session is old
    assert session.run_current(lambda active:active.authorize_task_resume(conn,SCOPE,run,task,**args)) is None
    with pytest.raises(PermissionError):session.authorize_task_resume(conn,SCOPE,run,task,**args)
    from aos_api.ecommerce_growth_runtime_adapters import _strict_analysis_command
    with pytest.raises(ValueError):_strict_analysis_command(cmd)
    for fake in (True,object(),state['stage']):
        with pytest.raises(TypeError):AipTaskStore(_analysis_resume_session=fake)
    with pytest.raises(TypeError):_AnalysisSnapshotResumeSession(object(),conn,cmd)


@pytest.mark.parametrize('fault', ['actor','reason','key','key-suffix','run-id','task-id','owner',
    'run-version','task-version','bool-version','run-status','task-status','plan','row-tenant',
    'row-project','scope','connection','transaction','command','stage-command','profile','expired'])
def test_task_grant_rejects_drift(session_case,monkeypatch,fault):
    conn,cmd,session,run,task,args,state = session_case
    def invoke(active):
        scope = SCOPE
        if fault=='actor':args['actor']='another'
        elif fault=='reason':args['reason']='resume'
        elif fault=='key':args['idempotency_key']='bi-fulfillment-resume-other'
        elif fault=='key-suffix':args['idempotency_key']+='x'
        elif fault=='run-id':run['run_id']='other'
        elif fault=='task-id':task['task_id']='other'
        elif fault=='owner':run['task_id']='other'
        elif fault=='run-version':run['version']+=1
        elif fault=='task-version':task['version']+=1
        elif fault=='bool-version':args['expected_task_version']=True
        elif fault=='run-status':run['status']='running'
        elif fault=='task-status':task['status']='executing'
        elif fault=='plan':run['plan_revision_id']='other'
        elif fault=='row-tenant':run['org_id']='dev-org'
        elif fault=='row-project':task['project_id']='other'
        elif fault=='scope':scope=TenantScope('dev-org','dev-project')
        elif fault=='connection':conn.pid+=1
        elif fault=='transaction':conn.xid+=1
        elif fault=='command':active._command['idempotencyKey']='other'
        elif fault=='stage-command':state['stage']._command['idempotencyKey']='other'
        elif fault=='profile':
            monkeypatch.setattr('aos_api.ecommerce_analysis_snapshot_resume.EcommerceInvestigationProfileCatalog.read',lambda *a:None)
        elif fault=='expired':conn.now+=timedelta(hours=1)
        return active.authorize_task_resume(conn,scope,run,task,**args)
    with pytest.raises((ValueError,PermissionError)):session.run_current(invoke)
    with pytest.raises((ValueError,PermissionError)):session.authorize_task_resume(conn,SCOPE,run,task,**args)


@pytest.mark.parametrize('fault',['nested','deferred','raised'])
def test_session_always_deactivates(session_case,fault):
    conn,cmd,session,run,task,args,state = session_case
    def consume(active):
        if fault=='nested':return active.run_current(lambda _:None)
        if fault=='deferred':return (n for n in [1])
        raise RuntimeError('named consumer failure')
    with pytest.raises((ValueError,RuntimeError)):session.run_current(consume)
    with pytest.raises(PermissionError):session.authorize_task_resume(conn,SCOPE,run,task,**args)


def test_caller_cannot_mutate_session_command(session_case):
    conn,cmd,session,run,task,args,state = session_case
    copied = session.command
    copied['profileRef']['resourceId']='changed'
    assert session.command==cmd
    assert session.control_key.startswith('bi-snapshot-resume-')
    session.run_current(lambda active:active.authorize_task_resume(conn,SCOPE,run,task,**args))
