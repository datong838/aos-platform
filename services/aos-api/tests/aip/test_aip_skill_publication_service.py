import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
import psycopg
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.aip_agent_registry_contracts import (
    PublishEvaluatedSkillRevisionRequest,
    PublishSkillTemplateRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked,
)
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetPiiState,
    DatasetRevisionRef,
    DatasetSourceKind,
    EvalCaseDefinition,
    EvalCaseResultEvidence,
    EvalCaseKind,
    EvalDatasetManifest,
    EvalReportRevision,
    EvalSuiteRevision,
    JudgeRevisionRef,
    PublicationEvent,
    PublicationEventType,
    ReleaseGateDecision,
    ReleaseGateStatus,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_execution_authority import (
    EvalIssuerRoot, canonical_certificate_bytes, canonical_receipt_bytes,
    certificate_hash, receipt_identity,
)
from aos_api.aip_eval_contracts import EvalExecutionReceipt, EvalExecutorCertificate
from aos_api.aip_eval_runner import (
    AipEvalRunner,
    compute_eval_report_hash,
)
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
)
from aos_api.aip_release_publication_service import (
    AipReleasePublicationIntegrityError,
    AipReleaseGateRejected,
    AipReleasePublicationService,
    _canonical_hash as release_hash,
)
from aos_api.aip_skill_publication_service import AipSkillPublicationService
from aos_api.aip_skill_publication_service import (
    PostgresSkillPublicationRouteAuthority,
)
from aos_api.aip_model_runtime_contracts import ModelRuntimeLifecycle
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from test_aip_eval_execution_authority import (
    ACTUAL_HASH, EXPECTED_HASH, INPUT_HASH, JUDGE, TENANT, _judge_output_hash,
)
from test_aip_eval_persisted_authority_reader import _seed as _seed_signed_pair
from test_aip_eval_report_proof_reader import _seed_report, _seed_sidecar
from test_aip_eval_writer_atomic import _seed_source, _source_objects

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
        logic_revision_ref=ref("LogicRevision", "logic.demo"),
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


def test_legacy_published_skill_without_logic_ref_remains_readable_but_new_ref_is_exact() -> None:
    legacy = skill_request(
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
    assert legacy.logic_revision_ref is None
    payload = legacy.model_dump(mode="json", by_alias=True)
    payload["logicRevisionRef"] = ref(
        "ModelRouteRevision", "logic.demo"
    ).model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="logic_revision_ref must reference"):
        PublishSkillTemplateRequest.model_validate(payload)


