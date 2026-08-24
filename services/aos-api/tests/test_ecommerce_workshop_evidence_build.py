from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import (
    BriefLifecycle,
    Coverage,
    EvidenceBundleRevision,
    ExactRevisionRef,
    Freshness,
    TaskBriefRevision,
)
from aos_api.aip_production_profile_contracts import ProductionProfile
from aos_api.ecommerce_workshop_evidence_build_service import (
    EcommerceWorkshopEvidenceBuildService,
    WorkshopEvidenceBuildBlocked,
    WorkshopEvidenceBuildRequest,
)
from aos_api.ecommerce_workshop_prepare_store import PreparationRecord
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 24, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")
PROFILE_REF = ExactRevisionRef(
    resource_type="ProductionProfileRevision",
    resource_id=(
        "bundle://aos/solution.ecommerce.growth@1.4.0/"
        "content/production-profiles/ecommerce.content-campaign.json"
    ),
    revision=7,
    content_hash="a" * 64,
)
EVIDENCE_REF = ExactRevisionRef(
    resource_type="Evidence",
    resource_id="evidence-1",
    revision=1,
    content_hash="b" * 64,
)


def _profile() -> ProductionProfile:
    return ProductionProfile.model_validate(
        {
            "schema": "aos.ecommerce-production-profile/v1",
            "moduleId": "ecommerce.content-campaign",
            "profileRevision": 1,
            "brief": {
                "mode": "owned",
                "briefType": "campaign-content",
                "requiredFields": ["objective"],
                "sourceResponsibilityPreserved": True,
            },
            "evidenceSelection": {
                "requiredFacts": ["audienceEvidence", "brandPolicy"],
                "requireProvenance": True,
                "requireFreshness": True,
                "requireNegativeEvidence": True,
            },
            "eval": {
                "gates": ["fact", "brand"],
                "failClosed": True,
                "sameRevisionRequired": True,
            },
            "responsibility": {
                "slots": [
                    {
                        "slotId": "content.review",
                        "responsibilityType": "independent_review",
                        "atomicSkillIds": ["content.review"],
                        "protected": True,
                        "mergeAllowed": False,
                        "returnStage": "prepare",
                    }
                ],
                "handoffRequired": True,
                "reassignmentRequiresCanonicalDecision": True,
            },
            "contributionProjection": {
                "showAtomicSkillAttribution": True,
                "showLogicRevision": True,
                "showCoworkerBinding": True,
                "showBlockers": True,
            },
        }
    )


def _prepared(*, evidence_refs: list[ExactRevisionRef] | None = None) -> dict[str, Any]:
    brief_ref = {
        "resourceType": "TaskBriefRevision",
        "resourceId": "brief-1",
        "revision": 1,
        "contentHash": "c" * 64,
    }
    return {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "moduleId": "ecommerce.content-campaign",
        "draftBriefRef": brief_ref,
        "briefDiff": [],
        "evidenceBuildRequest": {
            "requestId": "request-1",
            "revision": 1,
            "briefRef": brief_ref,
            "productionProfileRef": PROFILE_REF.model_dump(mode="json", by_alias=True),
            "requiredFactIds": ["audienceEvidence", "brandPolicy"],
            "subjectRefs": [],
            "canonicalEvidenceRefs": [
                item.model_dump(mode="json", by_alias=True)
                for item in (evidence_refs if evidence_refs is not None else [EVIDENCE_REF])
            ],
            "cutoffAt": NOW.isoformat(),
            "purpose": "campaign preparation",
            "marking": ["public"],
            "readiness": "blocked",
            "missingFactIds": ["audienceEvidence", "brandPolicy"],
            "blockers": [],
            "contentHash": "d" * 64,
        },
        "responsibilityRecommendation": {
            "recommendationId": "recommendation-1",
            "revision": 1,
            "briefRef": brief_ref,
            "productionProfileRef": PROFILE_REF.model_dump(mode="json", by_alias=True),
            "slots": [],
            "coverage": "blocked",
            "uncoveredSlotIds": [],
            "blockers": [],
            "contentHash": "e" * 64,
        },
        "receipt": {
            "preparationId": "preparation-1",
            "revision": 1,
            "requestHash": "f" * 64,
            "resultHash": "1" * 64,
            "replay": False,
            "inputCounts": {},
            "outputCounts": {},
            "sideEffects": {},
            "nextAllowedCommands": [],
            "createdAt": NOW.isoformat(),
        },
    }


class PreparationReader:
    def __init__(self, body: dict[str, Any]) -> None:
        self.body = body

    def get(self, scope: TenantScope, preparation_id: str) -> PreparationRecord:
        assert scope == SCOPE and preparation_id == "preparation-1"
        return PreparationRecord(
            preparation_id=preparation_id,
            module_id="ecommerce.content-campaign",
            request_hash="f" * 64,
            status="complete",
            result_body=self.body,
        )


