from datetime import UTC, datetime

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_price_disposition import (
    CreatePriceCaseRequest,
    CreatePriceDispositionContractRequest,
    EcommerceWorkshopPriceDispositionService,
    FreezePriceDispositionRequest,
    PreparePriceDispositionRequest,
    PriceDispositionBlocked,
    PriceDispositionKind,
    PriceDispositionOutcome,
    RecordPriceDispositionObservationRequest,
    REQUIRED_GATE_TYPES,
)
from aos_api.ecommerce_workshop_price_governance_contracts import PriceExactRef
from aos_api.ecommerce_workshop_price_research import (
    MonitoringPolicyRevision,
    PreparePriceResearchBatchItem,
    PriceBatchDisposition,
    PriceMatchConfidence,
    PriceResearchBatchLedger,
    PriceResearchBatchRevision,
)
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 25, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def ref(kind: str, identity: str, digest: str = "a", revision: int = 1) -> PriceExactRef:
    return PriceExactRef(resourceType=kind, resourceId=identity, revision=revision, contentHash=f"sha256:{digest * 64}", receiptId=f"receipt-{identity}")


class MemoryStore:
    def __init__(self):
        self.cases = {}; self.contracts = {}; self.dispositions = {}; self.observations = []; self.receipts = {}

    def append_case(self, _scope, item): self.cases[item.case_id] = item; return item
    def append_contract(self, _scope, item): self.contracts[item.contract_id] = item; return item
    def append_disposition(self, _scope, item): self.dispositions.setdefault(item.disposition_id, []).append(item); return item
    def append_observation(self, _scope, item): self.observations.append(item); return item
    def require_case(self, _scope, exact): return self.cases[exact.resource_id]
    def require_contract(self, _scope, exact): return self.contracts[exact.resource_id]
    def require_disposition(self, _scope, exact): return self.dispositions[exact.resource_id][-1]
    def latest_disposition(self, _scope, identity): return self.dispositions[identity][-1]
    def latest_disposition_or_none(self, _scope, identity): return self.dispositions.get(identity, [None])[-1]
    def require_gate_authorities(self, _scope, contract, gates):
        assert set(gates) == set(contract.required_gate_types)
    def require_outcome_receipt(self, scope, exact, binding_hash):
        if self.receipts.get((*scope.key, exact.resource_id)) != (exact.content_hash, binding_hash):
            raise PriceDispositionBlocked("PRICE_DISPOSITION_RECEIPT_MISSING_OR_BINDING_DRIFTED")
    def list_cases(self, _scope): return list(self.cases.values())
    def list_dispositions(self, _scope): return [items[-1] for items in self.dispositions.values()]
    def list_observations(self, _scope): return self.observations


class ResearchStore:
    def __init__(self, batch, policy): self.batch = batch; self.policy = policy
    def latest_batch(self, _scope, identity): assert identity == self.batch.batch_id; return self.batch
    def require_policy(self, _scope, exact): assert exact.resource_id == self.policy.policy_id; return self.policy


def authority_fixture():
    sku = ref("ProductSkuRevision", "sku-1", "b")
    eval_ref = ref("EvalContractRevision", "eval-1", "c")
    policy = MonitoringPolicyRevision(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id), policyId="policy-1", revision=1,
        scopeRefs=[sku], basis="landed", currency="CNY", unit="piece", toleranceRatio=.1, freshnessSeconds=3600,
        minimumOriginals=1, minimumMatchConfidence=PriceMatchConfidence.CONFIRMED, evalRef=eval_ref,
        contentHash="d" * 64, createdBy="operator", createdAt=NOW,
    )
    policy_ref = ref("MonitoringPolicyRevision", policy.policy_id, "d")
    item = PreparePriceResearchBatchItem(
        skuRef=sku, observationRef=ref("PriceObservationRevision", "observation-1"),
        matchObservationRef=ref("ProductMatchObservation", "match-1"), matchDecisionRef=ref("ProductMatchDecisionRevision", "decision-1"),
        disposition=PriceBatchDisposition.ELIGIBLE, licenseEligible=True, freshnessEligible=True, rateEligible=True, capacityEligible=True, budgetEligible=True,
    )
    batch = PriceResearchBatchRevision(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id), batchId="batch-1", revision=2, version=2,
        lifecycle="frozen", exactRefs={"monitoringPolicy": policy_ref, "eval": eval_ref}, skillRefs=[], items=[item],
        itemHashes=["e" * 64], ledger=PriceResearchBatchLedger(input=1, eligible=1, excluded=0, needsReview=0, unknown=0, deduplicated=0),
        priorContentHash="f" * 64, contentHash="1" * 64, createdBy="operator", createdAt=NOW,
    )
    store = MemoryStore(); service = EcommerceWorkshopPriceDispositionService(store, ResearchStore(batch, policy))
    case = service.create_case(SCOPE, CreatePriceCaseRequest(
        caseId="case-1", batchRef=ref("PriceResearchBatchRevision", "batch-1", "1", revision=2), policyRef=policy_ref,
        evidenceBundleRef=ref("EvidenceBundleRevision", "evidence"), evalRef=eval_ref, impactPreviewRef=ref("ImpactPreviewRevision", "impact"),
        targetRefs=[sku], calculationInputHash="2" * 64, anomalyCode="PRICE_DROP", severity="high",
        keyAssumptions=["same quote basis"], uncertainties=["future promotion"], detectedAt=NOW,
    ), "operator", now=NOW)
    return store, service, case, sku


