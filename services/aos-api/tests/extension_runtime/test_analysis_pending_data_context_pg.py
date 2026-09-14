"""Real paused task and pending Stores; upstream source/capability fixtures explicit."""
import pytest
from test_analysis_data_preparation_pg import (
    data_case, prepare, formal_case, preview_case, review_identity, compilation_case,
    publications, context_publication, context_case, startup_case, analysis_case,
    consumer_case, host_case, control_governed, governed, service_case, stored, pair, body,
    pytestmark,
)
from aos_api.ecommerce_analysis_pending_data_context import AnalysisPendingDataContext
from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore, TransactionBoundConnectFactory
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.data_requirement_store import DataRequirementStore, canonical_revision_content_hash
from aos_api.business_investigation_shared_contracts import DataRequirementStatus, InvestigationExactRef
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore, BusinessInvestigationRunControl


@pytest.fixture
def pending_case(data_case):
    conn, analysis, claimed, spec = data_case
    pending = prepare(data_case)
    tx = HostTransaction(conn)
    root = _HostAnalysisReceiptStore(tx, analysis.scope).read(claimed.target_idempotency_key)
    AutomationOccurrenceStore(TransactionBoundConnectFactory(tx, analysis.scope)).record_target_receipt(
        analysis.scope, occurrence_id=claimed.occurrence_id, owner=claimed.claim_owner,
        receipt_ref=root['receiptRef'], occurred_at=conn.execute(
            'SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0))
    return conn, analysis, root, pending, spec, AnalysisPendingDataContext(analysis)


def test_original_pending_window_and_runtime_are_read_only(pending_case):
    conn, analysis, root, pending, spec, owner = pending_case
    first = owner.run_current(conn, receipt_ref=root['receiptRef'], execute=lambda x:x)
    assert owner.run_current(conn, receipt_ref=root['receiptRef'], execute=lambda x:x) == first
    assert first['requirement']['timeWindow'] == spec.time_window.model_dump(mode='json', by_alias=True)
    assert first['requirementRef'] == pending['requirementRef']
    assert first['requirement']['qualityThreshold'] == 1
    assert conn.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s',
        analysis.scope.key).fetchone()['n'] == 0


@pytest.mark.parametrize('fault', ['current', 'checkpoint', 'expiry', 'purpose'])
def test_current_requirement_drift_rejected(pending_case, monkeypatch, fault):
    """Explicit reader doubles simulate independently drifting authority."""
    conn, _, root, _, _, owner = pending_case
    def mutate(value):
        updates = {'revision': value.revision + 1}
        if fault == 'checkpoint': updates = {'checkpoint_ref': value.checkpoint_ref.model_copy(update={'resource_id':'other'})}
        if fault == 'expiry': updates = {'expires_at': value.cutoff_at}
        if fault == 'purpose': updates = {'purpose_code':'other_purpose'}
        return value.model_copy(update=updates)
    methods = ['get_current'] if fault == 'current' else ['get_current', 'get_exact']
    for name in methods:
        original = getattr(DataRequirementStore, name)
        def changed(self, *args, original=original):
            return mutate(original(self, *args))
        monkeypatch.setattr(DataRequirementStore, name, changed)
    with pytest.raises(ValueError):
        owner.run_current(conn, receipt_ref=root['receiptRef'], execute=lambda x:pytest.fail('drift accepted'))


@pytest.mark.parametrize('during', [False, True])
def test_actual_cancelled_head_is_not_pending_authority(pending_case, during):
    conn, analysis, root, pending, _, owner = pending_case
    store = DataRequirementStore(TransactionBoundConnectFactory(HostTransaction(conn), analysis.scope))
    ref = InvestigationExactRef.model_validate(pending['requirementRef'])
    current = store.get_exact(analysis.scope, ref)
    def cancel():
        value = current.model_copy(update={'revision':2, 'prior_ref':ref, 'status':DataRequirementStatus.CANCELLED})
        value = value.model_copy(update={'content_hash':canonical_revision_content_hash(value)})
        store.cancel(analysis.scope, current.created_by, 'test-cancel-current', value, expected_version=1)
    if not during: cancel()
    with pytest.raises(ValueError):
        owner.run_current(conn, receipt_ref=root['receiptRef'], execute=lambda x:cancel() if during else pytest.fail('cancel accepted'))


@pytest.mark.parametrize('fault', ['mutation', 'deferred'])
def test_pending_consumer_cannot_change_or_defer_authority(pending_case, fault):
    conn, _, root, _, _, owner = pending_case
    def consume(value):
        if fault == 'mutation': value['requirement']['qualityThreshold'] = 0
        else: return (item for item in [value])
    with pytest.raises(ValueError): owner.run_current(conn, receipt_ref=root['receiptRef'], execute=consume)


@pytest.mark.parametrize('fault', ['no-pending', 'cancelled-run'])
def test_run_must_still_have_an_active_pending_requirement(pending_case, monkeypatch, fault):
    conn, _, root, _, _, owner = pending_case
    original = BusinessInvestigationRunStore.get_verified
    def changed(self, *args):
        value = original(self, *args)
        update = {'pending_requirement_ref':None} if fault == 'no-pending' else {'control':BusinessInvestigationRunControl.CANCELLED}
        return value.model_copy(update={'state':value.state.model_copy(update=update)})
    monkeypatch.setattr(BusinessInvestigationRunStore, 'get_verified', changed)
    with pytest.raises(ValueError):
        owner.run_current(conn, receipt_ref=root['receiptRef'], execute=lambda x:pytest.fail('inactive run accepted'))
