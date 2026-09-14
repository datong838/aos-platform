"""Original locked dispatch and Receipt Store; named snapshot stage, no real source."""
import pytest

from test_analysis_snapshot_resume_states_pg import (
    snapshot_case,resume_case,pytestmark,data_case,formal_case,preview_case,review_identity,compilation_case,
    publications,context_publication,context_case,startup_case,analysis_case,consumer_case,
    host_case,control_governed,governed,service_case,stored,pair,body,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore


@pytest.fixture
def unified_case(snapshot_case,resume_case):
    snapshot_case[2].context.origin=resume_case[2].origin
    return snapshot_case


def test_snapshot_unified_receipt_uses_original_locked_host_and_store(unified_case):
    conn,analysis,session,run,runtime,requirement,tasks,runs=unified_case
    receipt=session.resume()
    assert receipt['phase']=='RUNNING' and receipt['mappingRef'] is None
    assert receipt['taskRunRef']['resourceId']==runtime.task_run_ref.resource_id
    assert receipt['taskRunRef']['revision']==runtime.task_run_ref.version+1
    assert receipt['requestHash']==session.command['requestHash']
    saved=_HostAnalysisReceiptStore(HostTransaction(conn),analysis.scope).read(session.command['idempotencyKey'])
    assert saved==receipt
    assert _HostAnalysisReceiptStore(HostTransaction(conn),analysis.scope).read_exact(receipt['receiptRef'])==receipt
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='running'
    assert runs.get_verified(analysis.scope,run.authority.run_id).state.version==run.state.version+1
    assert not tasks.timeline(analysis.scope,runtime.task_run_ref.resource_id).steps


@pytest.mark.parametrize('fault',['save','verify','outer'])
def test_unified_receipt_failure_rolls_back_original_states(unified_case,monkeypatch,fault):
    conn,analysis,session,run,runtime,requirement,tasks,runs=unified_case
    if fault=='save':
        monkeypatch.setattr(_HostAnalysisReceiptStore,'put',lambda *a,**kw:(_ for _ in ()).throw(ValueError('named save failure')))
    elif fault=='verify':
        from aos_api.ecommerce_analysis_snapshot_resume import _CurrentSnapshotAnalysisHost
        monkeypatch.setattr(_CurrentSnapshotAnalysisHost,'verify_receipt',lambda *a,**kw:{})
    elif fault=='outer':
        from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
        original=AnalysisContinuationOrigin.run_current
        def failing(*args,**kwargs):
            result=original(*args,**kwargs)
            # The new read-only preflight returns None before any state writes.
            if isinstance(result,dict) and result.get('phase')=='RUNNING':
                raise ValueError('named post-host origin failure')
            return result
        monkeypatch.setattr(AnalysisContinuationOrigin,'run_current',failing)
    with pytest.raises((ValueError,RuntimeError)):session.resume()
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='paused'
    assert runs.get_verified(analysis.scope,run.authority.run_id).state==run.state
    assert _HostAnalysisReceiptStore(HostTransaction(conn),analysis.scope).read(session.command['idempotencyKey']) is None


def test_recreated_session_reads_committed_receipt_without_pending_or_writes(unified_case,monkeypatch):
    from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession
    from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext
    conn,analysis,session,run,runtime,requirement,tasks,runs=unified_case
    receipt=session.resume()
    after=runs.get_verified(analysis.scope,run.authority.run_id)
    def forbidden(*a,**kw):raise AssertionError('committed replay must not prepare or resume again')
    monkeypatch.setattr(AnalysisSnapshotResumeContext,'run_current',forbidden)
    monkeypatch.setattr(_AnalysisSnapshotResumeSession,'_resume_states',forbidden)
    monkeypatch.setattr(_HostAnalysisReceiptStore,'put',forbidden)
    recreated=_AnalysisSnapshotResumeSession(session.context,conn,session.command)
    assert recreated.resume()==receipt
    assert runs.get_verified(analysis.scope,run.authority.run_id)==after
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_ref=%s",
        ('run-control:resume:'+session.control_key,)).fetchone()['n']==1


@pytest.mark.parametrize('fault',['command-conflict','missing-unified','scope','advanced'])
def test_committed_conflict_or_partial_trace_never_resends(unified_case,monkeypatch,fault):
    from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession
    from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext
    from tests.test_analysis_snapshot_resume_contracts import seal
    conn,analysis,session,run,runtime,requirement,tasks,runs=unified_case
    session.resume()
    command=session.command
    if fault=='command-conflict':
        command['businessEvidenceRef']['resourceId']='other'
        seal(command)
    elif fault=='missing-unified':
        original=_HostAnalysisReceiptStore.read
        monkeypatch.setattr(_HostAnalysisReceiptStore,'read',lambda self,key:
            None if key==command['idempotencyKey'] else original(self,key))
    elif fault=='advanced':
        tasks.pause_run(analysis.scope,runtime.task_run_ref.resource_id,
            expected_run_version=runtime.task_run_ref.version+1,expected_task_version=runtime.task_ref.version+1,
            actor='snapshot-test-owner',idempotency_key='snapshot-successor-pause',reason='observe later state')
    def forbidden(*a,**kw):raise AssertionError('conflict must not resend through Pending')
    monkeypatch.setattr(AnalysisSnapshotResumeContext,'run_current',forbidden)
    before_task=tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id)
    before_run=runs.get_verified(analysis.scope,run.authority.run_id)
    with conn.transaction():
        if fault=='scope':conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        recreated=_AnalysisSnapshotResumeSession(session.context,conn,command)
        with pytest.raises((ValueError,PermissionError)):recreated.resume()
        if fault=='scope':conn.execute("SELECT set_config('aos.org_id','org-org',true)")
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id)==before_task
    assert runs.get_verified(analysis.scope,run.authority.run_id)==before_run
