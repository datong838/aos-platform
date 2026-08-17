from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate


NOW = datetime(2026, 8, 17, tzinfo=UTC)


def payload() -> dict:
    return {
        "policyId": "agnes-network-dev",
        "revision": 1,
        "allowedSchemes": ["https"],
        "allowedHosts": ["apihub.agnes-ai.com"],
        "allowedPorts": [443],
        "tlsRequired": True,
        "publicFallbackAllowed": False,
        "egressPolicyRef": {
            "assetType": "EgressPolicyRevision",
            "assetId": "agnes-egress-dev",
            "revision": 1,
            "contentHash": "a" * 64,
        },
        "effectiveFrom": NOW.isoformat(),
        "effectiveUntil": (NOW + timedelta(days=30)).isoformat(),
        "owner": "杜大同",
        "approvalRef": "approval:r1-04",
        "lifecycle": "active",
    }


def test_network_policy_is_strict_and_fail_closed() -> None:
    policy = NetworkPolicyRevisionCreate.model_validate(payload())
    assert policy.allowed_hosts == ["apihub.agnes-ai.com"]
    assert policy.allowed_ports == [443]
    assert policy.public_fallback_allowed is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowedSchemes", ["http"]),
        ("allowedHosts", ["*.agnes-ai.com"]),
        ("allowedHosts", ["127.0.0.1"]),
        ("allowedHosts", ["localhost"]),
        ("allowedPorts", [80]),
        ("tlsRequired", False),
        ("publicFallbackAllowed", True),
        ("approvalRef", " "),
    ],
)
def test_network_policy_rejects_unsafe_boundary(field: str, value: object) -> None:
    body = payload()
    body[field] = value
    with pytest.raises(ValidationError):
        NetworkPolicyRevisionCreate.model_validate(body)


def test_network_policy_requires_exact_egress_ref_and_valid_window() -> None:
    body = payload()
    body["egressPolicyRef"]["assetType"] = "PolicyRevision"
    with pytest.raises(ValidationError, match="EgressPolicyRevision"):
        NetworkPolicyRevisionCreate.model_validate(body)
    body = payload()
    body["effectiveUntil"] = body["effectiveFrom"]
    with pytest.raises(ValidationError, match="effective"):
        NetworkPolicyRevisionCreate.model_validate(body)


def test_network_policy_request_rejects_authority_injection() -> None:
    for key, value in (
        ("tenant", {"orgId": "dev-org", "projectId": "dev-project"}),
        ("contentHash", "b" * 64),
        ("createdBy", "caller"),
        ("createdAt", NOW.isoformat()),
    ):
        body = payload()
        body[key] = value
        with pytest.raises(ValidationError):
            NetworkPolicyRevisionCreate.model_validate(body)
