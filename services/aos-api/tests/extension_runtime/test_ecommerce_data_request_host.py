"""Data host wiring reuses canonical data commands and exact historical receipts."""

from types import SimpleNamespace

import pytest

from aos_api.ecommerce_growth_runtime_adapters import (
    DataRequirementRequestHostService, HostTransaction, _strict_data_request,
)
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import DataRequirementApplyResult, DataRequirementCommandReceipt
from tests.test_data_requirement_store import requirement, SCOPE, NOW


def command():
    raw = requirement().model_dump(by_alias=True, mode="json")
    keys = ("caseRef", "runRef", "checkpointRef", "channelRef", "entityRef",
            "purposeCode", "requiredFacts", "timeWindow", "grain", "cutoffAt",
            "freshnessMaxAgeSeconds", "qualityThreshold", "markings", "minPopulation",
            "acceptableDegradation", "requestedOutputs", "budgetMinor", "expiresAt")
    return {**{name: raw[name] for name in keys}, "operation": "data.requirement.request",
            "idempotencyKey": "data-request-1", "expectedRunVersion": 1}


@pytest.mark.parametrize("mutation", ["extra", "missing", "boolean_version", "wrong_ref", "boolean_budget"])
def test_data_request_rejects_incomplete_or_coerced_contract(mutation):
    value = command()
    if mutation == "extra": value["tenant"] = {"orgId": "dev-org"}
    if mutation == "missing": value.pop("freshnessMaxAgeSeconds")
    if mutation == "boolean_version": value["expectedRunVersion"] = True
    if mutation == "wrong_ref": value["checkpointRef"]["resourceType"] = "Task"
    if mutation == "boolean_budget": value["budgetMinor"] = True
    with pytest.raises(ValueError): _strict_data_request(value)


def components(item, *, changed_checkpoint=False, changed_version=False):
    exact = InvestigationExactRef(resource_type="DataRequirementRevision",
        resource_id=item.requirement_id, revision=item.revision, content_hash=item.content_hash)
    stored = DataRequirementCommandReceipt(item, DataRequirementApplyResult(exact, 1, item.content_hash, True))
    case = SimpleNamespace(case_id=item.case_ref.resource_id, revision=item.case_ref.revision,
        content_hash=item.case_ref.content_hash, channel_ref=item.channel_ref,
        business_entity_ref=item.entity_ref)
    run = SimpleNamespace(authority=SimpleNamespace(case_ref=item.case_ref,
        version=item.run_ref.revision, content_hash=item.run_ref.content_hash),
        state=SimpleNamespace(version=2 if changed_version else 1))
    data = SimpleNamespace(find_command_receipt=lambda *_: None,
                           get_exact=lambda *_: item)
    binder = SimpleNamespace(bind_receipt=lambda *_: SimpleNamespace(checkpoint_ref=SimpleNamespace(
        resource_id="changed" if changed_checkpoint else item.checkpoint_ref.resource_id,
        sequence=item.checkpoint_ref.revision, state_hash=item.checkpoint_ref.content_hash[7:])))
    calls = []
    def request(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(requirement_ref=exact, data_replayed=False)
    service = SimpleNamespace(request_missing_data=request)
    def read_transition(*args, **kwargs):
        if kwargs["expected_version"] != 1:
            raise ValueError("historical data-request Receipt drifted")
        return object()
    return (SimpleNamespace(get=lambda *_: case), SimpleNamespace(get=lambda *_: run, read_data_request_receipt=read_transition),
            SimpleNamespace(get_for_run=lambda *_: object()), binder, data, service), stored, calls


def test_data_host_checks_lineage_and_calls_existing_service(monkeypatch):
    item = requirement()
    parts, stored, calls = components(item)
    host = DataRequirementRequestHostService()
    monkeypatch.setattr(host, "_components", lambda *_: parts)
    def journal_not_yet_written(query, params):
        assert "ecommerce_growth_runtime_command_receipt" in query
        assert params == (*SCOPE.key, "ecommerce_growth_data_fulfill", "data-request-1")
        return SimpleNamespace(fetchone=lambda: None)
    transaction = HostTransaction(SimpleNamespace(execute=journal_not_yet_written))
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_data_fulfill")
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command())
    response = host.execute(transaction=transaction, scope=SCOPE, dispatch_ref=dispatch,
        command=command(), checked_at=NOW, occurred_at=None)
    assert response["authority"]["status"] == "requested"
    assert calls[0][0][:2] == (SCOPE, item.run_ref.resource_id)
    assert calls[0][1]["expected_version"] == 1
    assert calls[0][1]["actor"] == host.executor_identity
    parts[4].find_command_receipt = lambda *_: stored
    assert host.verify_receipt(transaction=transaction, scope=SCOPE, dispatch=dispatch,
        command=command(), receipt=response) == response
    changed = command(); changed["budgetMinor"] += 1
    with pytest.raises(ValueError, match="drifted"):
        host.verify_receipt(transaction=transaction, scope=SCOPE, dispatch=dispatch,
            command=changed, receipt=response)
    def forbidden(*args, **kwargs):
        raise AssertionError("completed replay must not consult current runtime")
    parts[0].get = forbidden
    parts[1].get = forbidden
    parts[3].bind_receipt = forbidden
    parts[5].request_missing_data = forbidden
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command())
    replay = host.execute(transaction=transaction, scope=SCOPE, dispatch_ref=dispatch,
        command=command(), checked_at=NOW, occurred_at=None)
    assert replay == {**response, "replayed": True}
    changed = command(); changed["expectedRunVersion"] = 2
    with pytest.raises(ValueError, match="drifted"):
        host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=changed)


@pytest.mark.parametrize("changed", ["checkpoint", "version"])
def test_data_host_refuses_drift_before_write(monkeypatch, changed):
    parts, _stored, calls = components(requirement(), changed_checkpoint=changed == "checkpoint",
                                       changed_version=changed == "version")
    host = DataRequirementRequestHostService()
    monkeypatch.setattr(host, "_components", lambda *_: parts)
    with pytest.raises(ValueError, match="drifted"):
        host.revalidate(transaction=HostTransaction(SimpleNamespace()), scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_data_fulfill"), command=command())
    assert not calls


@pytest.mark.parametrize("tamper", [None, "hash", "tenant", "expected_version"])
def test_historical_run_request_receipt_revalidates_original_state(tamper):
    from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore, BusinessInvestigationRunConflict
    from tests.test_ecommerce_business_investigation_data_command import state
    from tests.test_data_requirement_store import Connection, factory
    item = requirement()
    exact = InvestigationExactRef(resource_type="DataRequirementRevision", resource_id=item.requirement_id,
                                 revision=item.revision, content_hash=item.content_hash)
    original = state(2, pending=exact)
    payload = original.model_dump(by_alias=True, mode="json")
    if tamper == "hash": payload["createdBy"] = "changed"
    if tamper == "tenant": payload["tenant"]["orgId"] = "dev-org"
    row = {"run_id": original.run_id, "expected_version": 2 if tamper == "expected_version" else 1,
           "authority_data": payload}
    conn = Connection(row)
    store = BusinessInvestigationRunStore(factory(conn))
    if tamper:
        with pytest.raises(BusinessInvestigationRunConflict, match="drifted"):
            store.read_data_request_receipt(SCOPE, original.run_id, exact, expected_version=1, idempotency_key="request-1")
    else:
        assert store.read_data_request_receipt(SCOPE, original.run_id, exact,
            expected_version=1, idempotency_key="request-1") == original
    assert conn.commits == 0
