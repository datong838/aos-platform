"""Plan and explicitly apply the first governed internal knowledge seed.

Planning is side-effect free.  Applying is a separate, lease-gated caller
decision and persists deterministic authority records in PostgreSQL.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeScope,
    KnowledgeSourceKind,
    KnowledgeSourceRef,
    MemoryCandidateStatus,
    MemoryItem,
    MemoryItemRevision,
    RuntimeMemoryLayer,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_pipeline_contracts import (
    KnowledgePipelineInputReceipt,
    KnowledgePipelineKind,
    TrustedKnowledgeAdapterDefinition,
    TrustedKnowledgeCandidateDraft,
)
from aos_api.aip_memory_pipeline_service import AipMemoryPipelinePolicyBlocked
from aos_api.aip_memory_production_factory import build_memory_governance_service
from aos_api.aip_memory_search_index import (
    AipMemorySearchIndex,
    SearchReferenceDraft,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]

R15_TARGET_SCOPE = TenantScope("org-org", "dev-project")
R15_SOURCE_URI = "urn:aos:internal-knowledge:qyh-customer-service-escalation:v1"
R15_LICENSE_ID = "aos-internal-owned-v1"
R15_USAGE_POLICY = "workspace_retrieval"
R15_APPLICABILITY = (
    "skill:ecommerce.customer_service.response",
    "vertical:ecommerce",
    "tenant:org-org/dev-project",
)
R15_MARKINGS = ("internal",)
R15_ADAPTER_ID = "aos.knowledge.internal-document-seed"
R15_ADAPTER_REVISION = 1
R15_RECEIPT_TYPE = "aip.artifact_receipt"
R15_PROVIDER = "aos-internal-docintel"
R15_PROVIDER_VERSION = "r15-v1"
R15_SUBJECT = ResourceRef(
    resource_type="aip.agent",
    resource_id="ecommerce.customer_service",
    revision="1",
    authority="postgresql",
)
R15_SEARCH_TERMS = (
    "栖月汇客服",
    "售后升级",
    "客服承诺边界",
    "人工复核",
)

_SENSITIVE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("secret_api_key", re.compile(r"\b(?:sk|ak)-[A-Za-z0-9_-]{16,}\b")),
    ("secret_bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{12,}", re.I)),
    ("secret_assignment", re.compile(r"\b(?:api[_-]?key|token|password)\s*[:=]\s*\S+", re.I)),
    ("pii_email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)),
    ("pii_mobile", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("pii_cn_id", re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")),
)


class InternalKnowledgeSeedIds(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_id: str
    plan_revision_id: str
    run_id: str
    artifact_id: str
    payload_evidence_id: str
    pii_evidence_id: str
    receipt_id: str
    source_id: str
    candidate_id: str
    memory_item_id: str
    eval_run_id: str
    eval_report_id: str
    proposal_id: str
    draft_id: str
    approval_event_id: str


class InternalKnowledgeSeedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(pattern=r"^(ready|blocked)$")
    org_id: str
    project_id: str
    source_path: str
    source_uri: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: datetime
    freshness_expires_at: datetime
    license_id: str
    usage_policy: str
    applicability: list[str]
    markings: list[str]
    ids: InternalKnowledgeSeedIds
    blockers: list[str]

    @model_validator(mode="after")
    def _status_matches_blockers(self) -> "InternalKnowledgeSeedPlan":
        if (self.status == "ready") == bool(self.blockers):
            raise ValueError("ready plan must have no blockers; blocked plan must have blockers")
        return self


class InternalKnowledgeSeedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = Field(pattern=r"^(applied|replayed)$")
    memory_item: MemoryItem
    memory_revision: MemoryItemRevision
    search_reference_created: bool


def _stable_id(prefix: str, scope: TenantScope, content_hash: str) -> str:
    digest = hashlib.sha256(
        f"{scope.org_id}\x1f{scope.project_id}\x1f{R15_SOURCE_URI}\x1f{content_hash}".encode()
    ).hexdigest()
    return f"{prefix}-{digest[:40]}"


def _ids(scope: TenantScope, content_hash: str) -> InternalKnowledgeSeedIds:
    return InternalKnowledgeSeedIds(
        task_id=_stable_id("r15-task", scope, content_hash),
        plan_revision_id=_stable_id("r15-plan", scope, content_hash),
        run_id=_stable_id("r15-run", scope, content_hash),
        artifact_id=_stable_id("r15-artifact", scope, content_hash),
        payload_evidence_id=_stable_id("r15-payload", scope, content_hash),
        pii_evidence_id=_stable_id("r15-pii", scope, content_hash),
        receipt_id=_stable_id("r15-receipt", scope, content_hash),
        source_id=_stable_id("r15-source", scope, content_hash),
        candidate_id=_stable_id("r15-candidate", scope, content_hash),
        memory_item_id=_stable_id("r15-memory", scope, content_hash),
        eval_run_id=_stable_id("r15-eval-run", scope, content_hash),
        eval_report_id=_stable_id("r15-eval-report", scope, content_hash),
        proposal_id=_stable_id("r15-proposal", scope, content_hash),
        draft_id=_stable_id("r15-draft", scope, content_hash),
        approval_event_id=_stable_id("r15-approval", scope, content_hash),
    )


def _adapter_contract_hash() -> str:
    values = (
        R15_ADAPTER_ID,
        str(R15_ADAPTER_REVISION),
        KnowledgePipelineKind.SEED_IMPORT.value,
        R15_RECEIPT_TYPE,
        KnowledgeSourceKind.AUTHORIZED_DOCUMENT.value,
    )
    return hashlib.sha256("\x1f".join(values).encode()).hexdigest()


def internal_document_seed_adapter_definition() -> TrustedKnowledgeAdapterDefinition:
    return TrustedKnowledgeAdapterDefinition(
        adapter_id=R15_ADAPTER_ID,
        revision=R15_ADAPTER_REVISION,
        contract_hash=_adapter_contract_hash(),
        pipeline_kinds=[KnowledgePipelineKind.SEED_IMPORT],
        receipt_types=[R15_RECEIPT_TYPE],
        source_kinds=[KnowledgeSourceKind.AUTHORIZED_DOCUMENT],
    )


def build_internal_knowledge_receipt(
    plan: InternalKnowledgeSeedPlan,
) -> KnowledgePipelineInputReceipt:
    if plan.status != "ready":
        raise AipMemoryPipelinePolicyBlocked(plan.blockers or ["seed_plan_blocked"])
    receipt_ref = ResourceRef(
        resource_type=R15_RECEIPT_TYPE,
        resource_id=plan.ids.receipt_id,
        revision="1",
        authority="postgresql",
    )
    return KnowledgePipelineInputReceipt(
        tenant=TenantContext(org_id=plan.org_id, project_id=plan.project_id),
        receipt_ref=receipt_ref,
        artifact=ArtifactRef(
            artifact_id=plan.ids.artifact_id,
            artifact_type="knowledge_document",
            revision="1",
            content_hash=plan.content_hash,
        ),
        task_id=plan.ids.task_id,
        run_id=plan.ids.run_id,
        source=KnowledgeSourceRef(
            source_kind=KnowledgeSourceKind.AUTHORIZED_DOCUMENT,
            source_ref=receipt_ref,
            observed_at=plan.observed_at,
            freshness_expires_at=plan.freshness_expires_at,
            license_id=plan.license_id,
            usage_policy=plan.usage_policy,
            content_hash=plan.content_hash,
            provider=R15_PROVIDER,
            provider_version=R15_PROVIDER_VERSION,
            applicability=plan.applicability,
        ),
    )


class InternalDocumentSeedAdapter:
    """Map the frozen R15 Receipt into one governed semantic Candidate."""

    def __init__(self, plan: InternalKnowledgeSeedPlan) -> None:
        if plan.status != "ready":
            raise ValueError("internal knowledge adapter requires a ready plan")
        self._plan = plan.model_copy(deep=True)

    def adapt(
        self,
        receipt: KnowledgePipelineInputReceipt,
        *,
        pipeline_kind: KnowledgePipelineKind,
    ) -> list[TrustedKnowledgeCandidateDraft]:
        reasons: list[str] = []
        if pipeline_kind is not KnowledgePipelineKind.SEED_IMPORT:
            reasons.append("internal_seed_kind_not_allowed")
        if receipt != build_internal_knowledge_receipt(self._plan):
            reasons.append("internal_seed_receipt_drift")
        if reasons:
            raise AipMemoryPipelinePolicyBlocked(reasons)
        return [
            TrustedKnowledgeCandidateDraft(
                candidate_id=self._plan.ids.candidate_id,
                source_id=self._plan.ids.source_id,
                source_revision=1,
                knowledge_scope=KnowledgeScope.WORKSPACE,
                candidate_layer=RuntimeMemoryLayer.SEMANTIC,
                subject=R15_SUBJECT,
                confidence=1.0,
                marking=self._plan.markings,
            )
        ]


class InternalKnowledgeColdStartAuthority:
    """Persist exact, prerequisite authorities for one approved internal seed.

    This class does not call a Provider and does not create an AgentRun.  It
    prepares one deterministic internal-document governance decision; the
    production Memory governance service still owns approval and promotion.
    """

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def prepare(
        self,
        scope: TenantScope,
        plan: InternalKnowledgeSeedPlan,
        *,
        content: str,
        actor: str,
        reviewer: str,
        occurred_at: datetime,
    ) -> GovernanceApprovalRef:
        if scope != R15_TARGET_SCOPE or scope.key != (plan.org_id, plan.project_id):
            raise ValueError("R15 apply is restricted to org-org/dev-project")
        if plan.status != "ready" or occurred_at.utcoffset() is None:
            raise ValueError("R15 apply requires a ready plan and timezone-aware time")
        maker, checker = actor.strip(), reviewer.strip()
        if not maker or not checker or maker == checker:
            raise ValueError("R15 apply requires distinct maker and reviewer")
        if occurred_at >= plan.freshness_expires_at:
            raise ValueError("R15 source is stale at apply time")
        if hashlib.sha256(content.encode("utf-8")).hexdigest() != plan.content_hash:
            raise ValueError("R15 content hash drifted before apply")

        ids = plan.ids
        eval_hash = _derived_hash("eval-report", plan.content_hash)
        proposal_hash = _derived_hash("memory-promote-proposal", plan.content_hash)
        pii_hash = _derived_hash("pii-clear", plan.content_hash)
        receipt_hash = _derived_hash("artifact-receipt", plan.content_hash)
        subject = {
            "artifactId": ids.artifact_id,
            "artifactType": "knowledge_document",
            "revision": "1",
            "contentHash": plan.content_hash,
        }
        with self._connect_factory(scope) as conn:
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"r15:{scope.org_id}:{scope.project_id}:{plan.content_hash}",),
            )
            if conn.execute(
                "SELECT 1 FROM twa_workspace WHERE org_id=%s AND project_id=%s",
                scope.key,
            ).fetchone() is None:
                raise ValueError("R15 target workspace does not exist")
            conn.execute("SET CONSTRAINTS aip_task_current_plan_fk DEFERRED")
            conn.execute(
                """INSERT INTO aip_task (
                   org_id,project_id,task_id,task_type,title,status,idempotency_key,
                   request_hash,current_plan_revision_id,created_by)
                   VALUES (%s,%s,%s,'knowledge_cold_start',%s,'executing',%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,task_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.task_id,
                    "R15 内部知识冷启动",
                    ids.task_id,
                    plan.content_hash,
                    ids.plan_revision_id,
                    maker,
                ),
            )
            conn.execute(
                """INSERT INTO aip_plan_revision (
                   org_id,project_id,plan_revision_id,task_id,revision,content_hash,
                   steps,approval_status,approved_by,approved_at,idempotency_key,
                   request_hash,created_by)
                   VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,plan_revision_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.plan_revision_id,
                    ids.task_id,
                    plan.content_hash,
                    _json([{"step": "governed_internal_knowledge_seed"}]),
                    checker,
                    occurred_at,
                    ids.plan_revision_id,
                    plan.content_hash,
                    maker,
                ),
            )
            conn.execute(
                """INSERT INTO aip_task_run (
                   org_id,project_id,run_id,task_id,plan_revision_id,status,
                   idempotency_key,request_hash,created_by,started_at)
                   VALUES (%s,%s,%s,%s,%s,'running',%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,run_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.run_id,
                    ids.task_id,
                    ids.plan_revision_id,
                    ids.run_id,
                    plan.content_hash,
                    maker,
                    occurred_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_artifact (
                   org_id,project_id,artifact_id,run_id,artifact_type,content_ref,
                   source,evidence_refs,marking,content_hash,metadata,created_by)
                   VALUES (%s,%s,%s,%s,'knowledge_document',%s,%s::jsonb,%s::jsonb,
                     %s::jsonb,%s,%s::jsonb,%s)
                   ON CONFLICT (org_id,project_id,artifact_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.artifact_id,
                    ids.run_id,
                    plan.source_uri,
                    _json({"provider": R15_PROVIDER, "sourceUri": plan.source_uri}),
                    _json(
                        [
                            {"evidenceId": ids.payload_evidence_id},
                            {"evidenceId": ids.pii_evidence_id},
                            {"evidenceId": ids.receipt_id},
                        ]
                    ),
                    _json(plan.markings),
                    plan.content_hash,
                    _json(
                        {
                            "licenseId": plan.license_id,
                            "usagePolicy": plan.usage_policy,
                            "applicability": plan.applicability,
                        }
                    ),
                    maker,
                ),
            )
            evidence_rows = (
                (
                    ids.payload_evidence_id,
                    "knowledge_payload",
                    plan.content_hash,
                    {"content": content},
                ),
                (
                    ids.pii_evidence_id,
                    "pii_inspection",
                    pii_hash,
                    {"status": "clear", "detector": "r15-static-policy-v1"},
                ),
                (
                    ids.receipt_id,
                    "artifact_receipt",
                    receipt_hash,
                    {
                        "artifactId": ids.artifact_id,
                        "contentHash": plan.content_hash,
                        "licenseId": plan.license_id,
                    },
                ),
            )
            for evidence_id, evidence_type, content_hash, payload in evidence_rows:
                conn.execute(
                    """INSERT INTO aip_evidence (
                       org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,
                       source_type,source_ref,observed_at,freshness_at,content_hash,
                       redaction,payload,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,'internal_document',%s,%s,%s,
                         %s,'{}'::jsonb,%s::jsonb,%s)
                       ON CONFLICT (org_id,project_id,evidence_id) DO NOTHING""",
                    (
                        *scope.key,
                        evidence_id,
                        ids.run_id,
                        evidence_type,
                        _json(subject),
                        plan.source_uri,
                        plan.observed_at,
                        plan.freshness_expires_at,
                        content_hash,
                        _json(payload),
                        maker,
                    ),
                )
            conn.execute(
                """INSERT INTO aip_eval_run (
                   org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
                   target_ref,dataset_ref,judge_ref,status,idempotency_key,created_by,
                   started_at,finished_at)
                   VALUES (%s,%s,%s,'r15-internal-knowledge',1,%s,%s::jsonb,%s::jsonb,
                     %s::jsonb,'succeeded',%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,run_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.eval_run_id,
                    eval_hash,
                    _json(subject),
                    _json({"contentHash": plan.content_hash}),
                    _json({"kind": "deterministic_policy"}),
                    ids.eval_run_id,
                    checker,
                    occurred_at,
                    occurred_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_eval_report_revision (
                   org_id,project_id,report_id,revision,content_hash,run_id,
                   suite_ref,target_ref,dataset_ref,judge_ref,results,passed,failed,
                   total,pass_rate,gate_passed,created_at)
                   VALUES (%s,%s,%s,1,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                     %s::jsonb,1,0,1,1.0,true,%s)
                   ON CONFLICT (org_id,project_id,report_id,revision) DO NOTHING""",
                (
                    *scope.key,
                    ids.eval_report_id,
                    eval_hash,
                    ids.eval_run_id,
                    _json({"suiteId": "r15-internal-knowledge", "revision": 1}),
                    _json(subject),
                    _json({"contentHash": plan.content_hash}),
                    _json({"kind": "deterministic_policy"}),
                    _json([{"case": "pii_license_freshness", "passed": True}]),
                    occurred_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_action_proposal (
                   org_id,project_id,proposal_id,action_type_id,
                   action_type_revision_hash,action_type_snapshot,task_id,run_id,
                   purpose,risk_level,policy_snapshot,payload,proposal_hash,status,
                   expires_at,idempotency_key,request_hash,created_by)
                   VALUES (%s,%s,%s,'memory_promote',%s,%s::jsonb,%s,%s,%s,'R2',
                     %s::jsonb,%s::jsonb,%s,'approved',%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,proposal_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.proposal_id,
                    _derived_hash("memory-promote-action-type", "v1"),
                    _json({"id": "memory_promote", "revision": 1}),
                    ids.task_id,
                    ids.run_id,
                    "Promote one governed internal knowledge document",
                    _json({"makerChecker": True, "requiredApprovals": 1}),
                    _json({"candidateId": ids.candidate_id}),
                    proposal_hash,
                    plan.freshness_expires_at,
                    ids.proposal_id,
                    plan.content_hash,
                    maker,
                ),
            )
            conn.execute(
                """INSERT INTO aip_action_draft (
                   org_id,project_id,draft_id,proposal_id,proposal_version,
                   proposal_hash,snapshot,approval_policy,status,created_by)
                   VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,%s::jsonb,'approved',%s)
                   ON CONFLICT (org_id,project_id,draft_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.draft_id,
                    ids.proposal_id,
                    proposal_hash,
                    _json({"candidateId": ids.candidate_id, "contentHash": plan.content_hash}),
                    _json({"makerChecker": True, "requiredApprovals": 1}),
                    maker,
                ),
            )
            conn.execute(
                """INSERT INTO aip_action_approval_event (
                   org_id,project_id,approval_event_id,proposal_id,proposal_version,
                   proposal_hash,decision,actor_id,expires_at,idempotency_key,request_hash)
                   VALUES (%s,%s,%s,%s,1,%s,'approved',%s,%s,%s,%s)
                   ON CONFLICT (org_id,project_id,approval_event_id) DO NOTHING""",
                (
                    *scope.key,
                    ids.approval_event_id,
                    ids.proposal_id,
                    proposal_hash,
                    checker,
                    plan.freshness_expires_at,
                    ids.approval_event_id,
                    plan.content_hash,
                ),
            )
            self._verify_exact(conn, scope, plan, eval_hash, proposal_hash, content)
            conn.commit()
        return GovernanceApprovalRef(
            eval_report=ArtifactRef(
                artifact_id=ids.eval_report_id,
                artifact_type="eval_report",
                revision="1",
                content_hash=eval_hash,
            ),
            draft=ResourceRef(
                resource_type="aip.draft",
                resource_id=ids.draft_id,
                revision="1",
                authority="postgresql",
            ),
            approval_event=ResourceRef(
                resource_type="aip.approval_event",
                resource_id=ids.approval_event_id,
                revision="1",
                authority="postgresql",
            ),
        )

    @staticmethod
    def _verify_exact(
        conn: Any,
        scope: TenantScope,
        plan: InternalKnowledgeSeedPlan,
        eval_hash: str,
        proposal_hash: str,
        content: str,
    ) -> None:
        checks = (
            ("aip_task", "task_id", plan.ids.task_id, "request_hash", plan.content_hash),
            (
                "aip_plan_revision",
                "plan_revision_id",
                plan.ids.plan_revision_id,
                "content_hash",
                plan.content_hash,
            ),
            ("aip_task_run", "run_id", plan.ids.run_id, "request_hash", plan.content_hash),
            (
                "aip_artifact",
                "artifact_id",
                plan.ids.artifact_id,
                "content_hash",
                plan.content_hash,
            ),
            (
                "aip_eval_report_revision",
                "report_id",
                plan.ids.eval_report_id,
                "content_hash",
                eval_hash,
            ),
            (
                "aip_action_proposal",
                "proposal_id",
                plan.ids.proposal_id,
                "proposal_hash",
                proposal_hash,
            ),
        )
        for table, key_name, key, field, expected in checks:
            row = conn.execute(
                f"SELECT {field} FROM {table} WHERE org_id=%s AND project_id=%s AND {key_name}=%s",
                (*scope.key, key),
            ).fetchone()
            if row is None or row[field] != expected:
                raise RuntimeError(f"R15 authority drift: {table}")
        payload = conn.execute(
            """SELECT payload FROM aip_evidence
               WHERE org_id=%s AND project_id=%s AND evidence_id=%s""",
            (*scope.key, plan.ids.payload_evidence_id),
        ).fetchone()
        if payload is None or payload["payload"] != {"content": content}:
            raise RuntimeError("R15 authority drift: knowledge_payload")


def apply_internal_knowledge_seed(
    scope: TenantScope,
    plan: InternalKnowledgeSeedPlan,
    *,
    content: str,
    actor: str,
    reviewer: str,
    occurred_at: datetime,
    connect_factory: ConnectFactory | None = None,
) -> InternalKnowledgeSeedResult:
    """Apply one exact seed after the caller has acquired the required Lease."""

    connector = connect_factory or db_connect
    approval = InternalKnowledgeColdStartAuthority(connector).prepare(
        scope,
        plan,
        content=content,
        actor=actor,
        reviewer=reviewer,
        occurred_at=occurred_at,
    )
    receipt = build_internal_knowledge_receipt(plan)
    adapter_draft = InternalDocumentSeedAdapter(plan).adapt(
        receipt, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT
    )[0]
    store = AipMemoryStore(connector)
    store.create_source_revision(
        scope, adapter_draft.source_id, 1, receipt.source, actor=actor
    )
    request = SubmitMemoryCandidateRequest(
        candidate_layer=adapter_draft.candidate_layer,
        task_id=receipt.task_id,
        run_id=receipt.run_id,
        subject=adapter_draft.subject,
        payload=receipt.artifact,
        source=receipt.source,
        confidence=adapter_draft.confidence,
        marking=adapter_draft.marking,
    )
    candidate = store.submit_candidate(
        scope,
        adapter_draft.candidate_id,
        request,
        source_id=adapter_draft.source_id,
        source_revision=1,
        knowledge_scope=adapter_draft.knowledge_scope,
        actor=actor,
        occurred_at=occurred_at,
    )
    replayed = candidate.status is MemoryCandidateStatus.PROMOTED
    governance = build_memory_governance_service(
        store=store, connect_factory=connector
    )
    if candidate.status in {
        MemoryCandidateStatus.PENDING,
        MemoryCandidateStatus.QUARANTINED,
    }:
        candidate = governance.approve_candidate(
            scope,
            candidate.candidate_id,
            expected_version=candidate.version,
            governance=approval,
            required_applicability=list(R15_APPLICABILITY),
            actor=reviewer,
            occurred_at=occurred_at,
        )
    if candidate.status is MemoryCandidateStatus.APPROVED:
        _, item, revision = governance.promote_candidate(
            scope,
            candidate.candidate_id,
            memory_item_id=plan.ids.memory_item_id,
            expected_version=candidate.version,
            required_applicability=list(R15_APPLICABILITY),
            actor=reviewer,
            occurred_at=occurred_at,
            expires_at=plan.freshness_expires_at,
        )
    else:
        item, revision = store.get_memory_item(scope, plan.ids.memory_item_id)
    created = AipMemorySearchIndex(connector).upsert_reference(
        scope,
        SearchReferenceDraft(
            memory_item_id=item.memory_item_id,
            revision=revision.revision,
            content_hash=revision.content_hash,
            subject=item.subject,
            source_id=revision.source_id,
            source_revision=revision.source_revision,
            terms=list(R15_SEARCH_TERMS),
            markings=revision.markings,
            applicability=revision.applicability,
            freshness_expires_at=plan.freshness_expires_at,
        ),
        indexed_at=occurred_at,
    )
    with connector(scope) as conn:
        completed = conn.execute(
            """UPDATE aip_task_run
               SET status='succeeded',finished_at=%s
               WHERE org_id=%s AND project_id=%s AND run_id=%s
                 AND task_id=%s AND plan_revision_id=%s
                 AND request_hash=%s AND status IN ('running','succeeded')
               RETURNING status""",
            (
                occurred_at,
                *scope.key,
                plan.ids.run_id,
                plan.ids.task_id,
                plan.ids.plan_revision_id,
                plan.content_hash,
            ),
        ).fetchone()
        if completed is None or completed["status"] != "succeeded":
            raise RuntimeError("R15 task run completion authority drift")
        conn.commit()
    return InternalKnowledgeSeedResult(
        status="replayed" if replayed else "applied",
        memory_item=item,
        memory_revision=revision,
        search_reference_created=created,
    )


def _derived_hash(kind: str, value: str) -> str:
    return hashlib.sha256(f"{kind}\x1f{value}".encode()).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def plan_internal_knowledge_seed(
    scope: TenantScope,
    source_path: Path,
    *,
    observed_at: datetime,
    freshness_expires_at: datetime,
    now: datetime,
    expected_hash: str | None = None,
) -> InternalKnowledgeSeedPlan:
    """Create a deterministic, non-mutating plan for the R15 source document."""

    blockers: list[str] = []
    if scope != R15_TARGET_SCOPE:
        blockers.append("tenant_not_authorized")
    for name, value in (
        ("observed_at", observed_at),
        ("freshness_expires_at", freshness_expires_at),
        ("now", now),
    ):
        if value.utcoffset() is None:
            blockers.append(f"{name}_timezone_missing")
    try:
        raw = source_path.read_bytes()
    except OSError:
        raw = b""
        blockers.append("source_unreadable")
    content_hash = hashlib.sha256(raw).hexdigest()
    if not raw.strip():
        blockers.append("source_empty")
    else:
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            text = ""
            blockers.append("source_not_utf8")
        for reason, pattern in _SENSITIVE_PATTERNS:
            if pattern.search(text):
                blockers.append(reason)
    if expected_hash is not None and expected_hash != content_hash:
        blockers.append("source_hash_drift")
    if observed_at.utcoffset() is not None and now.utcoffset() is not None:
        if observed_at > now:
            blockers.append("observed_at_from_future")
    if (
        freshness_expires_at.utcoffset() is not None
        and observed_at.utcoffset() is not None
        and freshness_expires_at <= observed_at
    ):
        blockers.append("freshness_window_invalid")
    if freshness_expires_at.utcoffset() is not None and now.utcoffset() is not None:
        if freshness_expires_at <= now:
            blockers.append("source_stale")
    blockers = list(dict.fromkeys(blockers))
    return InternalKnowledgeSeedPlan(
        status="blocked" if blockers else "ready",
        org_id=scope.org_id,
        project_id=scope.project_id,
        source_path=str(source_path),
        source_uri=R15_SOURCE_URI,
        content_hash=content_hash,
        observed_at=observed_at,
        freshness_expires_at=freshness_expires_at,
        license_id=R15_LICENSE_ID,
        usage_policy=R15_USAGE_POLICY,
        applicability=list(R15_APPLICABILITY),
        markings=list(R15_MARKINGS),
        ids=_ids(scope, content_hash),
        blockers=blockers,
    )


__all__ = [
    "InternalDocumentSeedAdapter",
    "InternalKnowledgeColdStartAuthority",
    "InternalKnowledgeSeedIds",
    "InternalKnowledgeSeedPlan",
    "InternalKnowledgeSeedResult",
    "R15_ADAPTER_ID",
    "R15_TARGET_SCOPE",
    "apply_internal_knowledge_seed",
    "build_internal_knowledge_receipt",
    "internal_document_seed_adapter_definition",
    "plan_internal_knowledge_seed",
]