def test_governed_publication_request_rejects_wrong_ref_kinds() -> None:
    with pytest.raises(ValidationError, match="source_skill must reference SkillTemplate"):
        PublishEvaluatedSkillRevisionRequest(
            source_skill=ref("AgentTemplate", "skill.demo"),
            publication_id="publication-1",
            release_gate_decision_id="gate-1",
            model_route_ref=ref("ModelRouteRevision", "route-1"),
            runtime_policy_ref=ref("RuntimePolicyRevision", "policy-1"),
            logic_revision_ref=ref("LogicRevision", "logic.demo"),
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
    def __init__(self, scope=None):
        self.scope = scope

    def require_ready(self, scope, route_ref, policy_ref, *, evaluated_at):
        assert scope == self.scope if self.scope is not None else scope.org_id.startswith("bind3-org-")
        assert route_ref.asset_type == "ModelRouteRevision"
        assert policy_ref.asset_type == "RuntimePolicyRevision"
        assert evaluated_at.tzinfo is not None


class _PublishedLogicAuthority:
    def __init__(self, scope=None):
        self.scope = scope

    def require_published(
        self, _conn, scope, canonical_logic_id, logic_revision_ref
    ):
        assert scope == self.scope if self.scope is not None else scope.org_id.startswith("bind3-org-")
        assert canonical_logic_id == logic_revision_ref.asset_id
        assert logic_revision_ref.asset_type == "LogicRevision"


def test_skill_publication_route_gate_does_not_consume_transient_health(
    monkeypatch,
) -> None:
    route_ref = ref("ModelRouteRevision", "route-1")
    policy_ref = ref("RuntimePolicyRevision", "policy-1")
    gate_ref = ref("EvalGateDecision", "gate-1")
    route = SimpleNamespace(
        route_id="route-1",
        revision=1,
        content_hash=route_ref.content_hash,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        runtime_policy_ref=policy_ref,
        eval_gate_ref=gate_ref,
    )
    policy = SimpleNamespace(
        content_hash=policy_ref.content_hash,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        kill_switch_enabled=False,
    )

    class Store:
        @staticmethod
        def get_route(*_args):
            return route

        @staticmethod
        def get_policy(*_args):
            return policy

    class EvalAuthority:
        called = False

        def require_exact_passed(self, scope, selected_gate, **kwargs):
            self.called = True
            assert scope.key == ("org-org", "dev-project")
            assert selected_gate == gate_ref
            assert kwargs["expected_target"] == route_ref

    eval_authority = EvalAuthority()
    monkeypatch.setattr(
        "aos_api.aip_skill_publication_service.evaluation_candidate_ref",
        lambda _route: route_ref,
    )
    authority = PostgresSkillPublicationRouteAuthority(
        store=Store(), eval_authority=eval_authority
    )
    authority.require_ready(
        TenantScope("org-org", "dev-project"),
        route_ref,
        policy_ref,
        evaluated_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )
    assert eval_authority.called is True


def test_skill_publication_route_gate_blocks_kill_switch(monkeypatch) -> None:
    route_ref = ref("ModelRouteRevision", "route-1")
    policy_ref = ref("RuntimePolicyRevision", "policy-1")
    route = SimpleNamespace(
        route_id="route-1",
        revision=1,
        content_hash=route_ref.content_hash,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        runtime_policy_ref=policy_ref,
        eval_gate_ref=ref("EvalGateDecision", "gate-1"),
    )
    policy = SimpleNamespace(
        content_hash=policy_ref.content_hash,
        lifecycle=ModelRuntimeLifecycle.ACTIVE,
        kill_switch_enabled=True,
    )

    class Store:
        get_route = staticmethod(lambda *_args: route)
        get_policy = staticmethod(lambda *_args: policy)

    class EvalAuthority:
        require_exact_passed = staticmethod(lambda *_args, **_kwargs: None)

    monkeypatch.setattr(
        "aos_api.aip_skill_publication_service.evaluation_candidate_ref",
        lambda _route: route_ref,
    )
    authority = PostgresSkillPublicationRouteAuthority(
        store=Store(), eval_authority=EvalAuthority()
    )
    with pytest.raises(
        AipAgentRegistryTransitionBlocked,
        match="exact active route, policy, and Eval gate",
    ):
        authority.require_ready(
            TenantScope("org-org", "dev-project"),
            route_ref,
            policy_ref,
            evaluated_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
        )


def _canonical_hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _seed_historical_skill_report(scope, suite, suffix, expected_value):
    """Test-only historical row: no current formal executor is claimed."""
    created_at = datetime.now(UTC)
    run_id = f"historical-run-{suffix}"
    suite_ref = AssetRevisionRef(
        asset_type=AssetType.EVAL_SUITE,
        asset_id=suite.suite_id,
        revision=str(suite.revision),
        content_hash=suite.content_hash,
    )
    report = EvalReportRevision(
        tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
        report_id=f"historical-report-{suffix}", revision=1,
        content_hash="0" * 64, run_id=run_id,
        suite_ref=suite_ref, target=suite.target,
        dataset=suite.dataset, judge=suite.judge,
        results=[EvalCaseResultEvidence(
            case_id="positive-1", passed=True,
            actual_hash=_canonical_hash(expected_value),
            expected_hash=_canonical_hash(expected_value),
            detail_code="historical_test_only", duration_ms=0,
        )],
        passed=1, failed=0, total=1, pass_rate=1.0,
        gate_passed=True, created_at=created_at,
    )
    report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
    def json_ref(value):
        return json.dumps(value.model_dump(mode="json", by_alias=True))
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_eval_run
               (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
                target_ref,dataset_ref,judge_ref,status,idempotency_key,version,
                created_by,created_at,started_at,finished_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                       'succeeded',%s,3,'historical-test',%s,%s,%s)""",
            (*scope.key, run_id, suite.suite_id, suite.revision,
             suite.content_hash, json_ref(suite.target), json_ref(suite.dataset),
             json_ref(suite.judge), f"historical-{suffix}", created_at,
             created_at, created_at),
        )
        conn.commit()
    AipEvalRunner()._append_report(scope, report)
    return report


def _seed_historical_skill_release(scope, report, suffix):
    release = AipReleasePublicationService()
    decided_at = datetime.now(UTC)
    expires_at = decided_at + timedelta(days=30)
    report_ref = ArtifactRef(
        artifact_id=report.report_id,
        artifact_type=AssetType.EVAL_REPORT.value,
        revision=str(report.revision),
        content_hash=report.content_hash,
    )
    gate = ReleaseGateDecision(
        tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
        decision_id=f"historical-gate-{suffix}",
        target=report.target,
        suite_ref=report.suite_ref,
        eval_run_id=report.run_id,
        eval_report=report_ref,
        status=ReleaseGateStatus.PASSED,
        decision_hash=release_hash({
            "target": report.target,
            "suiteRef": report.suite_ref,
            "evalRunId": report.run_id,
            "evalReport": report_ref,
            "status": ReleaseGateStatus.PASSED.value,
            "expiresAt": expires_at,
        }),
        decided_by="historical-test",
        decided_at=decided_at,
        expires_at=expires_at,
    )
    event = PublicationEvent(
        tenant=gate.tenant,
        event_id=f"historical-event-{suffix}",
        publication_id=f"historical-publication-{suffix}",
        target=report.target,
        event_type=PublicationEventType.PUBLISHED,
        release_gate_decision_id=gate.decision_id,
        reason_hash="5" * 64,
        actor="historical-test",
        occurred_at=decided_at,
    )
    with connect(scope) as conn:
        release._insert_gate(conn, scope, gate)
        release._insert_event(conn, scope, event)
        conn.commit()
    return gate, event


def published_skill_runtime(*, skill_id=None, canonical_logic_id=None, scope=None, logic_revision_ref=None, stop_before_gate=False, historical_event=False, stop_before_skill_publication=False):
    suffix = uuid.uuid4().hex[:12]
    scope = scope or TenantScope(f"bind3-org-{suffix}", f"bind3-project-{suffix}")
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING", (scope.org_id, scope.org_id))
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (*scope.key, scope.project_id),
        )
        conn.commit()

    skill_id = skill_id or f"skill.bind3.{suffix}"
    source = skill_request(skill_id=skill_id, canonical_logic_id=canonical_logic_id or f"logic.bind3.{suffix}")
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
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_artifact
               (org_id,project_id,artifact_id,artifact_type,content_hash,
                content_ref,source,created_by)
               VALUES (%s,%s,%s,'eval_dataset_snapshot',%s,%s,'{}'::jsonb,'pytest-bind3'),
                      (%s,%s,%s,'redaction_receipt',%s,%s,%s::jsonb,'pytest-bind3')""",
            (*scope.key, f"skill-eval-{suffix}", "2" * 64,
             f"test-only://skill-eval-{suffix}",
             *scope.key, f"redaction-{suffix}", "4" * 64,
             f"test-only://redaction-{suffix}",
             json.dumps({"sourceArtifactRef": {
                 "artifactId": f"skill-eval-{suffix}",
                 "artifactType": "eval_dataset_snapshot", "revision": "1",
                 "contentHash": "2" * 64}})),
        )
        conn.commit()
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
                artifact_type="redaction_receipt",
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

    report = _seed_historical_skill_report(scope, suite, suffix, expected_value)
    if stop_before_gate:
        return SimpleNamespace(scope=scope, source=source, report=report,
                               suffix=suffix, skill_id=skill_id)
    if historical_event:
        gate, publication = _seed_historical_skill_release(scope, report, suffix)
    else:
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
            expected_target_type=AssetType.SKILL_TEMPLATE,
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
        logic_revision_ref=logic_revision_ref or ref("LogicRevision", source.canonical_logic_id),
        idempotency_key=f"publish-skill-{suffix}",
    )
    service = AipSkillPublicationService(
        route_authority=_ReadyRouteAuthority(scope),
        logic_authority=_PublishedLogicAuthority(scope),
    )
    if stop_before_skill_publication:
        return SimpleNamespace(scope=scope, source=source, service=service,
                               request=request, gate=gate, publication=publication,
                               report=report, suffix=suffix, skill_id=skill_id)
    published, receipt = service.publish_evaluated_revision(
        scope,
        request,
        actor="pytest-bind3",
        occurred_at=datetime(2026, 8, 15, 3, 30, tzinfo=UTC),
    )
    return SimpleNamespace(scope=scope, source=source, published=published, receipt=receipt,
        service=service, request=request, gate=gate, report=report, suffix=suffix, skill_id=skill_id)


