from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from aos_api.aip_contracts import TenantContext
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    ContractReadiness,
    ExactRevisionRef,
    ProductionContextRevision,
)
from aos_api.ecommerce_workshop_freeze_contracts import WorkshopFreezeRequest
from aos_api.ecommerce_workshop_freeze_service import (
    EcommerceWorkshopFreezeService,
    WorkshopFreezeBlocked,
)
from aos_api.ecommerce_workshop_prepare_store import PreparationRecord
from aos_api.tenant_scope import TenantScope
from test_ecommerce_workshop_evidence_build import PROFILE_REF, _prepared, _profile


NOW = datetime(2026, 8, 24, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
BUNDLE_REF = ExactRevisionRef(
    resource_type="EvidenceBundleRevision",
    resource_id="bundle-1",
    revision=1,
    content_hash="2" * 64,
)
EVAL_REF = ExactRevisionRef(
    resource_type="EvalContractRevision",
    resource_id="eval-1",
    revision=2,
    content_hash="3" * 64,
)
RESPONSIBILITY_REF = ExactRevisionRef(
    resource_type="ResponsibilityPlanRevision",
    resource_id="responsibility-1",
    revision=2,
    content_hash="4" * 64,
)
FROZEN_BRIEF_REF = ExactRevisionRef(
    resource_type="TaskBriefRevision",
    resource_id="brief-1",
    revision=2,
    content_hash="c" * 64,
)


class PreparationReader:
    def __init__(self, body: dict[str, Any] | None = None) -> None:
        self.body = body or _prepared()

    def get(self, scope: TenantScope, preparation_id: str) -> PreparationRecord:
        return PreparationRecord(
            preparation_id=preparation_id,
            module_id="ecommerce.content-campaign",
            request_hash="f" * 64,
            status="complete",
            result_body=self.body,
        )


class ProductionAuthority:
    def __init__(self) -> None:
        self.freeze_calls = 0
        self.freeze_body = None
        self.context: ProductionContextRevision | None = None

    def get_evidence_bundle(self, scope: TenantScope, bundle_id: str, revision: int = 1):
        return SimpleNamespace(content_hash=BUNDLE_REF.content_hash, brief_ref=FROZEN_BRIEF_REF)

    def get_brief(self, scope: TenantScope, brief_id: str, revision: int | None = None):
        return SimpleNamespace(content_hash=FROZEN_BRIEF_REF.content_hash, task_id="task-1")

    def get_eval_contract(self, scope: TenantScope, contract_id: str, revision: int | None = None):
        return SimpleNamespace(content_hash=EVAL_REF.content_hash)

    def get_responsibility_plan(
        self, scope: TenantScope, plan_id: str, revision: int | None = None
    ):
        return SimpleNamespace(content_hash=RESPONSIBILITY_REF.content_hash)

    def freeze_production_context(self, scope, actor, key, body):
        self.freeze_calls += 1
        self.freeze_body = body
        if self.context is None:
            self.context = ProductionContextRevision(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                context_id="ctx-1",
                revision=1,
                task_id=body.task_id,
                brief_ref=body.brief_ref,
                evidence_bundle_ref=body.evidence_bundle_ref,
                eval_contract_ref=body.eval_contract_ref,
                responsibility_plan_ref=body.responsibility_plan_ref,
                production_profile_ref=body.production_profile_ref,
                preparation_ref=body.preparation_ref,
                profile=body.profile,
                dependency_snapshot=[],
                dependency_snapshot_hash="5" * 64,
                content_hash="6" * 64,
                lifecycle=BriefLifecycle.FROZEN,
                readiness=ContractReadiness.READY,
                blockers=[],
                created_by=actor,
                created_at=NOW,
            )
        return self.context


def _request() -> WorkshopFreezeRequest:
    return WorkshopFreezeRequest(
        preparation_id="preparation-1",
        production_profile_ref=PROFILE_REF,
        evidence_bundle_ref=BUNDLE_REF,
        eval_contract_ref=EVAL_REF,
        responsibility_plan_ref=RESPONSIBILITY_REF,
    )


def _service(
    production: ProductionAuthority,
    preparation: PreparationReader | None = None,
) -> EcommerceWorkshopFreezeService:
    return EcommerceWorkshopFreezeService(
        preparation_store=preparation or PreparationReader(),  # type: ignore[arg-type]
        production_authority=production,
        profile_reader=lambda scope, ref: _profile(),
    )


def test_freeze_uses_server_owned_preparation_profile_and_four_exact_refs() -> None:
    production = ProductionAuthority()
    result = _service(production).freeze(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="freeze-1",
        body=_request(),
    )
    assert production.freeze_body.production_profile_ref == PROFILE_REF
    assert production.freeze_body.preparation_ref.content_hash == "1" * 64
    assert production.freeze_body.brief_ref == FROZEN_BRIEF_REF
    assert result.receipt.production_context_ref.content_hash == "6" * 64
    assert result.receipt.next_allowed_commands == ["compile"]
    assert set(result.receipt.side_effects.model_dump().values()) == {0}


def test_freeze_replay_delegates_idempotency_to_canonical_authority() -> None:
    production = ProductionAuthority()
    service = _service(production)
    results = [
        service.freeze(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="same-key",
            body=_request(),
        )
        for _ in range(2)
    ]
    assert results[0].receipt.production_context_ref == results[1].receipt.production_context_ref
    assert production.freeze_calls == 2


def test_freeze_fails_closed_on_tenant_profile_or_brief_lineage_drift() -> None:
    tenant_body = _prepared()
    tenant_body["tenant"] = {"orgId": "dev-org", "projectId": "dev-project"}
    with pytest.raises(WorkshopFreezeBlocked, match="tenant scope"):
        _service(ProductionAuthority(), PreparationReader(tenant_body)).freeze(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="tenant-drift",
            body=_request(),
        )

    missing_profile = EcommerceWorkshopFreezeService(
        preparation_store=PreparationReader(),  # type: ignore[arg-type]
        production_authority=ProductionAuthority(),
        profile_reader=lambda scope, ref: None,
    )
    with pytest.raises(WorkshopFreezeBlocked, match="installed production profile"):
        missing_profile.freeze(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="profile-drift",
            body=_request(),
        )

    production = ProductionAuthority()
    production.get_evidence_bundle = lambda scope, bundle_id, revision=1: SimpleNamespace(
        content_hash=BUNDLE_REF.content_hash,
        brief_ref=FROZEN_BRIEF_REF.model_copy(update={"content_hash": "7" * 64}),
    )
    with pytest.raises(WorkshopFreezeBlocked, match="Brief lineage"):
        _service(production).freeze(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="brief-drift",
            body=_request(),
        )
