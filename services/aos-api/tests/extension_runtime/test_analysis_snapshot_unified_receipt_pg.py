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
            original(*args,**kwargs)
            raise ValueError('named post-host origin failure')
        monkeypatch.setattr(AnalysisContinuationOrigin,'run_current',failing)
    with pytest.raises((ValueError,RuntimeError)):session.resume()
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='paused'
    assert runs.get_verified(analysis.scope,run.authority.run_id).state==run.state
    assert _HostAnalysisReceiptStore(HostTransaction(conn),analysis.scope).read(session.command['idempotencyKey']) is None