def test_unattested_skill_report_cannot_derive_release_gate() -> None:
    runtime = published_skill_runtime(stop_before_gate=True)
    release = AipReleasePublicationService()
    with pytest.raises(AipReleaseGateRejected, match="formal Skill Eval executor authority unavailable"):
        release.derive_gate(
            runtime.scope, actor="pytest-bind3",
            request=DeriveReleaseGateRequest(
                report_id=runtime.report.report_id,
                report_revision=runtime.report.revision,
                report_hash=runtime.report.content_hash,
                idempotency_key=f"unattested-gate-{runtime.suffix}",
            ),
        )
    with connect(runtime.scope) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s",
            runtime.scope.key,
        ).fetchone()["n"] == 0


def test_existing_unattested_skill_gate_cannot_create_publication_event() -> None:
    runtime = published_skill_runtime(stop_before_gate=True)
    release = AipReleasePublicationService()
    decided_at = datetime.now(UTC)
    expires_at = decided_at + timedelta(days=30)
    report_ref = ArtifactRef(
        artifact_id=runtime.report.report_id,
        artifact_type=AssetType.EVAL_REPORT.value,
        revision=str(runtime.report.revision),
        content_hash=runtime.report.content_hash,
    )
    gate = ReleaseGateDecision(
        tenant=TenantContext(org_id=runtime.scope.org_id, project_id=runtime.scope.project_id),
        decision_id=f"historical-gate-{runtime.suffix}",
        target=runtime.report.target,
        suite_ref=runtime.report.suite_ref,
        eval_run_id=runtime.report.run_id,
        eval_report=report_ref,
        status=ReleaseGateStatus.PASSED,
        decision_hash=release_hash({
            "target": runtime.report.target,
            "suiteRef": runtime.report.suite_ref,
            "evalRunId": runtime.report.run_id,
            "evalReport": report_ref,
            "status": ReleaseGateStatus.PASSED.value,
            "expiresAt": expires_at,
        }),
        decided_by="historical-test",
        decided_at=decided_at,
        expires_at=expires_at,
    )
    with connect(runtime.scope) as conn:
        release._insert_gate(conn, runtime.scope, gate)
        conn.commit()
    with pytest.raises(AipReleaseGateRejected, match="formal Skill Eval executor authority unavailable"):
        release.publish(
            runtime.scope, actor="pytest-bind3",
            expected_target_type=AssetType.SKILL_TEMPLATE,
            request=PublishReleaseRequest(
                release_gate_decision_id=gate.decision_id,
                reason_hash="5" * 64,
                idempotency_key=f"historical-skill-publish-{runtime.suffix}",
            ),
        )
    with connect(runtime.scope) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_publication_event WHERE org_id=%s AND project_id=%s",
            runtime.scope.key,
        ).fetchone()["n"] == 0


