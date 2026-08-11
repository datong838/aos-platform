from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from aos_api.aip_eval_contracts import (
    LineageEventType,
    LineageRootType,
    LineageSourceKind,
)
from aos_api.aip_lineage_service import (
    AipLineageConflict,
    AipLineageNotFound,
    AipLineageService,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
OTHER = TenantScope("org-org", "dev-project")
HASH = "a" * 64
H2 = "b" * 64
NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


@pytest.fixture()
def lineage_sources():
    suffix = uuid.uuid4().hex[:10]
    ids = {
        "task": f"task-{suffix}",
        "plan": f"plan-{suffix}",
        "run": f"run-{suffix}",
        "proposal": f"proposal-{suffix}",
        "lease": f"lease-{suffix}",
        "receipt": f"receipt-{suffix}",
        "reconcile": f"receipt-reconcile-{suffix}",
        "eval": f"eval-{suffix}",
        "report": f"report-{suffix}",
        "gate": f"gate-{suffix}",
        "publication": f"publication-{suffix}",
    }
    target = {
        "assetType": "logic_graph",
        "assetId": f"logic-{suffix}",
        "revision": "1",
        "contentHash": HASH,
    }
    dataset = {
        "datasetId": f"dataset-{suffix}",
        "revision": 1,
        "contentHash": HASH,
        "sourceHash": H2,
        "redactionPolicy": {
            "assetType": "policy",
            "assetId": "redaction-policy",
            "revision": "1",
            "contentHash": HASH,
        },
    }
    judge = {"judgeId": "judge", "revision": 1, "contentHash": HASH}
    suite = {
        "assetType": "eval_suite",
        "assetId": "suite",
        "revision": "1",
        "contentHash": HASH,
    }
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_task
               (org_id,project_id,task_id,task_type,title,status,idempotency_key,
                request_hash,version,created_by,created_at,updated_at)
               VALUES (%s,%s,%s,'test','lineage','approved',%s,%s,1,'tester',%s,%s)""",
            (*SCOPE.key, ids["task"], f"task-key-{suffix}", HASH, NOW, NOW),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision
               (org_id,project_id,plan_revision_id,task_id,revision,content_hash,
                steps,idempotency_key,request_hash,created_by,created_at,approval_status)
               VALUES (%s,%s,%s,%s,1,%s,'[]'::jsonb,%s,%s,'tester',%s,'approved')""",
            (
                *SCOPE.key,
                ids["plan"],
                ids["task"],
                HASH,
                f"plan-key-{suffix}",
                HASH,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_task_run
               (org_id,project_id,run_id,task_id,plan_revision_id,status,
                idempotency_key,request_hash,version,created_by,created_at,
                started_at,finished_at,updated_at)
               VALUES (%s,%s,%s,%s,%s,'succeeded',%s,%s,1,'tester',%s,%s,%s,%s)""",
            (
                *SCOPE.key,
                ids["run"],
                ids["task"],
                ids["plan"],
                f"run-key-{suffix}",
                HASH,
                NOW,
                NOW,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_artifact
               (org_id,project_id,artifact_id,run_id,artifact_type,content_hash,
                created_by,created_at)
               VALUES (%s,%s,%s,%s,'json',%s,'tester',%s)""",
            (*SCOPE.key, f"artifact-{suffix}", ids["run"], HASH, NOW),
        )
        conn.execute(
            """INSERT INTO aip_action_proposal
               (org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
                action_type_snapshot,purpose,risk_level,policy_snapshot,payload,diff,
                proposal_hash,status,expires_at,idempotency_key,request_hash,version,
                created_by,created_at,updated_at)
               VALUES (%s,%s,%s,'cancel_order',%s,'{}'::jsonb,'test','R1',
                '{}'::jsonb,'{}'::jsonb,'{}'::jsonb,%s,'reconciled',%s,%s,%s,1,
                'tester',%s,%s)""",
            (
                *SCOPE.key,
                ids["proposal"],
                HASH,
                HASH,
                NOW,
                f"proposal-key-{suffix}",
                HASH,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_event
               (org_id,project_id,event_id,proposal_id,event_type,actor_id,
                proposal_version,proposal_hash,created_at)
               VALUES (%s,%s,%s,%s,'approved','approver',1,%s,%s)""",
            (*SCOPE.key, f"action-event-{suffix}", ids["proposal"], HASH, NOW),
        )
        conn.execute(
            """INSERT INTO aip_action_execution_lease
               (org_id,project_id,lease_id,proposal_id,proposal_hash,attempt,status,
                owner_id,expires_at,created_at,consumed_at)
               VALUES (%s,%s,%s,%s,%s,1,'consumed','executor',%s,%s,%s)""",
            (*SCOPE.key, ids["lease"], ids["proposal"], HASH, NOW, NOW, NOW),
        )
        conn.execute(
            """INSERT INTO aip_action_receipt
               (org_id,project_id,receipt_id,proposal_id,lease_id,status,
                request_fingerprint,receipt_kind,created_at)
               VALUES (%s,%s,%s,%s,%s,'unknown',%s,'initial',%s)""",
            (*SCOPE.key, ids["receipt"], ids["proposal"], ids["lease"], HASH, NOW),
        )
        conn.execute(
            """INSERT INTO aip_action_receipt
               (org_id,project_id,receipt_id,proposal_id,lease_id,status,
                request_fingerprint,receipt_kind,supersedes_receipt_id,created_at)
               VALUES (%s,%s,%s,%s,%s,'reconciled',%s,'reconcile',%s,%s)""",
            (
                *SCOPE.key,
                ids["reconcile"],
                ids["proposal"],
                ids["lease"],
                HASH,
                ids["receipt"],
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_eval_run
               (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
                target_ref,dataset_ref,judge_ref,status,idempotency_key,version,
                created_by,created_at,started_at,finished_at)
               VALUES (%s,%s,%s,'suite',1,%s,%s::jsonb,%s::jsonb,%s::jsonb,
                'failed',%s,2,'tester',%s,%s,%s)""",
            (
                *SCOPE.key,
                ids["eval"],
                HASH,
                AipLineageService._json(target),
                AipLineageService._json(dataset),
                AipLineageService._json(judge),
                f"eval-key-{suffix}",
                NOW,
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_eval_run_event
               (org_id,project_id,event_id,run_id,sequence,event_type,from_status,
                to_status,payload_hash,actor,created_at)
               VALUES (%s,%s,%s,%s,1,'finished','running','failed',%s,'tester',%s)""",
            (*SCOPE.key, f"eval-event-{suffix}", ids["eval"], HASH, NOW),
        )
        conn.execute(
            """INSERT INTO aip_eval_report_revision
               (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
                target_ref,dataset_ref,judge_ref,results,passed,failed,total,
                pass_rate,gate_passed,created_at)
               VALUES (%s,%s,%s,1,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                '[{"caseId":"case-1","passed":false}]'::jsonb,0,1,1,0,FALSE,%s)""",
            (
                *SCOPE.key,
                ids["report"],
                HASH,
                ids["eval"],
                AipLineageService._json(suite),
                AipLineageService._json(target),
                AipLineageService._json(dataset),
                AipLineageService._json(judge),
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_release_gate_decision
               (org_id,project_id,decision_id,target_ref,suite_ref,eval_run_id,
                eval_report_ref,status,decision_hash,decided_by,decided_at)
               VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,
                %s::jsonb,'failed',%s,'tester',%s)""",
            (
                *SCOPE.key,
                ids["gate"],
                AipLineageService._json(target),
                AipLineageService._json(suite),
                ids["eval"],
                AipLineageService._json(
                    {
                        "artifactId": ids["report"],
                        "artifactType": "eval_report",
                        "revision": "1",
                        "contentHash": HASH,
                    }
                ),
                HASH,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO aip_publication_event
               (org_id,project_id,event_id,publication_id,target_ref,event_type,
                release_gate_decision_id,reason_hash,actor,occurred_at)
               VALUES (%s,%s,%s,%s,%s::jsonb,'revoked',%s,%s,'tester',%s)""",
            (
                *SCOPE.key,
                f"publication-event-{suffix}",
                ids["publication"],
                AipLineageService._json(target),
                ids["gate"],
                HASH,
                NOW,
            ),
        )
        conn.commit()
    yield ids


def test_reconcile_real_roots_is_idempotent_and_tenant_scoped(lineage_sources) -> None:
    service = AipLineageService()
    task = service.reconcile(SCOPE, LineageRootType.TASK_RUN, lineage_sources["run"])
    assert [event.source_kind for event in task] == [
        LineageSourceKind.ARTIFACT,
        LineageSourceKind.TASK_RUN,
    ]
    assert [event.sequence for event in task] == [1, 2]
    assert (
        service.reconcile(SCOPE, LineageRootType.TASK_RUN, lineage_sources["run"])
        == task
    )
    assert (
        service.list_events(OTHER, LineageRootType.TASK_RUN, lineage_sources["run"])
        == []
    )
    with pytest.raises(AipLineageNotFound):
        service.reconcile(OTHER, LineageRootType.TASK_RUN, lineage_sources["run"])


def test_action_unknown_and_reconcile_are_explicit(lineage_sources) -> None:
    events = AipLineageService().reconcile(
        SCOPE, LineageRootType.ACTION, lineage_sources["proposal"]
    )
    assert {event.event_type for event in events} >= {
        LineageEventType.APPROVAL,
        LineageEventType.ERROR,
        LineageEventType.RECONCILE,
    }
    unknown = next(
        event for event in events if event.source_id == lineage_sources["receipt"]
    )
    assert unknown.quality.value == "unknown"


def test_eval_failure_and_publication_revoke_are_real_facts(lineage_sources) -> None:
    service = AipLineageService()
    evaluated = service.reconcile(
        SCOPE, LineageRootType.EVAL_RUN, lineage_sources["eval"]
    )
    assert any(event.event_type is LineageEventType.ERROR for event in evaluated)
    assert any(
        event.source_kind is LineageSourceKind.EVAL_REPORT for event in evaluated
    )
    publication = service.reconcile(
        SCOPE,
        LineageRootType.PUBLICATION,
        lineage_sources["publication"],
    )
    assert len(publication) == 1
    assert publication[0].source_kind is LineageSourceKind.PUBLICATION_EVENT


def test_same_source_identifier_with_drift_fails_closed(lineage_sources) -> None:
    service = AipLineageService()
    service.reconcile(SCOPE, LineageRootType.TASK_RUN, lineage_sources["run"])
    with connect(SCOPE) as conn:
        conn.execute(
            """UPDATE aip_task_run SET request_hash=%s
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (H2, *SCOPE.key, lineage_sources["run"]),
        )
        conn.commit()
    with pytest.raises(AipLineageConflict):
        service.reconcile(SCOPE, LineageRootType.TASK_RUN, lineage_sources["run"])
