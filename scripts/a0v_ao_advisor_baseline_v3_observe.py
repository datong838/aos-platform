#!/usr/bin/env python3
"""Read-only AO Policy v3 authority and natural-chain observer."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import a0v_ao_advisor_baseline_v3 as v3
import a0v_q_advisor_baseline as base


STATE = v3.STATE / "observation"


def _phase(facts: dict) -> str:
    policy = facts["baseline"]["policy"]
    if policy.get("revision") != 3:
        return "awaiting_policy_v3"
    if not any(row["policy_revision"] == 3 for row in facts["controls"]):
        return "awaiting_control_v3"
    if not any(row["policy_revision"] == 3 and row["enabled"] for row in facts["bindings"]):
        return "awaiting_binding_v3"
    occurrences = [row for row in facts["occurrences"] if row["policy_revision"] == 3]
    if not occurrences:
        return "awaiting_occurrence_v3"
    if any(row["status"] in {"pending", "claimed"} for row in occurrences):
        return "occurrence_pending"
    attempts = {
        row["occurrence_id"]: row for row in facts["dispatchAttempts"]
        if row["occurrence_id"] in {item["occurrence_id"] for item in occurrences}
    }
    if not attempts or any(row["status"] != "receipt_recorded" for row in attempts.values()):
        return "awaiting_dispatch_receipt"
    if len(facts["targetReceipts"]) != len(occurrences):
        return "awaiting_target_receipt"
    if not facts["runs"]:
        return "awaiting_run"
    if not facts["growthPlans"]:
        return "analysis_running"
    return "growth_plan_ready"


def observe(previous) -> dict:
    baseline = v3._current_facts(previous)
    with previous._scope_and_connection()[1] as conn:
        controls = conn.execute(
            """SELECT receipt_id::text,idempotency_key,schedule_policy_id,policy_revision,
                      case_id,case_revision,approval_event_id,command_receipt_id,
                      installation_id::text,generation::text,execution_epoch,authority,content_hash
                 FROM ecommerce_schedule_policy_control_receipt
                WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s
                ORDER BY policy_revision""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        bindings = conn.execute(
            """SELECT policy_id,policy_revision,policy_hash,operation_id,
                      installation_id::text,generation::text,execution_epoch,
                      cadence,approved,enabled,watermark,revision
                 FROM automation_schedule_binding
                WHERE org_id=%s AND project_id=%s AND policy_id=%s
                ORDER BY policy_revision""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        occurrences = conn.execute(
            """SELECT occurrence_id::text,policy_revision,policy_hash,operation_id,
                      installation_id::text,generation::text,execution_epoch,
                      scheduled_at,local_slot,trigger_source,status,deadline,receipt_ref,
                      created_at,updated_at
                 FROM automation_occurrence
                WHERE org_id=%s AND project_id=%s AND policy_id=%s ORDER BY created_at""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        attempts = conn.execute(
            """SELECT a.attempt_id::text,a.occurrence_id::text,a.target_idempotency_key,
                      a.status,a.claimed_at,a.claim_until,a.receipt_ref,a.resolved_at
                 FROM automation_occurrence_dispatch_attempt a
                 JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
                WHERE a.org_id=%s AND a.project_id=%s AND o.policy_id=%s
                ORDER BY a.claimed_at""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        v3_occurrence_ids = {
            row["occurrence_id"] for row in occurrences if row["policy_revision"] == 3
        }
        target_keys = [
            row["target_idempotency_key"]
            for row in attempts
            if row["occurrence_id"] in v3_occurrence_ids
        ]
        receipts = (
            conn.execute(
                """SELECT operation_id,idempotency_key,request_hash,dispatch_revision,
                          installation_id::text,generation::text,execution_epoch,
                          cutover_group_id::text,cutover_group_revision,runtime_revision,
                          response,target_receipt_ref,actor,occurred_at
                     FROM ecommerce_growth_runtime_command_receipt
                    WHERE org_id=%s AND project_id=%s AND idempotency_key=ANY(%s)
                    ORDER BY occurred_at""",
                (*base.SCOPE.values(), target_keys),
            ).fetchall()
            if target_keys
            else []
        )
        triggers = conn.execute(
            """SELECT receipt_id::text,case_id,analysis_type,trigger_kind,trigger_key,
                      requested_run_id,active_run_id,outcome,request_hash,authority_data,created_at
                 FROM ecommerce_investigation_run_trigger_receipt
                WHERE org_id=%s AND project_id=%s AND case_id=%s ORDER BY created_at""",
            (*base.SCOPE.values(), base.CASE_ID),
        ).fetchall()
        runs = conn.execute(
            """SELECT r.run_id,r.case_id,r.case_revision,r.analysis_type,r.trigger_kind,
                      r.trigger_key,h.current_version,h.lifecycle,h.control,h.authority_data,h.updated_at
                 FROM ecommerce_investigation_run r
                 JOIN ecommerce_investigation_run_state_head h USING(org_id,project_id,run_id)
                WHERE r.org_id=%s AND r.project_id=%s AND r.case_id=%s ORDER BY r.created_at""",
            (*base.SCOPE.values(), base.CASE_ID),
        ).fetchall()
        v3_run_ids = {
            row["run_id"] for row in runs if row["trigger_key"] in set(target_keys)
        }
        plans = conn.execute(
            """SELECT h.plan_id,h.current_revision,h.version,r.content_hash,r.receipt_id,
                      r.payload,r.created_by,r.created_at,a.artifact_id,
                      ar.agent_run_id,ar.task_run_id,
                      t.goal#>>'{runRef,resourceId}' business_run_id
                 FROM ecommerce_analyst_growth_plan_head h
                 JOIN ecommerce_analyst_growth_plan_revision r
                   ON (r.org_id,r.project_id,r.plan_id,r.revision)=
                      (h.org_id,h.project_id,h.plan_id,h.current_revision)
                 JOIN aip_artifact a
                   ON (a.org_id,a.project_id,a.artifact_id)=
                      (r.org_id,r.project_id,r.payload#>>'{generationArtifactRef,resourceId}')
                  AND a.content_hash=r.payload#>>'{generationArtifactRef,contentHash}'
                 JOIN aip_agent_run ar
                   ON (ar.org_id,ar.project_id,ar.agent_run_id)=
                      (a.org_id,a.project_id,a.source->>'agentRunId')
                 JOIN aip_task_run tr
                   ON (tr.org_id,tr.project_id,tr.run_id)=
                      (ar.org_id,ar.project_id,ar.task_run_id)
                 JOIN aip_task t
                   ON (t.org_id,t.project_id,t.task_id)=(tr.org_id,tr.project_id,tr.task_id)
                WHERE h.org_id=%s AND h.project_id=%s
                  AND t.goal#>>'{runRef,resourceId}'=ANY(%s)
                ORDER BY h.updated_at""",
            (*base.SCOPE.values(), list(v3_run_ids)),
        ).fetchall()
        canary = conn.execute(
            """SELECT
              (SELECT count(*) FROM automation_schedule_binding
                WHERE org_id='dev-org' AND project_id='dev-project' AND policy_id=%s) bindings,
              (SELECT count(*) FROM automation_occurrence
                WHERE org_id='dev-org' AND project_id='dev-project' AND policy_id=%s) occurrences,
              (SELECT count(*) FROM ecommerce_investigation_run
                WHERE org_id='dev-org' AND project_id='dev-project' AND case_id=%s) runs""",
            (base.POLICY_ID, base.POLICY_ID, base.CASE_ID),
        ).fetchone()
    result = {
        "outcome": "AO_ADVISOR_BASELINE_V3_CHAIN_OBSERVED",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "sourceReads": 0,
        "businessWrites": 0,
        "baseline": baseline,
        "controls": [dict(row) for row in controls],
        "bindings": [dict(row) for row in bindings],
        "occurrences": [dict(row) for row in occurrences],
        "dispatchAttempts": [dict(row) for row in attempts],
        "targetReceipts": [dict(row) for row in receipts],
        "runTriggers": [dict(row) for row in triggers],
        "runs": [dict(row) for row in runs],
        "growthPlans": [dict(row) for row in plans],
        "canary": dict(canary),
    }
    result["phase"] = _phase(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("observe",))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    previous, _profile, _plane = v3.setup()
    result = observe(previous)
    if args.output is not None:
        if args.output.exists():
            raise RuntimeError("immutable observation output exists")
        base.freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
