"""PostgreSQL authority for W2-A task briefs and evidence bundles."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Any

from aos_api.aip_contracts import PlanStep, ResourceRef, TenantContext
from aos_api.aip_production_contracts import (
    ArtifactRelation, ArtifactRelationListResponse, BriefLifecycle,
    BuildEvidenceBundleRequest, CompileStageTemplateRequest, ContractBlocker,
    ContractReadiness, Coverage, CreateArtifactRelationRequest, CreateBriefRequest,
    CreateEvalContractRequest, CreateEvidenceBundleRequest,
    CreateResponsibilityPlanRequest, CreateReviewIssueRequest,
    CreateStageTemplateRequest, EvalContractListResponse, EvalContractRevision,
    EvidenceBundleListResponse, EvidenceBundleRevision, ExactArtifactRef,
    ExactRevisionRef, Freshness, ImpactPreviewListResponse, ImpactPreviewRevision,
    CreateImpactPreviewRequest, ReviseImpactPreviewRequest,
    ResolveReviewIssueRequest, ResponsibilityPlanListResponse,
    ResponsibilityPlanRevision, ReturnDecision, ReturnReviewIssueRequest,
    ReviseBriefRequest, ReviseEvalContractRequest,
    ReviseResponsibilityPlanRequest, ReviseStageTemplateRequest, ReviewIssue,
    ReviewIssueListResponse, ReviewIssueStatus, StageCompilationResult,
    StageDefinition, StageTemplateListResponse, StageTemplateRevision,
    TaskBriefListResponse, TaskBriefRevision,
)
from aos_api.aip_task_models import CreatePlanRevisionRequest
from aos_api.aip_task_store import (
    AipTaskIdempotencyConflict,
    AipTaskNotFound,
    AipTaskStore,
    AipTaskStoreError,
    AipTaskTransitionBlocked,
    AipTaskVersionConflict,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]
ResponsibilityTemplateResolver = Callable[[TenantScope, ExactRevisionRef], bool]
StageTemplateSourceResolver = Callable[[TenantScope, ExactRevisionRef], bool]


class ProductionContractError(RuntimeError):
    code = "AIP_PRODUCTION_CONTRACT_ERROR"


class ProductionContractNotFound(ProductionContractError):
    code = "AIP_RESOURCE_NOT_FOUND"


class ProductionContractConflict(ProductionContractError):
    code = "AIP_VERSION_CONFLICT"


class ProductionContractIdempotencyConflict(ProductionContractError):
    code = "AIP_IDEMPOTENCY_CONFLICT"


class ProductionContractDependencyBlocked(ProductionContractError):
    code = "AIP_DEPENDENCY_BLOCKED"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_action_binding_hash(
    *,
    org_id: str,
    project_id: str,
    preview_id: str,
    revision: int,
    content_hash: str,
    dependency_snapshot_hash: str,
    binding_refs: Any,
    capability_ref: Any,
    account_ref: Any,
    expires_at: Any,
) -> str:
    """W-L18: server-owned Preview↔Action joint binding hash (ADR 42 §4 subset)."""
    return canonical_hash(
        {
            "tenant": {"orgId": org_id, "projectId": project_id},
            "previewId": preview_id,
            "revision": int(revision),
            "contentHash": content_hash,
            "dependencySnapshotHash": dependency_snapshot_hash,
            "bindingRefs": binding_refs,
            "capabilityRef": capability_ref,
            "accountRef": account_ref,
            "expiresAt": expires_at,
        }
    )


class AipProductionContractStore:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        responsibility_template_resolver: ResponsibilityTemplateResolver | None = None,
        stage_template_source_resolver: StageTemplateSourceResolver | None = None,
        task_store: AipTaskStore | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._responsibility_template_resolver = responsibility_template_resolver
        self._stage_template_source_resolver = stage_template_source_resolver
        self._task_store = task_store or AipTaskStore(self._connect_factory)

    def create_eval_contract(self, scope: TenantScope, actor: str, key: str,
                             body: CreateEvalContractRequest) -> EvalContractRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "eval_contract.create", key, request_hash)
            if replay:
                return self.get_eval_contract(scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            self._require_eval_suite(conn, scope, body.suite_ref)
            contract_id = f"eval-contract-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash(payload)
            conn.execute("INSERT INTO aip_eval_contract_head(org_id,project_id,contract_id,current_revision,version) VALUES(%s,%s,%s,1,1)", (*scope.key, contract_id))
            row = self._insert_eval(conn, scope, contract_id, 1, actor, body, content_hash, BriefLifecycle.DRAFT)
            self._receipt(conn, scope, "eval_contract.create", key, request_hash,
                {"resourceType":"EvalContractRevision","resourceId":contract_id,"revision":1,"contentHash":content_hash}, actor)
            conn.commit()
            return self._eval_contract(scope, row, 1, conn)

    def revise_eval_contract(self, scope: TenantScope, actor: str, contract_id: str,
                             key: str, body: ReviseEvalContractRequest) -> EvalContractRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"contractId": contract_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "eval_contract.revise", key, request_hash)
            if replay:
                return self.get_eval_contract(scope, contract_id, int(replay["revision"]), conn=conn)
            head = self._head(conn, scope, "aip_eval_contract_head", "contract_id", contract_id)
            if not head:
                raise ProductionContractNotFound("eval contract not found")
            if int(head["version"]) != body.expected_version:
                raise ProductionContractConflict("stale eval contract version")
            current = self.get_eval_contract(scope, contract_id, int(head["current_revision"]), conn=conn)
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("only a draft eval contract can be revised")
            self._require_eval_suite(conn, scope, body.suite_ref)
            revision = int(head["current_revision"]) + 1
            content = body.model_dump(mode="json", by_alias=True, exclude={"expected_version"})
            content_hash = canonical_hash(content)
            row = self._insert_eval(conn, scope, contract_id, revision, actor, body, content_hash, BriefLifecycle.DRAFT)
            self._advance_head(conn, scope, "aip_eval_contract_head", "contract_id", contract_id, revision)
            self._receipt(conn, scope, "eval_contract.revise", key, request_hash,
                {"resourceType":"EvalContractRevision","resourceId":contract_id,"revision":revision,"contentHash":content_hash}, actor)
            conn.commit()
            return self._eval_contract(scope, row, int(head["version"]) + 1, conn)

    def freeze_eval_contract(self, scope: TenantScope, actor: str, contract_id: str,
                             expected_version: int, key: str) -> EvalContractRevision:
        request_hash = canonical_hash({"contractId": contract_id, "expectedVersion": expected_version})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "eval_contract.freeze", key, request_hash)
            if replay:
                return self.get_eval_contract(scope, contract_id, int(replay["revision"]), conn=conn)
            head = self._head(conn, scope, "aip_eval_contract_head", "contract_id", contract_id)
            if not head:
                raise ProductionContractNotFound("eval contract not found")
            if int(head["version"]) != expected_version:
                raise ProductionContractConflict("stale eval contract version")
            current = self.get_eval_contract(scope, contract_id, int(head["current_revision"]), conn=conn)
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("eval contract is not a draft")
            if current.readiness is not ContractReadiness.READY:
                codes = ",".join(blocker.code for blocker in current.blockers)
                raise ProductionContractDependencyBlocked(f"EVAL_CONTRACT_NOT_READY:{codes}")
            revision = int(head["current_revision"]) + 1
            row = conn.execute("""INSERT INTO aip_eval_contract_revision
                (org_id,project_id,contract_id,revision,suite_ref,publication_ref,release_gate_ref,
                 artifact_schema_ref,severity_thresholds,gate_policy,return_mapping,override_policy,
                 content_hash,lifecycle,created_by)
                SELECT org_id,project_id,contract_id,%s,suite_ref,publication_ref,release_gate_ref,
                 artifact_schema_ref,severity_thresholds,gate_policy,return_mapping,override_policy,
                 content_hash,'frozen',%s FROM aip_eval_contract_revision
                WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s RETURNING *""",
                (revision, actor, *scope.key, contract_id, head["current_revision"])).fetchone()
            self._advance_head(conn, scope, "aip_eval_contract_head", "contract_id", contract_id, revision)
            self._receipt(conn, scope, "eval_contract.freeze", key, request_hash,
                {"resourceType":"EvalContractRevision","resourceId":contract_id,"revision":revision,"contentHash":row["content_hash"]}, actor)
            conn.commit()
            return self._eval_contract(scope, row, expected_version + 1, conn)

    def get_eval_contract(self, scope: TenantScope, contract_id: str, revision: int | None = None,
                          *, conn: Any | None = None) -> EvalContractRevision:
        def read(c: Any) -> EvalContractRevision:
            head = c.execute("SELECT * FROM aip_eval_contract_head WHERE org_id=%s AND project_id=%s AND contract_id=%s", (*scope.key, contract_id)).fetchone()
            if not head:
                raise ProductionContractNotFound("eval contract not found")
            selected = revision or int(head["current_revision"])
            row = c.execute("SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s", (*scope.key, contract_id, selected)).fetchone()
            if not row:
                raise ProductionContractNotFound("eval contract revision not found")
            return self._eval_contract(scope, row, int(head["version"]), c)
        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as c:
            return read(c)

    def list_eval_contracts(self, scope: TenantScope) -> EvalContractListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute("""SELECT revision.*,head.version FROM aip_eval_contract_head head
                JOIN aip_eval_contract_revision revision ON revision.org_id=head.org_id
                 AND revision.project_id=head.project_id AND revision.contract_id=head.contract_id
                 AND revision.revision=head.current_revision
                WHERE head.org_id=%s AND head.project_id=%s
                ORDER BY revision.created_at DESC,revision.contract_id""", scope.key).fetchall()
            items = [self._eval_contract(scope, row, int(row["version"]), conn) for row in rows]
            return EvalContractListResponse(tenant=self._tenant(scope), items=items, count=len(items))

    def create_responsibility_plan(self, scope: TenantScope, actor: str, key: str,
                                   body: CreateResponsibilityPlanRequest) -> ResponsibilityPlanRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "responsibility_plan.create", key, request_hash)
            if replay:
                return self.get_responsibility_plan(scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            self._require_responsibility_dependencies(conn, scope, body)
            plan_id = f"responsibility-plan-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash(payload)
            conn.execute("INSERT INTO aip_responsibility_plan_head(org_id,project_id,plan_id,current_revision,version) VALUES(%s,%s,%s,1,1)", (*scope.key, plan_id))
            row = self._insert_responsibility(conn, scope, plan_id, 1, actor, body, content_hash, BriefLifecycle.DRAFT)
            self._receipt(conn, scope, "responsibility_plan.create", key, request_hash,
                {"resourceType":"ResponsibilityPlanRevision","resourceId":plan_id,"revision":1,"contentHash":content_hash}, actor)
            conn.commit()
            return self._responsibility_plan(scope, row, 1, conn)

    def revise_responsibility_plan(self, scope: TenantScope, actor: str, plan_id: str,
                                   key: str, body: ReviseResponsibilityPlanRequest) -> ResponsibilityPlanRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"planId": plan_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "responsibility_plan.revise", key, request_hash)
            if replay:
                return self.get_responsibility_plan(scope, plan_id, int(replay["revision"]), conn=conn)
            head = self._head(conn, scope, "aip_responsibility_plan_head", "plan_id", plan_id)
            if not head:
                raise ProductionContractNotFound("responsibility plan not found")
            if int(head["version"]) != body.expected_version:
                raise ProductionContractConflict("stale responsibility plan version")
            current = self.get_responsibility_plan(scope, plan_id, int(head["current_revision"]), conn=conn)
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("only a draft responsibility plan can be revised")
            self._require_responsibility_dependencies(conn, scope, body)
            revision = int(head["current_revision"]) + 1
            content = body.model_dump(mode="json", by_alias=True, exclude={"expected_version"})
            content_hash = canonical_hash(content)
            row = self._insert_responsibility(conn, scope, plan_id, revision, actor, body, content_hash, BriefLifecycle.DRAFT)
            self._advance_head(conn, scope, "aip_responsibility_plan_head", "plan_id", plan_id, revision)
            self._receipt(conn, scope, "responsibility_plan.revise", key, request_hash,
                {"resourceType":"ResponsibilityPlanRevision","resourceId":plan_id,"revision":revision,"contentHash":content_hash}, actor)
            conn.commit()
            return self._responsibility_plan(scope, row, int(head["version"]) + 1, conn)

    def freeze_responsibility_plan(self, scope: TenantScope, actor: str, plan_id: str,
                                   expected_version: int, key: str) -> ResponsibilityPlanRevision:
        request_hash = canonical_hash({"planId": plan_id, "expectedVersion": expected_version})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "responsibility_plan.freeze", key, request_hash)
            if replay:
                return self.get_responsibility_plan(scope, plan_id, int(replay["revision"]), conn=conn)
            head = self._head(conn, scope, "aip_responsibility_plan_head", "plan_id", plan_id)
            if not head:
                raise ProductionContractNotFound("responsibility plan not found")
            if int(head["version"]) != expected_version:
                raise ProductionContractConflict("stale responsibility plan version")
            current = self.get_responsibility_plan(scope, plan_id, int(head["current_revision"]), conn=conn)
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("responsibility plan is not a draft")
            if current.readiness is not ContractReadiness.READY:
                codes = ",".join(blocker.code for blocker in current.blockers)
                raise ProductionContractDependencyBlocked(f"RESPONSIBILITY_PLAN_NOT_READY:{codes}")
            revision = int(head["current_revision"]) + 1
            row = conn.execute("""INSERT INTO aip_responsibility_plan_revision
                (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
                 content_hash,lifecycle,created_by)
                SELECT org_id,project_id,plan_id,%s,profile,template_ref,slots,merge_decisions,
                 content_hash,'frozen',%s FROM aip_responsibility_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s RETURNING *""",
                (revision, actor, *scope.key, plan_id, head["current_revision"])).fetchone()
            self._advance_head(conn, scope, "aip_responsibility_plan_head", "plan_id", plan_id, revision)
            self._receipt(conn, scope, "responsibility_plan.freeze", key, request_hash,
                {"resourceType":"ResponsibilityPlanRevision","resourceId":plan_id,"revision":revision,"contentHash":row["content_hash"]}, actor)
            conn.commit()
            return self._responsibility_plan(scope, row, expected_version + 1, conn)

    def get_responsibility_plan(self, scope: TenantScope, plan_id: str, revision: int | None = None,
                                *, conn: Any | None = None) -> ResponsibilityPlanRevision:
        def read(c: Any) -> ResponsibilityPlanRevision:
            head = c.execute("SELECT * FROM aip_responsibility_plan_head WHERE org_id=%s AND project_id=%s AND plan_id=%s", (*scope.key, plan_id)).fetchone()
            if not head:
                raise ProductionContractNotFound("responsibility plan not found")
            selected = revision or int(head["current_revision"])
            row = c.execute("SELECT * FROM aip_responsibility_plan_revision WHERE org_id=%s AND project_id=%s AND plan_id=%s AND revision=%s", (*scope.key, plan_id, selected)).fetchone()
            if not row:
                raise ProductionContractNotFound("responsibility plan revision not found")
            return self._responsibility_plan(scope, row, int(head["version"]), c)
        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as c:
            return read(c)

    def list_responsibility_plans(self, scope: TenantScope) -> ResponsibilityPlanListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute("""SELECT revision.*,head.version FROM aip_responsibility_plan_head head
                JOIN aip_responsibility_plan_revision revision ON revision.org_id=head.org_id
                 AND revision.project_id=head.project_id AND revision.plan_id=head.plan_id
                 AND revision.revision=head.current_revision
                WHERE head.org_id=%s AND head.project_id=%s
                ORDER BY revision.created_at DESC,revision.plan_id""", scope.key).fetchall()
            items = [self._responsibility_plan(scope, row, int(row["version"]), conn) for row in rows]
            return ResponsibilityPlanListResponse(tenant=self._tenant(scope), items=items, count=len(items))

    def create_impact_preview(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: CreateImpactPreviewRequest,
    ) -> ImpactPreviewRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "impact_preview.create", key, request_hash)
            if replay:
                return self.get_impact_preview(
                    scope, replay["resourceId"], int(replay["revision"]), conn=conn
                )
            self._require_task_plan(conn, scope, body)
            preview_id = f"impact-preview-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash(payload)
            snapshot, blockers, readiness = self._preview_dependency_state(
                conn, scope, body
            )
            conn.execute(
                """INSERT INTO aip_impact_preview_head
                (org_id,project_id,preview_id,current_revision,version)
                VALUES(%s,%s,%s,1,1)""",
                (*scope.key, preview_id),
            )
            row = self._insert_impact_preview(
                conn,
                scope,
                preview_id,
                1,
                actor,
                body,
                content_hash,
                snapshot,
                blockers,
                readiness,
                BriefLifecycle.DRAFT,
            )
            self._receipt(
                conn,
                scope,
                "impact_preview.create",
                key,
                request_hash,
                {
                    "resourceType": "ImpactPreviewRevision",
                    "resourceId": preview_id,
                    "revision": 1,
                    "contentHash": content_hash,
                },
                actor,
            )
            conn.commit()
            return self._impact_preview(scope, row, 1)

    def revise_impact_preview(
        self,
        scope: TenantScope,
        actor: str,
        preview_id: str,
        key: str,
        body: ReviseImpactPreviewRequest,
    ) -> ImpactPreviewRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"previewId": preview_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "impact_preview.revise", key, request_hash)
            if replay:
                return self.get_impact_preview(
                    scope, preview_id, int(replay["revision"]), conn=conn
                )
            head = self._head(
                conn, scope, "aip_impact_preview_head", "preview_id", preview_id
            )
            if not head:
                raise ProductionContractNotFound("impact preview not found")
            if int(head["version"]) != body.expected_version:
                raise ProductionContractConflict("stale impact preview version")
            current = self.get_impact_preview(
                scope, preview_id, int(head["current_revision"]), conn=conn
            )
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("only a draft impact preview can be revised")
            self._require_task_plan(conn, scope, body)
            revision = int(head["current_revision"]) + 1
            content = body.model_dump(
                mode="json", by_alias=True, exclude={"expected_version"}
            )
            content_hash = canonical_hash(content)
            snapshot, blockers, readiness = self._preview_dependency_state(
                conn, scope, body
            )
            row = self._insert_impact_preview(
                conn,
                scope,
                preview_id,
                revision,
                actor,
                body,
                content_hash,
                snapshot,
                blockers,
                readiness,
                BriefLifecycle.DRAFT,
            )
            self._advance_head(
                conn,
                scope,
                "aip_impact_preview_head",
                "preview_id",
                preview_id,
                revision,
            )
            self._receipt(
                conn,
                scope,
                "impact_preview.revise",
                key,
                request_hash,
                {
                    "resourceType": "ImpactPreviewRevision",
                    "resourceId": preview_id,
                    "revision": revision,
                    "contentHash": content_hash,
                },
                actor,
            )
            conn.commit()
            return self._impact_preview(scope, row, int(head["version"]) + 1)

    def freeze_impact_preview(
        self,
        scope: TenantScope,
        actor: str,
        preview_id: str,
        expected_version: int,
        key: str,
    ) -> ImpactPreviewRevision:
        request_hash = canonical_hash(
            {"previewId": preview_id, "expectedVersion": expected_version}
        )
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "impact_preview.freeze", key, request_hash)
            if replay:
                return self.get_impact_preview(
                    scope, preview_id, int(replay["revision"]), conn=conn
                )
            head = self._head(
                conn, scope, "aip_impact_preview_head", "preview_id", preview_id
            )
            if not head:
                raise ProductionContractNotFound("impact preview not found")
            if int(head["version"]) != expected_version:
                raise ProductionContractConflict("stale impact preview version")
            current = self.get_impact_preview(
                scope, preview_id, int(head["current_revision"]), conn=conn
            )
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("impact preview is not a draft")
            body = CreateImpactPreviewRequest.model_validate(
                current.model_dump(
                    mode="json",
                    by_alias=True,
                    include=set(CreateImpactPreviewRequest.model_fields),
                )
            )
            snapshot, blockers, readiness = self._preview_dependency_state(
                conn, scope, body
            )
            if readiness is not ContractReadiness.READY:
                codes = ",".join(blocker.code for blocker in blockers)
                raise ProductionContractDependencyBlocked(
                    f"IMPACT_PREVIEW_NOT_READY:{codes}"
                )
            revision = int(head["current_revision"]) + 1
            row = self._insert_impact_preview(
                conn,
                scope,
                preview_id,
                revision,
                actor,
                body,
                current.content_hash,
                snapshot,
                blockers,
                readiness,
                BriefLifecycle.FROZEN,
                frozen_by=actor,
            )
            self._advance_head(
                conn,
                scope,
                "aip_impact_preview_head",
                "preview_id",
                preview_id,
                revision,
            )
            self._receipt(
                conn,
                scope,
                "impact_preview.freeze",
                key,
                request_hash,
                {
                    "resourceType": "ImpactPreviewRevision",
                    "resourceId": preview_id,
                    "revision": revision,
                    "contentHash": current.content_hash,
                },
                actor,
            )
            conn.commit()
            return self._impact_preview(scope, row, expected_version + 1)

    def get_impact_preview(
        self,
        scope: TenantScope,
        preview_id: str,
        revision: int | None = None,
        *,
        conn: Any | None = None,
    ) -> ImpactPreviewRevision:
        def read(connection: Any) -> ImpactPreviewRevision:
            head = connection.execute(
                """SELECT * FROM aip_impact_preview_head
                WHERE org_id=%s AND project_id=%s AND preview_id=%s""",
                (*scope.key, preview_id),
            ).fetchone()
            if not head:
                raise ProductionContractNotFound("impact preview not found")
            selected = revision or int(head["current_revision"])
            row = connection.execute(
                """SELECT * FROM aip_impact_preview_revision
                WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=%s""",
                (*scope.key, preview_id, selected),
            ).fetchone()
            if not row:
                raise ProductionContractNotFound("impact preview revision not found")
            return self._impact_preview(scope, row, int(head["version"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def list_impact_previews(self, scope: TenantScope) -> ImpactPreviewListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT revision.*,head.version FROM aip_impact_preview_head head
                JOIN aip_impact_preview_revision revision ON revision.org_id=head.org_id
                  AND revision.project_id=head.project_id
                  AND revision.preview_id=head.preview_id
                  AND revision.revision=head.current_revision
                WHERE head.org_id=%s AND head.project_id=%s
                ORDER BY revision.created_at DESC,revision.preview_id""",
                scope.key,
            ).fetchall()
        items = [self._impact_preview(scope, row, int(row["version"])) for row in rows]
        return ImpactPreviewListResponse(
            tenant=self._tenant(scope), items=items, count=len(items)
        )

    def assert_frozen_preview_current(
        self, conn: Any, scope: TenantScope, ref: ExactRevisionRef
    ) -> Any:
        if ref.resource_type != "ImpactPreviewRevision":
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_REF_INVALID")
        row = conn.execute(
            """SELECT * FROM aip_impact_preview_revision
            WHERE org_id=%s AND project_id=%s AND preview_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if not row:
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_MISSING")
        if row["content_hash"] != ref.content_hash:
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_HASH_DRIFTED")
        if row["lifecycle"] != "frozen" or row["readiness"] != "ready":
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_NOT_FROZEN_READY")
        if row["expires_at"] <= datetime.now(timezone.utc):
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_EXPIRED")
        body = self._impact_body(row)
        snapshot, blockers, readiness = self._preview_dependency_state(conn, scope, body)
        if blockers or readiness is not ContractReadiness.READY:
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_DEPENDENCY_DRIFTED")
        if canonical_hash(snapshot) != row["dependency_snapshot_hash"]:
            raise ProductionContractDependencyBlocked("IMPACT_PREVIEW_SNAPSHOT_DRIFTED")
        return row

    def create_stage_template(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: CreateStageTemplateRequest,
    ) -> StageTemplateRevision:
        self._validate_stage_graph(body.stages)
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "stage_template.create", key, request_hash)
            if replay:
                return self.get_stage_template(
                    scope, replay["resourceId"], int(replay["revision"]), conn=conn
                )
            template_id = f"stage-template-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash(payload)
            conn.execute(
                """INSERT INTO aip_stage_template_head
                (org_id,project_id,template_id,current_revision,version)
                VALUES(%s,%s,%s,1,1)""",
                (*scope.key, template_id),
            )
            row = self._insert_stage_template(
                conn,
                scope,
                template_id,
                1,
                actor,
                body,
                content_hash,
                BriefLifecycle.DRAFT,
            )
            self._receipt(
                conn,
                scope,
                "stage_template.create",
                key,
                request_hash,
                {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": template_id,
                    "revision": 1,
                    "contentHash": content_hash,
                },
                actor,
            )
            conn.commit()
            return self._stage_template(scope, row, 1)

    def revise_stage_template(
        self,
        scope: TenantScope,
        actor: str,
        template_id: str,
        key: str,
        body: ReviseStageTemplateRequest,
    ) -> StageTemplateRevision:
        self._validate_stage_graph(body.stages)
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"templateId": template_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "stage_template.revise", key, request_hash)
            if replay:
                return self.get_stage_template(
                    scope, template_id, int(replay["revision"]), conn=conn
                )
            head = self._head(
                conn,
                scope,
                "aip_stage_template_head",
                "template_id",
                template_id,
            )
            if not head:
                raise ProductionContractNotFound("stage template not found")
            if int(head["version"]) != body.expected_version:
                raise ProductionContractConflict("stale stage template version")
            current = self.get_stage_template(
                scope, template_id, int(head["current_revision"]), conn=conn
            )
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("only a draft stage template can be revised")
            revision = int(head["current_revision"]) + 1
            content = body.model_dump(
                mode="json", by_alias=True, exclude={"expected_version"}
            )
            content_hash = canonical_hash(content)
            row = self._insert_stage_template(
                conn,
                scope,
                template_id,
                revision,
                actor,
                body,
                content_hash,
                BriefLifecycle.DRAFT,
            )
            self._advance_head(
                conn,
                scope,
                "aip_stage_template_head",
                "template_id",
                template_id,
                revision,
            )
            self._receipt(
                conn,
                scope,
                "stage_template.revise",
                key,
                request_hash,
                {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": template_id,
                    "revision": revision,
                    "contentHash": content_hash,
                },
                actor,
            )
            conn.commit()
            return self._stage_template(scope, row, int(head["version"]) + 1)

    def freeze_stage_template(
        self,
        scope: TenantScope,
        actor: str,
        template_id: str,
        expected_version: int,
        key: str,
    ) -> StageTemplateRevision:
        request_hash = canonical_hash(
            {"templateId": template_id, "expectedVersion": expected_version}
        )
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "stage_template.freeze", key, request_hash)
            if replay:
                return self.get_stage_template(
                    scope, template_id, int(replay["revision"]), conn=conn
                )
            head = self._head(
                conn,
                scope,
                "aip_stage_template_head",
                "template_id",
                template_id,
            )
            if not head:
                raise ProductionContractNotFound("stage template not found")
            if int(head["version"]) != expected_version:
                raise ProductionContractConflict("stale stage template version")
            current = self.get_stage_template(
                scope, template_id, int(head["current_revision"]), conn=conn
            )
            if current.lifecycle is not BriefLifecycle.DRAFT:
                raise ProductionContractConflict("stage template is not a draft")
            if current.blockers:
                codes = ",".join(blocker.code for blocker in current.blockers)
                raise ProductionContractDependencyBlocked(
                    f"STAGE_TEMPLATE_NOT_READY:{codes}"
                )
            revision = int(head["current_revision"]) + 1
            sealed_at = datetime.now(timezone.utc)
            seal_hash = canonical_hash(
                {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": template_id,
                    "revision": revision,
                    "contentHash": current.content_hash,
                    "sealedBy": actor,
                    "sealedAt": sealed_at.isoformat(),
                }
            )
            row = conn.execute(
                """INSERT INTO aip_stage_template_revision
                (org_id,project_id,template_id,revision,profile,source_bundle_ref,stages,
                 content_hash,lifecycle,sealed_by,sealed_at,seal_hash,created_by)
                SELECT org_id,project_id,template_id,%s,profile,source_bundle_ref,stages,
                 content_hash,'frozen',%s,%s,%s,%s
                FROM aip_stage_template_revision
                WHERE org_id=%s AND project_id=%s AND template_id=%s AND revision=%s
                RETURNING *""",
                (
                    revision,
                    actor,
                    sealed_at,
                    seal_hash,
                    actor,
                    *scope.key,
                    template_id,
                    head["current_revision"],
                ),
            ).fetchone()
            self._advance_head(
                conn,
                scope,
                "aip_stage_template_head",
                "template_id",
                template_id,
                revision,
            )
            self._receipt(
                conn,
                scope,
                "stage_template.freeze",
                key,
                request_hash,
                {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": template_id,
                    "revision": revision,
                    "contentHash": row["content_hash"],
                },
                actor,
            )
            conn.commit()
            return self._stage_template(scope, row, expected_version + 1)

    def get_stage_template(
        self,
        scope: TenantScope,
        template_id: str,
        revision: int | None = None,
        *,
        conn: Any | None = None,
    ) -> StageTemplateRevision:
        def read(connection: Any) -> StageTemplateRevision:
            head = connection.execute(
                """SELECT * FROM aip_stage_template_head
                WHERE org_id=%s AND project_id=%s AND template_id=%s""",
                (*scope.key, template_id),
            ).fetchone()
            if not head:
                raise ProductionContractNotFound("stage template not found")
            selected = revision or int(head["current_revision"])
            row = connection.execute(
                """SELECT * FROM aip_stage_template_revision
                WHERE org_id=%s AND project_id=%s AND template_id=%s AND revision=%s""",
                (*scope.key, template_id, selected),
            ).fetchone()
            if not row:
                raise ProductionContractNotFound("stage template revision not found")
            return self._stage_template(scope, row, int(head["version"]))

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def list_stage_templates(self, scope: TenantScope) -> StageTemplateListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT revision.*,head.version
                FROM aip_stage_template_head head
                JOIN aip_stage_template_revision revision
                  ON revision.org_id=head.org_id AND revision.project_id=head.project_id
                 AND revision.template_id=head.template_id
                 AND revision.revision=head.current_revision
                WHERE head.org_id=%s AND head.project_id=%s
                ORDER BY revision.created_at DESC,revision.template_id""",
                scope.key,
            ).fetchall()
            items = [
                self._stage_template(scope, row, int(row["version"])) for row in rows
            ]
            return StageTemplateListResponse(
                tenant=self._tenant(scope), items=items, count=len(items)
            )

    def compile_stage_template(
        self,
        scope: TenantScope,
        actor: str,
        template_id: str,
        key: str,
        body: CompileStageTemplateRequest,
    ) -> StageCompilationResult:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"templateId": template_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "stage_template.compile", key, request_hash)
            if replay:
                return StageCompilationResult.model_validate(replay)
            template = self.get_stage_template(
                scope, template_id, body.template_revision, conn=conn
            )
            if template.lifecycle is not BriefLifecycle.FROZEN:
                raise ProductionContractDependencyBlocked("STAGE_TEMPLATE_NOT_FROZEN")
            if template.content_hash != body.template_content_hash:
                raise ProductionContractDependencyBlocked("STAGE_TEMPLATE_DRIFTED")
            if template.profile != body.profile:
                raise ProductionContractDependencyBlocked("STAGE_TEMPLATE_PROFILE_MISMATCH")
            if template.blockers:
                raise ProductionContractDependencyBlocked("STAGE_TEMPLATE_SOURCE_DRIFTED")
            plan = self.get_responsibility_plan(
                scope,
                body.responsibility_plan_ref.resource_id,
                body.responsibility_plan_ref.revision,
                conn=conn,
            )
            if plan.content_hash != body.responsibility_plan_ref.content_hash:
                raise ProductionContractDependencyBlocked("RESPONSIBILITY_PLAN_DRIFTED")
            if plan.lifecycle is not BriefLifecycle.FROZEN:
                raise ProductionContractDependencyBlocked("RESPONSIBILITY_PLAN_NOT_FROZEN")
            if (
                plan.readiness is not ContractReadiness.READY
                or plan.coverage is not Coverage.COMPLETE
            ):
                raise ProductionContractDependencyBlocked("RESPONSIBILITY_PLAN_NOT_READY")
            if plan.profile != body.profile:
                raise ProductionContractDependencyBlocked("RESPONSIBILITY_PROFILE_MISMATCH")

            slot_ids = {slot.slot_id for slot in plan.slots}
            missing_slots = sorted(
                {
                    slot_id
                    for stage in template.stages
                    for slot_id in stage.required_slot_ids
                    if slot_id not in slot_ids
                }
            )
            if missing_slots:
                raise ProductionContractDependencyBlocked(
                    "STAGE_REQUIRED_SLOT_MISSING:" + ",".join(missing_slots)
                )
            applicable: list[str] = []
            not_applicable: list[str] = []
            stage_compilation: list[dict[str, Any]] = []
            steps: list[PlanStep] = []
            dependencies: list[dict[str, Any]] = []
            for stage in template.stages:
                is_applicable = (
                    stage.applicability.kind.value == "always"
                    or body.profile in stage.applicability.profiles
                )
                (applicable if is_applicable else not_applicable).append(stage.stage_id)
                stage_compilation.append(
                    {
                        **stage.model_dump(mode="json", by_alias=True),
                        "applicabilityResult": (
                            "applicable" if is_applicable else "not_applicable"
                        ),
                        "evaluatedProfile": body.profile,
                    }
                )
                steps.append(
                    PlanStep(
                        step_key=stage.stage_id,
                        title=stage.title,
                        input_refs=[stage.input_schema_ref],
                    )
                )
                dependencies.extend(
                    {"from": dependency, "to": stage.stage_id}
                    for dependency in stage.depends_on
                )

        production_risk = {
            "productionContract": {
                "compilerVersion": "w2c.v1",
                "stageTemplateRef": {
                    "resourceType": "StageTemplateRevision",
                    "resourceId": template.template_id,
                    "revision": template.revision,
                    "contentHash": template.content_hash,
                },
                "responsibilityPlanRef": body.responsibility_plan_ref.model_dump(
                    mode="json", by_alias=True
                ),
                "stageCompilation": stage_compilation,
                "productionStartGateRequired": True,
                "productionStartGateRef": None,
            }
        }
        plan_key = "w2c-" + canonical_hash(
            {"templateId": template_id, "idempotencyKey": key}
        )[:48]
        try:
            canonical_plan = self._task_store.create_plan(
                scope,
                actor,
                body.task_id,
                plan_key,
                CreatePlanRevisionRequest(
                    expected_task_version=body.expected_task_version,
                    steps=steps,
                    dependencies=dependencies,
                    risk=production_risk,
                ),
            )
        except (AipTaskNotFound, AipTaskVersionConflict) as exc:
            raise ProductionContractConflict(str(exc)) from exc
        except AipTaskIdempotencyConflict as exc:
            raise ProductionContractIdempotencyConflict(str(exc)) from exc
        except AipTaskTransitionBlocked as exc:
            raise ProductionContractDependencyBlocked(str(exc)) from exc
        except AipTaskStoreError as exc:
            raise ProductionContractError(str(exc)) from exc

        result = StageCompilationResult(
            tenant=self._tenant(scope),
            task_id=body.task_id,
            template_ref=ExactRevisionRef(
                resource_type="StageTemplateRevision",
                resource_id=template.template_id,
                revision=template.revision,
                content_hash=template.content_hash,
            ),
            responsibility_plan_ref=body.responsibility_plan_ref,
            plan_ref=ExactRevisionRef(
                resource_type="PlanRevision",
                resource_id=canonical_plan.id,
                revision=canonical_plan.revision,
                content_hash=canonical_plan.content_hash,
            ),
            compiler_version="w2c.v1",
            applicable_stage_ids=applicable,
            not_applicable_stage_ids=not_applicable,
            created_at=canonical_plan.created_at,
        )
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "stage_template.compile", key, request_hash)
            if replay:
                return StageCompilationResult.model_validate(replay)
            self._receipt(
                conn,
                scope,
                "stage_template.compile",
                key,
                request_hash,
                result.model_dump(mode="json", by_alias=True),
                actor,
            )
            conn.commit()
        return result

    def create_artifact_relation(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: CreateArtifactRelationRequest,
    ) -> ArtifactRelation:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "artifact_relation.create", key, request_hash)
            if replay:
                return self.get_artifact_relation(scope, replay["resourceId"], conn=conn)
            self._require_artifact(conn, scope, body.from_artifact)
            self._require_artifact(conn, scope, body.to_artifact)
            cycle = conn.execute(
                """WITH RECURSIVE reachable(artifact_id) AS (
                  SELECT to_artifact_id FROM aip_artifact_relation
                   WHERE org_id=%s AND project_id=%s AND from_artifact_id=%s
                  UNION
                  SELECT relation.to_artifact_id FROM aip_artifact_relation relation
                  JOIN reachable path ON relation.from_artifact_id=path.artifact_id
                   WHERE relation.org_id=%s AND relation.project_id=%s)
                SELECT 1 FROM reachable WHERE artifact_id=%s LIMIT 1""",
                (
                    *scope.key,
                    body.to_artifact.artifact_id,
                    *scope.key,
                    body.from_artifact.artifact_id,
                ),
            ).fetchone()
            if cycle:
                raise ProductionContractDependencyBlocked("ARTIFACT_RELATION_CYCLE")
            relation_id = f"artifact-relation-{uuid.uuid4().hex[:20]}"
            row = conn.execute(
                """INSERT INTO aip_artifact_relation
                (org_id,project_id,relation_id,relation_type,from_artifact_id,
                 from_content_hash,to_artifact_id,to_content_hash,reason,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    relation_id,
                    body.relation_type.value,
                    body.from_artifact.artifact_id,
                    body.from_artifact.content_hash,
                    body.to_artifact.artifact_id,
                    body.to_artifact.content_hash,
                    body.reason,
                    actor,
                ),
            ).fetchone()
            self._receipt(
                conn,
                scope,
                "artifact_relation.create",
                key,
                request_hash,
                {"resourceType": "ArtifactRelation", "resourceId": relation_id},
                actor,
            )
            conn.commit()
            return self._artifact_relation(scope, row)

    def get_artifact_relation(
        self,
        scope: TenantScope,
        relation_id: str,
        *,
        conn: Any | None = None,
    ) -> ArtifactRelation:
        def read(connection: Any) -> ArtifactRelation:
            row = connection.execute(
                """SELECT * FROM aip_artifact_relation
                WHERE org_id=%s AND project_id=%s AND relation_id=%s""",
                (*scope.key, relation_id),
            ).fetchone()
            if not row:
                raise ProductionContractNotFound("artifact relation not found")
            return self._artifact_relation(scope, row)

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def list_artifact_relations(
        self, scope: TenantScope
    ) -> ArtifactRelationListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_artifact_relation
                WHERE org_id=%s AND project_id=%s
                ORDER BY created_at DESC,relation_id""",
                scope.key,
            ).fetchall()
            items = [self._artifact_relation(scope, row) for row in rows]
            return ArtifactRelationListResponse(
                tenant=self._tenant(scope), items=items, count=len(items)
            )

    def create_review_issue(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: CreateReviewIssueRequest,
    ) -> ReviewIssue:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "review_issue.create", key, request_hash)
            if replay:
                return self.get_review_issue(scope, replay["resourceId"], conn=conn)
            self._require_artifact(conn, scope, body.artifact_ref)
            self._require_eval_report(conn, scope, body.eval_report_ref)
            self._require_evidence(conn, scope, body.evidence_refs)
            issue_id = f"review-issue-{uuid.uuid4().hex[:20]}"
            row = conn.execute(
                """INSERT INTO aip_review_issue
                (org_id,project_id,issue_id,rule_ref,severity,artifact_id,artifact_hash,
                 eval_report_id,eval_report_revision,eval_report_hash,location,evidence_refs,
                 suggested_fix,return_stage,status,version,created_by,updated_by)
                VALUES(%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                 %s,%s,'open',1,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    issue_id,
                    self._json(payload["ruleRef"]),
                    body.severity.value,
                    body.artifact_ref.artifact_id,
                    body.artifact_ref.content_hash,
                    body.eval_report_ref.resource_id,
                    body.eval_report_ref.revision,
                    body.eval_report_ref.content_hash,
                    self._json(body.location),
                    self._json(payload["evidenceRefs"]),
                    body.suggested_fix,
                    body.return_stage,
                    actor,
                    actor,
                ),
            ).fetchone()
            self._review_event(
                conn,
                scope,
                issue_id,
                1,
                "opened",
                1,
                payload,
                actor,
            )
            self._receipt(
                conn,
                scope,
                "review_issue.create",
                key,
                request_hash,
                {"resourceType": "ReviewIssue", "resourceId": issue_id, "version": 1},
                actor,
            )
            conn.commit()
            return self._review_issue(scope, row)

    def get_review_issue(
        self,
        scope: TenantScope,
        issue_id: str,
        *,
        conn: Any | None = None,
        for_update: bool = False,
    ) -> ReviewIssue:
        def read(connection: Any) -> ReviewIssue:
            suffix = " FOR UPDATE" if for_update else ""
            row = connection.execute(
                """SELECT * FROM aip_review_issue
                WHERE org_id=%s AND project_id=%s AND issue_id=%s""" + suffix,
                (*scope.key, issue_id),
            ).fetchone()
            if not row:
                raise ProductionContractNotFound("review issue not found")
            return self._review_issue(scope, row)

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def list_review_issues(self, scope: TenantScope) -> ReviewIssueListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_review_issue
                WHERE org_id=%s AND project_id=%s
                ORDER BY updated_at DESC,issue_id""",
                scope.key,
            ).fetchall()
            items = [self._review_issue(scope, row) for row in rows]
            return ReviewIssueListResponse(
                tenant=self._tenant(scope), items=items, count=len(items)
            )

    def resolve_review_issue(
        self,
        scope: TenantScope,
        actor: str,
        issue_id: str,
        key: str,
        body: ResolveReviewIssueRequest,
    ) -> ReviewIssue:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"issueId": issue_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "review_issue.resolve", key, request_hash)
            if replay:
                return self.get_review_issue(scope, issue_id, conn=conn)
            current = self.get_review_issue(
                scope, issue_id, conn=conn, for_update=True
            )
            if current.status is not ReviewIssueStatus.OPEN:
                raise ProductionContractConflict("review issue is not open")
            if current.version != body.expected_version:
                raise ProductionContractConflict("stale review issue version")
            row = conn.execute(
                """UPDATE aip_review_issue SET status='resolved',version=version+1,
                 updated_by=%s,updated_at=NOW()
                WHERE org_id=%s AND project_id=%s AND issue_id=%s AND version=%s
                RETURNING *""",
                (actor, *scope.key, issue_id, body.expected_version),
            ).fetchone()
            self._review_event(
                conn,
                scope,
                issue_id,
                2,
                "resolved",
                body.expected_version + 1,
                payload,
                actor,
            )
            self._receipt(
                conn,
                scope,
                "review_issue.resolve",
                key,
                request_hash,
                {
                    "resourceType": "ReviewIssue",
                    "resourceId": issue_id,
                    "version": body.expected_version + 1,
                },
                actor,
            )
            conn.commit()
            return self._review_issue(scope, row)

    def return_review_issue(
        self,
        scope: TenantScope,
        actor: str,
        issue_id: str,
        key: str,
        body: ReturnReviewIssueRequest,
    ) -> ReturnDecision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash({"issueId": issue_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "review_issue.return", key, request_hash)
            if replay:
                return self._return_decision_by_id(
                    scope, replay["resourceId"], conn=conn
                )
            issue = self.get_review_issue(
                scope, issue_id, conn=conn, for_update=True
            )
            if issue.status is not ReviewIssueStatus.OPEN:
                raise ProductionContractConflict("review issue is not open")
            if issue.version != body.expected_version:
                raise ProductionContractConflict("stale review issue version")
            if issue.return_stage != body.target_stage:
                raise ProductionContractDependencyBlocked("RETURN_STAGE_MISMATCH")
            self._require_artifact(conn, scope, issue.artifact_ref)
            self._require_eval_report(conn, scope, issue.eval_report_ref)
            self._require_evidence(conn, scope, issue.evidence_refs)
            run = conn.execute(
                """SELECT run.*,task.status AS task_status,task.version AS task_version
                FROM aip_task_run run
                JOIN aip_task task ON task.org_id=run.org_id AND task.project_id=run.project_id
                 AND task.task_id=run.task_id
                WHERE run.org_id=%s AND run.project_id=%s AND run.run_id=%s
                FOR UPDATE OF run,task""",
                (*scope.key, body.run_id),
            ).fetchone()
            if not run or run["status"] != "running" or run["task_status"] != "executing":
                raise ProductionContractDependencyBlocked("RETURN_TARGET_NOT_RUNNING")
            plan = conn.execute(
                """SELECT steps FROM aip_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
                (*scope.key, run["plan_revision_id"]),
            ).fetchone()
            if not plan or body.target_stage not in {
                str(item.get("stepKey")) for item in self._load(plan["steps"])
            }:
                raise ProductionContractDependencyBlocked("RETURN_STAGE_NOT_IN_PLAN")
            existing_key = conn.execute(
                """SELECT * FROM aip_return_decision
                WHERE org_id=%s AND project_id=%s AND attempt_idempotency_key=%s""",
                (*scope.key, body.attempt_idempotency_key),
            ).fetchone()
            if existing_key:
                raise ProductionContractIdempotencyConflict(
                    "attempt idempotency key already belongs to another return"
                )
            latest = conn.execute(
                """SELECT * FROM aip_step_run
                WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key=%s
                ORDER BY attempt DESC LIMIT 1 FOR UPDATE""",
                (*scope.key, body.run_id, body.target_stage),
            ).fetchone()
            if not latest:
                raise ProductionContractDependencyBlocked("RETURN_SOURCE_ATTEMPT_MISSING")
            if latest["status"] not in {"succeeded", "failed", "skipped", "unknown"}:
                raise ProductionContractDependencyBlocked("RETURN_SOURCE_ATTEMPT_NOT_TERMINAL")
            attempt = int(latest["attempt"]) + 1
            step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
            conn.execute(
                """INSERT INTO aip_step_run
                (org_id,project_id,step_run_id,run_id,step_key,attempt,status,input_refs,
                 created_at,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,'queued',%s::jsonb,NOW(),NOW())""",
                (
                    *scope.key,
                    step_run_id,
                    body.run_id,
                    body.target_stage,
                    attempt,
                    self._json(self._load(latest["input_refs"])),
                ),
            )
            decision_id = f"return-decision-{uuid.uuid4().hex[:20]}"
            decision_hash = canonical_hash(
                {
                    "issueId": issue_id,
                    "issueVersion": body.expected_version,
                    "runId": body.run_id,
                    "stepKey": body.target_stage,
                    "stepRunId": step_run_id,
                    "attempt": attempt,
                    "attemptIdempotencyKey": body.attempt_idempotency_key,
                    "reason": body.reason,
                    "actor": actor,
                }
            )
            decision = conn.execute(
                """INSERT INTO aip_return_decision
                (org_id,project_id,decision_id,issue_id,issue_version,run_id,step_key,
                 step_run_id,attempt,attempt_idempotency_key,reason,decision_hash,actor)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (
                    *scope.key,
                    decision_id,
                    issue_id,
                    body.expected_version,
                    body.run_id,
                    body.target_stage,
                    step_run_id,
                    attempt,
                    body.attempt_idempotency_key,
                    body.reason,
                    decision_hash,
                    actor,
                ),
            ).fetchone()
            conn.execute(
                """UPDATE aip_review_issue SET status='returned',version=version+1,
                 updated_by=%s,updated_at=NOW()
                WHERE org_id=%s AND project_id=%s AND issue_id=%s AND version=%s""",
                (actor, *scope.key, issue_id, body.expected_version),
            )
            self._review_event(
                conn,
                scope,
                issue_id,
                2,
                "returned",
                body.expected_version + 1,
                {**payload, "decisionHash": decision_hash, "stepRunId": step_run_id},
                actor,
            )
            self._receipt(
                conn,
                scope,
                "review_issue.return",
                key,
                request_hash,
                {
                    "resourceType": "ReturnDecision",
                    "resourceId": decision_id,
                    "contentHash": decision_hash,
                },
                actor,
            )
            conn.commit()
            return self._return_decision(scope, decision)

    def _return_decision_by_id(
        self,
        scope: TenantScope,
        decision_id: str,
        *,
        conn: Any | None = None,
    ) -> ReturnDecision:
        def read(connection: Any) -> ReturnDecision:
            row = connection.execute(
                """SELECT * FROM aip_return_decision
                WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, decision_id),
            ).fetchone()
            if not row:
                raise ProductionContractNotFound("return decision not found")
            return self._return_decision(scope, row)

        if conn is not None:
            return read(conn)
        with self._connect_factory(scope) as connection:
            return read(connection)

    def create_brief(self, scope: TenantScope, actor: str, key: str, body: CreateBriefRequest) -> TaskBriefRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "task_brief.create", key, request_hash)
            if replay:
                return self.get_brief(scope, replay["resourceId"], int(replay["revision"]), conn=conn)
            if not conn.execute("SELECT 1 FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s", (*scope.key, body.task_id)).fetchone():
                raise ProductionContractDependencyBlocked("task not found in tenant scope")
            brief_id = f"brief-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash({"briefType": body.brief_type, "schemaRef": payload["schemaRef"], "spec": body.spec})
            conn.execute("INSERT INTO aip_task_brief_head(org_id,project_id,brief_id,task_id,current_revision,version) VALUES(%s,%s,%s,%s,1,1)", (*scope.key, brief_id, body.task_id))
            row = conn.execute("""INSERT INTO aip_task_brief_revision(org_id,project_id,brief_id,revision,task_id,brief_type,schema_ref,spec,content_hash,lifecycle,created_by)
                VALUES(%s,%s,%s,1,%s,%s,%s::jsonb,%s::jsonb,%s,'draft',%s) RETURNING *""",
                (*scope.key, brief_id, body.task_id, body.brief_type, self._json(payload["schemaRef"]), self._json(body.spec), content_hash, actor)).fetchone()
            self._receipt(conn, scope, "task_brief.create", key, request_hash, {"resourceType":"TaskBriefRevision","resourceId":brief_id,"revision":1,"contentHash":content_hash}, actor)
            conn.commit()
            return self._brief(scope, row, 1)

    def revise_brief(self, scope: TenantScope, actor: str, brief_id: str, key: str, body: ReviseBriefRequest) -> TaskBriefRevision:
        payload = body.model_dump(mode="json", by_alias=True); request_hash = canonical_hash({"briefId":brief_id, **payload})
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "task_brief.revise", key, request_hash)
            if replay: return self.get_brief(scope, brief_id, int(replay["revision"]), conn=conn)
            head = conn.execute("SELECT * FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND brief_id=%s FOR UPDATE", (*scope.key, brief_id)).fetchone()
            if not head: raise ProductionContractNotFound("task brief not found")
            if int(head["version"]) != body.expected_version: raise ProductionContractConflict("stale task brief version")
            current = self.get_brief(scope, brief_id, int(head["current_revision"]), conn=conn)
            if current.lifecycle != BriefLifecycle.DRAFT: raise ProductionContractConflict("only a draft brief can be revised")
            revision = int(head["current_revision"]) + 1
            content_hash = canonical_hash({"briefType":body.brief_type,"schemaRef":payload["schemaRef"],"spec":body.spec})
            row = conn.execute("""INSERT INTO aip_task_brief_revision(org_id,project_id,brief_id,revision,task_id,brief_type,schema_ref,spec,content_hash,lifecycle,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,'draft',%s) RETURNING *""",
                (*scope.key, brief_id, revision, head["task_id"], body.brief_type, self._json(payload["schemaRef"]), self._json(body.spec), content_hash, actor)).fetchone()
            conn.execute("UPDATE aip_task_brief_head SET current_revision=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND brief_id=%s", (revision,*scope.key,brief_id))
            self._receipt(conn,scope,"task_brief.revise",key,request_hash,{"resourceType":"TaskBriefRevision","resourceId":brief_id,"revision":revision,"contentHash":content_hash},actor)
            conn.commit(); return self._brief(scope,row,int(head["version"])+1)

    def freeze_brief(self, scope: TenantScope, actor: str, brief_id: str, expected_version: int, key: str) -> TaskBriefRevision:
        request_hash=canonical_hash({"briefId":brief_id,"expectedVersion":expected_version})
        with self._connect_factory(scope) as conn:
            replay=self._replay(conn,scope,"task_brief.freeze",key,request_hash)
            if replay: return self.get_brief(scope,brief_id,int(replay["revision"]),conn=conn)
            head=conn.execute("SELECT * FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND brief_id=%s FOR UPDATE",(*scope.key,brief_id)).fetchone()
            if not head: raise ProductionContractNotFound("task brief not found")
            if int(head["version"])!=expected_version: raise ProductionContractConflict("stale task brief version")
            current=self.get_brief(scope,brief_id,int(head["current_revision"]),conn=conn)
            if current.lifecycle != BriefLifecycle.DRAFT: raise ProductionContractConflict("task brief is not a draft")
            revision=int(head["current_revision"])+1
            row=conn.execute("""INSERT INTO aip_task_brief_revision(org_id,project_id,brief_id,revision,task_id,brief_type,schema_ref,spec,content_hash,lifecycle,created_by)
                SELECT org_id,project_id,brief_id,%s,task_id,brief_type,schema_ref,spec,content_hash,'frozen',%s
                FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=%s RETURNING *""",
                (revision,actor,*scope.key,brief_id,head["current_revision"])).fetchone()
            conn.execute("UPDATE aip_task_brief_head SET current_revision=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND brief_id=%s",(revision,*scope.key,brief_id))
            self._receipt(conn,scope,"task_brief.freeze",key,request_hash,{"resourceType":"TaskBriefRevision","resourceId":brief_id,"revision":int(row["revision"]),"contentHash":row["content_hash"]},actor)
            conn.commit(); return self._brief(scope,row,expected_version+1)

    def get_brief(self, scope: TenantScope, brief_id: str, revision: int | None = None, *, conn: Any | None = None) -> TaskBriefRevision:
        def read(c: Any) -> TaskBriefRevision:
            head=c.execute("SELECT * FROM aip_task_brief_head WHERE org_id=%s AND project_id=%s AND brief_id=%s",(*scope.key,brief_id)).fetchone()
            if not head: raise ProductionContractNotFound("task brief not found")
            rev=revision or int(head["current_revision"])
            row=c.execute("SELECT * FROM aip_task_brief_revision WHERE org_id=%s AND project_id=%s AND brief_id=%s AND revision=%s",(*scope.key,brief_id,rev)).fetchone()
            if not row: raise ProductionContractNotFound("task brief revision not found")
            return self._brief(scope,row,int(head["version"]))
        if conn is not None: return read(conn)
        with self._connect_factory(scope) as c: return read(c)

    def list_briefs(self, scope: TenantScope) -> TaskBriefListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT revision.*, head.version
                FROM aip_task_brief_head head
                JOIN aip_task_brief_revision revision
                  ON revision.org_id=head.org_id AND revision.project_id=head.project_id
                 AND revision.brief_id=head.brief_id AND revision.revision=head.current_revision
                WHERE head.org_id=%s AND head.project_id=%s
                ORDER BY revision.created_at DESC, revision.brief_id""",
                scope.key,
            ).fetchall()
            items = [self._brief(scope, row, int(row["version"])) for row in rows]
            return TaskBriefListResponse(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                items=items,
                count=len(items),
            )

    def create_evidence_bundle(self, scope: TenantScope, actor: str, key: str, body: CreateEvidenceBundleRequest) -> EvidenceBundleRevision:
        """W-L9: create is an alias of build; coverage is always server-owned."""
        return self.build_evidence_bundle(scope, actor, key, BuildEvidenceBundleRequest.model_validate(body.model_dump()))

    def build_evidence_bundle(
        self,
        scope: TenantScope,
        actor: str,
        key: str,
        body: BuildEvidenceBundleRequest,
    ) -> EvidenceBundleRevision:
        payload = body.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay = self._replay(conn, scope, "evidence_bundle.build", key, request_hash)
            if replay:
                return self.get_evidence_bundle(
                    scope, replay["resourceId"], int(replay["revision"]), conn=conn
                )
            # Legacy create receipt key also replays for same payload.
            legacy = self._replay(conn, scope, "evidence_bundle.create", key, request_hash)
            if legacy:
                return self.get_evidence_bundle(
                    scope, legacy["resourceId"], int(legacy["revision"]), conn=conn
                )
            brief = self.get_brief(
                scope, body.brief_ref.resource_id, body.brief_ref.revision, conn=conn
            )
            if (
                brief.lifecycle != BriefLifecycle.FROZEN
                or brief.content_hash != body.brief_ref.content_hash
            ):
                raise ProductionContractDependencyBlocked(
                    "brief exact ref is not frozen/current"
                )
            coverage, missing, conflicts, uncertainties, freshness = (
                self._compute_evidence_bundle_coverage(conn, scope, body)
            )
            authority_payload = {
                **payload,
                "coverage": coverage.value,
                "missing": missing,
                "conflicts": conflicts,
                "uncertainties": uncertainties,
                "freshness": freshness.value,
            }
            bundle_id = f"evidence-bundle-{uuid.uuid4().hex[:20]}"
            content_hash = canonical_hash(authority_payload)
            row = conn.execute(
                """INSERT INTO aip_evidence_bundle_revision(
                   org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,
                   item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,
                   license_summary,content_hash,lifecycle,created_by)
                   VALUES(%s,%s,%s,1,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,
                          %s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,'frozen',%s)
                   RETURNING *""",
                (
                    *scope.key,
                    bundle_id,
                    self._json(payload["briefRef"]),
                    self._json(payload["subjectRefs"]),
                    body.cutoff_at,
                    self._json(payload["itemRefs"]),
                    coverage.value,
                    self._json(missing),
                    self._json(conflicts),
                    self._json(uncertainties),
                    freshness.value,
                    self._json(body.marking),
                    self._json(body.license_summary),
                    content_hash,
                    actor,
                ),
            ).fetchone()
            result = {
                "resourceType": "EvidenceBundleRevision",
                "resourceId": bundle_id,
                "revision": 1,
                "contentHash": content_hash,
            }
            self._receipt(
                conn, scope, "evidence_bundle.build", key, request_hash, result, actor
            )
            self._receipt(
                conn, scope, "evidence_bundle.create", key, request_hash, result, actor
            )
            conn.commit()
            return self._bundle(scope, row)

    def _compute_evidence_bundle_coverage(
        self,
        conn: Any,
        scope: TenantScope,
        body: BuildEvidenceBundleRequest | CreateEvidenceBundleRequest,
    ) -> tuple[Coverage, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], Freshness]:
        required = list(body.required_fact_ids)
        provided: set[str] = set()
        providers: dict[str, list[str]] = {}
        stale = False
        cutoff = body.cutoff_at
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=timezone.utc)
        for item in body.item_refs:
            if item.resource_type != "Evidence":
                raise ProductionContractDependencyBlocked(
                    "W2-A bundles only accept Evidence refs"
                )
            row = conn.execute(
                """SELECT evidence_id,content_hash,payload,freshness_at FROM aip_evidence
                   WHERE org_id=%s AND project_id=%s AND evidence_id=%s""",
                (*scope.key, item.resource_id),
            ).fetchone()
            if not row or row["content_hash"] != item.content_hash:
                raise ProductionContractDependencyBlocked(
                    "evidence exact ref missing or drifted"
                )
            for fact_id in self._evidence_fact_ids(row["payload"]):
                provided.add(fact_id)
                providers.setdefault(fact_id, []).append(row["evidence_id"])
            freshness_at = row["freshness_at"]
            if freshness_at is not None:
                if freshness_at.tzinfo is None:
                    freshness_at = freshness_at.replace(tzinfo=timezone.utc)
                if freshness_at < cutoff:
                    stale = True
        missing = [
            {"factId": fact_id}
            for fact_id in required
            if fact_id not in provided
        ]
        conflicts = [
            {
                "factId": fact_id,
                "evidenceIds": evidence_ids,
                "code": "FACT_MULTI_SOURCE",
            }
            for fact_id, evidence_ids in sorted(providers.items())
            if len(evidence_ids) > 1 and fact_id in required
        ]
        uncertainties: list[dict[str, Any]] = []
        covered = len(required) - len(missing)
        if missing and covered == 0:
            coverage = Coverage.BLOCKED
        elif missing:
            coverage = Coverage.PARTIAL
        else:
            coverage = Coverage.COMPLETE
        freshness = Freshness.STALE if stale else Freshness.FRESH
        if coverage is Coverage.BLOCKED:
            freshness = Freshness.BLOCKED
        return coverage, missing, conflicts, uncertainties, freshness

    @staticmethod
    def _evidence_fact_ids(payload: Any) -> list[str]:
        value = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(value, dict):
            return []
        raw = value.get("factIds")
        if raw is None:
            raw = value.get("facts")
        if isinstance(raw, dict):
            return [str(key).strip() for key in raw.keys() if str(key).strip()]
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return []

    def get_evidence_bundle(self, scope: TenantScope, bundle_id: str, revision: int=1, *, conn: Any|None=None) -> EvidenceBundleRevision:
        def read(c:Any):
            row=c.execute("SELECT * FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s",(*scope.key,bundle_id,revision)).fetchone()
            if not row: raise ProductionContractNotFound("evidence bundle not found")
            return self._bundle(scope,row)
        if conn is not None:return read(conn)
        with self._connect_factory(scope) as c:return read(c)

    def list_evidence_bundles(self, scope: TenantScope) -> EvidenceBundleListResponse:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_evidence_bundle_revision
                WHERE org_id=%s AND project_id=%s
                ORDER BY created_at DESC, bundle_id, revision DESC""",
                scope.key,
            ).fetchall()
            items = [self._bundle(scope, row) for row in rows]
            return EvidenceBundleListResponse(
                tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                items=items,
                count=len(items),
            )

    @staticmethod
    def _validate_stage_graph(stages: list[StageDefinition]) -> None:
        stage_ids = {stage.stage_id for stage in stages}
        unknown = sorted(
            {
                dependency
                for stage in stages
                for dependency in stage.depends_on
                if dependency not in stage_ids
            }
        )
        if unknown:
            raise ProductionContractDependencyBlocked(
                "STAGE_DEPENDENCY_UNKNOWN:" + ",".join(unknown)
            )

        dependencies = {stage.stage_id: set(stage.depends_on) for stage in stages}
        ready = sorted(stage_id for stage_id, refs in dependencies.items() if not refs)
        visited: set[str] = set()
        while ready:
            stage_id = ready.pop(0)
            if stage_id in visited:
                continue
            visited.add(stage_id)
            for candidate, refs in dependencies.items():
                if candidate in visited or stage_id not in refs:
                    continue
                refs.remove(stage_id)
                if not refs:
                    ready.append(candidate)
            ready.sort()
        if len(visited) != len(stages):
            cyclic = sorted(stage_ids - visited)
            raise ProductionContractDependencyBlocked(
                "STAGE_DEPENDENCY_CYCLE:" + ",".join(cyclic)
            )

    def _insert_stage_template(
        self,
        conn: Any,
        scope: TenantScope,
        template_id: str,
        revision: int,
        actor: str,
        body: CreateStageTemplateRequest | ReviseStageTemplateRequest,
        content_hash: str,
        lifecycle: BriefLifecycle,
    ) -> Any:
        payload = body.model_dump(
            mode="json", by_alias=True, exclude={"expected_version"}
        )
        return conn.execute(
            """INSERT INTO aip_stage_template_revision
            (org_id,project_id,template_id,revision,profile,source_bundle_ref,stages,
             content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
            RETURNING *""",
            (
                *scope.key,
                template_id,
                revision,
                body.profile,
                self._json(payload["sourceBundleRef"]),
                self._json(payload["stages"]),
                content_hash,
                lifecycle.value,
                actor,
            ),
        ).fetchone()

    def _stage_template(
        self, scope: TenantScope, row: Any, version: int
    ) -> StageTemplateRevision:
        source_ref = ExactRevisionRef.model_validate(self._load(row["source_bundle_ref"]))
        blockers: list[ContractBlocker] = []
        if self._stage_template_source_resolver is None:
            blockers.append(
                ContractBlocker(
                    code="STAGE_SOURCE_AUTHORITY_UNAVAILABLE",
                    message="StageTemplate sourceBundleRef 权威解析器不可用",
                    resource_ref=source_ref,
                )
            )
        elif not self._stage_template_source_resolver(scope, source_ref):
            blockers.append(
                ContractBlocker(
                    code="STAGE_SOURCE_MISSING_OR_DRIFTED",
                    message="StageTemplate sourceBundleRef 缺失或 exact ref 漂移",
                    resource_ref=source_ref,
                )
            )
        return StageTemplateRevision(
            tenant=self._tenant(scope),
            template_id=row["template_id"],
            revision=int(row["revision"]),
            version=version,
            profile=row["profile"],
            source_bundle_ref=source_ref,
            stages=[StageDefinition.model_validate(item) for item in self._load(row["stages"])],
            content_hash=row["content_hash"],
            lifecycle=row["lifecycle"],
            sealed_by=row["sealed_by"],
            sealed_at=row["sealed_at"],
            seal_hash=row["seal_hash"],
            readiness=(
                ContractReadiness.READY if not blockers else ContractReadiness.BLOCKED
            ),
            blockers=blockers,
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _require_artifact(
        conn: Any, scope: TenantScope, ref: ExactArtifactRef
    ) -> None:
        row = conn.execute(
            """SELECT content_hash FROM aip_artifact
            WHERE org_id=%s AND project_id=%s AND artifact_id=%s""",
            (*scope.key, ref.artifact_id),
        ).fetchone()
        if not row or not row["content_hash"]:
            raise ProductionContractDependencyBlocked("ARTIFACT_HASH_MISSING")
        if row["content_hash"] != ref.content_hash:
            raise ProductionContractDependencyBlocked("ARTIFACT_HASH_DRIFTED")

    @staticmethod
    def _require_eval_report(
        conn: Any, scope: TenantScope, ref: ExactRevisionRef
    ) -> None:
        if ref.resource_type != "EvalReportRevision":
            raise ProductionContractDependencyBlocked("EVAL_REPORT_REF_TYPE_INVALID")
        row = conn.execute(
            """SELECT content_hash FROM aip_eval_report_revision
            WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if not row:
            raise ProductionContractDependencyBlocked("EVAL_REPORT_MISSING")
        if row["content_hash"] != ref.content_hash:
            raise ProductionContractDependencyBlocked("EVAL_REPORT_DRIFTED")

    @staticmethod
    def _require_evidence(
        conn: Any, scope: TenantScope, refs: list[ExactRevisionRef]
    ) -> None:
        for ref in refs:
            if ref.resource_type != "Evidence" or ref.revision != 1:
                raise ProductionContractDependencyBlocked("EVIDENCE_REF_INVALID")
            row = conn.execute(
                """SELECT content_hash FROM aip_evidence
                WHERE org_id=%s AND project_id=%s AND evidence_id=%s""",
                (*scope.key, ref.resource_id),
            ).fetchone()
            if not row:
                raise ProductionContractDependencyBlocked("EVIDENCE_MISSING")
            if row["content_hash"] != ref.content_hash:
                raise ProductionContractDependencyBlocked("EVIDENCE_DRIFTED")

    def _artifact_relation(self, scope: TenantScope, row: Any) -> ArtifactRelation:
        return ArtifactRelation(
            tenant=self._tenant(scope),
            relation_id=row["relation_id"],
            relation_type=row["relation_type"],
            from_artifact=ExactArtifactRef(
                artifact_id=row["from_artifact_id"],
                content_hash=row["from_content_hash"],
            ),
            to_artifact=ExactArtifactRef(
                artifact_id=row["to_artifact_id"],
                content_hash=row["to_content_hash"],
            ),
            reason=row["reason"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    def _review_event(
        self,
        conn: Any,
        scope: TenantScope,
        issue_id: str,
        sequence: int,
        event_type: str,
        issue_version: int,
        payload: dict[str, Any],
        actor: str,
    ) -> None:
        conn.execute(
            """INSERT INTO aip_review_issue_event
            (org_id,project_id,event_id,issue_id,sequence,event_type,issue_version,
             payload_hash,actor)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *scope.key,
                f"review-event-{uuid.uuid4().hex[:20]}",
                issue_id,
                sequence,
                event_type,
                issue_version,
                canonical_hash(payload),
                actor,
            ),
        )

    def _review_issue(self, scope: TenantScope, row: Any) -> ReviewIssue:
        return ReviewIssue(
            tenant=self._tenant(scope),
            issue_id=row["issue_id"],
            rule_ref=ExactRevisionRef.model_validate(self._load(row["rule_ref"])),
            severity=row["severity"],
            artifact_ref=ExactArtifactRef(
                artifact_id=row["artifact_id"], content_hash=row["artifact_hash"]
            ),
            eval_report_ref=ExactRevisionRef(
                resource_type="EvalReportRevision",
                resource_id=row["eval_report_id"],
                revision=int(row["eval_report_revision"]),
                content_hash=row["eval_report_hash"],
            ),
            location=self._load(row["location"]),
            evidence_refs=[
                ExactRevisionRef.model_validate(item)
                for item in self._load(row["evidence_refs"])
            ],
            suggested_fix=row["suggested_fix"],
            return_stage=row["return_stage"],
            status=row["status"],
            version=int(row["version"]),
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_by=row["updated_by"],
            updated_at=row["updated_at"],
        )

    def _return_decision(self, scope: TenantScope, row: Any) -> ReturnDecision:
        return ReturnDecision(
            tenant=self._tenant(scope),
            decision_id=row["decision_id"],
            issue_id=row["issue_id"],
            issue_version=int(row["issue_version"]),
            run_id=row["run_id"],
            step_key=row["step_key"],
            step_run_id=row["step_run_id"],
            attempt=int(row["attempt"]),
            attempt_idempotency_key=row["attempt_idempotency_key"],
            reason=row["reason"],
            decision_hash=row["decision_hash"],
            actor=row["actor"],
            created_at=row["created_at"],
        )

    def _require_task_plan(
        self,
        conn: Any,
        scope: TenantScope,
        body: CreateImpactPreviewRequest | ReviseImpactPreviewRequest,
    ) -> None:
        task = conn.execute(
            """SELECT task_id FROM aip_task
            WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*scope.key, body.task_id),
        ).fetchone()
        if not task:
            raise ProductionContractDependencyBlocked("TASK_MISSING")
        plan = conn.execute(
            """SELECT task_id,revision,content_hash FROM aip_plan_revision
            WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s""",
            (*scope.key, body.plan_ref.resource_id),
        ).fetchone()
        if not plan or plan["task_id"] != body.task_id:
            raise ProductionContractDependencyBlocked("PLAN_MISSING_OR_TASK_MISMATCH")
        if (
            int(plan["revision"]) != body.plan_ref.revision
            or plan["content_hash"] != body.plan_ref.content_hash
        ):
            raise ProductionContractDependencyBlocked("PLAN_EXACT_REF_DRIFTED")

    def _preview_dependency_state(
        self,
        conn: Any,
        scope: TenantScope,
        body: CreateImpactPreviewRequest | ReviseImpactPreviewRequest,
    ) -> tuple[list[dict[str, Any]], list[ContractBlocker], ContractReadiness]:
        snapshot: list[dict[str, Any]] = []
        blockers: list[ContractBlocker] = []
        exact_specs = (
            (body.plan_ref, "aip_plan_revision", "plan_revision_id", False),
            (body.brief_ref, "aip_task_brief_revision", "brief_id", True),
            (
                body.evidence_bundle_ref,
                "aip_evidence_bundle_revision",
                "bundle_id",
                True,
            ),
            (body.eval_contract_ref, "aip_eval_contract_revision", "contract_id", True),
            (
                body.responsibility_plan_ref,
                "aip_responsibility_plan_revision",
                "plan_id",
                True,
            ),
            (
                body.stage_template_ref,
                "aip_stage_template_revision",
                "template_id",
                True,
            ),
        )
        for ref, table, id_column, require_frozen in exact_specs:
            self._snapshot_exact(
                conn,
                scope,
                ref,
                table,
                id_column,
                snapshot,
                blockers,
                require_frozen=require_frozen,
            )
        if body.model_route_ref:
            self._snapshot_exact(
                conn,
                scope,
                body.model_route_ref,
                "aip_model_route_revision",
                "model_route_id",
                snapshot,
                blockers,
                require_frozen=False,
            )
        if body.runtime_policy_ref:
            self._snapshot_exact(
                conn,
                scope,
                body.runtime_policy_ref,
                "aip_runtime_policy_revision",
                "runtime_policy_id",
                snapshot,
                blockers,
                require_frozen=False,
            )
        if body.capability_ref:
            ref = body.capability_ref
            row = conn.execute(
                """SELECT revision,content_hash,lifecycle,readiness
                FROM aip_capability_revision WHERE capability_id=%s AND revision=%s""",
                (ref.resource_id, ref.revision),
            ).fetchone()
            observed = {
                "resourceType": ref.resource_type,
                "resourceId": ref.resource_id,
                "requestedRevision": ref.revision,
                "requestedHash": ref.content_hash,
                "observedRevision": int(row["revision"]) if row else None,
                "observedHash": row["content_hash"] if row else None,
                "lifecycle": row["lifecycle"] if row else None,
                "readiness": row["readiness"] if row else None,
            }
            snapshot.append(observed)
            if not row:
                blockers.append(
                    ContractBlocker(
                        code="CAPABILITY_MISSING",
                        message="CapabilityRevision 不存在",
                        resource_ref=ref,
                    )
                )
            elif row["content_hash"] != ref.content_hash:
                blockers.append(
                    ContractBlocker(
                        code="CAPABILITY_DRIFTED",
                        message="CapabilityRevision exact hash 漂移",
                        resource_ref=ref,
                    )
                )
            elif row["lifecycle"] != "published" or row["readiness"] != "available":
                blockers.append(
                    ContractBlocker(
                        code="CAPABILITY_NOT_READY",
                        message="CapabilityRevision 尚不可生产使用",
                        resource_ref=ref,
                    )
                )
        mutable_specs = {
            "AgentInstance": ("aip_agent_instance", "instance_id", "status", {"active"}),
            "SkillBinding": ("aip_skill_binding", "binding_id", "status", {"active"}),
            "CapabilityBinding": (
                "aip_capability_binding",
                "binding_id",
                "status",
                {"active"},
            ),
        }
        for ref in body.binding_refs:
            table, id_column, status_column, ready_values = mutable_specs[ref.resource_type]
            row = conn.execute(
                f"""SELECT version,{status_column} AS status FROM {table}
                WHERE org_id=%s AND project_id=%s AND {id_column}=%s""",
                (*scope.key, ref.resource_id),
            ).fetchone()
            observed = {
                "resourceType": ref.resource_type,
                "resourceId": ref.resource_id,
                "requestedVersion": ref.version,
                "observedVersion": int(row["version"]) if row else None,
                "status": row["status"] if row else None,
            }
            snapshot.append(observed)
            if not row:
                blockers.append(
                    ContractBlocker(
                        code=f"{ref.resource_type.upper()}_MISSING",
                        message=f"{ref.resource_type} 不存在",
                    )
                )
            elif int(row["version"]) != ref.version:
                blockers.append(
                    ContractBlocker(
                        code=f"{ref.resource_type.upper()}_DRIFTED",
                        message=f"{ref.resource_type} version 漂移",
                    )
                )
            elif row["status"] not in ready_values:
                blockers.append(
                    ContractBlocker(
                        code=f"{ref.resource_type.upper()}_NOT_READY",
                        message=f"{ref.resource_type} 尚未 active",
                    )
                )
        if body.account_ref:
            snapshot.append(
                {
                    "resourceType": body.account_ref.resource_type,
                    "resourceId": body.account_ref.resource_id,
                    "requestedVersion": body.account_ref.version,
                    "observedVersion": None,
                    "status": "authority_unavailable",
                }
            )
            blockers.append(
                ContractBlocker(
                    code="ACCOUNT_AUTHORITY_UNAVAILABLE",
                    message="受控账号 authority 尚未接入 W2-D",
                )
            )
        impact = body.impact.model_dump(mode="json", by_alias=True)
        if any(item["quality"] == "unknown" for item in impact.values()):
            blockers.append(
                ContractBlocker(
                    code="IMPACT_REQUIRED_DIMENSION_UNKNOWN",
                    message="必需 impact 分区仍为 unknown",
                )
            )
        if body.expires_at <= datetime.now(timezone.utc):
            blockers.append(
                ContractBlocker(code="IMPACT_PREVIEW_EXPIRED", message="ImpactPreview 已过期")
            )
        if not blockers:
            readiness = ContractReadiness.READY
        elif any("DRIFTED" in item.code or "EXPIRED" in item.code for item in blockers):
            readiness = ContractReadiness.STALE
        elif any("UNKNOWN" in item.code for item in blockers):
            readiness = ContractReadiness.UNKNOWN
        else:
            readiness = ContractReadiness.BLOCKED
        return snapshot, blockers, readiness

    def _snapshot_exact(
        self,
        conn: Any,
        scope: TenantScope,
        ref: ExactRevisionRef,
        table: str,
        id_column: str,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
        *,
        require_frozen: bool,
    ) -> None:
        row = conn.execute(
            f"""SELECT revision,content_hash{',lifecycle' if require_frozen else ''}
            FROM {table} WHERE org_id=%s AND project_id=%s
              AND {id_column}=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        observed = {
            "resourceType": ref.resource_type,
            "resourceId": ref.resource_id,
            "requestedRevision": ref.revision,
            "requestedHash": ref.content_hash,
            "observedRevision": int(row["revision"]) if row else None,
            "observedHash": row["content_hash"] if row else None,
            "lifecycle": row["lifecycle"] if row and require_frozen else None,
        }
        snapshot.append(observed)
        if not row:
            blockers.append(
                ContractBlocker(
                    code=f"{ref.resource_type.upper()}_MISSING",
                    message=f"{ref.resource_type} exact revision 不存在",
                    resource_ref=ref,
                )
            )
        elif row["content_hash"] != ref.content_hash:
            blockers.append(
                ContractBlocker(
                    code=f"{ref.resource_type.upper()}_DRIFTED",
                    message=f"{ref.resource_type} exact hash 漂移",
                    resource_ref=ref,
                )
            )
        elif require_frozen and row["lifecycle"] != "frozen":
            blockers.append(
                ContractBlocker(
                    code=f"{ref.resource_type.upper()}_NOT_FROZEN",
                    message=f"{ref.resource_type} 尚未 frozen",
                    resource_ref=ref,
                )
            )

    def _insert_impact_preview(
        self,
        conn: Any,
        scope: TenantScope,
        preview_id: str,
        revision: int,
        actor: str,
        body: CreateImpactPreviewRequest | ReviseImpactPreviewRequest,
        content_hash: str,
        snapshot: list[dict[str, Any]],
        blockers: list[ContractBlocker],
        readiness: ContractReadiness,
        lifecycle: BriefLifecycle,
        *,
        frozen_by: str | None = None,
    ) -> Any:
        payload = body.model_dump(mode="json", by_alias=True, exclude={"expected_version"})
        blocker_payload = [item.model_dump(mode="json", by_alias=True) for item in blockers]
        return conn.execute(
            """INSERT INTO aip_impact_preview_revision
            (org_id,project_id,preview_id,revision,task_id,plan_ref,brief_ref,
             evidence_bundle_ref,eval_contract_ref,responsibility_plan_ref,stage_template_ref,
             model_route_ref,runtime_policy_ref,binding_refs,capability_ref,account_ref,
             impact,expires_at,content_hash,dependency_snapshot_hash,dependency_snapshot,
             lifecycle,readiness,blockers,frozen_by,frozen_at,created_by)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
             %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,
             %s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,
             CASE WHEN %s::text IS NULL THEN NULL ELSE NOW() END,%s) RETURNING *""",
            (
                *scope.key,
                preview_id,
                revision,
                body.task_id,
                self._json(payload["planRef"]),
                self._json(payload["briefRef"]),
                self._json(payload["evidenceBundleRef"]),
                self._json(payload["evalContractRef"]),
                self._json(payload["responsibilityPlanRef"]),
                self._json(payload["stageTemplateRef"]),
                self._json(payload.get("modelRouteRef")),
                self._json(payload.get("runtimePolicyRef")),
                self._json(payload["bindingRefs"]),
                self._json(payload.get("capabilityRef")),
                self._json(payload.get("accountRef")),
                self._json(payload["impact"]),
                body.expires_at,
                content_hash,
                canonical_hash(snapshot),
                self._json(snapshot),
                lifecycle.value,
                readiness.value,
                self._json(blocker_payload),
                frozen_by,
                frozen_by,
                actor,
            ),
        ).fetchone()

    def _impact_body(self, row: Any) -> CreateImpactPreviewRequest:
        return CreateImpactPreviewRequest(
            task_id=row["task_id"],
            plan_ref=self._load(row["plan_ref"]),
            brief_ref=self._load(row["brief_ref"]),
            evidence_bundle_ref=self._load(row["evidence_bundle_ref"]),
            eval_contract_ref=self._load(row["eval_contract_ref"]),
            responsibility_plan_ref=self._load(row["responsibility_plan_ref"]),
            stage_template_ref=self._load(row["stage_template_ref"]),
            model_route_ref=self._load(row["model_route_ref"]),
            runtime_policy_ref=self._load(row["runtime_policy_ref"]),
            binding_refs=self._load(row["binding_refs"]),
            capability_ref=self._load(row["capability_ref"]),
            account_ref=self._load(row["account_ref"]),
            impact=self._load(row["impact"]),
            expires_at=row["expires_at"],
        )

    def _impact_preview(
        self, scope: TenantScope, row: Any, version: int
    ) -> ImpactPreviewRevision:
        body = self._impact_body(row)
        action_binding_hash = compute_action_binding_hash(
            org_id=scope.org_id,
            project_id=scope.project_id,
            preview_id=row["preview_id"],
            revision=int(row["revision"]),
            content_hash=row["content_hash"],
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            binding_refs=self._load(row["binding_refs"]),
            capability_ref=self._load(row["capability_ref"]),
            account_ref=self._load(row["account_ref"]),
            expires_at=row["expires_at"],
        )
        return ImpactPreviewRevision(
            **body.model_dump(),
            tenant=self._tenant(scope),
            preview_id=row["preview_id"],
            revision=int(row["revision"]),
            version=version,
            content_hash=row["content_hash"],
            dependency_snapshot_hash=row["dependency_snapshot_hash"],
            action_binding_hash=action_binding_hash,
            lifecycle=row["lifecycle"],
            readiness=row["readiness"],
            blockers=self._load(row["blockers"]),
            frozen_by=row["frozen_by"],
            frozen_at=row["frozen_at"],
            created_by=row["created_by"],
            created_at=row["created_at"],
        )

    def _require_eval_suite(self, conn: Any, scope: TenantScope, ref: ExactRevisionRef) -> None:
        row = conn.execute(
            """SELECT content_hash FROM aip_eval_suite_revision
            WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if not row:
            raise ProductionContractDependencyBlocked("EVAL_SUITE_MISSING")
        if row["content_hash"] != ref.content_hash:
            raise ProductionContractDependencyBlocked("EVAL_SUITE_DRIFTED")

    def _eval_blockers(self, conn: Any, scope: TenantScope, row: Any) -> list[ContractBlocker]:
        blockers: list[ContractBlocker] = []
        suite_ref = ExactRevisionRef.model_validate(self._load(row["suite_ref"]))
        try:
            self._require_eval_suite(conn, scope, suite_ref)
        except ProductionContractDependencyBlocked as exc:
            blockers.append(ContractBlocker(code=str(exc), message="评测套件 exact ref 不可用", resource_ref=suite_ref))
        publication = self._load(row["publication_ref"])
        if not publication:
            blockers.append(ContractBlocker(code="EVAL_PUBLICATION_MISSING", message="尚未绑定发布事件"))
        else:
            ref = ExactRevisionRef.model_validate(publication)
            publication_row = conn.execute("""SELECT * FROM aip_publication_event
                WHERE org_id=%s AND project_id=%s AND event_id=%s""",
                (*scope.key, ref.resource_id)).fetchone()
            if not publication_row:
                blockers.append(ContractBlocker(code="EVAL_PUBLICATION_MISSING", message="发布事件不存在", resource_ref=ref))
            elif publication_row["event_type"] != "published":
                blockers.append(ContractBlocker(code="EVAL_PUBLICATION_REVOKED", message="发布事件不是有效 published", resource_ref=ref))
            elif canonical_hash(self._publication_snapshot(publication_row)) != ref.content_hash:
                blockers.append(ContractBlocker(code="EVAL_PUBLICATION_DRIFTED", message="发布事件 exact hash 漂移", resource_ref=ref))
        gate = self._load(row["release_gate_ref"])
        if not gate:
            blockers.append(ContractBlocker(code="EVAL_GATE_MISSING", message="尚未绑定发布门决定"))
        else:
            ref = ExactRevisionRef.model_validate(gate)
            gate_row = conn.execute("""SELECT * FROM aip_release_gate_decision
                WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
                (*scope.key, ref.resource_id)).fetchone()
            if not gate_row:
                blockers.append(ContractBlocker(code="EVAL_GATE_MISSING", message="发布门决定不存在", resource_ref=ref))
            elif gate_row["status"] != "passed":
                blockers.append(ContractBlocker(code="EVAL_GATE_INVALIDATED", message="发布门决定未通过或已失效", resource_ref=ref))
            elif gate_row["decision_hash"] != ref.content_hash:
                blockers.append(ContractBlocker(code="EVAL_GATE_DRIFTED", message="发布门决定 exact hash 漂移", resource_ref=ref))
        return blockers

    def _require_responsibility_dependencies(
        self, conn: Any, scope: TenantScope,
        body: CreateResponsibilityPlanRequest | ReviseResponsibilityPlanRequest,
    ) -> None:
        if self._responsibility_template_resolver is None:
            raise ProductionContractDependencyBlocked("RESPONSIBILITY_TEMPLATE_AUTHORITY_UNAVAILABLE")
        if not self._responsibility_template_resolver(scope, body.template_ref):
            raise ProductionContractDependencyBlocked("RESPONSIBILITY_TEMPLATE_MISSING_OR_DRIFTED")
        for slot in body.slots:
            if slot.assignee.kind.value != "agent_instance":
                raise ProductionContractDependencyBlocked(f"ASSIGNEE_AUTHORITY_UNAVAILABLE:{slot.slot_id}")
            row = conn.execute("""SELECT version FROM aip_agent_instance
                WHERE org_id=%s AND project_id=%s AND instance_id=%s""",
                (*scope.key, slot.assignee.resource_id)).fetchone()
            if not row:
                raise ProductionContractDependencyBlocked(f"ASSIGNEE_MISSING:{slot.slot_id}")
            if int(row["version"]) != slot.assignee.version:
                raise ProductionContractDependencyBlocked(f"ASSIGNEE_DRIFTED:{slot.slot_id}")

    def _responsibility_blockers(self, conn: Any, scope: TenantScope, row: Any) -> tuple[list[ContractBlocker], list[str]]:
        """W-L4: coverage via assignee SkillBinding → CapabilityBinding operational, not tenant-global."""
        blockers: list[ContractBlocker] = []
        uncovered: list[str] = []
        now = datetime.now(timezone.utc)
        for slot in self._load(row["slots"]):
            slot_id = slot["slotId"]
            assignee = slot["assignee"]
            instance_id = assignee["resourceId"]
            required = set(slot["requiredCapabilityIds"])
            skill_rows = conn.execute(
                """SELECT capability_refs FROM aip_skill_binding
                   WHERE org_id=%s AND project_id=%s AND instance_id=%s AND status='active'""",
                (*scope.key, instance_id),
            ).fetchall()
            if not skill_rows:
                blockers.append(
                    ContractBlocker(
                        code="SKILL_BINDING_NOT_ACTIVE",
                        message=f"职责 {slot_id} 没有 active SkillBinding",
                    )
                )
                uncovered.append(slot_id)
                continue
            binding_ids: list[str] = []
            for skill in skill_rows:
                for ref in self._load(skill["capability_refs"]) or []:
                    if isinstance(ref, str) and ref.strip():
                        binding_ids.append(ref.strip())
                    elif isinstance(ref, dict):
                        identifier = ref.get("bindingId") or ref.get("resourceId")
                        if isinstance(identifier, str) and identifier.strip():
                            binding_ids.append(identifier.strip())
            binding_ids = sorted(set(binding_ids))
            if not binding_ids:
                blockers.append(
                    ContractBlocker(
                        code="CAPABILITY_BINDING_MISSING",
                        message=f"职责 {slot_id} 的 SkillBinding 未挂 CapabilityBinding",
                    )
                )
                uncovered.append(slot_id)
                continue
            cap_rows = conn.execute(
                """SELECT * FROM aip_capability_binding
                   WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)""",
                (*scope.key, binding_ids),
            ).fetchall()
            found = {item["binding_id"] for item in cap_rows}
            slot_codes: set[str] = set()
            if found != set(binding_ids):
                slot_codes.add("CAPABILITY_BINDING_MISSING")
            provided: set[str] = set()
            for crow in cap_rows:
                cap_id = self._capability_identifier(self._load(crow["capability_ref"]))
                if not cap_id:
                    slot_codes.add("CAPABILITY_BINDING_MISSING")
                    continue
                if crow["status"] != "active" or crow["health"] != "healthy":
                    slot_codes.add("CAPABILITY_BINDING_NOT_ACTIVE")
                    continue
                usable = crow["operational_readiness"] == "available" or (
                    crow["operational_readiness"] == "degraded"
                    and bool(crow["allow_degraded"])
                )
                if not usable:
                    slot_codes.add("CAPABILITY_BINDING_NOT_OPERATIONAL")
                    continue
                if (
                    crow["dependency_snapshot_hash"] is None
                    or crow["readiness_expires_at"] is None
                    or crow["readiness_expires_at"] <= now
                ):
                    slot_codes.add("CAPABILITY_BINDING_STALE")
                    continue
                provided.add(cap_id)
            if not required <= provided:
                if "CAPABILITY_BINDING_NOT_OPERATIONAL" not in slot_codes and (
                    "CAPABILITY_BINDING_STALE" not in slot_codes
                ):
                    slot_codes.add("CAPABILITY_BINDING_NOT_ACTIVE")
            if slot_codes:
                messages = {
                    "CAPABILITY_BINDING_MISSING": f"职责 {slot_id} 缺少 assignee 归属的 CapabilityBinding",
                    "CAPABILITY_BINDING_NOT_ACTIVE": f"职责 {slot_id} 的 required capabilities 未全部由 assignee 的 operational Binding 覆盖",
                    "CAPABILITY_BINDING_NOT_OPERATIONAL": f"职责 {slot_id} 的 CapabilityBinding 未达 operational 可用",
                    "CAPABILITY_BINDING_STALE": f"职责 {slot_id} 的 CapabilityBinding readiness 已过期或未求值",
                }
                for code in sorted(slot_codes):
                    blockers.append(ContractBlocker(code=code, message=messages[code]))
                uncovered.append(slot_id)
        return blockers, uncovered

    def _insert_eval(self, conn: Any, scope: TenantScope, contract_id: str, revision: int,
                     actor: str, body: CreateEvalContractRequest | ReviseEvalContractRequest,
                     content_hash: str, lifecycle: BriefLifecycle):
        payload = body.model_dump(mode="json", by_alias=True, exclude={"expected_version"})
        return conn.execute("""INSERT INTO aip_eval_contract_revision
            (org_id,project_id,contract_id,revision,suite_ref,publication_ref,release_gate_ref,
             artifact_schema_ref,severity_thresholds,gate_policy,return_mapping,override_policy,
             content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
             %s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *""",
            (*scope.key, contract_id, revision, self._json(payload["suiteRef"]),
             self._json(payload.get("publicationRef")), self._json(payload.get("releaseGateRef")),
             self._json(payload["artifactSchemaRef"]), self._json(payload["severityThresholds"]),
             self._json(payload["gatePolicy"]), self._json(payload["returnMapping"]),
             self._json(payload["overridePolicy"]), content_hash, lifecycle.value, actor)).fetchone()

    def _insert_responsibility(self, conn: Any, scope: TenantScope, plan_id: str, revision: int,
                               actor: str, body: CreateResponsibilityPlanRequest | ReviseResponsibilityPlanRequest,
                               content_hash: str, lifecycle: BriefLifecycle):
        payload = body.model_dump(mode="json", by_alias=True, exclude={"expected_version"})
        return conn.execute("""INSERT INTO aip_responsibility_plan_revision
            (org_id,project_id,plan_id,revision,profile,template_ref,slots,merge_decisions,
             content_hash,lifecycle,created_by)
            VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *""",
            (*scope.key, plan_id, revision, body.profile, self._json(payload["templateRef"]),
             self._json(payload["slots"]), self._json(payload["mergeDecisions"]),
             content_hash, lifecycle.value, actor)).fetchone()

    def _eval_contract(self, scope: TenantScope, row: Any, version: int, conn: Any) -> EvalContractRevision:
        blockers = self._eval_blockers(conn, scope, row)
        return EvalContractRevision(
            tenant=self._tenant(scope), contract_id=row["contract_id"], revision=int(row["revision"]),
            version=version, suite_ref=self._load(row["suite_ref"]), publication_ref=self._load(row["publication_ref"]),
            release_gate_ref=self._load(row["release_gate_ref"]), artifact_schema_ref=self._load(row["artifact_schema_ref"]),
            severity_thresholds=self._load(row["severity_thresholds"]), gate_policy=self._load(row["gate_policy"]),
            return_mapping=self._load(row["return_mapping"]), override_policy=self._load(row["override_policy"]),
            content_hash=row["content_hash"], lifecycle=row["lifecycle"],
            readiness=ContractReadiness.READY if not blockers else ContractReadiness.BLOCKED,
            blockers=blockers, created_by=row["created_by"], created_at=row["created_at"])

    def _responsibility_plan(self, scope: TenantScope, row: Any, version: int, conn: Any) -> ResponsibilityPlanRevision:
        blockers, uncovered = self._responsibility_blockers(conn, scope, row)
        return ResponsibilityPlanRevision(
            tenant=self._tenant(scope), plan_id=row["plan_id"], revision=int(row["revision"]), version=version,
            profile=row["profile"], template_ref=self._load(row["template_ref"]), slots=self._load(row["slots"]),
            merge_decisions=self._load(row["merge_decisions"]),
            coverage=Coverage.COMPLETE if not uncovered else Coverage.BLOCKED, uncovered_slots=uncovered,
            content_hash=row["content_hash"], lifecycle=row["lifecycle"],
            readiness=ContractReadiness.READY if not blockers else ContractReadiness.BLOCKED,
            blockers=blockers, created_by=row["created_by"], created_at=row["created_at"])

    @staticmethod
    def _publication_snapshot(row: Any) -> dict[str, Any]:
        return {key: row[key] for key in (
            "event_id", "publication_id", "target_ref", "event_type",
            "release_gate_decision_id", "reason_hash", "actor", "occurred_at")}

    @staticmethod
    def _capability_identifier(ref: Any) -> str | None:
        """Skill/capability bindings may store plain ids or ResourceRef-shaped objects."""
        if isinstance(ref, str):
            value = ref.strip()
            return value or None
        if isinstance(ref, dict):
            value = ref.get("assetId") or ref.get("resourceId") or ref.get("capabilityId")
            if isinstance(value, str):
                value = value.strip()
                return value or None
        return None

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _head(conn: Any, scope: TenantScope, table: str, column: str, identifier: str):
        return conn.execute(f"SELECT * FROM {table} WHERE org_id=%s AND project_id=%s AND {column}=%s FOR UPDATE", (*scope.key, identifier)).fetchone()

    @staticmethod
    def _advance_head(conn: Any, scope: TenantScope, table: str, column: str, identifier: str, revision: int) -> None:
        conn.execute(f"UPDATE {table} SET current_revision=%s,version=version+1,updated_at=NOW() WHERE org_id=%s AND project_id=%s AND {column}=%s", (revision, *scope.key, identifier))

    @staticmethod
    def _json(value:Any)->str:return json.dumps(value,ensure_ascii=False,separators=(",",":"),default=str)
    @staticmethod
    def _load(value:Any)->Any:return json.loads(value) if isinstance(value,str) else value
    def _replay(self,conn:Any,scope:TenantScope,operation:str,key:str,request_hash:str):
        row=conn.execute("SELECT * FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation=%s AND idempotency_key=%s",(*scope.key,operation,key)).fetchone()
        if row and row["request_hash"]!=request_hash: raise ProductionContractIdempotencyConflict("idempotency key payload drift")
        return self._load(row["result_ref"]) if row else None
    def _receipt(self,conn:Any,scope:TenantScope,operation:str,key:str,request_hash:str,result:dict[str,Any],actor:str):
        conn.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,receipt_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s)",(*scope.key,f"w2r-{uuid.uuid4().hex[:20]}",operation,key,request_hash,self._json(result),actor))
    def _brief(self,scope:TenantScope,row:Any,version:int)->TaskBriefRevision:
        return TaskBriefRevision(tenant=TenantContext(org_id=scope.org_id,project_id=scope.project_id),brief_id=row["brief_id"],task_id=row["task_id"],revision=int(row["revision"]),version=version,brief_type=row["brief_type"],schema_ref=ResourceRef.model_validate(self._load(row["schema_ref"])),spec=self._load(row["spec"]),content_hash=row["content_hash"],lifecycle=BriefLifecycle(row["lifecycle"]),created_by=row["created_by"],created_at=row["created_at"])
    def _bundle(self,scope:TenantScope,row:Any)->EvidenceBundleRevision:
        return EvidenceBundleRevision(tenant=TenantContext(org_id=scope.org_id,project_id=scope.project_id),bundle_id=row["bundle_id"],revision=int(row["revision"]),brief_ref=ExactRevisionRef.model_validate(self._load(row["brief_ref"])),subject_refs=[ResourceRef.model_validate(x) for x in self._load(row["subject_refs"])],cutoff_at=row["cutoff_at"],item_refs=[ExactRevisionRef.model_validate(x) for x in self._load(row["item_refs"])],coverage=row["coverage"],missing=self._load(row["missing"]),conflicts=self._load(row["conflicts"]),uncertainties=self._load(row["uncertainties"]),freshness=row["freshness"],marking=self._load(row["marking"]),license_summary=self._load(row["license_summary"]),content_hash=row["content_hash"],lifecycle=BriefLifecycle(row["lifecycle"]),created_by=row["created_by"],created_at=row["created_at"])
