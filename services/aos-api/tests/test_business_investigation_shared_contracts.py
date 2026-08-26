from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from aos_api.business_investigation_shared_contracts import (
    AdaptiveProfileContract,
    BusinessInvestigationSharedEnvelope,
    DataFulfillmentReceiptContract,
    DataRequirementContract,
    ObservationContract,
    SemanticHydrationReceiptContract,
    SourceMappingContract,
)


NOW = datetime(2026, 8, 26, 3, 0, tzinfo=UTC)
HASH = f"sha256:{'a' * 64}"
TENANT = {"orgId": "org-org", "projectId": "dev-project"}


def ref(resource_type: str, resource_id: str, *, receipt_id: str | None = None) -> dict[str, object]:
    value: dict[str, object] = {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": HASH,
    }
    if receipt_id is not None:
        value["receiptId"] = receipt_id
    return value


def envelope() -> dict[str, object]:
    channel_ref = ref("ChannelRevision", "channel-niushop")
    return {
        "schemaVersion": "aos.business-investigation.shared/v1",
        "tenant": TENANT,
        "channel": {
            "channelId": "channel-niushop",
            "platform": "niushop",
            "displayName": "栖月汇微商城",
            "channelRef": channel_ref,
        },
        "businessEntity": {
            "businessEntityId": "shop-qyh",
            "entityType": "shop",
            "displayName": "栖月汇",
            "channelRef": channel_ref,
        },
        "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
        "runRef": ref("BusinessInvestigationRun", "run-1"),
        "readiness": {
            "status": "ready",
            "sourceReadinessRef": ref("SourceReadinessEnvelope", "readiness-1", receipt_id="receipt-ready-1"),
            "coverage": {"required": 3, "fulfilled": 3, "unknown": 0},
            "freshness": {
                "status": "fresh",
                "dataCutoff": NOW,
                "expiresAt": NOW + timedelta(hours=1),
            },
            "blockers": [],
        },
        "artifactRefs": [
            ref("BusinessDossierRevision", "dossier-1"),
            ref("InsightRevision", "insight-1"),
        ],
    }


def test_shared_envelope_is_strict_tenant_bound_and_exact() -> None:
    parsed = BusinessInvestigationSharedEnvelope.model_validate(envelope())
    assert parsed.tenant.org_id == "org-org"
    assert parsed.readiness.status.value == "ready"
    assert parsed.model_dump(by_alias=True)["caseRef"]["contentHash"] == HASH

    bad_hash = envelope()
    bad_hash["caseRef"] = {**ref("BusinessInvestigationCaseRevision", "case-1"), "contentHash": "a" * 64}
    with pytest.raises(ValidationError, match="sha256"):
        BusinessInvestigationSharedEnvelope.model_validate(bad_hash)

    leaked = envelope()
    leaked["rawPayload"] = {"mobile": "13800000000"}
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        BusinessInvestigationSharedEnvelope.model_validate(leaked)


def test_ready_requires_complete_fresh_coverage_and_no_blockers() -> None:
    missing = envelope()
    missing["readiness"] = {
        **missing["readiness"],
        "coverage": {"required": 3, "fulfilled": 2, "unknown": 1},
    }
    with pytest.raises(ValidationError, match="ready readiness"):
        BusinessInvestigationSharedEnvelope.model_validate(missing)

    unknown = envelope()
    unknown["readiness"] = {**unknown["readiness"], "status": "mystery"}
    with pytest.raises(ValidationError):
        BusinessInvestigationSharedEnvelope.model_validate(unknown)