def test_historical_unattested_skill_event_cannot_mint_new_skill_revision() -> None:
    runtime = published_skill_runtime(
        historical_event=True, stop_before_skill_publication=True
    )
    with pytest.raises(
        AipAgentRegistryTransitionBlocked,
        match="formal Skill Eval executor authority unavailable",
    ):
        runtime.service.publish_evaluated_revision(
            runtime.scope, runtime.request, actor="pytest-bind3",
            occurred_at=datetime.now(UTC),
        )
    with connect(runtime.scope) as conn:
        rows = conn.execute(
            "SELECT revision,lifecycle FROM aip_skill_template_revision WHERE skill_id=%s ORDER BY revision",
            (runtime.skill_id,),
        ).fetchall()
        receipt_count = conn.execute(
            """SELECT count(*) AS n FROM aip_agent_registry_receipt
               WHERE org_id=%s AND project_id=%s AND operation='skill_template.publish_evaluated'""",
            runtime.scope.key,
        ).fetchone()["n"]
    assert [(row["revision"], row["lifecycle"]) for row in rows] == [(1, "evaluated")]
    assert receipt_count == 0


def test_final_skill_publication_rechecks_evidence_in_stable_tenant_snapshot() -> None:
    runtime = published_skill_runtime(
        historical_event=True, stop_before_skill_publication=True,
    )
    with pytest.raises(AipAgentRegistryTransitionBlocked) as captured:
        runtime.service.publish_evaluated_revision(
            runtime.scope, runtime.request, actor="pytest-bind3",
            occurred_at=datetime.now(UTC),
        )
    gate_error = captured.value.__cause__
    assert isinstance(gate_error, AipReleaseGateRejected)
    proof_error = gate_error.__cause__
    assert isinstance(proof_error, EvalExecutionRejected)
    assert "sidecar" in str(proof_error), repr(proof_error.__cause__)
    with connect(runtime.scope) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s
              AND operation='skill_template.publish_evaluated'""",
            runtime.scope.key,
        ).fetchone()["n"] == 0


def _test_only_signed_pair_for_skill(suite, *, at):
    """Bind isolated signer claims to the original evaluated Skill source."""
    issuer, target_key, judge_key = (Ed25519PrivateKey.generate() for _ in range(3))

    def public_bytes(key):
        return key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )

    root = EvalIssuerRoot(
        issuer_id="e17-s2c-test-issuer", key_id="test-key-1",
        public_key=public_bytes(issuer), purpose="eval-execution",
        not_before=at - timedelta(days=1), not_after=at + timedelta(days=1),
    )
    suite_ref = AssetRevisionRef(
        asset_type=AssetType.EVAL_SUITE, asset_id=suite.suite_id,
        revision=str(suite.revision), content_hash=suite.content_hash,
    )

    def signed(purpose, identity_id, executor_ref, key, output_hash, **judge_fields):
        cert = EvalExecutorCertificate(
            identity_id=identity_id, tenant=TENANT, purpose=purpose,
            executor_ref=executor_ref, issuer_id=root.issuer_id,
            issuer_key_id=root.key_id,
            public_key_base64=base64.b64encode(public_bytes(key)).decode(),
            valid_from=at - timedelta(hours=1),
            valid_until=at + timedelta(hours=1), signature_base64="pending",
        )
        cert = cert.model_copy(update={"signature_base64": base64.b64encode(
            issuer.sign(canonical_certificate_bytes(cert)),
        ).decode()})
        receipt = EvalExecutionReceipt(
            receipt_id=receipt_identity(TENANT, "run-1", "case-1", purpose),
            tenant=TENANT, purpose=purpose, run_id="run-1", suite_ref=suite_ref,
            case_id="case-1", identity_id=cert.identity_id,
            certificate_hash=certificate_hash(cert), executor_ref=executor_ref,
            input_hash=INPUT_HASH, output_hash=output_hash,
            occurred_at=at, signature_base64="pending", **judge_fields,
        )
        receipt = receipt.model_copy(update={"signature_base64": base64.b64encode(
            key.sign(canonical_receipt_bytes(receipt)),
        ).decode()})
        return cert, receipt, key

    target = signed("target", "e17-s2c-target", suite.target,
                    target_key, ACTUAL_HASH)
    judge = signed(
        "judge", "e17-s2c-judge", suite.judge, judge_key,
        _judge_output_hash(ACTUAL_HASH, EXPECTED_HASH, True, "exact_match"),
        actual_hash=ACTUAL_HASH, expected_hash=EXPECTED_HASH,
        passed=True, detail_code="exact_match",
    )
    return root, target, judge


@pytest.fixture()
def isolated_signed_skill_rows():
    yield
    with psycopg.connect(get_dsn()) as conn:
        assert conn.info.dbname.startswith("aos_test_")
        assert conn.info.dbname.endswith("_ti4_test")
        for table in (
            "aip_publication_event", "aip_release_gate_decision",
            "aip_eval_case_execution_proof", "aip_eval_execution_receipt",
            "aip_eval_report_revision", "aip_eval_authority_revocation",
            "aip_eval_run", "aip_eval_executor_identity", "aip_eval_issuer_root",
            "aip_eval_suite_revision", "aip_eval_dataset_revision",
        ):
            conn.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(sql.Identifier(table)))
            conn.execute(sql.SQL("DELETE FROM {} WHERE org_id=%s AND project_id=%s").format(
                sql.Identifier(table)), ("org-org", "dev-project"))
            conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(sql.Identifier(table)))
        conn.commit()


def test_original_evaluated_skill_signed_gate_event_publishes_once(
    isolated_signed_skill_rows,
) -> None:
    scope = TenantScope("org-org", "dev-project")
    suffix = uuid.uuid4().hex[:12]
    source_request = skill_request(
        skill_id=f"e17.s2c.test.{suffix}",
        canonical_logic_id=f"e17.s2c.logic.{suffix}",
    )
    source_request = source_request.model_copy(update={"content_hash": _canonical_hash(
        source_request.model_dump(mode="json", by_alias=True, exclude={"content_hash"}),
    )})
    source = AipSkillRegistry().publish_skill(source_request, actor="e17-s2c-test")
    target_ref = AssetRevisionRef(
        asset_type=AssetType.SKILL_TEMPLATE, asset_id=source.skill_id,
        revision=str(source.revision), content_hash=source.content_hash,
    )
    suite, base = _source_objects()
    suite = suite.model_copy(update={"target": target_ref})
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    suite_ref = AssetRevisionRef(
        asset_type=AssetType.EVAL_SUITE, asset_id=suite.suite_id,
        revision=str(suite.revision), content_hash=suite.content_hash,
    )
    now = datetime.now(UTC)
    report = base.model_copy(update={
        "target": target_ref, "suite_ref": suite_ref, "created_at": now,
    })
    report = report.model_copy(update={"content_hash": compute_eval_report_hash(report)})
    root, target, judge = _test_only_signed_pair_for_skill(suite, at=now)
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES ('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES ('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        _seed_source(conn, suite)
        _seed_signed_pair(conn, root, target, judge, suite_ref=suite_ref)
        _seed_report(conn, report)
        _seed_sidecar(conn, target, judge)
        conn.commit()

    release = AipReleasePublicationService()
    gate = release.derive_gate(scope, actor="e17-s2c-test", request=DeriveReleaseGateRequest(
        report_id=report.report_id, report_revision=report.revision,
        report_hash=report.content_hash, idempotency_key=f"s2c-gate-{suffix}",
    ))
    assert gate.status is ReleaseGateStatus.PASSED
    event = release.publish(scope, actor="e17-s2c-test", request=PublishReleaseRequest(
        release_gate_decision_id=gate.decision_id, reason_hash="5" * 64,
        idempotency_key=f"s2c-event-{suffix}",
    ))
    assert event.target == target_ref
    request = PublishEvaluatedSkillRevisionRequest(
        source_skill=ref("SkillTemplate", source.skill_id).model_copy(
            update={"content_hash": source.content_hash}),
        publication_id=event.publication_id,
        release_gate_decision_id=gate.decision_id,
        model_route_ref=ref("ModelRouteRevision", f"route-{suffix}"),
        runtime_policy_ref=ref("RuntimePolicyRevision", f"policy-{suffix}"),
        logic_revision_ref=ref("LogicRevision", source.canonical_logic_id),
        idempotency_key=f"s2c-publish-{suffix}",
    )
    service = AipSkillPublicationService(
        route_authority=_ReadyRouteAuthority(scope),
        logic_authority=_PublishedLogicAuthority(scope),
    )
    published, receipt = service.publish_evaluated_revision(
        scope, request, actor="e17-s2c-test", occurred_at=now,
    )
    assert published.lifecycle is TemplateLifecycle.PUBLISHED
    assert published.parent_ref.content_hash == source.content_hash
    assert published.release_gate_ref.asset_id == gate.decision_id
    assert published.publication_ref.resource_id == event.event_id
    assert published.model_route_ref == request.model_route_ref
    assert published.runtime_policy_ref == request.runtime_policy_ref
    assert published.logic_revision_ref == request.logic_revision_ref
    replay, replay_receipt = service.publish_evaluated_revision(
        scope, request, actor="e17-s2c-test", occurred_at=now,
    )
    assert replay == published and replay_receipt == receipt
    with pytest.raises(
        AipAgentRegistryTransitionBlocked,
        match="exact published LogicRevision",
    ):
        AipSkillPublicationService().publish_evaluated_revision(
            scope, request.model_copy(update={
                "idempotency_key": f"s3b-original-logic-{suffix}",
            }), actor="e17-s2c-test",
        )
    with pytest.raises(
        AipAgentRegistryTransitionBlocked,
        match="model route is unavailable",
    ):
        AipSkillPublicationService(
            logic_authority=_PublishedLogicAuthority(scope),
        ).publish_evaluated_revision(
            scope, request.model_copy(update={
                "idempotency_key": f"s3b-original-route-{suffix}",
            }), actor="e17-s2c-test",
        )
    with pytest.raises(AipAgentRegistryNotFound, match="skill publication event not found"):
        service.publish_evaluated_revision(
            scope, request.model_copy(update={
                "publication_id": f"missing-{suffix}",
                "idempotency_key": f"s2c-wrong-event-{suffix}",
            }), actor="e17-s2c-test",
        )
    with connect() as conn:
        conn.execute("""INSERT INTO aip_eval_authority_revocation
            (org_id,project_id,event_id,identity_id,revoked_at,owner_ref,
             approval_ref,reason_hash)
            VALUES ('org-org','dev-project',%s,%s,%s,%s,%s,%s)""",
            (f"s2c-revoked-{suffix}", target[0].identity_id,
             datetime.now(UTC), "e17-s2c-test-owner",
             Jsonb({"testOnly": True}), "e" * 64))
        conn.commit()
    with pytest.raises(AipAgentRegistryTransitionBlocked):
        service.publish_evaluated_revision(
            scope, request.model_copy(update={
                "idempotency_key": f"s2c-after-revocation-{suffix}",
            }), actor="e17-s2c-test",
        )
    with connect(scope) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM aip_agent_registry_receipt
            WHERE org_id=%s AND project_id=%s
              AND operation='skill_template.publish_evaluated'""",
            scope.key,
        ).fetchone()["n"] == 1


