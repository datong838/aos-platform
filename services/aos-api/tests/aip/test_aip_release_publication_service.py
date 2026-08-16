from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
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
    PublicationEventType,
    ReleaseGateStatus,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_eval_runner import (
    AipEvalRunner,
    JudgeExecution,
    ResolvedArtifact,
    TargetExecution,
)
from aos_api.aip_logic_graph_models import CreateLogicGraphRequest
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
    RevokePublicationRequest,
)
from aos_api.aip_release_publication_service import (
    AipPublicationAlreadyRevoked,
    AipReleaseGateRejected,
    AipReleasePublicationConflict,
    AipReleasePublicationNotFound,
    AipReleasePublicationService,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

H1, H2, H3, H4 = (char * 64 for char in "1234")
NOW = datetime(2026, 8, 11, 14, 0, tzinfo=UTC)
INPUT_VALUE = {"amount": 100}
EXPECTED_VALUE = {"decision": "allow"}


def _hash(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.fixture()
def release_runtime():
    suffix = uuid.uuid4().hex[:12]
    scope = TenantScope(f"e2-org-{suffix}", f"e2-project-{suffix}")
    other = TenantScope(f"e2-other-{suffix}", f"e2-other-project-{suffix}")
    with connect() as conn:
        for current in (scope, other):
            conn.execute(
                "INSERT INTO twa_org (id,name) VALUES (%s,%s)",
                (current.org_id, current.org_id),
            )
            conn.execute(
                "INSERT INTO twa_workspace (org_id,project_id,name) VALUES (%s,%s,%s)",
                (*current.key, current.project_id),
            )
        conn.commit()

    graph = LogicGraphStore().create(
        scope.org_id,
        scope.project_id,
        "e2-test",
        CreateLogicGraphRequest(
            name="E2 release target",
            nodes=[{"id": "input", "kind": "input", "label": "Input"}],
            entry_node_ids=["input"],
        ),
    )
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH,
        asset_id=graph.id,
        revision=str(graph.revision),
        content_hash=graph.graph_hash,
    )
    dataset = DatasetRevisionRef(
        dataset_id=f"dataset-{suffix}",
        revision=1,
        content_hash=H1,
        source_hash=H2,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id="redaction-policy",
            revision="1",
            content_hash=H3,
        ),
    )
    registry = AipEvalPackRegistry()
    registry.register_dataset_revision(
        scope,
        dataset,
        EvalDatasetManifest(
            source_kind=DatasetSourceKind.OBJECT_SNAPSHOT,
            source_id=f"object-snapshot-{suffix}",
            source_revision="1",
            source_hash=H2,
            fields_allowlist=["amount"],
            redaction_receipt=ArtifactRef(
                artifact_id="redaction-receipt",
                artifact_type="receipt",
                revision="1",
                content_hash=H4,
            ),
            pii_state=DatasetPiiState.REDACTED,
            case_count=1,
            captured_at=NOW,
        ),
        actor="e2-test",
    )
    input_ref = ArtifactRef(
        artifact_id="input",
        artifact_type="eval_input",
        revision="1",
        content_hash=_hash(INPUT_VALUE),
    )
    expected_ref = ArtifactRef(
        artifact_id="expected",
        artifact_type="eval_expected",
        revision="1",
        content_hash=_hash(EXPECTED_VALUE),
    )
    suite = EvalSuiteRevision(
        suite_id=f"suite-{suffix}",
        revision=1,
        content_hash="0" * 64,
        target=target,
        dataset=dataset,
        judge=JudgeRevisionRef(judge_id="exact-judge", revision=1, content_hash=H4),
        cases=[
            EvalCaseDefinition(
                case_id="positive-1",
                kind=EvalCaseKind.POSITIVE,
                input_artifact=input_ref,
                expected_artifact=expected_ref,
                timeout_ms=1000,
            )
        ],
        gate_threshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    registry.register_suite_revision(scope, suite, actor="e2-test")
    runner = AipEvalRunner()

    def resolve(ref):
        value = INPUT_VALUE if ref == input_ref else EXPECTED_VALUE
        return ResolvedArtifact(reference=ref, value=value)

    report = runner.run(
        scope,
        suite_id=suite.suite_id,
        suite_revision=1,
        idempotency_key=f"run-{suffix}",
        actor="e2-test",
        resolve_artifact=resolve,
        execute_target=lambda ref, _value: TargetExecution(
            target=ref, value=EXPECTED_VALUE
        ),
        execute_judge=lambda ref, actual, expected: JudgeExecution(
            judge=ref,
            passed=actual == expected,
            detail_code="exact_match",
        ),
    )
    yield scope, other, report, AipReleasePublicationService()


def _gate_request(report, key="gate-once"):
    return DeriveReleaseGateRequest(
        report_id=report.report_id,
        report_revision=report.revision,
        report_hash=report.content_hash,
        idempotency_key=key,
    )


def test_gate_publish_and_revoke_are_derived_and_append_only(release_runtime) -> None:
    scope, _other, report, service = release_runtime
    gate = service.derive_gate(scope, actor="publisher", request=_gate_request(report))
    assert gate.status is ReleaseGateStatus.PASSED
    assert gate.target == report.target
    assert service.derive_gate(
        scope, actor="publisher", request=_gate_request(report)
    ) == gate

    published = service.publish(
        scope,
        actor="publisher",
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash=H1,
            idempotency_key="publish-once",
        ),
    )
    assert published.event_type is PublicationEventType.PUBLISHED
    assert service.publish(
        scope,
        actor="publisher",
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash=H1,
            idempotency_key="publish-once",
        ),
    ) == published

    revoked = service.revoke(
        scope,
        publication_id=published.publication_id,
        actor="publisher",
        request=RevokePublicationRequest(
            reason_hash=H2,
            idempotency_key="revoke-once",
        ),
    )
    assert revoked.event_type is PublicationEventType.REVOKED
    assert revoked.publication_id == published.publication_id
    with connect(scope) as conn:
        facts = conn.execute(
            "SELECT event_type FROM aip_publication_event WHERE publication_id=%s ORDER BY occurred_at",
            (published.publication_id,),
        ).fetchall()
    assert [row["event_type"] for row in facts] == ["published", "revoked"]


