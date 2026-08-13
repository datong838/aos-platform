"""PostgreSQL authority for W2-A task briefs and evidence bundles."""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.aip_production_contracts import (
    BriefLifecycle, ContractBlocker, ContractReadiness, Coverage,
    CreateBriefRequest, CreateEvalContractRequest, CreateEvidenceBundleRequest,
    CreateResponsibilityPlanRequest, EvalContractListResponse,
    EvalContractRevision, EvidenceBundleRevision, ExactRevisionRef,
    ResponsibilityPlanListResponse, ResponsibilityPlanRevision,
    ReviseBriefRequest, ReviseEvalContractRequest,
    ReviseResponsibilityPlanRequest, TaskBriefRevision,
    EvidenceBundleListResponse, TaskBriefListResponse,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]
ResponsibilityTemplateResolver = Callable[[TenantScope, ExactRevisionRef], bool]


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


class AipProductionContractStore:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        responsibility_template_resolver: ResponsibilityTemplateResolver | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._responsibility_template_resolver = responsibility_template_resolver

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
        payload=body.model_dump(mode="json",by_alias=True); request_hash=canonical_hash(payload)
        with self._connect_factory(scope) as conn:
            replay=self._replay(conn,scope,"evidence_bundle.create",key,request_hash)
            if replay: return self.get_evidence_bundle(scope,replay["resourceId"],int(replay["revision"]),conn=conn)
            brief=self.get_brief(scope,body.brief_ref.resource_id,body.brief_ref.revision,conn=conn)
            if brief.lifecycle != BriefLifecycle.FROZEN or brief.content_hash != body.brief_ref.content_hash:
                raise ProductionContractDependencyBlocked("brief exact ref is not frozen/current")
            for item in body.item_refs:
                if item.resource_type != "Evidence": raise ProductionContractDependencyBlocked("W2-A bundles only accept Evidence refs")
                row=conn.execute("SELECT content_hash FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s",(*scope.key,item.resource_id)).fetchone()
                if not row or row["content_hash"] != item.content_hash: raise ProductionContractDependencyBlocked("evidence exact ref missing or drifted")
            bundle_id=f"evidence-bundle-{uuid.uuid4().hex[:20]}"; content_hash=canonical_hash(payload)
            row=conn.execute("""INSERT INTO aip_evidence_bundle_revision(org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,item_refs,coverage,missing,conflicts,uncertainties,freshness,marking,license_summary,content_hash,lifecycle,created_by)
                VALUES(%s,%s,%s,1,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s::jsonb,%s::jsonb,%s,'frozen',%s) RETURNING *""",
                (*scope.key,bundle_id,self._json(payload["briefRef"]),self._json(payload["subjectRefs"]),body.cutoff_at,self._json(payload["itemRefs"]),body.coverage.value,self._json(body.missing),self._json(body.conflicts),self._json(body.uncertainties),body.freshness.value,self._json(body.marking),self._json(body.license_summary),content_hash,actor)).fetchone()
            self._receipt(conn,scope,"evidence_bundle.create",key,request_hash,{"resourceType":"EvidenceBundleRevision","resourceId":bundle_id,"revision":1,"contentHash":content_hash},actor)
            conn.commit(); return self._bundle(scope,row)

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
        blockers: list[ContractBlocker] = []
        uncovered: list[str] = []
        for slot in self._load(row["slots"]):
            slot_id = slot["slotId"]
            assignee = slot["assignee"]
            instance_id = assignee["resourceId"]
            capabilities = set(slot["requiredCapabilityIds"])
            skill_rows = conn.execute("""SELECT capability_refs FROM aip_skill_binding
                WHERE org_id=%s AND project_id=%s AND instance_id=%s AND status='active'""",
                (*scope.key, instance_id)).fetchall()
            if not skill_rows:
                blockers.append(ContractBlocker(code="SKILL_BINDING_NOT_ACTIVE", message=f"职责 {slot_id} 没有 active SkillBinding"))
            bound_capabilities: set[str] = set()
            for skill in skill_rows:
                for ref in self._load(skill["capability_refs"]):
                    identifier = ref.get("assetId") or ref.get("resourceId") or ref.get("capabilityId")
                    if identifier:
                        bound_capabilities.add(identifier)
            active_capability_rows = conn.execute("""SELECT capability_ref FROM aip_capability_binding
                WHERE org_id=%s AND project_id=%s AND status='active' AND health='healthy'""",
                scope.key).fetchall()
            active_capabilities = {
                value for item in active_capability_rows
                if (value := (self._load(item["capability_ref"]).get("assetId")
                              or self._load(item["capability_ref"]).get("resourceId")
                              or self._load(item["capability_ref"]).get("capabilityId")))
            }
            if not capabilities <= (bound_capabilities & active_capabilities):
                blockers.append(ContractBlocker(code="CAPABILITY_BINDING_NOT_ACTIVE", message=f"职责 {slot_id} 的 required capabilities 未全部 active/healthy"))
            if not skill_rows or not capabilities <= (bound_capabilities & active_capabilities):
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
