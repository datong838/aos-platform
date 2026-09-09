from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_fulfillment_store import DataFulfillmentBindResult, canonical_fulfillment_content_hash
from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    DataFulfillHostService,
    DataRequirementRequestHostService,
    _strict_data_bind,
)
from aos_api.tenant_scope import TenantScope
from tests.test_data_requirement_store import NOW, SCOPE, requirement
from tests.extension_runtime.test_ecommerce_data_request_host import command as request_command, components


HASH = "sha256:" + "a" * 64
CUTOFF = datetime(2026, 8, 26, 5, tzinfo=UTC)


def ref(kind, identity, *, receipt=None, revision=1):
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": revision,
        "contentHash": HASH,
    }
    if receipt is not None:
        value["receiptId"] = receipt
    return value


def bind_command(**changes):
    payload = {
        "operation": "data.fulfillment.bind",
        "idempotencyKey": "fulfillment-once",
        "requirementRef": ref("DataRequirementRevision", "requirement-1"),
        "sourceReadinessRef": ref("SourceReadinessEnvelope", "readiness-1", receipt="readiness-receipt-1"),
        "artifactRefs": [ref("EvidenceBundleRevision", "evidence-1")],
        "factRefs": [ref("FactRevision", "fact-1")],
        "cutoffAt": CUTOFF.isoformat(),
        "qualityScore": 0.98,
        "sourceSummaryHash": HASH,
    }
    payload.update(changes)
    return payload


def test_data_fulfill_host_is_the_runtime_registry_service():
    import aos_api.ecommerce_growth_runtime_adapters as adapters

    assert adapters.DataFulfillHostService is DataFulfillHostService
    assert DataFulfillHostService.executor_identity == DataRequirementRequestHostService.executor_identity


@pytest.mark.parametrize("mutation", ["extra", "missing_facts", "nan_quality", "wrong_requirement"])
def test_bind_command_rejects_incomplete_or_client_authority(mutation):
    value = bind_command()
    if mutation == "extra":
        value["tenant"] = {"orgId": "dev-org"}
    if mutation == "missing_facts":
        value["factRefs"] = []
    if mutation == "nan_quality":
        value["qualityScore"] = float("nan")
    if mutation == "wrong_requirement":
        value["requirementRef"]["resourceType"] = "Task"
    with pytest.raises(ValueError):
        _strict_data_bind(value)


def test_data_fulfill_host_delegates_requirement_request(monkeypatch):
    item = requirement()
    parts, stored, calls = components(item)
    host = DataFulfillHostService()
    monkeypatch.setattr(host._request, "_components", lambda *_: parts)
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_data_fulfill")
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=request_command())
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=request_command(),
        checked_at=NOW,
        occurred_at=None,
    )
    assert "requirementRef" in response
    assert "fulfillmentRef" not in response
    assert calls


def test_data_fulfill_host_binds_without_copying_client_quality_score(monkeypatch):
    item = requirement()
    bound = []
    fulfillment = DataFulfillmentReceiptRecord.model_validate(
        {
            "schemaVersion": "aos.data-fulfillment-authority-receipt/v1",
            "tenant": {"orgId": "org-org", "projectId": "dev-project"},
            "fulfillmentId": "fulfillment-once",
            "receiptId": "receipt-bind-1",
            "requirementRef": ref("DataRequirementRevision", item.requirement_id, revision=item.revision),
            "status": "fulfilled",
            "artifactRefs": [ref("EvidenceBundleRevision", "evidence-1")],
            "sourceReadinessRef": ref("SourceReadinessEnvelope", "readiness-1", receipt="readiness-receipt-1"),
            "cutoffAt": item.cutoff_at,
            "fulfilledAt": NOW,
            "contentHash": HASH,
            "createdBy": DataFulfillHostService.executor_identity,
            "blockers": [],
        }
    )
    fulfillment = fulfillment.model_copy(update={"content_hash": canonical_fulfillment_content_hash(fulfillment)})

    def bind(scope, actor, key, record):
        bound.append((scope, actor, key, record))
        return DataFulfillmentBindResult(fulfillment.receipt_id, fulfillment.content_hash, False)

    data = SimpleNamespace(get_exact=lambda *_: item)
    store = SimpleNamespace(bind=bind, read_exact=lambda *_: fulfillment)
    host = DataFulfillHostService()
    monkeypatch.setattr(host, "_bind_components", lambda *_: (data, store))
    transaction = HostTransaction(SimpleNamespace())
    dispatch = SimpleNamespace(operation_id="ecommerce_growth_data_fulfill")
    command = bind_command(
        requirementRef=ref("DataRequirementRevision", item.requirement_id, revision=item.revision),
        cutoffAt=item.cutoff_at.astimezone(UTC).isoformat(),
    )
    host.revalidate(transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command)
    response = host.execute(
        transaction=transaction,
        scope=SCOPE,
        dispatch_ref=dispatch,
        command=command,
        checked_at=NOW,
        occurred_at=NOW,
    )
    assert set(response) == {"fulfillmentRef"}
    assert response["fulfillmentRef"]["resourceType"] == "DataFulfillmentReceipt"
    assert "qualityScore" not in response
    assert bound[0][1] == host.executor_identity
    assert bound[0][3].created_by == host.executor_identity
    assert host.verify_receipt(
        transaction=transaction, scope=SCOPE, dispatch=dispatch, command=command, receipt=response
    ) == response


def test_bind_rejects_cutoff_drift_from_requirement(monkeypatch):
    item = requirement()
    host = DataFulfillHostService()
    monkeypatch.setattr(
        host,
        "_bind_components",
        lambda *_: (SimpleNamespace(get_exact=lambda *_: item), SimpleNamespace()),
    )
    command = bind_command(
        requirementRef=ref("DataRequirementRevision", item.requirement_id, revision=item.revision),
        cutoffAt=datetime(2026, 9, 8, tzinfo=UTC).isoformat(),
    )
    with pytest.raises(ValueError, match="cutoff"):
        host.revalidate(
            transaction=HostTransaction(SimpleNamespace()),
            scope=SCOPE,
            dispatch=SimpleNamespace(operation_id="ecommerce_growth_data_fulfill"),
            command=command,
        )
