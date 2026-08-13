from datetime import UTC, datetime

import pytest

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import ModelRouteResolution, ModelRuntimeReadiness
from aos_api.aip_provider_usage_bridge import (
    AipProviderUsageBridge,
    AipProviderUsageEnvelopeError,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 14, tzinfo=UTC)
HASH = "a" * 64


def ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=asset_id, revision=1, contentHash=HASH)


def resolution() -> ModelRouteResolution:
    return ModelRouteResolution(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        route=ref("ModelRouteRevision", "route-1"),
        policy=ref("RuntimePolicyRevision", "policy-1"),
        readiness=ModelRuntimeReadiness.READY,
        selectedModel=ref("RegisteredModelRevision", "model-1"),
        selectedProvider=ref("ProviderInstanceRevision", "provider-1"),
        selectedPriceSnapshot=ref("ModelPriceSnapshotRevision", "price-1"),
        blockerCodes=[],
        resolvedAt=NOW,
    )


class Receipt:
    def __init__(self, receipt_id):
        self.receipt_id = receipt_id


class UsageService:
    def __init__(self):
        self.calls = []

    def ingest_usage(self, scope, request):
        self.calls.append((scope, request))
        return Receipt(f"usage-{len(self.calls)}")


def envelope():
    return {
        "providerReceiptId": "provider-call-1",
        "usageReceipts": [
            {
                "usageKind": "input_token",
                "quantity": 10,
                "unit": "token",
                "quality": "measured",
                "sourceHash": "1" * 64,
                "observedAt": NOW,
            },
            {
                "usageKind": "cost",
                "quantity": None,
                "unit": "currency",
                "currency": "CNY",
                "quality": "unknown",
                "sourceHash": "2" * 64,
                "observedAt": NOW,
            },
        ],
    }


def test_provider_usage_is_forwarded_to_existing_aip4_authority() -> None:
    service = UsageService()
    ids = AipProviderUsageBridge(service).record(
        SCOPE, "lineage-1", resolution(), envelope()
    )
    assert ids == ["usage-1", "usage-2"]
    assert all(call[0] == SCOPE for call in service.calls)
    assert service.calls[0][1].provider == "provider-1"
    assert service.calls[0][1].lineage_id == "lineage-1"
    assert service.calls[1][1].quantity is None


@pytest.mark.parametrize(
    "response,message",
    [
        ({"usageReceipts": [{}]}, "provider_receipt_id_required"),
        ({"providerReceiptId": "call-1", "usageReceipts": []}, "usage_receipts_required"),
    ],
)
def test_missing_provider_usage_authority_fails_closed(response, message) -> None:
    with pytest.raises(AipProviderUsageEnvelopeError, match=message):
        AipProviderUsageBridge(UsageService()).record(
            SCOPE, "lineage-1", resolution(), response
        )