def test_supporting_contracts_preserve_owner_refs_and_unknown() -> None:
    requirement = DataRequirementContract.model_validate(
        {
            "schemaVersion": "aos.data-requirement/v1",
            "tenant": TENANT,
            "requirementId": "requirement-1",
            "caseRef": ref("BusinessInvestigationCaseRevision", "case-1"),
            "runRef": ref("BusinessInvestigationRun", "run-1"),
            "purpose": "经营画像缺口",
            "factTypes": ["Order", "Product"],
            "status": "requested",
            "requestedAt": NOW,
            "blockers": [],
        }
    )
    assert requirement.status.value == "requested"

    fulfillment = DataFulfillmentReceiptContract.model_validate(
        {
            "schemaVersion": "aos.data-fulfillment-receipt/v1",
            "tenant": TENANT,
            "fulfillmentId": "fulfillment-1",
            "requirementRef": ref("DataRequirementRevision", "requirement-1"),
            "status": "unknown",
            "artifactRefs": [],
            "fulfilledAt": NOW,
            "blockers": [{"code": "SOURCE_READINESS_STALE", "severity": "blocking", "dependency": "P01", "requiredAction": "等待新鲜履行"}],
        }
    )
    assert fulfillment.status.value == "unknown"
    assert fulfillment.artifact_refs == []

    observation = ObservationContract.model_validate(
        {
            "schemaVersion": "aos.platform-observation/v1",
            "tenant": TENANT,
            "observationId": "observation-1",
            "status": "blocked",
            "observedAt": NOW,
            "sourceRef": ref("PlatformSourceRevision", "source-1"),
            "evidenceRefs": [],
            "blockers": [{"code": "PLATFORM_PERMISSION_REQUIRED", "severity": "blocking", "dependency": "platform", "requiredAction": "补齐只读权限"}],
        }
    )
    assert observation.status.value == "blocked"

    hydration = SemanticHydrationReceiptContract.model_validate(
        {
            "schemaVersion": "aos.semantic-hydration-receipt/v1",
            "tenant": TENANT,
            "hydrationId": "hydration-1",
            "status": "unknown",
            "observationRef": ref("PlatformObservation", "observation-1"),
            "mappingRef": ref("SourceMappingRevision", "mapping-1"),
            "outputRefs": [],
            "hydratedAt": NOW,
            "blockers": [{"code": "MAPPING_CONFLICT", "severity": "blocking", "dependency": "mapping", "requiredAction": "人工确认映射"}],
        }
    )
    assert hydration.output_refs == []


def test_mapping_and_adaptive_profile_keep_exact_owner_refs() -> None:
    mapping = SourceMappingContract.model_validate(
        {
            "schemaVersion": "aos.source-mapping/v1",
            "tenant": TENANT,
            "mappingId": "mapping-1",
            "observationRef": ref("PlatformObservation", "observation-1"),
            "sourceField": "order.pay_amount",
            "canonicalField": "Order.paidAmount",
            "confidence": 0.93,
            "confirmedBy": None,
            "blockers": [],
        }
    )
    assert mapping.observation_ref.resource_type == "PlatformObservation"

    profile = AdaptiveProfileContract.model_validate(
        {
            "schemaVersion": "aos.adaptive-profile/v1",
            "tenant": TENANT,
            "profileId": "profile-1",
            "sourceRef": ref("PlatformSourceRevision", "source-1"),
            "hypothesisRefs": [ref("SemanticHypothesisRevision", "hypothesis-1")],
            "coverage": {"required": 2, "fulfilled": 1, "unknown": 1},
            "blockers": [{"code": "FIELD_MAPPING_UNKNOWN", "severity": "warning", "dependency": "order.discount", "requiredAction": "人工确认字段语义"}],
        }
    )
    assert profile.coverage.unknown == 1

    invalid_profile = profile.model_dump(by_alias=True)
    invalid_profile["sourceRef"] = ref("PlatformObservation", "observation-1")
    with pytest.raises(ValidationError, match="sourceRef"):
        AdaptiveProfileContract.model_validate(invalid_profile)


def test_json_schema_freezes_python_enum_and_required_fields() -> None:
    schema_path = Path(__file__).parents[3] / "packages/contracts/schemas/business-investigation/shared-v1.schema.json"
    schema = json.loads(schema_path.read_text())
    assert schema["$id"] == "https://aos.dev/schemas/business-investigation/shared-v1.schema.json"
    assert schema["$defs"]["exactRef"]["properties"]["contentHash"]["pattern"] == r"^sha256:[0-9a-f]{64}$"
    assert schema["$defs"]["readinessStatus"]["enum"] == ["ready", "blocked", "stale", "unknown"]
    assert schema["$defs"]["sharedEnvelope"]["additionalProperties"] is False
    assert set(schema["$defs"]["sharedEnvelope"]["required"]) == {
        "schemaVersion", "tenant", "channel", "businessEntity", "caseRef", "runRef", "readiness", "artifactRefs"
    }
