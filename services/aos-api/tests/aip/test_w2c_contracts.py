from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import PlanStep, ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
    ProductionContractNotFound,
)
from aos_api.aip_production_contracts import (
    AssigneeKind,
    AssigneeRef,
    BriefLifecycle,
    CompileStageTemplateRequest,
    ContractReadiness,
    Coverage,
    CreateArtifactRelationRequest,
    CreateReviewIssueRequest,
    CreateStageTemplateRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    ResponsibilityPlanRevision,
    ResponsibilitySlot,
    ReturnReviewIssueRequest,
    ReviewSeverity,
    StageApplicability,
    StageDefinition,
)
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "dev-project")
ACTOR = "test:w2c"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="aip",
    )


def _exact(kind: str, identifier: str, digest: str = HASH_A) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identifier,
        revision=1,
        content_hash=digest,
    )


def _stage(
    stage_id: str, *, depends_on: list[str] | None = None
) -> StageDefinition:
    return StageDefinition(
        stage_id=stage_id,
        title=stage_id,
        depends_on=depends_on or [],
        applicability=StageApplicability(kind="always"),
        required_slot_ids=["content.review"],
        input_schema_ref=_resource("Schema", f"{stage_id}.input"),
        output_schema_ref=_resource("Schema", f"{stage_id}.output"),
    )


def _stage_request() -> CreateStageTemplateRequest:
    return CreateStageTemplateRequest(
        profile="ecommerce-standard",
        source_bundle_ref=_exact("AssetBundleRevision", "bundle-ecommerce"),
        stages=[_stage("draft"), _stage("review", depends_on=["draft"])],
    )


def _seed_other_scope() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES('other-org','隔离组织') "
            "ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) "
            "VALUES('other-org','dev-project','隔离工作区') ON CONFLICT DO NOTHING"
        )
        conn.commit()