@pytest.mark.xfail(
    strict=True,
    reason="formal Skill Eval signer and execution Receipt are unavailable; lambda Eval cannot publish",
)
def test_real_eval_publication_creates_new_immutable_skill_revision_and_receipt() -> None:
    runtime = published_skill_runtime()
    scope, source, published, receipt = runtime.scope, runtime.source, runtime.published, runtime.receipt
    service, request, gate = runtime.service, runtime.request, runtime.gate
    suffix, skill_id = runtime.suffix, runtime.skill_id
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
    assert published.logic_revision_ref == request.logic_revision_ref
    assert published.publication_tenant == TenantContext(
        org_id=scope.org_id, project_id=scope.project_id
    )
    assert receipt.operation == "skill_template.publish_evaluated"
    assert replay == published and replay_receipt == receipt
    r3_request = request.model_copy(
        update={
            "model_route_ref": ref("ModelRouteRevision", f"route-{suffix}-r2"),
            "idempotency_key": f"publish-skill-{suffix}-r3",
        }
    )
    published_r3, _ = service.publish_evaluated_revision(
        scope,
        r3_request,
        actor="pytest-bind3",
        occurred_at=datetime(2026, 8, 15, 3, 32, tzinfo=UTC),
    )
    unchanged_r2 = AipSkillRegistry().get_skill(skill_id, 2)
    assert published_r3.revision == 3
    assert published_r3.lifecycle is TemplateLifecycle.PUBLISHED
    assert published_r3.model_route_ref == r3_request.model_route_ref
    assert unchanged_r2.content_hash == published.content_hash
    assert unchanged_r2.model_route_ref == request.model_route_ref
