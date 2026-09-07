"""AR2-3 package-owned Niushop read and public Data fulfillment contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sys

import pytest

from aos_api.business_investigation_niushop_profile import NiushopProfile as LegacyNiushopProfile


ROOT = Path(__file__).resolve().parents[4]
SDK_ROOT = ROOT / "packages/aos-extension-sdk/python"
NIUSHOP_ROOT = ROOT / "bundles/platforms/ecommerce-niushop/backend"
GROWTH_ROOT = ROOT / "bundles/solutions/ecommerce-growth/backend"
for dependency in (SDK_ROOT, NIUSHOP_ROOT, GROWTH_ROOT):
    if str(dependency) not in sys.path:
        sys.path.insert(0, str(dependency))

from aos_extension_sdk import ConnectorRequest, DispatchRef
from aos_api.extension_runtime.connector_broker import (
    ConnectorAuthoritySnapshot,
    ConnectorBroker,
    ConnectorOperationSchema,
)
from ecommerce_growth.data_fulfillment import (
    DataRequirementSpec,
    bind_observation_fulfillment,
    request_requirement,
)
from ecommerce_growth.sdk_ports import ExactRef as GrowthRef
from ecommerce_niushop.business_investigation_niushop_profile import (
    NiushopProfile as PackageNiushopProfile,
    evaluate_niushop_profile as evaluate_package_profile,
)
from ecommerce_niushop.connector import (
    NiushopFactQuery,
    connector_operation_schema,
    read_bounded_facts,
)
from ecommerce_niushop.sdk_ports import ExactRef as AdapterRef


HASH_A = f"sha256:{'a' * 64}"
HASH_B = f"sha256:{'b' * 64}"
CUTOFF = datetime(2026, 9, 8, 0, tzinfo=UTC)
PROFILE_FIXTURE = ROOT / "services/aos-api/tests/fixtures/business_investigation/niushop_profile.json"


def dispatch(operation: str, *, org_id: str = "org-org") -> DispatchRef:
    return DispatchRef.from_payload(
        {
            "orgId": org_id,
            "projectId": "dev-project",
            "operationId": operation,
            "handlerKind": "extension",
            "dispatchRevision": 1,
            "installationId": "11111111-1111-4111-8111-111111111111",
            "generation": "22222222-2222-4222-8222-222222222222",
            "executionEpoch": 1,
            "cutoverGroupId": "33333333-3333-4333-8333-333333333333",
            "cutoverGroupRevision": 1,
        }
    )


def adapter_ref(kind: str, identity: str, *, receipt_id: str | None = None) -> AdapterRef:
    return AdapterRef(
        resourceType=kind,
        resourceId=identity,
        revision=1,
        contentHash=HASH_A,
        receiptId=receipt_id,
    )


def growth_ref(kind: str, identity: str, *, receipt_id: str | None = None) -> GrowthRef:
    return GrowthRef(kind, identity, 1, HASH_A, receipt_id)


def query() -> NiushopFactQuery:
    return NiushopFactQuery(
        requirementRef=adapter_ref("DataRequirementRevision", "requirement-1"),
        connectionRef=adapter_ref("ConnectionRevision", "connection-1"),
        sourceReadinessRef=adapter_ref(
            "SourceReadinessEnvelope", "readiness-1", receipt_id="readiness-receipt-1"
        ),
        mappingRef=adapter_ref("SourceMappingRevision", "mapping-1"),
        cutoffAt=CUTOFF,
        factFamilies=["order", "payment"],
        objectIds=[],
        selectedFields=["orderCount", "paidAmountMinor"],
        maxRows=100,
        timeoutSeconds=10,
        idempotencyKey="niushop-read-1",
    )


def exact_payload(ref: AdapterRef) -> dict[str, object]:
    return ref.model_dump(by_alias=True, exclude_none=True)


def observation(item: NiushopFactQuery | None = None) -> dict[str, object]:
    item = item or query()
    return {
        "requirementRef": exact_payload(item.requirement_ref),
        "sourceReadinessRef": exact_payload(item.source_readiness_ref),
        "mappingRef": exact_payload(item.mapping_ref),
        "cutoffAt": CUTOFF.isoformat(),
        "observedAt": (CUTOFF + timedelta(minutes=2)).isoformat(),
        "facts": [
            {
                "factId": "order-count-2026-09-08",
                "factFamily": "order",
                "canonicalType": "Order",
                "objectId": "shop-qyh",
                "field": "orderCount",
                "value": 92,
                "asOf": CUTOFF.isoformat(),
            },
            {
                "factId": "paid-amount-2026-09-08",
                "factFamily": "payment",
                "canonicalType": "Payment",
                "objectId": "shop-qyh",
                "field": "paidAmountMinor",
                "value": 1826000,
                "asOf": CUTOFF.isoformat(),
            },
        ],
        "factRefs": [
            exact_payload(adapter_ref("FactRevision", "order-count-2026-09-08")),
            exact_payload(adapter_ref("FactRevision", "paid-amount-2026-09-08")),
        ],
        "evidenceRefs": [
            exact_payload(adapter_ref("EvidenceBundleRevision", "evidence-qyh-2026-09-08"))
        ],
        "qualityScore": 0.98,
        "sourceSummaryHash": HASH_B,
    }


class ReadExecutor:
    def __init__(self, result=None):
        self.result = result

    def execute(self, *, dispatch_ref, request):
        assert dispatch_ref.org_id == "org-org" and dispatch_ref.project_id == "dev-project"
        assert set(request.to_payload()["typedParams"]) == {
            "requirementRef", "sourceReadinessRef", "mappingRef", "factFamilies",
            "objectIds", "selectedFields", "maxRows", "timeoutSeconds"
        }
        return self.result or observation()


class Authority:
    def __init__(self, *, available=True, mapping_hash=HASH_A):
        self.available = available
        self.mapping_hash = mapping_hash

    def revalidate(self, *, dispatch_ref, request):
        params = request.typed_params
        mapping_ref = dict(params["mappingRef"])
        mapping_ref["contentHash"] = self.mapping_hash
        return ConnectorAuthoritySnapshot(
            available=self.available,
            connection_ref=dict(request.connection_ref),
            requirement_ref=dict(params["requirementRef"]),
            source_readiness_ref=dict(params["sourceReadinessRef"]),
            mapping_ref=mapping_ref,
            cutoff_at=request.cutoff_at,
        )


def read_schema() -> ConnectorOperationSchema:
    return ConnectorOperationSchema.from_payload(connector_operation_schema())


def read_port(*, authority=None, result=None) -> ConnectorBroker:
    return ConnectorBroker(
        {"ecommerce_niushop_facts_read": read_schema()},
        authority or Authority(),
        ReadExecutor(result),
    )


class DataPort:
    def __init__(self):
        self.commands: list[dict] = []

    def commit(self, *, dispatch_ref, command):
        assert dispatch_ref.org_id == "org-org" and dispatch_ref.project_id == "dev-project"
        assert "tenant" not in command and "orgId" not in command and "projectId" not in command
        self.commands.append(dict(command))
        if command["operation"] == "data.requirement.request":
            return {
                "requirementRef": {
                    "resourceType": "DataRequirementRevision",
                    "resourceId": "requirement-1",
                    "revision": 1,
                    "contentHash": HASH_A,
                }
            }
        return {
            "fulfillmentRef": {
                "resourceType": "DataFulfillmentReceipt",
                "resourceId": "fulfillment-1",
                "revision": 1,
                "contentHash": HASH_B,
                "receiptId": "fulfillment-receipt-1",
            }
        }


def test_package_owns_the_existing_profile_without_semantic_drift() -> None:
    payload = json.loads(PROFILE_FIXTURE.read_text(encoding="utf-8"))
    profile = PackageNiushopProfile.model_validate(payload)
    legacy = LegacyNiushopProfile.model_validate(payload)
    receipt = evaluate_package_profile(profile)
    assert receipt.status == "passed"
    assert profile.model_dump(by_alias=True, mode="json") == legacy.model_dump(
        by_alias=True, mode="json"
    )
    assert "NO_SOURCE_READ" in receipt.non_claims


def test_bounded_connector_produces_same_cutoff_qiyuehui_shaped_facts() -> None:
    item = query()
    result = read_bounded_facts(
        item,
        dispatch_ref=dispatch("ecommerce_niushop_facts_read"),
        port=read_port(),
    )
    assert result.cutoff_at == CUTOFF and result.quality_score == 0.98
    assert {fact.fact_family for fact in result.facts} == {"order", "payment"}
    assert all(fact.as_of == CUTOFF for fact in result.facts)


def test_connector_rejects_arbitrary_targets_credentials_and_nonfinite_values() -> None:
    connection = exact_payload(adapter_ref("ConnectionRevision", "connection-1"))
    for params in (
        {"sql": "SELECT *"},
        {"nested": {"token": "secret"}},
        {"url": "https://example.invalid"},
        {"value": float("nan")},
    ):
        with pytest.raises(ValueError):
            ConnectorRequest(connection, "ecommerce_niushop_facts_read", params, CUTOFF, "key")

    original = {"factFamilies": ["order"]}
    frozen = ConnectorRequest(
        connection, "ecommerce_niushop_facts_read", original, CUTOFF, "key"
    )
    original["sql"] = "SELECT secret"
    original["factFamilies"].append("customer")
    assert frozen.to_payload()["typedParams"] == {"factFamilies": ["order"]}
    with pytest.raises(TypeError):
        frozen.typed_params["sql"] = "SELECT secret"


def test_host_broker_revalidates_allowlist_readiness_mapping_and_exact_refs() -> None:
    item = query()
    params = {
        "requirementRef": exact_payload(item.requirement_ref),
        "sourceReadinessRef": exact_payload(item.source_readiness_ref),
        "mappingRef": exact_payload(item.mapping_ref),
        "factFamilies": ["order"],
        "objectIds": [],
        "selectedFields": ["orderCount"],
        "maxRows": 10,
        "timeoutSeconds": 5,
    }
    connection = exact_payload(item.connection_ref)
    for drift in ({**params, "tableName": "orders"}, {**params, "maxRows": 1001}):
        request = ConnectorRequest(
            connection, "ecommerce_niushop_facts_read", drift, CUTOFF, "broker-key"
        )
        with pytest.raises(ValueError):
            read_port().request(
                dispatch_ref=dispatch("ecommerce_niushop_facts_read"), request=request
            )
    request = ConnectorRequest(
        connection, "ecommerce_niushop_facts_read", params, CUTOFF, "broker-key"
    )
    for authority in (Authority(available=False), Authority(mapping_hash=HASH_B)):
        with pytest.raises(PermissionError, match="authority"):
            read_port(authority=authority).request(
                dispatch_ref=dispatch("ecommerce_niushop_facts_read"), request=request
            )
    for target_name in (
        "tablename", "TableName", "TABLE", "querytarget", "QueryTarget",
        "DatabaseName", "SchemaName",
    ):
        unsafe_schema = connector_operation_schema()
        unsafe_schema["parameters"][0]["name"] = target_name
        with pytest.raises(ValueError, match="parameter rule"):
            ConnectorOperationSchema.from_payload(unsafe_schema)


@pytest.mark.parametrize("drift", ["field", "object", "ref", "nan", "max_rows"])
def test_adapter_rejects_unrequested_or_untraceable_facts(drift: str) -> None:
    item = query().model_copy(update={"object_ids": ["shop-qyh"]})
    result = observation(item)
    if drift == "field":
        result["facts"][0]["field"] = "unrequestedSensitiveField"
    elif drift == "object":
        result["facts"][0]["objectId"] = "another-shop"
    elif drift == "ref":
        result["factRefs"][0]["resourceId"] = "unrelated"
    else:
        if drift == "nan":
            result["facts"][0]["value"] = float("nan")
        else:
            item = item.model_copy(update={"max_rows": 1})
    with pytest.raises(ValueError):
        read_bounded_facts(
            item,
            dispatch_ref=dispatch("ecommerce_niushop_facts_read"),
            port=read_port(result=result),
        )


def test_growth_composes_requirement_and_fulfillment_without_tenant_override() -> None:
    data_port = DataPort()
    growth_dispatch = dispatch("ecommerce_growth_data_fulfill")
    spec = DataRequirementSpec(
        case_ref=growth_ref("BusinessInvestigationCaseRevision", "case-1"),
        run_ref=growth_ref("BusinessInvestigationRun", "run-1"),
        checkpoint_ref=growth_ref("CheckpointRevision", "checkpoint-1"),
        channel_ref=growth_ref("ChannelRevision", "channel-niushop"),
        entity_ref=growth_ref("BusinessEntityRevision", "shop-qyh"),
        required_facts=("Order", "Payment"),
        window_start=CUTOFF - timedelta(days=30),
        window_end=CUTOFF,
        cutoff_at=CUTOFF,
        quality_threshold=0.95,
        min_population=20,
        idempotency_key="requirement-once",
    )
    requirement_ref = request_requirement(data_port, growth_dispatch, spec)
    fulfillment_ref = bind_observation_fulfillment(
        data_port,
        growth_dispatch,
        requirement_ref=requirement_ref,
        cutoff_at=CUTOFF,
        observation=observation(),
        idempotency_key="fulfillment-once",
    )
    assert requirement_ref.resource_type == "DataRequirementRevision"
    assert fulfillment_ref.resource_type == "DataFulfillmentReceipt"
    assert [item["operation"] for item in data_port.commands] == [
        "data.requirement.request", "data.fulfillment.bind"
    ]


def test_authority_cutoff_quality_and_cross_tenant_drift_fail_closed() -> None:
    item = query()
    wrong_cutoff = observation(item)
    wrong_cutoff["cutoffAt"] = (CUTOFF + timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError, match="cutoff"):
        bind_observation_fulfillment(
            DataPort(), dispatch("ecommerce_growth_data_fulfill"),
            requirement_ref=growth_ref("DataRequirementRevision", "requirement-1"),
            cutoff_at=CUTOFF, observation=wrong_cutoff, idempotency_key="bind",
        )

    bad_quality = observation(item)
    bad_quality["qualityScore"] = float("nan")
    with pytest.raises(ValueError, match="quality"):
        bind_observation_fulfillment(
            DataPort(), dispatch("ecommerce_growth_data_fulfill"),
            requirement_ref=growth_ref("DataRequirementRevision", "requirement-1"),
            cutoff_at=CUTOFF, observation=bad_quality, idempotency_key="bind",
        )

    with pytest.raises(AssertionError):
        read_bounded_facts(
            item,
            dispatch_ref=dispatch("ecommerce_niushop_facts_read", org_id="dev-org"),
            port=read_port(),
        )
    with pytest.raises(PermissionError):
        request_requirement(
            DataPort(), dispatch("ecommerce_growth_case_put"),
            DataRequirementSpec(
                growth_ref("BusinessInvestigationCaseRevision", "case-1"),
                growth_ref("BusinessInvestigationRun", "run-1"),
                growth_ref("CheckpointRevision", "checkpoint-1"),
                growth_ref("ChannelRevision", "channel-niushop"),
                growth_ref("BusinessEntityRevision", "shop-qyh"),
                ("Order",), CUTOFF - timedelta(days=1), CUTOFF, CUTOFF, 0.9, 1, "key",
            ),
        )