def test_release_is_tenant_scoped_and_idempotency_conflicts(release_runtime) -> None:
    scope, other, report, service = release_runtime
    gate = service.derive_gate(scope, actor="publisher", request=_gate_request(report))
    with pytest.raises(AipReleasePublicationNotFound):
        service.derive_gate(other, actor="publisher", request=_gate_request(report))
    with pytest.raises(AipReleasePublicationConflict):
        service.derive_gate(
            scope,
            actor="other-actor",
            request=_gate_request(report),
        )
    with pytest.raises(AipReleasePublicationNotFound):
        service.publish(
            other,
            actor="publisher",
            request=PublishReleaseRequest(
                release_gate_decision_id=gate.decision_id,
                reason_hash=H1,
                idempotency_key="other-publish",
            ),
        )


def test_failed_gate_cannot_publish_and_duplicate_revoke_is_rejected(
    release_runtime,
) -> None:
    scope, _other, report, service = release_runtime
    gate = service.derive_gate(scope, actor="publisher", request=_gate_request(report))
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_release_gate_decision (
                   org_id,project_id,decision_id,target_ref,suite_ref,eval_run_id,
                   eval_report_ref,status,decision_hash,invalidated_by,decided_by,decided_at,
                   expires_at
                   ) SELECT org_id,project_id,%s,target_ref,suite_ref,eval_run_id,
                            eval_report_ref,'failed',%s,NULL,decided_by,decided_at,
                            expires_at
                 FROM aip_release_gate_decision WHERE decision_id=%s""",
            ("failed-gate", H3, gate.decision_id),
        )
        conn.commit()
    with pytest.raises(AipReleaseGateRejected):
        service.publish(
            scope,
            actor="publisher",
            request=PublishReleaseRequest(
                release_gate_decision_id="failed-gate",
                reason_hash=H1,
                idempotency_key="failed-publish",
            ),
        )

    published = service.publish(
        scope,
        actor="publisher",
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash=H1,
            idempotency_key="publish-for-revoke",
        ),
    )
    service.revoke(
        scope,
        publication_id=published.publication_id,
        actor="publisher",
        request=RevokePublicationRequest(reason_hash=H2, idempotency_key="revoke-a"),
    )
    with pytest.raises(AipPublicationAlreadyRevoked):
        service.revoke(
            scope,
            publication_id=published.publication_id,
            actor="publisher",
            request=RevokePublicationRequest(
                reason_hash=H2, idempotency_key="revoke-b"
            ),
        )
    with pytest.raises(AipEvalAuthorityConflict, match="withdrawn"):
        AipEvalRunner().run(
            scope,
            suite_id=report.suite_ref.asset_id,
            suite_revision=int(report.suite_ref.revision),
            idempotency_key="run-after-revoke",
            actor="e2-test",
            resolve_artifact=lambda _ref: pytest.fail("withdrawn target must not resolve"),
            execute_target=lambda _ref, _value: pytest.fail(
                "withdrawn target must not execute"
            ),
            execute_judge=lambda _ref, _actual, _expected: pytest.fail(
                "withdrawn target must not judge"
            ),
        )