def exact(item, kind: str, identity: str) -> PriceExactRef:
    return ref(kind, getattr(item, identity), item.content_hash[0], revision=item.revision)


def create_contract(service, kind: PriceDispositionKind):
    return service.create_contract(SCOPE, CreatePriceDispositionContractRequest(
        contractId=f"contract-{kind.value}", revision=1, kind=kind,
        payloadSchemaRef=ref("SchemaRevision", f"schema-{kind.value}"), riskPolicyRef=ref("RiskPolicyRevision", f"risk-{kind.value}"),
    ), "operator", now=NOW)


def prepare(service, case, sku, contract, identity="disposition-1"):
    gates = {name: ref(kind, f"{name}-1") for name, kind in REQUIRED_GATE_TYPES[contract.kind].items()}
    return service.prepare(SCOPE, PreparePriceDispositionRequest(
        dispositionId=identity, caseRef=exact(case, "PriceCaseRevision", "case_id"),
        contractRef=exact(contract, "PriceDispositionContractRevision", "contract_id"), targetRefs=[sku], gateRefs=gates,
        purpose="compile a governed contribution", requestedOutcome="review before any effect",
    ), "operator", now=NOW)


@pytest.mark.parametrize("kind", list(PriceDispositionKind))
def test_four_disposition_contracts_are_typed_and_never_execute(kind):
    _store, service, case, sku = authority_fixture()
    contract = create_contract(service, kind)
    disposition = prepare(service, case, sku, contract, identity=f"disposition-{kind.value}")
    assert contract.required_gate_types == REQUIRED_GATE_TYPES[kind]
    assert disposition.kind is kind and disposition.execution_allowed is False
    assert disposition.provider_call_count == disposition.notification_send_count == disposition.repricing_count == disposition.external_effect_count == 0
    if kind is PriceDispositionKind.REPRICING:
        assert disposition.operational_blockers == ["PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED"]


def test_freeze_uses_exact_refs_and_preserves_zero_effects():
    _store, service, case, sku = authority_fixture()
    prepared = prepare(service, case, sku, create_contract(service, PriceDispositionKind.INTERNAL_ADVICE))
    frozen = service.freeze(SCOPE, prepared.disposition_id, FreezePriceDispositionRequest(
        expectedVersion=prepared.version, expectedContentHash=prepared.content_hash,
        exactRefs={"case": prepared.case_ref, "contract": prepared.contract_ref, **prepared.gate_refs},
    ), "reviewer", now=NOW)
    assert frozen.lifecycle == "frozen" and frozen.version == 2 and frozen.prior_content_hash == prepared.content_hash
    assert frozen.external_effect_count == 0


def test_contract_gate_and_observation_outcome_cannot_cross_kinds():
    store, service, case, sku = authority_fixture()
    prepared = prepare(service, case, sku, create_contract(service, PriceDispositionKind.INTERNAL_ADVICE))
    frozen = service.freeze(SCOPE, prepared.disposition_id, FreezePriceDispositionRequest(
        expectedVersion=1, expectedContentHash=prepared.content_hash,
        exactRefs={"case": prepared.case_ref, "contract": prepared.contract_ref, **prepared.gate_refs},
    ), "reviewer", now=NOW)
    receipt = ref("AdoptionReceipt", "adoption-1", "9")
    store.receipts[(*SCOPE.key, receipt.resource_id)] = (receipt.content_hash, frozen.binding_hash)
    with pytest.raises(PriceDispositionBlocked, match="OUTCOME_KIND_DRIFTED"):
        service.record_observation(SCOPE, RecordPriceDispositionObservationRequest(
            dispositionRef=exact(frozen, "PriceDispositionRevision", "disposition_id"), receiptRef=receipt,
            outcome=PriceDispositionOutcome.APPLIED, observedAt=NOW,
        ))
    with pytest.raises(ValueError, match="cannot self-resolve"):
        RecordPriceDispositionObservationRequest(
            dispositionRef=exact(frozen, "PriceDispositionRevision", "disposition_id"), receiptRef=receipt,
            outcome=PriceDispositionOutcome.UNKNOWN, resolvedOutcome=PriceDispositionOutcome.ADOPTED,
            manualCaseRef=ref("ManualReconcileCase", "manual-1"), observedAt=NOW,
        )


def test_contribution_view_exposes_skill_logic_colleague_and_operational_blockers():
    _store, service, case, sku = authority_fixture()
    prepare(service, case, sku, create_contract(service, PriceDispositionKind.REPRICING))
    view = service.contribution_view(SCOPE, now=NOW)
    assert view.logic_id == "ecommerce-price-governance" and view.primary_colleague == "数据参谋"
    assert view.collaborator_colleagues == ["活动策划师", "导购顾问"]
    assert len(view.atomic_skill_ids) == 5 and view.repricing_enabled is view.external_effects_allowed is False
    assert "PRICE_REPRICE_OPERATIONAL_AUTHORITY_NOT_GRANTED" in view.blockers