class ProductionAuthority:
    def __init__(self) -> None:
        self.freeze_count = 0
        self.build_count = 0
        self.current = self._brief(1, 1, BriefLifecycle.DRAFT)

    @staticmethod
    def _brief(revision: int, version: int, lifecycle: BriefLifecycle) -> TaskBriefRevision:
        return TaskBriefRevision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            brief_id="brief-1",
            task_id="task-1",
            revision=revision,
            version=version,
            brief_type="campaign-content",
            schema_ref=ResourceRef(
                resource_type="Schema",
                resource_id="campaign",
                revision="1",
                authority="aip",
            ),
            spec={"objective": "launch"},
            content_hash="c" * 64,
            lifecycle=lifecycle,
            created_by="user:test",
            created_at=NOW,
        )

    def get_brief(self, scope: TenantScope, brief_id: str, revision: int | None = None):
        assert scope == SCOPE and brief_id == "brief-1" and revision is None
        return self.current

    def freeze_brief(self, scope: TenantScope, actor: str, brief_id: str, expected_version: int, key: str):
        assert expected_version == self.current.version
        self.freeze_count += 1
        self.current = self._brief(2, 2, BriefLifecycle.FROZEN)
        return self.current

    def build_evidence_bundle(self, scope: TenantScope, actor: str, key: str, body):
        assert body.required_fact_ids == ["audienceEvidence", "brandPolicy"]
        assert body.item_refs == [EVIDENCE_REF]
        assert body.brief_ref.revision == 2
        self.build_count += 1
        return EvidenceBundleRevision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            bundle_id="bundle-1",
            revision=1,
            brief_ref=body.brief_ref,
            subject_refs=[],
            cutoff_at=NOW,
            item_refs=[EVIDENCE_REF],
            coverage=Coverage.COMPLETE,
            missing=[],
            conflicts=[],
            uncertainties=[],
            freshness=Freshness.FRESH,
            marking=["public"],
            license_summary=body.license_summary,
            content_hash="2" * 64,
            lifecycle=BriefLifecycle.FROZEN,
            created_by=actor,
            created_at=NOW,
        )


def _request() -> WorkshopEvidenceBuildRequest:
    return WorkshopEvidenceBuildRequest(
        preparation_id="preparation-1",
        production_profile_ref=PROFILE_REF,
    )


def test_build_uses_canonical_preparation_and_profile_then_freezes_and_builds() -> None:
    production = ProductionAuthority()
    service = EcommerceWorkshopEvidenceBuildService(
        preparation_store=PreparationReader(_prepared()),  # type: ignore[arg-type]
        production_authority=production,
        profile_reader=lambda scope, ref: _profile(),
    )
    result = service.build(
        SCOPE,
        actor="user:test",
        module_id="ecommerce.content-campaign",
        idempotency_key="build-1",
        body=_request(),
    )
    assert result.bundle.coverage is Coverage.COMPLETE
    assert result.receipt.frozen_brief_ref.revision == 2
    assert set(result.receipt.side_effects.model_dump().values()) == {0}
    assert production.freeze_count == 1 and production.build_count == 1


def test_build_replay_reuses_frozen_brief_without_refreezing() -> None:
    production = ProductionAuthority()
    service = EcommerceWorkshopEvidenceBuildService(
        preparation_store=PreparationReader(_prepared()),  # type: ignore[arg-type]
        production_authority=production,
        profile_reader=lambda scope, ref: _profile(),
    )
    for _ in range(2):
        service.build(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="same-key",
            body=_request(),
        )
    assert production.freeze_count == 1 and production.build_count == 2


def test_build_fails_closed_without_canonical_evidence_or_installed_profile() -> None:
    production = ProductionAuthority()
    service = EcommerceWorkshopEvidenceBuildService(
        preparation_store=PreparationReader(_prepared(evidence_refs=[])),  # type: ignore[arg-type]
        production_authority=production,
        profile_reader=lambda scope, ref: _profile(),
    )
    with pytest.raises(WorkshopEvidenceBuildBlocked, match="canonical Evidence"):
        service.build(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="blocked",
            body=_request(),
        )
    missing_profile = EcommerceWorkshopEvidenceBuildService(
        preparation_store=PreparationReader(_prepared()),  # type: ignore[arg-type]
        production_authority=production,
        profile_reader=lambda scope, ref: None,
    )
    with pytest.raises(WorkshopEvidenceBuildBlocked, match="installed production profile"):
        missing_profile.build(
            SCOPE,
            actor="user:test",
            module_id="ecommerce.content-campaign",
            idempotency_key="blocked-profile",
            body=_request(),
        )
