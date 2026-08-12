from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    ArtifactGovernanceInspection,
    GovernanceApprovalRef,
    KnowledgeScope,
    KnowledgeSourceRef,
    LicensePolicyDecision,
    MemoryCandidateStatus,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_governance import (
    AipMemoryGovernanceBlocked,
    AipMemoryGovernanceService,
)
from aos_api.aip_memory_store import AipMemoryNotFound, AipMemoryStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 12, 13, tzinfo=UTC)
SOURCE_HASH = "a" * 64
PAYLOAD_HASH = "b" * 64
EVAL_HASH = "c" * 64


def resource(kind: str, identifier: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision=revision,
        authority="postgresql",
    )


def _seed_authorities(suffix: str) -> dict[str, str]:
    task_id = f"memory-task-{suffix}"
    plan_id = f"memory-plan-{suffix}"
    run_id = f"memory-run-{suffix}"
    proposal_id = f"memory-proposal-{suffix}"
    draft_id = f"memory-draft-{suffix}"
    approval_id = f"memory-approval-{suffix}"
    eval_run_id = f"memory-eval-run-{suffix}"
    report_id = f"memory-eval-report-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory','memory','executing',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, task_id, task_id, SOURCE_HASH, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
               org_id,project_id,plan_revision_id,task_id,revision,content_hash,
               steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,'[]'::jsonb,'approved',%s,%s,'pytest')""",
            (*PRIMARY.key, plan_id, task_id, SOURCE_HASH, plan_id, SOURCE_HASH),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
               org_id,project_id,run_id,task_id,plan_revision_id,status,
               idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'pytest')""",
            (*PRIMARY.key, run_id, task_id, plan_id, run_id, SOURCE_HASH),
        )
        conn.execute(
            """INSERT INTO aip_eval_run (
               org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
               target_ref,dataset_ref,judge_ref,status,idempotency_key,created_by,
               started_at,finished_at)
               VALUES (%s,%s,%s,'suite',1,%s,'{}','{}','{}','succeeded',%s,
               'pytest',%s,%s)""",
            (*PRIMARY.key, eval_run_id, SOURCE_HASH, eval_run_id, NOW, NOW),
        )
        conn.execute(
            """INSERT INTO aip_eval_report_revision (
               org_id,project_id,report_id,revision,content_hash,run_id,
               suite_ref,target_ref,dataset_ref,judge_ref,results,passed,failed,
               total,pass_rate,gate_passed,created_at)
               VALUES (%s,%s,%s,1,%s,%s,'{}','{}','{}','{}',
               '[{"case":"memory"}]',1,0,1,1.0,true,%s)""",
            (*PRIMARY.key, report_id, EVAL_HASH, eval_run_id, NOW),
        )
        conn.execute(
            """INSERT INTO aip_action_proposal (
               org_id,project_id,proposal_id,action_type_id,
               action_type_revision_hash,action_type_snapshot,task_id,run_id,
               purpose,risk_level,policy_snapshot,payload,proposal_hash,status,
               expires_at,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,'memory_promote',%s,'{}',%s,%s,'memory','R2',
               '{}','{}',%s,'approved',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, proposal_id, SOURCE_HASH, task_id, run_id, SOURCE_HASH,
             NOW + timedelta(days=1), proposal_id, SOURCE_HASH),
        )
        conn.execute(
            """INSERT INTO aip_action_draft (
               org_id,project_id,draft_id,proposal_id,proposal_version,
               proposal_hash,snapshot,approval_policy,status,created_by)
               VALUES (%s,%s,%s,%s,1,%s,'{}','{}','approved','pytest')""",
            (*PRIMARY.key, draft_id, proposal_id, SOURCE_HASH),
        )
        conn.execute(
            """INSERT INTO aip_action_approval_event (
               org_id,project_id,approval_event_id,proposal_id,proposal_version,
               proposal_hash,decision,actor_id,expires_at,idempotency_key,
               request_hash)
               VALUES (%s,%s,%s,%s,1,%s,'approved','pytest',%s,%s,%s)""",
            (*PRIMARY.key, approval_id, proposal_id, SOURCE_HASH,
             NOW + timedelta(days=1), approval_id, SOURCE_HASH),
        )
        conn.commit()
    return {
        "task_id": task_id,
        "run_id": run_id,
        "draft_id": draft_id,
        "approval_id": approval_id,
        "report_id": report_id,
    }


@pytest.fixture()
def chain() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:12]
    authority = _seed_authorities(suffix)
    payload = ArtifactRef(
        artifact_id=f"memory-payload-{suffix}",
        artifact_type="memory_candidate",
        revision="1",
        content_hash=PAYLOAD_HASH,
    )
    source = KnowledgeSourceRef(
        source_kind="authorized_document",
        source_uri=f"urn:aip5:{suffix}",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal-authorized",
        usage_policy="summary-and-citation",
        content_hash=SOURCE_HASH,
        provider="pytest",
        provider_version="1",
        applicability=["vertical:ecommerce", "role:data_advisor"],
    )
    request = SubmitMemoryCandidateRequest(
        candidate_layer="semantic",
        task_id=authority["task_id"],
        run_id=authority["run_id"],
        subject=resource("ecom.product", f"product-{suffix}"),
        payload=payload,
        source=source,
        confidence=0.9,
        marking=["internal"],
    )
    governance = GovernanceApprovalRef(
        eval_report=ArtifactRef(
            artifact_id=authority["report_id"],
            artifact_type="eval_report",
            revision="1",
            content_hash=EVAL_HASH,
        ),
        draft=resource("aip.draft", authority["draft_id"]),
        approval_event=resource("aip.approval_event", authority["approval_id"]),
    )
    store = AipMemoryStore()
    source_id = f"memory-source-{suffix}"
    candidate_id = f"memory-candidate-{suffix}"
    store.create_source_revision(PRIMARY, source_id, 1, source, actor="pytest")
    candidate = store.submit_candidate(
        PRIMARY,
        candidate_id,
        request,
        source_id=source_id,
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    )
    inspection = ArtifactGovernanceInspection(
        artifact=payload,
        pii_status="clear",
        inspection_ref=resource("aip.pii_inspection", f"inspection-{suffix}"),
    )
    return {
        "store": store,
        "candidate": candidate,
        "governance": governance,
        "inspection": inspection,
        "suffix": suffix,
    }


def service(chain, *, pii: str = "clear", license_decision="allowed"):
    inspection = chain["inspection"].model_copy(update={"pii_status": pii})
    return AipMemoryGovernanceService(
        artifact_inspector=lambda _scope, _artifact: inspection,
        license_resolver=lambda _scope, _source: LicensePolicyDecision(license_decision),
    )


def test_all_seven_gates_approve_and_promote_with_exact_authorities(chain) -> None:
    approved = service(chain).approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert approved.status is MemoryCandidateStatus.APPROVED
    promoted, item, revision = service(chain).promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=f"memory-item-{chain['suffix']}",
        expected_version=2,
        required_applicability=["vertical:ecommerce"],
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert promoted.status is MemoryCandidateStatus.PROMOTED
    assert item.subject == chain["candidate"].request.subject
    assert revision.content_hash == PAYLOAD_HASH


@pytest.mark.parametrize(
    ("pii", "license_decision", "applicability", "time_delta", "reason"),
    [
        ("contains_pii", "allowed", ["vertical:ecommerce"], 1, "pii_detected"),
        ("unknown", "allowed", ["vertical:ecommerce"], 1, "pii_status_unknown"),
        ("clear", "denied", ["vertical:ecommerce"], 1, "license_denied"),
        ("clear", "unknown", ["vertical:ecommerce"], 1, "license_status_unknown"),
        ("clear", "allowed", [], 1, "applicability_missing"),
        ("clear", "allowed", ["vertical:beauty"], 1, "applicability_mismatch"),
        ("clear", "allowed", ["vertical:ecommerce"], 60 * 24 * 31, "source_stale"),
    ],
)
def test_unknown_or_failed_gate_is_quarantined(
    chain, pii, license_decision, applicability, time_delta, reason
) -> None:
    candidate = service(chain, pii=pii, license_decision=license_decision).approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=applicability,
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=time_delta),
    )
    assert candidate.status is MemoryCandidateStatus.QUARANTINED
    assert reason in candidate.quarantine_reasons


def test_source_hash_mismatch_is_quarantined(chain) -> None:
    bad_inspection = chain["inspection"].model_copy(
        update={
            "artifact": chain["inspection"].artifact.model_copy(
                update={"content_hash": "d" * 64}
            )
        }
    )
    svc = AipMemoryGovernanceService(
        artifact_inspector=lambda _scope, _artifact: bad_inspection,
        license_resolver=lambda _scope, _source: LicensePolicyDecision.ALLOWED,
    )
    candidate = svc.approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert candidate.quarantine_reasons == ["source_hash_mismatch"]


def test_governance_authority_forgery_is_quarantined(chain) -> None:
    other = chain["governance"].model_copy(
        update={
            "approval_event": resource("aip.approval_event", "forged-approval")
        }
    )
    candidate = service(chain).approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=other,
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert candidate.quarantine_reasons == ["approval_authority_invalid"]


def test_inspector_and_license_errors_fail_closed(chain) -> None:
    svc = AipMemoryGovernanceService(
        artifact_inspector=lambda _scope, _artifact: (_ for _ in ()).throw(
            RuntimeError("scanner unavailable")
        ),
        license_resolver=lambda _scope, _source: (_ for _ in ()).throw(
            RuntimeError("policy unavailable")
        ),
    )
    candidate = svc.approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    assert candidate.quarantine_reasons == [
        "source_artifact_unverified",
        "license_status_unknown",
    ]


def test_redacted_inspection_requires_exact_receipt(chain) -> None:
    with pytest.raises(ValueError, match="redaction receipt"):
        ArtifactGovernanceInspection(
            artifact=chain["candidate"].request.payload,
            pii_status="redacted",
            inspection_ref=resource("aip.pii_inspection", "pii-redacted"),
        )
    inspected = ArtifactGovernanceInspection(
        artifact=chain["candidate"].request.payload,
        pii_status="redacted",
        inspection_ref=resource("aip.pii_inspection", "pii-redacted"),
        redaction_receipt=resource("aip.redaction_receipt", "redaction-1"),
    )
    assert inspected.redaction_receipt.resource_id == "redaction-1"


def test_cross_tenant_is_invisible_and_duplicate_or_conflict_is_quarantined(chain) -> None:
    with pytest.raises(AipMemoryNotFound):
        service(chain).approve_candidate(
            CANARY,
            chain["candidate"].candidate_id,
            expected_version=1,
            governance=chain["governance"],
            required_applicability=["vertical:ecommerce"],
            actor="reviewer",
            occurred_at=NOW + timedelta(minutes=1),
        )

    approved = service(chain).approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    service(chain).promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=f"memory-item-{chain['suffix']}",
        expected_version=2,
        required_applicability=["vertical:ecommerce"],
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=2),
    )

    # A second Candidate for the same subject cannot silently duplicate or overwrite.
    second_id = f"memory-candidate-second-{chain['suffix']}"
    second = chain["store"].submit_candidate(
        PRIMARY,
        second_id,
        chain["candidate"].request,
        source_id=f"memory-source-{chain['suffix']}",
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=3),
    )
    duplicate = service(chain).approve_candidate(
        PRIMARY,
        second.candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=4),
    )
    assert duplicate.quarantine_reasons == ["duplicate_memory"]

    conflict_payload = chain["candidate"].request.payload.model_copy(
        update={"artifact_id": f"memory-conflict-{chain['suffix']}", "content_hash": "d" * 64}
    )
    conflict_request = chain["candidate"].request.model_copy(
        update={"payload": conflict_payload}
    )
    conflict = chain["store"].submit_candidate(
        PRIMARY,
        f"memory-candidate-conflict-{chain['suffix']}",
        conflict_request,
        source_id=f"memory-source-{chain['suffix']}",
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW + timedelta(minutes=5),
    )
    conflict_inspection = chain["inspection"].model_copy(
        update={"artifact": conflict_payload}
    )
    conflict_service = AipMemoryGovernanceService(
        artifact_inspector=lambda _scope, _artifact: conflict_inspection,
        license_resolver=lambda _scope, _source: LicensePolicyDecision.ALLOWED,
    )
    conflicted = conflict_service.approve_candidate(
        PRIMARY,
        conflict.candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=6),
    )
    assert conflicted.quarantine_reasons == ["memory_conflict"]


def test_promotion_rechecks_time_sensitive_gates(chain) -> None:
    approved = service(chain).approve_candidate(
        PRIMARY,
        chain["candidate"].candidate_id,
        expected_version=1,
        governance=chain["governance"],
        required_applicability=["vertical:ecommerce"],
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(AipMemoryGovernanceBlocked, match="source_stale"):
        service(chain).promote_candidate(
            PRIMARY,
            approved.candidate_id,
            memory_item_id=f"memory-item-{chain['suffix']}",
            expected_version=2,
            required_applicability=["vertical:ecommerce"],
            actor="promoter",
            occurred_at=NOW + timedelta(days=31),
        )
