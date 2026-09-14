"""Completed canonical event and current source context, with explicit source fixtures."""
import asyncio
from types import SimpleNamespace
import pytest
from test_product_event_analysis_bootstrap_pg import (
    formal_case,preview_case,review_identity,compilation_case,publications,context_publication,
    context_case,startup_case,analysis_case,consumer_case,host_case,control_governed,governed,
    service_case,stored,pair,body,
)
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory

pytestmark=[pytest.mark.parametrize('startup_case',['defer-host'],indirect=True),
            pytest.mark.parametrize('stored',['qualified-runtime'],indirect=True)]


@pytest.fixture
def completed_case(formal_case):
    conn,analysis,claimed=formal_case
    receipt=asyncio.run(analysis.handle(claimed))
    AutomationOccurrenceStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope)).record_target_receipt(
        analysis.scope,occurrence_id=claimed.occurrence_id,owner=claimed.claim_owner,receipt_ref=receipt,
        occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0))
    return conn,analysis,claimed,receipt


def current(data,execute=lambda value:value):
    from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
    conn,analysis,claimed,receipt=data
    return AnalysisContinuationContext(analysis).run_current(conn,receipt_ref=receipt,execute=execute)


def test_completed_event_uses_current_source_without_a_claim(completed_case):
    conn,analysis,claimed,receipt=completed_case
    result=current(completed_case)
    assert result['analysisReceipt']['receiptRef']==receipt
    assert result['occurrence']['status']=='accepted'
    row=conn.execute('SELECT status,claim_owner,claim_until FROM automation_occurrence WHERE org_id=%s AND project_id=%s AND occurrence_id=%s',(*analysis.scope.key,claimed.occurrence_id)).fetchone()
    assert row==dict(status='accepted',claim_owner=None,claim_until=None)


def test_unfinished_event_is_not_a_completed_continuation(formal_case):
    conn,analysis,claimed=formal_case
    receipt=asyncio.run(analysis.handle(claimed))
    with pytest.raises(ValueError):current((conn,analysis,claimed,receipt))


def test_wrong_original_batch_is_rejected(completed_case):
    conn,analysis,claimed,receipt=completed_case
    original=analysis.source.reader._journal
    analysis.source.reader._journal=SimpleNamespace(_run_id='wrong-batch')
    try:
        with pytest.raises(ValueError,match='original'):current(completed_case)
    finally:analysis.source.reader._journal=original


def test_callback_event_drift_rolls_back(completed_case):
    conn,analysis,claimed,receipt=completed_case
    before=current(completed_case)
    def change(value):
        conn.execute("UPDATE automation_occurrence SET deadline=deadline+interval '1 second' WHERE org_id=%s AND project_id=%s AND occurrence_id=%s",(*analysis.scope.key,claimed.occurrence_id))
        return value
    with pytest.raises(ValueError):current(completed_case,change)
    assert current(completed_case)==before


def test_deferred_callback_is_rejected(completed_case):
    async def later(value):return value
    with pytest.raises((TypeError,ValueError,RuntimeError)):current(completed_case,later)
