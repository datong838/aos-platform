"""W7-06 immutable four-gate media review acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
    ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    AssembleMediaGateSetRequest,
    AttachArtifactFamilyMemberRequest,
    CreateReviewIssueRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    MediaGateDefinition,
    MediaGateKind,
    MediaGateOutcome,
    MediaGateResultInput,
    RegisterArtifactFamilyRequest,
    RegisterMediaGateProfileRequest,
    RegisterReviewRuleRevisionRequest,
    ReviewIssueVersionRef,
    ReviewSeverity,
)
from aos_api.aip_eval_contracts import EvalStageAttemptRef
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
ISOLATION_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "test:w7-06"
MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/w7_004_media_four_gate_review.py"
)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _headers(key: str) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": SCOPE.org_id,
        "X-Project-Id": SCOPE.project_id,
        "Idempotency-Key": key,
    }


def _started_run(client) -> str:
    suffix = uuid.uuid4().hex
    headers = _headers(f"w7-06-task-{suffix}")
    task = client.post(
        "/v1/aip/tasks",
        headers=headers,
        json={"type": "media", "title": f"W7-06 gates {suffix}"},
    ).json()
    plan = client.post(
        f"/v1/aip/tasks/{task['id']}/plans",
        headers={**headers, "Idempotency-Key": f"w7-06-plan-{suffix}"},
        json={
            "expectedTaskVersion": task["version"],
            "steps": [{"stepKey": "render", "title": "受控媒体渲染"}],
            "dependencies": [],
        },
    ).json()
    planning = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    approved = client.post(
        f"/v1/aip/tasks/{task['id']}/plans/{plan['revision']}/approve",
        headers={**headers, "Idempotency-Key": f"w7-06-approve-{suffix}"},
        json={
            "expectedTaskVersion": planning["version"],
            "expectedContentHash": plan["contentHash"],
        },
    )
    assert approved.status_code == 200, approved.text
    approved_task = client.get(f"/v1/aip/tasks/{task['id']}", headers=headers).json()
    response = client.post(
        f"/v1/aip/tasks/{task['id']}/runs",
        headers={**headers, "Idempotency-Key": f"w7-06-run-{suffix}"},
        json={
            "planRevisionId": plan["id"],
            "expectedTaskVersion": approved_task["version"],
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["id"]


def _artifact(run_id: str, family_id: str, revision: int, role: str) -> ExactArtifactRef:
    token = f"{family_id}:{revision}:{role}:{uuid.uuid4().hex}"
    content_hash = _hash(token)
    artifact_id = AipTaskStore().record_artifact(
        SCOPE,
        run_id,
        ACTOR,
        "artifact_family_manifest" if role == "family_manifest" else "media_asset",
        {
            "contentRef": f"memory://{token}",
            "contentHash": content_hash,
            "metadata": {
                "artifactFamily": {
                    "familyId": family_id,
                    "familyRevision": revision,
                    "role": role,
                    "profile": "STANDARD",
                    "platform": "douyin",
                    "renditionSpec": {"ratio": "9:16", "codec": "h264"},
                    "lineageRefs": [
                        {
                            "resourceType": "StageTemplateRevision",
                            "resourceId": "media-standard",
                            "revision": 1,
                            "contentHash": "a" * 64,
                        }
                    ],
                }
            },
        },
    )
    return ExactArtifactRef(artifactId=artifact_id, contentHash=content_hash)


class _ReadyStore(AipProductionContractStore):
    def _eval_blockers(self, conn, scope, row):  # type: ignore[no-untyped-def]
        return []


def _authority(client, *, failed_gate: MediaGateKind | None = None):
    run_id = _started_run(client)
    family_id = f"family-{uuid.uuid4().hex[:20]}"
    manifest = _artifact(run_id, family_id, 1, "family_manifest")
    master = _artifact(run_id, family_id, 2, "master")
    variant = _artifact(run_id, family_id, 3, "variant")
    store = _ReadyStore(stage_template_source_resolver=lambda scope, ref: True)
    store.register_artifact_family(
        SCOPE,
        ACTOR,
        f"family-{family_id}",
        RegisterArtifactFamilyRequest(familyId=family_id, manifestArtifact=manifest),
    )
    family = store.attach_artifact_family_member(
        SCOPE,
        ACTOR,
        family_id,
        f"master-{family_id}",
        AttachArtifactFamilyMemberRequest(
            artifactRef=master,
            expectedFamilyVersion=1,
            reason="W7-06 exact master",
        ),
    )
    store.attach_artifact_family_member(
        SCOPE,
        ACTOR,
        family_id,
        f"variant-{family_id}",
        AttachArtifactFamilyMemberRequest(
            artifactRef=variant,
            expectedFamilyVersion=family.version,
            masterRef=master,
            reason="W7-06 exact variant",
        ),
    )

    policy_ref = ExactRevisionRef(
        resourceType="MediaGatePolicyRevision",
        resourceId=f"policy-{uuid.uuid4().hex[:12]}",
        revision=1,
        contentHash=_hash("policy:" + family_id),
    )
    return_mapping: dict[str, str] = {}
    definitions: list[MediaGateDefinition] = []
    for kind in MediaGateKind:
        rule = store.register_review_rule_revision(
            SCOPE,
            ACTOR,
            f"rule-{kind.value}-{family_id}",
            RegisterReviewRuleRevisionRequest(
                ruleId=f"media-{kind.value}-{family_id}",
                revision=1,
                spec={"kind": kind.value, "deterministic": True},
            ),
        )
        return_stage = f"fix-{kind.value}"
        return_mapping[f"media.{kind.value}"] = return_stage
        definitions.append(
            MediaGateDefinition(
                gateId=f"media.{kind.value}",
                kind=kind,
                ruleRef=ExactRevisionRef(
                    resourceType="EvalRuleRevision",
                    resourceId=rule.rule_id,
                    revision=rule.revision,
                    contentHash=rule.content_hash,
                ),
                returnStage=return_stage,
            )
        )
    profile = store.register_media_gate_profile(
        SCOPE,
        ACTOR,
        f"profile-{family_id}",
        RegisterMediaGateProfileRequest(
            profileId=f"profile-{family_id}",
            revision=1,
            sourceBundleRef=ExactRevisionRef(
                resourceType="BundleManifestRevision",
                resourceId="workshop-media-gates",
                revision=1,
                contentHash=_hash("bundle:" + family_id),
            ),
            signatureRef=ExactRevisionRef(
                resourceType="BundleSignatureVerification",
                resourceId="signature",
                revision=1,
                contentHash=_hash("signature:" + family_id),
            ),
            policyRef=policy_ref,
            gates=definitions,
        ),
    )
    contract_id = f"contract-{uuid.uuid4().hex[:20]}"
    contract_payload = {
        "suiteRef": {"resourceType": "EvalSuiteRevision", "resourceId": "media-suite", "revision": 1, "contentHash": "b" * 64},
        "publicationRef": None,
        "releaseGateRef": None,
        "artifactSchemaRef": {"resourceType": "Schema", "resourceId": "media-variant", "revision": "1", "authority": "aip"},
        "severityThresholds": {"error": 1.0},
        "gatePolicy": {"mode": "all"},
        "returnMapping": return_mapping,
        "overridePolicy": {"allowed": False},
    }
    contract_hash = _hash(json.dumps(contract_payload, sort_keys=True))
    contract_ref = ExactRevisionRef(
        resourceType="EvalContractRevision",
        resourceId=contract_id,
        revision=1,
        contentHash=contract_hash,
    )
    input_hash = _hash("attempt:" + family_id)
    step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
    attempt_ref = EvalStageAttemptRef(
        runId=run_id,
        stepKey="render",
        stepRunId=step_run_id,
        attempt=1,
        inputHash=input_hash,
    )
    cutoff = datetime.now(UTC).replace(microsecond=0)
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_eval_contract_head
            (org_id,project_id,contract_id,current_revision,version)
            VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, contract_id),
        )
        conn.execute(
            """INSERT INTO aip_eval_contract_revision
            (org_id,project_id,contract_id,revision,suite_ref,publication_ref,
             release_gate_ref,artifact_schema_ref,severity_thresholds,gate_policy,
             return_mapping,override_policy,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,%s::jsonb,NULL,NULL,%s::jsonb,%s::jsonb,%s::jsonb,
             %s::jsonb,%s::jsonb,%s,'frozen',%s)""",
            (
                *SCOPE.key,
                contract_id,
                json.dumps(contract_payload["suiteRef"]),
                json.dumps(contract_payload["artifactSchemaRef"]),
                json.dumps(contract_payload["severityThresholds"]),
                json.dumps(contract_payload["gatePolicy"]),
                json.dumps(return_mapping),
                json.dumps(contract_payload["overridePolicy"]),
                contract_hash,
                ACTOR,
            ),
        )
        conn.execute(
            """INSERT INTO aip_step_run
            (org_id,project_id,step_run_id,run_id,step_key,attempt,status,input_hash)
            VALUES(%s,%s,%s,%s,'render',1,'succeeded',%s)""",
            (*SCOPE.key, step_run_id, run_id, input_hash),
        )
        conn.commit()

    gate_results: list[MediaGateResultInput] = []
    for definition in definitions:
        is_failed = definition.kind is failed_gate
        report_id = f"report-{uuid.uuid4().hex[:20]}"
        report_hash = _hash(report_id)
        eval_run_id = f"eval-run-{uuid.uuid4().hex[:20]}"
        with connect(SCOPE) as conn:
            conn.execute(
                """INSERT INTO aip_eval_run
                (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
                 eval_contract_ref,subject_artifact_ref,stage_attempt_ref,gate_policy_ref,
                 evidence_cutoff_at,target_ref,dataset_ref,judge_ref,status,
                 idempotency_key,version,created_by)
                VALUES(%s,%s,%s,'media-suite',1,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                 %s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,'succeeded',%s,1,%s)""",
                (
                    *SCOPE.key,
                    eval_run_id,
                    "b" * 64,
                    json.dumps(contract_ref.model_dump(mode="json", by_alias=True)),
                    json.dumps({"resourceType": "Artifact", "resourceId": variant.artifact_id, "contentHash": variant.content_hash}),
                    json.dumps(attempt_ref.model_dump(mode="json", by_alias=True)),
                    json.dumps(policy_ref.model_dump(mode="json", by_alias=True)),
                    cutoff,
                    json.dumps({"resourceType": "Artifact", "resourceId": variant.artifact_id}),
                    json.dumps({"datasetId": "media-gates", "revision": 1}),
                    json.dumps({"judgeId": "deterministic", "revision": 1}),
                    f"eval-{eval_run_id}",
                    ACTOR,
                ),
            )
            conn.execute(
                """INSERT INTO aip_eval_report_revision
                (org_id,project_id,report_id,revision,content_hash,run_id,
                 eval_contract_ref,subject_artifact_ref,stage_attempt_ref,gate_policy_ref,
                 evidence_cutoff_at,suite_ref,target_ref,dataset_ref,judge_ref,results,
                 passed,failed,total,pass_rate,gate_passed,created_at)
                VALUES(%s,%s,%s,1,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
                 %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,1,%s,%s,%s)""",
                (
                    *SCOPE.key,
                    report_id,
                    report_hash,
                    eval_run_id,
                    json.dumps(contract_ref.model_dump(mode="json", by_alias=True)),
                    json.dumps({"resourceType": "Artifact", "resourceId": variant.artifact_id, "contentHash": variant.content_hash}),
                    json.dumps(attempt_ref.model_dump(mode="json", by_alias=True)),
                    json.dumps(policy_ref.model_dump(mode="json", by_alias=True)),
                    cutoff,
                    json.dumps(contract_payload["suiteRef"]),
                    json.dumps({"resourceType": "Artifact", "resourceId": variant.artifact_id}),
                    json.dumps({"datasetId": "media-gates", "revision": 1}),
                    json.dumps({"judgeId": "deterministic", "revision": 1}),
                    json.dumps([{"gateId": definition.gate_id, "passed": not is_failed}]),
                    0 if is_failed else 1,
                    1 if is_failed else 0,
                    0.0 if is_failed else 1.0,
                    not is_failed,
                    cutoff,
                ),
            )
            conn.commit()
        report_ref = ExactRevisionRef(
            resourceType="EvalReportRevision",
            resourceId=report_id,
            revision=1,
            contentHash=report_hash,
        )
        issue_ref = None
        if is_failed:
            issue = store.create_review_issue(
                SCOPE,
                ACTOR,
                f"issue-{report_id}",
                CreateReviewIssueRequest(
                    ruleRef=definition.rule_ref,
                    severity=ReviewSeverity.ERROR,
                    artifactRef=variant,
                    evalReportRef=report_ref,
                    location={"gateId": definition.gate_id},
                    suggestedFix=f"return to {definition.return_stage}",
                    returnStage=definition.return_stage,
                ),
            )
            issue_ref = ReviewIssueVersionRef(resourceId=issue.issue_id, version=issue.version)
        gate_results.append(
            MediaGateResultInput(
                gateId=definition.gate_id,
                outcome=MediaGateOutcome.FAILED if is_failed else MediaGateOutcome.PASSED,
                evalReportRef=report_ref,
                ruleRef=definition.rule_ref,
                issueRef=issue_ref,
            )
        )
    request = AssembleMediaGateSetRequest(
        reviewCycleId=f"cycle-{uuid.uuid4().hex[:20]}",
        artifactRef=variant,
        evalContractRef=contract_ref,
        gateProfileRef=ExactRevisionRef(
            resourceType="MediaGateProfileRevision",
            resourceId=profile.profile_id,
            revision=profile.revision,
            contentHash=profile.content_hash,
        ),
        policyRef=policy_ref,
        cutoffAt=cutoff,
        stageAttemptRef=attempt_ref,
        gateResults=gate_results,
    )
    return store, request


def test_four_exact_passed_gates_are_eligible_but_do_not_approve(client) -> None:
    store, request = _authority(client)
    decision = store.assemble_media_gate_set(
        SCOPE, ACTOR, f"assemble-{uuid.uuid4().hex}", request
    )
    assert decision.readiness.value == "ready"
    assert decision.eligible_for_approval is True
    assert decision.blocker_codes == []
    assert len(decision.gate_results) == 4
    with pytest.raises(ProductionContractNotFound):
        store.get_media_gate_set(ISOLATION_SCOPE, decision.gate_set_id)


def test_failed_gate_requires_exact_issue_and_blocks_approval(client) -> None:
    store, request = _authority(client, failed_gate=MediaGateKind.COPYRIGHT)
    decision = store.assemble_media_gate_set(
        SCOPE, ACTOR, f"assemble-{uuid.uuid4().hex}", request
    )
    assert decision.readiness.value == "blocked"
    assert decision.eligible_for_approval is False
    assert decision.blocker_codes == ["MEDIA_GATE_COPYRIGHT_FAILED"]
    copyright_result = next(item for item in decision.gate_results if item.gate_id == "media.copyright")
    assert copyright_result.issue_ref is not None


def test_cross_policy_or_attempt_binding_fails_closed(client) -> None:
    store, request = _authority(client)
    drifted = request.model_copy(
        update={
            "policy_ref": request.policy_ref.model_copy(
                update={"content_hash": "f" * 64}
            )
        }
    )
    with pytest.raises(ProductionContractDependencyBlocked, match="MEDIA_GATE_POLICY_DRIFTED"):
        store.assemble_media_gate_set(
            SCOPE, ACTOR, f"assemble-{uuid.uuid4().hex}", drifted
        )


def test_w7_06_migration_chain_rls_append_only_and_fail_closed_downgrade() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert 'down_revision: str | Sequence[str] | None = "w7_003"' in text
    assert text.count("FORCE ROW LEVEL SECURITY") >= 1
    assert "aip_media_gate_profile_revision" in text
    assert "aip_contract_migration_decision" in text
    assert "aip_media_gate_set_decision" in text
    assert "cannot downgrade w7_004 with media review authority data" in text
    spec = importlib.util.spec_from_file_location("w7_004", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "w7_004"
