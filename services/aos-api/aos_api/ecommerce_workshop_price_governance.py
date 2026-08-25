"""Tenant-bound GET-only W2-07 price-governance contract shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from aos_api.aip_contracts import TenantContext
from aos_api.ecommerce_workshop_price_governance_contracts import PRICE_GOVERNANCE_REMEDY_SCHEMA_VERSION, PRICE_GOVERNANCE_SCHEMA_VERSION, PriceAxisReadiness, PriceBlocker, PriceCountLedger, PriceGovernanceViewId, PriceGovernanceViewSlice, PriceObservationProjection, PricePageInfo, PriceReadinessAxis, WorkshopPriceGovernanceViewEnvelope
from aos_api.ecommerce_workshop_price_governance_reader import PriceGovernanceCanonicalReader, PriceGovernanceReadError, PriceGovernanceViewObservation, validate_price_observation
from aos_api.ecommerce_workshop_remedy_scenario import EcommerceWorkshopRemedyScenario
from aos_api.tenant_scope import TenantScope

Clock = Callable[[], datetime]


def _observation_bucket(item: PriceObservationProjection) -> str:
    if item.comparability == "comparable":
        return "eligible"
    if item.comparability == "unknown" or item.freshness == "unknown" or item.license == "unknown" or item.match_status == "unknown":
        return "unknown"
    if item.match_status == "preliminary":
        return "needs_review"
    return "excluded"


class EcommerceWorkshopPriceGovernance:
    """Expose price authority gaps without inventing quotes or capabilities."""

    def __init__(self, *, reader: PriceGovernanceCanonicalReader | None = None, remedy_scenario: EcommerceWorkshopRemedyScenario | None = None, clock: Clock | None = None) -> None:
        self._reader = reader
        self._remedy_scenario = remedy_scenario
        self._clock = clock or (lambda: datetime.now(UTC))

    def read(self, *, org_id: str, project_id: str) -> WorkshopPriceGovernanceViewEnvelope:
        cutoff = self._clock()
        if cutoff.utcoffset() is None:
            raise ValueError("price-governance clock must be timezone-aware")
        scope = TenantScope(org_id=org_id, project_id=project_id)
        candidates: list[tuple[PriceGovernanceViewId, PriceBlocker, PriceGovernanceViewObservation | None]] = []
        for view_id in PriceGovernanceViewId:
            blocker = PriceBlocker(code=f"PRICE_{view_id.value.upper()}_AUTHORITY_NOT_AVAILABLE", dependency=f"workshop.price-governance.{view_id.value}-authority", required_action="provide tenant-bound licensed exact price authority at one revision and cutoff")
            observation = None
            try:
                observation = self._reader.read_view(scope, view_id=view_id, cutoff=cutoff, limit=100) if self._reader is not None else None
                if observation is not None:
                    validate_price_observation(observation, scope=scope, cutoff=cutoff)
            except (PriceGovernanceReadError, ValueError, TypeError):
                observation = None
            candidates.append((view_id, blocker, observation))
        trusted_revisions = {item.resource_revision for _, _, item in candidates if item is not None and all(axis.status not in {"blocked", "unknown"} for axis in item.readiness_axes)}
        revision_conflict = len(trusted_revisions) > 1
        revision = next(iter(trusted_revisions)) if len(trusted_revisions) == 1 else 1
        views = []
        for view_id, blocker, observation in candidates:
            if revision_conflict:
                blocker = PriceBlocker(code="PRICE_SHARED_RESOURCE_REVISION_CONFLICT", dependency="workshop.price-governance.resource-revision", required_action="re-read all three canonical views at one exact revision and cutoff")
                observation = None
            axes = []
            trusted = observation is not None and all(axis.status not in {"blocked", "unknown"} for axis in observation.readiness_axes)
            if trusted:
                axes = list(observation.readiness_axes)
                projected = list(observation.observations)
                refs = list(observation.authority_refs)
                buckets = {name: sum(_observation_bucket(item) == name for item in projected) for name in ("eligible", "excluded", "needs_review", "unknown")}
                ledger = PriceCountLedger(input=observation.input_count, eligible=buckets["eligible"], excluded=buckets["excluded"], needsReview=buckets["needs_review"], unknown=buckets["unknown"], deduplicated=observation.deduplicated_count)
            else:
                for axis in PriceReadinessAxis:
                    axis_blocker = PriceBlocker(code="REPRICING_R4_SPECIALIZED_GATE_REQUIRED" if axis is PriceReadinessAxis.REPRICING else blocker.code, dependency=f"price.{axis.value}", required_action="keep repricing disabled until the specialized R4 gate is operational" if axis is PriceReadinessAxis.REPRICING else blocker.required_action)
                    axes.append(PriceAxisReadiness(axis=axis, status="disabled" if axis is PriceReadinessAxis.REPRICING else "blocked", blockers=[axis_blocker]))
                projected, refs = [], []
                ledger = PriceCountLedger(input=0, eligible=0, excluded=0, needsReview=0, unknown=0, deduplicated=0)
            views.append(PriceGovernanceViewSlice(view_id=view_id, status="ready" if trusted else "blocked", resource_revision=revision, data_cutoff=cutoff, readiness_axes=axes, observations=projected, authority_refs=refs, blockers=[] if trusted else [blocker], count_ledger=ledger))
        scenario = self._remedy_scenario.read(scope=scope, cutoff=cutoff) if self._remedy_scenario is not None else None
        return WorkshopPriceGovernanceViewEnvelope(schemaVersion=PRICE_GOVERNANCE_REMEDY_SCHEMA_VERSION if scenario is not None else PRICE_GOVERNANCE_SCHEMA_VERSION, tenant=TenantContext(org_id=org_id, project_id=project_id), resource_revision=revision, evaluated_at=cutoff, data_cutoff=cutoff, views=views, remedyScenario=scenario, page=PricePageInfo(count=sum(len(item.observations) for item in views)))


__all__ = ["EcommerceWorkshopPriceGovernance"]
