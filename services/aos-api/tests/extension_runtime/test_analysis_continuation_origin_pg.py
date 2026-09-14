"""Actual initialization origin proof; current source fixtures remain explicit."""
import pytest
from test_analysis_continuation_context_pg import (
    completed_case,formal_case,preview_case,review_identity,compilation_case,publications,context_publication,
    context_case,startup_case,analysis_case,consumer_case,host_case,control_governed,governed,
    service_case,stored,pair,body,
)
pytestmark=[pytest.mark.parametrize('startup_case',['defer-host'],indirect=True),
            pytest.mark.parametrize('stored',['qualified-runtime'],indirect=True)]


def read(data,execute=lambda value:value):
    from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
    from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
    conn,analysis,claimed,receipt=data
    return AnalysisContinuationOrigin(AnalysisContinuationContext(analysis)).run_current(
        conn,receipt_ref=receipt,execute=execute)


def test_actual_original_initialization_is_readable(completed_case):
    result=read(completed_case)
    assert result['initializationEvidenceRef']['resourceType']=='Evidence'
    assert result['analysisReceipt']['receiptRef']==completed_case[3]


@pytest.mark.parametrize('fault',['rejected','membership','draft'])
def test_current_origin_drift_is_rejected(completed_case,fault):
    conn,analysis,claimed,receipt=completed_case
    if fault=='rejected':conn.execute("UPDATE aip_action_proposal SET status='rejected' WHERE org_id=%s AND project_id=%s AND action_type_id='ecommerce_analysis_bootstrap'",analysis.scope.key)
    elif fault=='membership':conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*analysis.scope.key,analysis.source.actor))
    else:conn.execute("UPDATE aip_action_draft SET snapshot='{}' WHERE org_id=%s AND project_id=%s",analysis.scope.key)
    with pytest.raises((ValueError,PermissionError)):read(completed_case)


def test_origin_changed_during_callback_is_rolled_back(completed_case):
    conn,analysis,claimed,receipt=completed_case
    before=read(completed_case)
    def mutate(value):
        conn.execute("UPDATE aip_action_proposal SET status='rejected' WHERE org_id=%s AND project_id=%s AND action_type_id='ecommerce_analysis_bootstrap'",analysis.scope.key)
        return value
    with pytest.raises(ValueError):read(completed_case,mutate)
    assert read(completed_case)==before


def test_revoked_original_evidence_is_rejected(completed_case):
    from uuid import uuid4
    conn,analysis,claimed,receipt=completed_case
    reference=read(completed_case)['initializationEvidenceRef']
    conn.execute("""INSERT INTO aip_evidence_revoke_event(org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
        VALUES(%s,%s,%s,%s,1,%s,'fixture revoke','fixture')""",(*analysis.scope.key,uuid4().hex,
        reference['resourceId'],reference['contentHash'].removeprefix('sha256:')))
    with pytest.raises(ValueError,match='Evidence drifted'):read(completed_case)


def test_actual_independent_initialization_origin(formal_case,monkeypatch):
    import asyncio
    from uuid import uuid4
    from aos_api.ecommerce_analysis_bootstrap_start import _BootstrapProductionStartService
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.aip_production_contracts import ActionProposalExactRef
    from aos_api.automation_occurrence_store import AutomationOccurrenceStore
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    original=_BootstrapProductionStartService.start
    def reviewed(self,scope,actor,key,body):
        approved=AipActionStore(self._connect_factory,bootstrap_guard=self._guard).decide(
            scope,'fixture-approver',body.action_proposal_ref.proposal_id,uuid4().hex,
            DecideActionProposalRequest(expectedProposalVersion=body.action_proposal_ref.version,
                expectedProposalHash=body.action_proposal_ref.proposal_hash,decision=ApprovalDecision.APPROVED)).proposal
        reviewed_body=body.model_copy(update={'action_proposal_ref':ActionProposalExactRef(
            proposalId=approved.id,version=approved.version,proposalHash=approved.proposal_hash)})
        return original(self,scope,actor,key,reviewed_body)
    monkeypatch.setattr(_BootstrapProductionStartService,'start',reviewed)
    conn,analysis,claimed=formal_case
    receipt=asyncio.run(analysis.handle(claimed))
    AutomationOccurrenceStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope)).record_target_receipt(
        analysis.scope,occurrence_id=claimed.occurrence_id,owner=claimed.claim_owner,receipt_ref=receipt,
        occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0))
    assert read((conn,analysis,claimed,receipt))['analysisReceipt']['receiptRef']==receipt
