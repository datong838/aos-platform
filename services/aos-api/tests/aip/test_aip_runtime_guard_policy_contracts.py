from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_runtime_guard_policy_contracts import (
    DataClassificationPolicyRevisionCreate,
    EgressPolicyRevisionCreate,
)


NOW = datetime(2026, 8, 17, tzinfo=UTC)


def egress_payload() -> dict:
    return {
        "policyId": "agnes-egress-dev",
        "revision": 1,
        "environment": "development",
        "allowedSchemes": ["https"],
        "allowedHosts": ["apihub.agnes-ai.com"],
        "allowedPorts": [443],
        "allowPublicFallback": False,
        "unknownDestinationBehavior": "block",
        "regionState": "confirmed",
        "region": "cn-approved-development",
        "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
        "owner": "杜大同",
        "approvalRef": "approval:r1-03",
        "lifecycle": "active",
    }


def classification_payload() -> dict:
    return {
        "policyId": "agnes-data-dev",
        "revision": 1,
        "environment": "development",
        "allowedClassifications": ["public_catalog", "approved_internal_knowledge"],
        "prohibitedClassifications": [
            "direct_pii",
            "raw_order_detail",
            "customer_conversation",
            "credential",
            "commercial_sensitive",
            "cross_tenant",
            "unknown",
        ],
        "denyUnknown": True,
        "allowDirectPii": False,
        "allowCommercialSensitive": False,
        "allowCrossTenant": False,
        "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
        "owner": "杜大同",
        "approvalRef": "approval:r1-03",
        "lifecycle": "active",
    }


def test_approved_guard_policy_contracts_are_strict_and_fail_closed() -> None:
    egress = EgressPolicyRevisionCreate.model_validate(egress_payload())
    data = DataClassificationPolicyRevisionCreate.model_validate(classification_payload())
    assert egress.allowed_hosts == ["apihub.agnes-ai.com"]
    assert egress.allow_public_fallback is False
    assert data.deny_unknown is True
    assert "credential" in data.prohibited_classifications


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("environment", "production"),
        ("allowedSchemes", ["http"]),
        ("allowedHosts", ["example.com"]),
        ("allowedPorts", [80]),
        ("allowPublicFallback", True),
        ("unknownDestinationBehavior", "allow"),
    ],
)
def test_egress_contract_rejects_unapproved_boundary(field: str, value: object) -> None:
    body = egress_payload()
    body[field] = value
    with pytest.raises(ValidationError):
        EgressPolicyRevisionCreate.model_validate(body)


def test_active_egress_requires_confirmed_nonempty_region() -> None:
    for state, region in (("unknown", None), ("confirmed", None)):
        body = egress_payload()
        body["regionState"] = state
        body["region"] = region
        with pytest.raises(ValidationError, match="region"):
            EgressPolicyRevisionCreate.model_validate(body)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowedClassifications", ["direct_pii"]),
        ("prohibitedClassifications", ["credential"]),
        ("denyUnknown", False),
        ("allowDirectPii", True),
        ("allowCommercialSensitive", True),
        ("allowCrossTenant", True),
    ],
)
def test_data_policy_rejects_unsafe_or_incomplete_boundary(field: str, value: object) -> None:
    body = classification_payload()
    body[field] = value
    with pytest.raises(ValidationError):
        DataClassificationPolicyRevisionCreate.model_validate(body)


@pytest.mark.parametrize(
    "factory",
    [egress_payload, classification_payload],
)
def test_guard_policy_request_rejects_authority_injection(factory) -> None:
    model = EgressPolicyRevisionCreate if factory is egress_payload else DataClassificationPolicyRevisionCreate
    for key, value in (
        ("tenant", {"orgId": "dev-org", "projectId": "dev-project"}),
        ("contentHash", "a" * 64),
        ("createdBy", "caller"),
        ("createdAt", NOW.isoformat()),
    ):
        body = factory()
        body[key] = value
        with pytest.raises(ValidationError):
            model.model_validate(body)
