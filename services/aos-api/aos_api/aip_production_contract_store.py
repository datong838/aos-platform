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
    BriefLifecycle, CreateBriefRequest, CreateEvidenceBundleRequest,
    EvidenceBundleRevision, ExactRevisionRef, ReviseBriefRequest, TaskBriefRevision,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


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
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

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
