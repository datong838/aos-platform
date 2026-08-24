from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.aip_contracts import PlanStep, ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
)
from aos_api.aip_production_contracts import (
    ContractReadiness,
    CreateImpactPreviewRequest,
    ExactRevisionRef,
    FreezeProductionContextRequest,
    ImpactAssessment,
    ImpactDimension,
    ImpactQuality,
    MutableAuthorityRef,
    ReviseImpactPreviewRequest,
)
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "dev-project")
HASHES = {
    "brief": "a" * 64,
    "bundle": "b" * 64,
    "eval": "c" * 64,
    "resp": "d" * 64,
    "stage": "e" * 64,
}


def _exact(kind: str, identifier: str, digest: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identifier,
        revision=1,
        content_hash=digest,
    )


def _dimension(value: object) -> ImpactDimension:
    return ImpactDimension(
        quality=ImpactQuality.MEASURED,
        value=value,
        source_refs=[
            ResourceRef(
                resource_type="Evidence",
                resource_id="w2d-authoritative",
                revision="1",
                authority="aip",
            )
        ],
        cutoff_at=datetime.now(timezone.utc),
    )


def _seed() -> tuple[CreateImpactPreviewRequest, str]:
    suffix = uuid.uuid4().hex[:12]
    brief_id = f"brief-{suffix}"
    bundle_id = f"bundle-{suffix}"
    eval_id = f"eval-{suffix}"
    responsibility_id = f"responsibility-{suffix}"
    stage_id = f"stage-{suffix}"
    template_id = f"template-{suffix}"
    instance_id = f"agent-{suffix}"
    def exact(resource_type: str, resource_id: str, content_hash: str) -> dict[str, object]:
        return {
            "resourceType": resource_type,
            "resourceId": resource_id,
            "revision": 1,
            "contentHash": content_hash,
        }

    def schema(resource_id: str) -> dict[str, object]:
        return {
            "resourceType": "Schema",
            "resourceId": resource_id,
            "revision": "1",
            "authority": "aip",
        }
    task_store = AipTaskStore()
    task = task_store.create_task(
        SCOPE,
        "test:w2d",
        f"task-{suffix}",
        CreateTaskRequest(title="W2-D impact preview"),
    )
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES('other-org','隔离组织') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
            VALUES('other-org','dev-project','隔离工作区') ON CONFLICT DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO aip_task_brief_head
            (org_id,project_id,brief_id,task_id,current_revision,version)
            VALUES(%s,%s,%s,%s,1,1)""",
            (*SCOPE.key, brief_id, task.id),
        )
        conn.execute(
            """INSERT INTO aip_task_brief_revision
            (org_id,project_id,brief_id,revision,task_id,brief_type,schema_ref,spec,
             content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,%s,'production','{}','{}',%s,'frozen','test')""",
            (*SCOPE.key, brief_id, task.id, HASHES["brief"]),
        )
        conn.execute(
            """INSERT INTO aip_evidence_bundle_revision
            (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
             item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
             license_summary,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,%s::jsonb,'[]',NOW(),'[]','complete','[]','[]','[]',
             'fresh','[]','{}',%s,'frozen','test')""",
            (
                *SCOPE.key,
                bundle_id,
                '{"resourceType":"TaskBriefRevision","resourceId":"%s","revision":1,"contentHash":"%s"}'
                % (brief_id, HASHES["brief"]),
                HASHES["bundle"],
            ),
        )
        conn.execute(
            """INSERT INTO aip_eval_contract_head
            (org_id,project_id,contract_id,current_revision,version) VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, eval_id),
        )
        conn.execute(
            """INSERT INTO aip_eval_contract_revision
            (org_id,project_id,contract_id,revision,suite_ref,artifact_schema_ref,
             severity_thresholds,gate_policy,return_mapping,override_policy,
             content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
             %s::jsonb,%s,'frozen','test')""",
            (
                *SCOPE.key,
                eval_id,
                json.dumps(exact("EvalSuiteRevision", f"suite-{suffix}", "6" * 64)),
                json.dumps(schema(f"artifact-{suffix}")),
                json.dumps({"critical": 1.0}),
                json.dumps({"mode": "all"}),
                json.dumps({"critical": "draft"}),
                json.dumps({"allowed": False}),
                HASHES["eval"],
            ),
        )
        conn.execute(
            """INSERT INTO aip_responsibility_plan_head
            (org_id,project_id,plan_id,current_revision,version) VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, responsibility_id),
        )
        conn.execute(
            """INSERT INTO aip_responsibility_plan_revision
            (org_id,project_id,plan_id,revision,profile,template_ref,slots,
             merge_decisions,content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,1,'ecommerce',%s::jsonb,%s::jsonb,'[]',%s,'frozen','test')""",
            (
                *SCOPE.key,
                responsibility_id,
                json.dumps(exact("ResponsibilityTemplateRevision", f"responsibility-template-{suffix}", "7" * 64)),
                json.dumps(
                    [
                        {
                            "slotId": "production.execute",
                            "responsibilityType": "production_execution",
                            "requiredCapabilityIds": ["capability.production.execute"],
                            "inputSchemaRef": schema(f"production-input-{suffix}"),
                            "outputSchemaRef": schema(f"production-output-{suffix}"),
                            "gateRefs": [],
                            "returnStage": "prepare",
                            "assignee": {
                                "kind": "agent_instance",
                                "resourceId": instance_id,
                                "version": 1,
                            },
                        }
                    ]
                ),
                HASHES["resp"],
            ),
        )
        conn.execute(
            """INSERT INTO aip_stage_template_head
            (org_id,project_id,template_id,current_revision,version) VALUES(%s,%s,%s,1,1)""",
            (*SCOPE.key, stage_id),
        )
        conn.execute(
            """INSERT INTO aip_stage_template_revision
            (org_id,project_id,template_id,revision,profile,source_bundle_ref,stages,
             content_hash,lifecycle,sealed_by,sealed_at,seal_hash,created_by)
            VALUES(%s,%s,%s,1,'ecommerce','{}','[{}]',%s,'frozen','test',NOW(),%s,'test')""",
            (*SCOPE.key, stage_id, HASHES["stage"], "f" * 64),
        )
        conn.execute(
            """INSERT INTO aip_agent_template_revision
            (template_id,revision,display_name,role_key,lifecycle,source_ref,
             source_license,manifest,content_hash,created_by)
            VALUES(%s,1,'W2D Agent',%s,'published','{}','internal','{}',%s,'test')""",
            (template_id, f"w2d-{suffix}", "9" * 64),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance
            (org_id,project_id,instance_id,template_id,template_revision,status,
             overlay,version,created_by)
            VALUES(%s,%s,%s,%s,1,'active','{}',1,'test')""",
            (*SCOPE.key, instance_id, template_id),
        )
        conn.commit()
    store = AipProductionContractStore()
    context = store.freeze_production_context(
        SCOPE,
        "test:w2d",
        f"context-{suffix}",
        FreezeProductionContextRequest(
            task_id=task.id,
            brief_ref=_exact("TaskBriefRevision", brief_id, HASHES["brief"]),
            evidence_bundle_ref=_exact(
                "EvidenceBundleRevision", bundle_id, HASHES["bundle"]
            ),
            eval_contract_ref=_exact(
                "EvalContractRevision", eval_id, HASHES["eval"]
            ),
            responsibility_plan_ref=_exact(
                "ResponsibilityPlanRevision", responsibility_id, HASHES["resp"]
            ),
            profile="ecommerce",
        ),
    )
    context_ref = _exact(
        "ProductionContextRevision", context.context_id, context.content_hash
    )
    plan = task_store.create_plan(
        SCOPE,
        "test:w2d",
        task.id,
        f"plan-{suffix}",
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[PlanStep(step_key="start", title="受控启动")],
            risk={
                "productionContract": {
                    "compilerVersion": "w2c.v1",
                    "productionContextRef": context_ref.model_dump(
                        mode="json", by_alias=True
                    ),
                    "productionStartGateRequired": True,
                    "productionStartGateRef": None,
                }
            },
        ),
    )
    request = CreateImpactPreviewRequest(
        task_id=task.id,
        plan_ref=_exact("PlanRevision", plan.id, plan.content_hash),
        production_context_ref=context_ref,
        brief_ref=_exact("TaskBriefRevision", brief_id, HASHES["brief"]),
        evidence_bundle_ref=_exact(
            "EvidenceBundleRevision", bundle_id, HASHES["bundle"]
        ),
        eval_contract_ref=_exact("EvalContractRevision", eval_id, HASHES["eval"]),
        responsibility_plan_ref=_exact(
            "ResponsibilityPlanRevision", responsibility_id, HASHES["resp"]
        ),
        stage_template_ref=_exact(
            "StageTemplateRevision", stage_id, HASHES["stage"]
        ),
        binding_refs=[
            MutableAuthorityRef(
                resource_type="AgentInstance", resource_id=instance_id, version=1
            )
        ],
        impact=ImpactAssessment(
            object_scope=_dimension(["Order"]),
            channel_scope=_dimension(["weapp"]),
            cost=_dimension({"amount": 1}),
            budget=_dimension({"remaining": 10}),
            risks=_dimension(["low"]),
            reversibility=_dimension({"mode": "compensate"}),
            approval_chain=_dimension(["maker", "checker"]),
            rate_capacity_kill=_dimension({"rate": 1, "killSwitch": False}),
        ),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    return request, instance_id


def test_impact_preview_create_freeze_replay_and_tenant_isolation() -> None:
    request, _ = _seed()
    store = AipProductionContractStore()
    key = f"preview-{uuid.uuid4().hex}"
    created = store.create_impact_preview(SCOPE, "test:w2d", key, request)
    replay = store.create_impact_preview(SCOPE, "test:w2d", key, request)
    assert replay.preview_id == created.preview_id
    assert created.readiness is ContractReadiness.READY
    frozen = store.freeze_impact_preview(
        SCOPE, "test:w2d", created.preview_id, 1, f"freeze-{uuid.uuid4().hex}"
    )
    assert (frozen.revision, frozen.version, frozen.lifecycle.value) == (2, 2, "frozen")
    assert frozen.content_hash == created.content_hash
    assert store.list_impact_previews(OTHER_SCOPE).count == 0
    with pytest.raises(ProductionContractIdempotencyConflict):
        changed = request.model_copy(
            update={"expires_at": request.expires_at + timedelta(minutes=1)}
        )
        store.create_impact_preview(SCOPE, "test:w2d", key, changed)


def test_frozen_preview_detects_mutable_binding_drift() -> None:
    request, instance_id = _seed()
    store = AipProductionContractStore()
    created = store.create_impact_preview(
        SCOPE, "test:w2d", f"preview-{uuid.uuid4().hex}", request
    )
    frozen = store.freeze_impact_preview(
        SCOPE, "test:w2d", created.preview_id, 1, f"freeze-{uuid.uuid4().hex}"
    )
    ref = _exact(
        "ImpactPreviewRevision", frozen.preview_id, frozen.content_hash
    ).model_copy(update={"revision": frozen.revision})
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_agent_instance SET version=2
            WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
            (*SCOPE.key, instance_id),
        )
        conn.commit()
        with pytest.raises(
            ProductionContractDependencyBlocked,
            match="DEPENDENCY_DRIFTED|SNAPSHOT_DRIFTED",
        ):
            store.assert_frozen_preview_current(conn, SCOPE, ref)


