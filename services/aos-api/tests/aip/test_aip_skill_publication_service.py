import hashlib
import json
import uuid
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
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetPiiState,
    DatasetRevisionRef,
    DatasetSourceKind,
    EvalCaseDefinition,
    EvalCaseKind,
    EvalDatasetManifest,
    EvalSuiteRevision,
    JudgeRevisionRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_runner import (
    AipEvalRunner,
    JudgeExecution,
    ResolvedArtifact,
    TargetExecution,
)
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
)
from aos_api.aip_release_publication_service import (
    AipReleasePublicationIntegrityError,
    AipReleasePublicationService,
)
from aos_api.aip_skill_publication_service import AipSkillPublicationService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

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


class _ReadyRouteAuthority:
    def require_ready(self, scope, route_ref, policy_ref, *, evaluated_at):
        assert scope.org_id.startswith("bind3-org-")
        assert route_ref.asset_type == "ModelRouteRevision"
        assert policy_ref.asset_type == "RuntimePolicyRevision"
        assert evaluated_at.tzinfo is not None


def _canonical_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def test_real_eval_publication_creates_new_immutable_skill_revision_and_receipt() -> None:
    suffix = uuid.uuid4().hex[:12]
    scope = TenantScope(f"bind3-org-{suffix}", f"bind3-project-{suffix}")
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s)", (scope.org_id, scope.org_id))
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s)",
            (*scope.key, scope.project_id),
        )
        conn.commit()

    skill_id = f"skill.bind3.{suffix}"
    source = skill_request(skill_id=skill_id, canonical_logic_id=f"logic.bind3.{suffix}")
    source = source.model_copy(update={"content_hash": _canonical_hash(source.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    source = AipSkillRegistry().publish_skill(source, actor="pytest-bind3")
    target = AssetRevisionRef(
        asset_type=AssetType.SKILL_TEMPLATE,
        asset_id=source.skill_id,
        revision=str(source.revision),
        content_hash=source.content_hash,
    )
    dataset = DatasetRevisionRef(
        dataset_id=f"dataset-{suffix}",
        revision=1,
        content_hash="1" * 64,
        source_hash="2" * 64,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id="redaction-policy",
            revision="1",
            content_hash="3" * 64,
        ),
    )
    registry = AipEvalPackRegistry()
    registry.register_dataset_revision(
        scope,
        dataset,
        EvalDatasetManifest(
            source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
            source_id=f"skill-eval-{suffix}",
            source_revision="1",
            source_hash="2" * 64,
            fields_allowlist=["prompt"],
            redaction_receipt=ArtifactRef(
                artifact_id=f"redaction-{suffix}",
                artifact_type="receipt",
                revision="1",
                content_hash="4" * 64,
            ),
            pii_state=DatasetPiiState.REDACTED,
            case_count=1,
            captured_at=datetime(2026, 8, 15, 3, 0, tzinfo=UTC),
        ),
        actor="pytest-bind3",
    )
    input_value = {"prompt": "safe"}
    expected_value = {"decision": "pass"}
    input_ref = ArtifactRef(
        artifact_id=f"input-{suffix}", artifact_type="eval_input", revision="1",
        content_hash=_canonical_hash(input_value),
    )
    expected_ref = ArtifactRef(
        artifact_id=f"expected-{suffix}", artifact_type="eval_expected", revision="1",
        content_hash=_canonical_hash(expected_value),
    )
    suite = EvalSuiteRevision(
        suite_id=f"suite-{suffix}", revision=1, content_hash="0" * 64,
        target=target, dataset=dataset,
        judge=JudgeRevisionRef(judge_id="exact-judge", revision=1, content_hash="4" * 64),
        cases=[EvalCaseDefinition(
            case_id="positive-1", kind=EvalCaseKind.POSITIVE,
            input_artifact=input_ref, expected_artifact=expected_ref, timeout_ms=1000,
        )],
        gate_threshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    registry.register_suite_revision(scope, suite, actor="pytest-bind3")

    def resolve_artifact(reference):
        value = input_value if reference == input_ref else expected_value
        return ResolvedArtifact(reference=reference, value=value)

    report = AipEvalRunner().run(
        scope,
        suite_id=suite.suite_id,
        suite_revision=1,
        idempotency_key=f"run-{suffix}",
        actor="pytest-bind3",
        resolve_artifact=resolve_artifact,
        execute_target=lambda reference, _value: TargetExecution(
            target=reference, value=expected_value
        ),
        execute_judge=lambda reference, actual, expected: JudgeExecution(
            judge=reference,
            passed=actual == expected,
            detail_code="exact_match",
        ),
    )
    release = AipReleasePublicationService()
    gate = release.derive_gate(
        scope,
        actor="pytest-bind3",
        request=DeriveReleaseGateRequest(
            report_id=report.report_id,
            report_revision=report.revision,
            report_hash=report.content_hash,
            idempotency_key=f"gate-{suffix}",
        ),
    )
    publication = release.publish(
        scope,
        actor="pytest-bind3",
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash="5" * 64,
            idempotency_key=f"publication-{suffix}",
        ),
    )
    request = PublishEvaluatedSkillRevisionRequest(
        source_skill=ref("SkillTemplate", source.skill_id).model_copy(
            update={"content_hash": source.content_hash}
        ),
        publication_id=publication.publication_id,
        release_gate_decision_id=gate.decision_id,
        model_route_ref=ref("ModelRouteRevision", f"route-{suffix}"),
        runtime_policy_ref=ref("RuntimePolicyRevision", f"policy-{suffix}"),
        idempotency_key=f"publish-skill-{suffix}",
    )
    service = AipSkillPublicationService(route_authority=_ReadyRouteAuthority())
    published, receipt = service.publish_evaluated_revision(
        scope,
        request,
        actor="pytest-bind3",
        occurred_at=datetime(2026, 8, 15, 3, 30, tzinfo=UTC),
    )
    replay, replay_receipt = service.publish_evaluated_revision(
        scope,
        request,
        actor="pytest-bind3",
        occurred_at=datetime(2026, 8, 15, 3, 31, tzinfo=UTC),
    )
    assert source.lifecycle is TemplateLifecycle.EVALUATED and source.revision == 1
    assert published.lifecycle is TemplateLifecycle.PUBLISHED and published.revision == 2
    assert published.parent_ref == request.source_skill
    assert published.release_gate_ref.asset_id == gate.decision_id
    assert published.publication_tenant == TenantContext(
        org_id=scope.org_id, project_id=scope.project_id
    )
    assert receipt.operation == "skill_template.publish_evaluated"
    assert replay == published and replay_receipt == receipt
