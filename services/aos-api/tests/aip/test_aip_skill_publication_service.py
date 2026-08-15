from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import (
    PublishEvaluatedSkillRevisionRequest,
    PublishSkillTemplateRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_release_publication_service import (
    AipReleasePublicationIntegrityError,
    AipReleasePublicationService,
)
from aos_api.aip_skill_publication_service import AipSkillPublicationService
from aos_api.aip_skill_registry import AipSkillRegistry

HASH = "a" * 64


def ref(kind: str, asset_id: str = "asset") -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind, asset_id=asset_id, revision=1, content_hash=HASH
    )


def skill_request(**updates) -> PublishSkillTemplateRequest:
    payload = dict(
        skill_id="skill.demo",
        revision=1,
        canonical_logic_id="logic.demo",
        lifecycle=TemplateLifecycle.EVALUATED,
        input_schema={},
        output_schema={},
        tool_allowlist=[],
        required_capabilities=[],
        risk_level="low",
        memory_policy_ref=ref("MemoryPolicyRevision", "memory"),
        handoff_policy_ref=ref("HandoffPolicyRevision", "handoff"),
        source_ref=ResourceRef(
            resource_type="SolutionPack",
            resource_id="solution.demo",
            revision="1",
            authority="postgresql",
        ),
        source_license="Apache-2.0",
        content_hash=HASH,
    )
    payload.update(updates)
    return PublishSkillTemplateRequest(**payload)


def test_direct_registry_publication_is_fail_closed_before_persistence() -> None:
    published = skill_request(
        lifecycle=TemplateLifecycle.PUBLISHED,
        parent_ref=ref("SkillTemplate", "skill.demo"),
        publication_tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        release_gate_ref=ref("EvalGateDecision", "gate-1"),
        publication_ref=ResourceRef(
            resource_type="PublicationEvent",
            resource_id="event-1",
            revision="publication-1",
            authority="postgresql",
        ),
        model_route_ref=ref("ModelRouteRevision", "route-1"),
        runtime_policy_ref=ref("RuntimePolicyRevision", "policy-1"),
    )
    with pytest.raises(
        AipAgentRegistryTransitionBlocked, match="governed Eval publication"
    ):
        AipSkillRegistry(connect_factory=lambda *_: None).publish_skill(
            published, actor="pytest"
        )


def test_published_contract_requires_all_exact_provenance() -> None:
    with pytest.raises(ValidationError, match="exact publication provenance"):
        skill_request(lifecycle=TemplateLifecycle.PUBLISHED)
    with pytest.raises(ValidationError, match="non-published skill"):
        skill_request(parent_ref=ref("SkillTemplate", "skill.demo"))


def test_governed_publication_request_rejects_wrong_ref_kinds() -> None:
    with pytest.raises(ValidationError, match="source_skill must reference SkillTemplate"):
        PublishEvaluatedSkillRevisionRequest(
            source_skill=ref("AgentTemplate", "skill.demo"),
            publication_id="publication-1",
            release_gate_decision_id="gate-1",
            model_route_ref=ref("ModelRouteRevision", "route-1"),
            runtime_policy_ref=ref("RuntimePolicyRevision", "policy-1"),
            idempotency_key="publish-once",
        )


class _SkillTargetConnection:
    def __init__(self, *, lifecycle: str = "evaluated", content_hash: str = HASH):
        self.lifecycle = lifecycle
        self.content_hash = content_hash

    def execute(self, _sql, _params):
        return self

    def fetchone(self):
        return {"lifecycle": self.lifecycle, "content_hash": self.content_hash}


def test_release_authority_accepts_only_exact_evaluated_skill_target() -> None:
    target = AssetRevisionRef(
        asset_type=AssetType.SKILL_TEMPLATE,
        asset_id="skill.demo",
        revision="1",
        content_hash=HASH,
    )
    AipReleasePublicationService._verify_publishable_target(
        _SkillTargetConnection(), None, target
    )
    with pytest.raises(AipReleasePublicationIntegrityError):
        AipReleasePublicationService._verify_publishable_target(
            _SkillTargetConnection(lifecycle="published"), None, target
        )


def test_governed_receipt_result_identity_is_stable_and_strict() -> None:
    assert AipSkillPublicationService._result_id("skill.demo", 2) == "skill.demo@r2"
    assert AipSkillPublicationService._parse_result_id("skill.demo@r2") == (
        "skill.demo",
        2,
    )
    with pytest.raises(Exception, match="receipt result is invalid"):
        AipSkillPublicationService._parse_result_id("skill.demo")