def test_impact_preview_revise_uses_version_cas_and_idempotency() -> None:
    request, _ = _seed()
    store = AipProductionContractStore()
    created = store.create_impact_preview(
        SCOPE, "test:w2d", f"preview-{uuid.uuid4().hex}", request
    )
    revise = ReviseImpactPreviewRequest(
        **request.model_dump(),
        expected_version=created.version,
    )
    key = f"revise-{uuid.uuid4().hex}"
    revised = store.revise_impact_preview(
        SCOPE, "test:w2d", created.preview_id, key, revise
    )
    replay = store.revise_impact_preview(
        SCOPE, "test:w2d", created.preview_id, key, revise
    )
    assert (revised.revision, revised.version) == (2, 2)
    assert replay.revision == revised.revision
    with pytest.raises(ProductionContractConflict, match="stale"):
        store.revise_impact_preview(
            SCOPE,
            "test:w2d",
            created.preview_id,
            f"stale-{uuid.uuid4().hex}",
            revise,
        )


def test_w2d_tables_are_force_rls_and_revision_is_append_only() -> None:
    request, _ = _seed()
    store = AipProductionContractStore()
    created = store.create_impact_preview(
        SCOPE, "test:w2d", f"preview-{uuid.uuid4().hex}", request
    )
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class
            WHERE relname IN ('aip_impact_preview_head','aip_impact_preview_revision',
                              'aip_production_start_decision') ORDER BY relname"""
        ).fetchall()
        assert len(rows) == 3
        assert all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in rows)
        with pytest.raises(Exception, match="AIP4_APPEND_ONLY"):
            with conn.transaction():
                conn.execute(
                    """UPDATE aip_impact_preview_revision SET created_by='mutated'
                    WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=1""",
                    (*SCOPE.key, created.preview_id),
                )