def _seed_review_authorities() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    artifact_ids = [f"artifact-{name}-{suffix}" for name in ("a", "b", "c")]
    evidence_id = f"evidence-{suffix}"
    eval_run_id = f"eval-run-{suffix}"
    report_id = f"eval-report-{suffix}"
    now = datetime.now(timezone.utc)
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_review_rule_revision
            (org_id,project_id,rule_id,revision,spec,content_hash,created_by)
            VALUES(%s,%s,'rule-w2c',1,'{"check":"w2c-review"}'::jsonb,%s,%s)
            ON CONFLICT DO NOTHING""",
            (*SCOPE.key, HASH_A, ACTOR),
        )
        for artifact_id, digest in zip(
            artifact_ids, (HASH_A, HASH_B, HASH_C), strict=True
        ):
            conn.execute(
                """INSERT INTO aip_artifact
                (org_id,project_id,artifact_id,artifact_type,content_hash,created_by)
                VALUES(%s,%s,%s,'content',%s,%s)""",
                (*SCOPE.key, artifact_id, digest, ACTOR),
            )
        conn.execute(
            """INSERT INTO aip_evidence
            (org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,
             source_ref,observed_at,freshness_at,content_hash,created_by)
            VALUES(%s,%s,%s,'review','{}','database','w2c-test',%s,%s,%s,%s)""",
            (*SCOPE.key, evidence_id, now, now, HASH_C, ACTOR),
        )
        conn.execute(
            """INSERT INTO aip_eval_run
            (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,
             dataset_ref,judge_ref,status,idempotency_key,created_by,started_at,finished_at)
            VALUES(%s,%s,%s,'suite-w2c',1,%s,'{}','{}','{}','succeeded',%s,%s,%s,%s)""",
            (*SCOPE.key, eval_run_id, HASH_A, eval_run_id, ACTOR, now, now),
        )
        conn.execute(
            """INSERT INTO aip_eval_report_revision
            (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
             target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
             gate_passed,created_at)
            VALUES(%s,%s,%s,1,%s,%s,'{}','{}','{}','{}','[{"case":"w2c"}]',
             1,0,1,1.0,true,%s)""",
            (*SCOPE.key, report_id, HASH_B, eval_run_id, now),
        )
        conn.commit()
    return {
        "artifact_a": artifact_ids[0],
        "artifact_b": artifact_ids[1],
        "artifact_c": artifact_ids[2],
        "evidence": evidence_id,
        "report": report_id,
    }


def _review_request(authority: dict[str, str]) -> CreateReviewIssueRequest:
    return CreateReviewIssueRequest(
        rule_ref=_exact("EvalRuleRevision", "rule-w2c"),
        severity=ReviewSeverity.ERROR,
        artifact_ref=ExactArtifactRef(
            artifact_id=authority["artifact_a"], content_hash=HASH_A
        ),
        eval_report_ref=_exact(
            "EvalReportRevision", authority["report"], HASH_B
        ),
        location={"path": "title"},
        evidence_refs=[_exact("Evidence", authority["evidence"], HASH_C)],
        suggested_fix="修正标题后重新评审",
        return_stage="draft",
    )


def test_stage_contract_rejects_unknown_predicate_and_invalid_graph() -> None:
    with pytest.raises(ValidationError):
        StageApplicability.model_validate({"kind": "python_eval", "profiles": []})
    with pytest.raises(
        ProductionContractDependencyBlocked, match="STAGE_DEPENDENCY_UNKNOWN"
    ):
        AipProductionContractStore._validate_stage_graph(
            [_stage("draft", depends_on=["missing"])]
        )
    with pytest.raises(
        ProductionContractDependencyBlocked, match="STAGE_DEPENDENCY_CYCLE"
    ):
        AipProductionContractStore._validate_stage_graph(
            [_stage("draft", depends_on=["review"]), _stage("review", depends_on=["draft"])]
        )


def test_stage_template_freeze_is_exact_append_only_and_tenant_isolated() -> None:
    _seed_other_scope()
    store = AipProductionContractStore(
        stage_template_source_resolver=lambda _scope, _ref: True
    )
    draft = store.create_stage_template(
        SCOPE, ACTOR, _key("stage-create"), _stage_request()
    )
    frozen = store.freeze_stage_template(
        SCOPE, ACTOR, draft.template_id, draft.version, _key("stage-freeze")
    )

    assert (draft.lifecycle.value, frozen.lifecycle.value) == ("draft", "frozen")
    assert frozen.content_hash == draft.content_hash
    assert frozen.seal_hash and frozen.sealed_by == ACTOR
    with pytest.raises(ProductionContractNotFound):
        store.get_stage_template(OTHER_SCOPE, draft.template_id)
    with connect(SCOPE) as conn:
        with pytest.raises(Exception, match="AIP4_APPEND_ONLY"):
            with conn.transaction():
                conn.execute(
                    """UPDATE aip_stage_template_revision SET created_by='mutated'
                    WHERE org_id=%s AND project_id=%s AND template_id=%s AND revision=1""",
                    (*SCOPE.key, draft.template_id),
                )


def test_artifact_relation_rejects_hash_drift_and_directed_cycle() -> None:
    authority = _seed_review_authorities()
    store = AipProductionContractStore()

    relation_ab = store.create_artifact_relation(
        SCOPE,
        ACTOR,
        _key("relation-ab"),
        CreateArtifactRelationRequest(
            relation_type="derived_from",
            from_artifact=ExactArtifactRef(
                artifact_id=authority["artifact_a"], content_hash=HASH_A
            ),
            to_artifact=ExactArtifactRef(
                artifact_id=authority["artifact_b"], content_hash=HASH_B
            ),
            reason="A 生成 B",
        ),
    )
    store.create_artifact_relation(
        SCOPE,
        ACTOR,
        _key("relation-bc"),
        CreateArtifactRelationRequest(
            relation_type="derived_from",
            from_artifact=ExactArtifactRef(
                artifact_id=authority["artifact_b"], content_hash=HASH_B
            ),
            to_artifact=ExactArtifactRef(
                artifact_id=authority["artifact_c"], content_hash=HASH_C
            ),
            reason="B 生成 C",
        ),
    )
    assert relation_ab.from_artifact.artifact_id == authority["artifact_a"]
    with pytest.raises(ProductionContractDependencyBlocked, match="HASH_DRIFTED"):
        store.create_artifact_relation(
            SCOPE,
            ACTOR,
            _key("relation-drift"),
            CreateArtifactRelationRequest(
                relation_type="variant_of",
                from_artifact=ExactArtifactRef(
                    artifact_id=authority["artifact_a"], content_hash=HASH_B
                ),
                to_artifact=ExactArtifactRef(
                    artifact_id=authority["artifact_b"], content_hash=HASH_B
                ),
                reason="漂移",
            ),
        )
    with pytest.raises(ProductionContractDependencyBlocked, match="CYCLE"):
        store.create_artifact_relation(
            SCOPE,
            ACTOR,
            _key("relation-cycle"),
            CreateArtifactRelationRequest(
                relation_type="derived_from",
                from_artifact=ExactArtifactRef(
                    artifact_id=authority["artifact_c"], content_hash=HASH_C
                ),
                to_artifact=ExactArtifactRef(
                    artifact_id=authority["artifact_a"], content_hash=HASH_A
                ),
                reason="禁止 C 回到 A",
            ),
        )


def test_stage_compiler_preserves_not_applicable_stage_in_canonical_plan() -> None:
    task_store = AipTaskStore()
    task = task_store.create_task(
        SCOPE, ACTOR, _key("task"), CreateTaskRequest(title="W2-C compiler")
    )
    stage_request = CreateStageTemplateRequest(
        profile="ecommerce-standard",
        source_bundle_ref=_exact("AssetBundleRevision", "bundle-ecommerce"),
        stages=[
            _stage("draft"),
            _stage("livestream", depends_on=["draft"]).model_copy(
                update={
                    "applicability": StageApplicability(
                        kind="profile_in", profiles=["livestream"]
                    )
                }
            ),
        ],
    )
    slot = ResponsibilitySlot(
        slot_id="content.review",
        responsibility_type="independent_review",
        required_capability_ids=["capability.content.review"],
        input_schema_ref=_resource("Schema", "content.review.input"),
        output_schema_ref=_resource("Schema", "content.review.output"),
        return_stage="draft",
        assignee=AssigneeRef(
            kind=AssigneeKind.AGENT_INSTANCE,
            resource_id="agent-content-w2c",
            version=1,
        ),
    )
    responsibility = ResponsibilityPlanRevision(
        tenant={"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        plan_id="responsibility-plan-w2c",
        revision=1,
        version=1,
        profile="ecommerce-standard",
        template_ref=_exact(
            "ResponsibilityTemplateRevision", "responsibility-template-w2c"
        ),
        slots=[slot],
        merge_decisions=[],
        coverage=Coverage.COMPLETE,
        uncovered_slots=[],
        content_hash=HASH_C,
        lifecycle=BriefLifecycle.FROZEN,
        readiness=ContractReadiness.READY,
        blockers=[],
        created_by=ACTOR,
        created_at=datetime.now(timezone.utc),
    )

    class CompilerStore(AipProductionContractStore):
        def get_responsibility_plan(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return responsibility

        def get_production_context(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                content_hash=HASH_B,
                lifecycle=BriefLifecycle.FROZEN,
                readiness=ContractReadiness.READY,
                task_id=task.id,
                profile="ecommerce-standard",
                responsibility_plan_ref=_exact(
                    "ResponsibilityPlanRevision", responsibility.plan_id, HASH_C
                ),
            )

    store = CompilerStore(
        stage_template_source_resolver=lambda _scope, _ref: True,
        task_store=task_store,
    )
    draft = store.create_stage_template(
        SCOPE, ACTOR, _key("stage-create"), stage_request
    )
    frozen = store.freeze_stage_template(
        SCOPE, ACTOR, draft.template_id, draft.version, _key("stage-freeze")
    )
    compile_key = _key("stage-compile")
    context_ref = _exact("ProductionContextRevision", "context-w2c", HASH_B)
    request = CompileStageTemplateRequest(
        task_id=task.id,
        expected_task_version=task.version,
        template_revision=frozen.revision,
        template_content_hash=frozen.content_hash,
        responsibility_plan_ref=_exact(
            "ResponsibilityPlanRevision", responsibility.plan_id, HASH_C
        ),
        production_context_ref=context_ref,
        profile="ecommerce-standard",
    )
    result = store.compile_stage_template(
        SCOPE, ACTOR, frozen.template_id, compile_key, request
    )
    replay = store.compile_stage_template(
        SCOPE, ACTOR, frozen.template_id, compile_key, request
    )

    assert replay.plan_ref == result.plan_ref
    assert result.production_context_ref == context_ref
    assert result.applicable_stage_ids == ["draft"]
    assert result.not_applicable_stage_ids == ["livestream"]
    with connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT steps,risk FROM aip_plan_revision
            WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*SCOPE.key, result.plan_ref.resource_id),
        ).fetchone()
    assert [step["stepKey"] for step in row["steps"]] == ["draft", "livestream"]
    compilation = row["risk"]["productionContract"]["stageCompilation"]
    assert [item["applicabilityResult"] for item in compilation] == [
        "applicable",
        "not_applicable",
    ]
    assert row["risk"]["productionContract"]["productionStartGateRequired"] is True
    assert row["risk"]["productionContract"]["productionContextRef"] == (
        context_ref.model_dump(mode="json", by_alias=True)
    )


def test_review_return_appends_one_queued_attempt_and_preserves_old_attempt() -> None:
    authority = _seed_review_authorities()
    task_store = AipTaskStore()
    task = task_store.create_task(
        SCOPE, ACTOR, _key("task"), CreateTaskRequest(title="W2-C return runtime")
    )
    plan = task_store.create_plan(
        SCOPE,
        ACTOR,
        task.id,
        _key("plan"),
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[PlanStep(step_key="draft", title="生成草稿")],
        ),
    )
    task_store.approve_plan(
        SCOPE, ACTOR, task.id, plan.revision, task.version + 1, plan.content_hash
    )
    run = task_store.create_run(
        SCOPE,
        ACTOR,
        task.id,
        _key("run"),
        CreateTaskRunRequest(
            plan_revision_id=plan.id, expected_task_version=task.version + 2
        ),
    )
    task_store.start_run(
        SCOPE,
        run.id,
        expected_run_version=run.version,
        expected_task_version=task.version + 2,
        actor=ACTOR,
        idempotency_key=_key("start"),
    )
    old_step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_step_run
            (org_id,project_id,step_run_id,run_id,step_key,attempt,status)
            VALUES(%s,%s,%s,%s,'draft',1,'failed')""",
            (*SCOPE.key, old_step_run_id, run.id),
        )
        conn.commit()

    store = AipProductionContractStore()
    issue = store.create_review_issue(
        SCOPE, ACTOR, _key("issue"), _review_request(authority)
    )
    decision = store.return_review_issue(
        SCOPE,
        ACTOR,
        issue.issue_id,
        _key("return"),
        ReturnReviewIssueRequest(
            expected_version=issue.version,
            run_id=run.id,
            target_stage="draft",
            reason="按评审意见返工",
            attempt_idempotency_key=_key("attempt"),
        ),
    )

    assert decision.attempt == 2
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT step_run_id,attempt,status FROM aip_step_run
            WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='draft'
            ORDER BY attempt""",
            (*SCOPE.key, run.id),
        ).fetchall()
    assert [(row["attempt"], row["status"]) for row in rows] == [
        (1, "failed"),
        (2, "queued"),
    ]
    assert rows[0]["step_run_id"] == old_step_run_id
    assert store.get_review_issue(SCOPE, issue.issue_id).status.value == "returned"
