from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_price_disposition import (
    PriceDispositionBlocked,
    PriceDispositionContractRevision,
    PriceDispositionKind,
    REQUIRED_GATE_TYPES,
)
from aos_api.ecommerce_workshop_price_disposition_store import EcommerceWorkshopPriceDispositionStore
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str) -> PriceExactRef:
    return PriceExactRef(resourceType=kind, resourceId=identity, revision=1, contentHash=f"sha256:{'a' * 64}", receiptId=f"receipt-{identity}")


def contract() -> PriceDispositionContractRevision:
    return PriceDispositionContractRevision(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id), contractId="contract-1", revision=1,
        kind=PriceDispositionKind.INTERNAL_ADVICE, payloadSchemaRef=ref("SchemaRevision", "schema"),
        riskPolicyRef=ref("RiskPolicyRevision", "risk"), requiredGateTypes=REQUIRED_GATE_TYPES[PriceDispositionKind.INTERNAL_ADVICE],
        externalEffectCapable=False, contentHash="b" * 64, createdBy="operator", createdAt=NOW,
    )


def test_production_store_never_trusts_caller_shaped_gate_refs():
    store = EcommerceWorkshopPriceDispositionStore(connect_factory=lambda _scope: None)
    gates = {name: ref(kind, name) for name, kind in REQUIRED_GATE_TYPES[PriceDispositionKind.INTERNAL_ADVICE].items()}
    with pytest.raises(PriceDispositionBlocked, match="GATE_AUTHORITY_RESOLVER_UNAVAILABLE"):
        store.require_gate_authorities(SCOPE, contract(), gates)


def test_store_rejects_cross_tenant_authority_before_persistence():
    item = contract().model_copy(update={"tenant": TenantContext(orgId="dev-org", projectId="dev-project")})
    with pytest.raises(PriceDispositionBlocked, match="TENANT_DRIFT"):
        EcommerceWorkshopPriceDispositionStore._assert_tenant(SCOPE, item)
