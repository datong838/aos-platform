#!/usr/bin/env python3
"""Gate and configure the QYH advisor Policy v3 on the exact AO runtime."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path

import a0v_ao_replacement_recovery as replacement
import a0v_ao_saved_snapshot_recovery as snapshot
import a0v_ao_successor_business as successor
import a0v_q_advisor_baseline as base


STATE = base.STATE / "v3-ao"
ATTEMPT_ID = "67c2331d-b73f-4863-b881-0d67e6c55508"
DEFINITION_ID = snapshot.snapshot.DEFINITION_ID
GROUP_ID = snapshot.GROUP
POLICY_KEY = "a0v-ao-advisor-baseline-policy-put-20260919-v3"
APPROVAL_KEY = "a0v-ao-advisor-baseline-schedule-approval-20260919-v3"
EXPECTED_OCCURRENCES = {
    "3c927751-b91a-53d0-8a42-7c5223ea109d",
    "34733f17-f1ce-582d-b1b6-585a96aee2ff",
}
EXPECTED_CLOSURES = {
    "a0v-s-baseline-pre-target-close-20260917",
    "a0v-s-baseline-v2-pre-target-close-20260917",
}
STORE_KEY = (
    "snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
    "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b"
)


def _load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private AO v3 {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def _preflight_profile():
    path = base.ROOT / "scripts/a0v_p02_current_preflight.py"
    spec = importlib.util.spec_from_file_location("ao_advisor_product_preflight", path)
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.BUNDLE_ROOT = replacement.BUNDLE_ROOT
    profile.CURRENT_CREATE = replacement.AO_DIR / "create-result.json"
    profile.CUTOVER_RESUME = successor.STATE.parent / "cutover-ao/resume-result.json"
    profile.AUTHORITY_WINDOW_MINUTES = 90
    original_resume = profile.require_cutover_resume
    original_head = profile.require_current_head

    def resume(create, binding, result, row):
        return original_resume(
            create, binding, result, row, expected_outcome="CURRENT_AO_CUTOVER_RESUME"
        )

    def head(create, observed, binding, cutover_resumed=False):
        if (
            create.get("installationId") != successor.AO_ID
            or str(binding.get("generation")) != successor.AO_GENERATION
            or observed.get("lock_hash") != successor.LOCK
            or binding.get("config_ref") != successor.CONFIG
            or binding.get("revision") != 6
            or binding.get("execution_epoch") != 3
            or not cutover_resumed
        ):
            raise ValueError("exact resumed AO runtime required")
        return original_head(create, observed, binding, cutover_resumed)

    profile.require_cutover_resume = resume
    profile.require_current_head = head
    return profile


def setup():
    previous = __import__("a0v_qyh_current_product_event_first_chain")
    return previous, _preflight_profile(), successor.setup()


def _current_facts(previous) -> dict:
    with previous._scope_and_connection()[1] as conn:
        attempt = conn.execute(
            """SELECT attempt_id::text,state,revision,installation_id::text,generation::text,
                      execution_epoch,operation_kind,operation_key,completed_at,terminal_reason_code
                 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (*base.SCOPE.values(), ATTEMPT_ID),
        ).fetchone()
        definition = conn.execute(
            """SELECT definition_id::text,revision,state,installation_id::text,generation::text
                 FROM pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
            (*base.SCOPE.values(), DEFINITION_ID),
        ).fetchone()
        recovery = conn.execute(
            """SELECT revision,current_definition_revision,input_manifest_hash
                 FROM pipeline_snapshot_group_recovery_receipt
                WHERE org_id=%s AND project_id=%s AND group_id=%s
                ORDER BY revision DESC LIMIT 1""",
            (*base.SCOPE.values(), GROUP_ID),
        ).fetchone()
        snapshot_facts = conn.execute(
            """SELECT
              (SELECT count(*) FROM pipeline_snapshot_schedule_member
                WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
              (SELECT count(*) FROM meta_schedule_run r
                 JOIN pipeline_snapshot_schedule_member m
                   ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
                WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
                  AND r.status='succeeded' AND r.executor_stopped IS TRUE) succeeded_runs,
              (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d
                 JOIN pipeline_snapshot_schedule_member m
                   ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
                WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s) datasets,
              (SELECT count(*) FROM pipeline_snapshot_group_relationship
                WHERE org_id=%s AND project_id=%s AND group_id=%s) relationships,
              (SELECT count(*) FROM pipeline_snapshot_group_link_command
                WHERE org_id=%s AND project_id=%s AND group_id=%s) link_commands,
              (SELECT coalesce(max(link_count),0) FROM pipeline_snapshot_group_link_command
                WHERE org_id=%s AND project_id=%s AND group_id=%s) link_count,
              (SELECT count(*) FROM pipeline_snapshot_group_retirement
                WHERE org_id=%s AND project_id=%s AND group_id=%s) retirements,
              (SELECT count(*) FROM ecom_ingest_receipt
                WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s) store_receipts,
              (SELECT count(*) FROM ecom_link
                WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL) live_links""",
            (
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), GROUP_ID,
                *base.SCOPE.values(), STORE_KEY,
                *base.SCOPE.values(),
            ),
        ).fetchone()
        runtime_facts = conn.execute(
            """SELECT
              (SELECT count(*) FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND execution_epoch=3 AND operation_fence IS FALSE
                  AND revision=96 AND cutover_group_revision=123) routes,
              (SELECT count(*) FROM extension_runtime_resource_lease
                WHERE org_id=%s AND project_id=%s AND generation=%s
                  AND cleanup_state='pending' AND observed_release IS FALSE) live_resources,
              (SELECT count(*) FROM extension_runtime_binding
                WHERE org_id='dev-org' AND project_id='dev-project'
                  AND installation_id=%s) canary_bindings""",
            (
                *base.SCOPE.values(), successor.AO_ID, successor.AO_GENERATION,
                *base.SCOPE.values(), successor.AO_GENERATION,
                successor.AO_ID,
            ),
        ).fetchone()
        case = conn.execute(
            """SELECT r.authority_data FROM ecommerce_investigation_case_head h
                 JOIN ecommerce_investigation_case_revision r
                   ON (r.org_id,r.project_id,r.case_id,r.revision)=
                      (h.org_id,h.project_id,h.case_id,h.current_revision)
                WHERE h.org_id=%s AND h.project_id=%s AND h.case_id=%s""",
            (*base.SCOPE.values(), base.CASE_ID),
        ).fetchone()
        policy = conn.execute(
            """SELECT authority_data FROM ecommerce_investigation_schedule_policy_head
                WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchone()
        occurrences = conn.execute(
            """SELECT occurrence_id::text,status,policy_revision,installation_id::text,
                      generation::text,execution_epoch
                 FROM automation_occurrence
                WHERE org_id=%s AND project_id=%s AND policy_id=%s ORDER BY created_at""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        closures = conn.execute(
            """SELECT idempotency_key,authority_data,content_hash
                 FROM ecommerce_unaccepted_analysis_closure_receipt
                WHERE org_id=%s AND project_id=%s
                  AND idempotency_key=ANY(%s) ORDER BY idempotency_key""",
            (*base.SCOPE.values(), list(EXPECTED_CLOSURES)),
        ).fetchall()
        active_runs = conn.execute(
            """SELECT count(*) AS n FROM ecommerce_investigation_run_state_head h
                 JOIN ecommerce_investigation_run r USING(org_id,project_id,run_id)
                WHERE h.org_id=%s AND h.project_id=%s AND r.case_id=%s
                  AND lower(h.lifecycle) NOT IN ('succeeded','failed','cancelled')""",
            (*base.SCOPE.values(), base.CASE_ID),
        ).fetchone()["n"]
        growth_plans = conn.execute(
            """SELECT count(*) AS n FROM ecommerce_analyst_growth_plan_head
                WHERE org_id=%s AND project_id=%s""",
            tuple(base.SCOPE.values()),
        ).fetchone()["n"]
        canary = conn.execute(
            """SELECT count(*) AS n FROM automation_occurrence
                WHERE org_id='dev-org' AND project_id='dev-project' AND policy_id=%s""",
            (base.POLICY_ID,),
        ).fetchone()["n"]
    if None in (attempt, definition, recovery, case, policy):
        raise RuntimeError("complete AO recovery and advisor authority required")
    return {
        "attempt": dict(attempt),
        "definition": dict(definition),
        "recovery": dict(recovery),
        "snapshot": dict(snapshot_facts),
        "runtime": dict(runtime_facts),
        "case": case["authority_data"],
        "policy": policy["authority_data"],
        "occurrences": [dict(row) for row in occurrences],
        "closures": [dict(row) for row in closures],
        "activeRuns": active_runs,
        "growthPlanHeads": growth_plans,
        "canaryOccurrences": canary,
    }


def preflight(previous, profile, _plane) -> dict:
    facts = _current_facts(previous)
    attempt, definition, recovery = facts["attempt"], facts["definition"], facts["recovery"]
    snapshot_facts = facts["snapshot"]
    occurrences = facts["occurrences"]
    closures = facts["closures"]
    if attempt.get("state") != "succeeded" or attempt.get("completed_at") is None:
        raise RuntimeError("AO recovery is not terminal-success; Product preflight was not opened")
    current = profile.run("preflight")
    if (
        current.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN"
        or attempt.get("attempt_id") != ATTEMPT_ID
        or attempt.get("state") != "succeeded"
        or attempt.get("installation_id") != successor.AO_ID
        or attempt.get("generation") != successor.AO_GENERATION
        or attempt.get("execution_epoch") != 3
        or attempt.get("operation_kind") != "recoverable_store"
        or attempt.get("completed_at") is None
        or attempt.get("terminal_reason_code") is not None
        or definition != {
            "definition_id": str(DEFINITION_ID),
            "revision": 59,
            "state": "enabled",
            "installation_id": successor.AO_ID,
            "generation": successor.AO_GENERATION,
        }
        or recovery.get("revision") != 19
        or recovery.get("current_definition_revision") != 59
        or recovery.get("input_manifest_hash") != snapshot.MANIFEST
        or facts["runtime"] != {"routes": 9, "live_resources": 3, "canary_bindings": 0}
        or snapshot_facts != {
            "members": 12,
            "succeeded_runs": 12,
            "datasets": 12,
            "relationships": 1,
            "link_commands": 1,
            "link_count": 1168,
            "retirements": 1,
            "store_receipts": 1,
            "live_links": 1168,
        }
        or facts["case"].get("revision") != 4
        or facts["case"].get("version") != 4
        or facts["case"].get("lifecycle") != "ACTIVE"
        or facts["case"].get("schedulePolicyRef", {}).get("revision") != 2
        or facts["policy"].get("revision") != 2
        or facts["policy"].get("version") != 2
        or facts["policy"].get("enabled") is not True
        or facts["policy"].get("caseRef", {}).get("revision") != 3
        or {row["occurrence_id"] for row in occurrences} != EXPECTED_OCCURRENCES
        or {row["policy_revision"] for row in occurrences} != {1, 2}
        or any(row["status"] != "cancelled" for row in occurrences)
        or {row["idempotency_key"] for row in closures} != EXPECTED_CLOSURES
        or any(
            row["authority_data"].get("businessAccepted") is not False
            or row["authority_data"].get("priorOccurrence", {}).get("occurrence_id")
            not in EXPECTED_OCCURRENCES
            or row["authority_data"].get("targetEvidence", {}).get("receiptCount") != 0
            or row["authority_data"].get("targetEvidence", {}).get("runCount") != 0
            for row in closures
        )
        or facts["activeRuns"] != 0
        or facts["growthPlanHeads"] != 0
        or facts["canaryOccurrences"] != 0
    ):
        raise RuntimeError("AO Policy v3 entry gate is not green")
    return {
        "outcome": "AO_ADVISOR_BASELINE_V3_PREFLIGHT_GREEN",
        "installationRef": current["currentInstallationRef"],
        "runtimeBinding": current["runtimeBinding"],
        "facts": facts,
    }


def _policy(case: dict, *, enabled: bool = True) -> dict:
    return {
        "schedulePolicyId": base.POLICY_ID,
        "caseRef": {
            "resourceType": "BusinessInvestigationCaseRevision",
            "resourceId": base.CASE_ID,
            "revision": case["revision"],
            "contentHash": case["contentHash"],
            "receiptId": None,
        },
        "analysisType": "initial_store_analysis",
        "policyKind": "initial_checkup",
        "cadence": "once",
        "enabled": enabled,
        "overlapPolicy": "skip",
        "timezone": "Asia/Shanghai",
        "weeklyDay": None,
        "localTime": None,
    }


def approve(previous, _profile, _plane) -> dict:
    from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_budget_reservation_store import canonical_hash
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.tenant_scope import TenantScope

    prepared = _load("preflight")
    case = prepared["facts"]["case"]
    policy = _policy(case)
    payload = {
        "caseId": base.CASE_ID,
        "schedulePolicyId": base.POLICY_ID,
        "expectedPolicyRevision": 2,
        "expectedCaseVersion": 4,
        "policyHash": canonical_hash(policy, prefixed=True),
    }
    intent = {"maker": base.MAKER, "checker": base.CHECKER, "payload": payload}
    base.freeze_or_match(STATE / "approval-intent.json", intent)
    scope = TenantScope(**base.SCOPE)
    store = AipActionStore(previous._web_connection)
    snapshot_row = store.action_type_snapshot(scope, "ecommerce_growth_schedule_put")
    body = CreateActionProposalRequest(
        actionTypeId="ecommerce_growth_schedule_put",
        purpose="栖月汇经营参谋在 AO 完整恢复后的 Policy v3 自然首链",
        payload=payload,
        expiresAt=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    risk = classify_action_risk(
        "ecommerce_growth_schedule_put", snapshot_row, payload, body.risk_hint
    )
    reviewed = store.create_proposal(
        scope, base.MAKER, APPROVAL_KEY + ":proposal", body, snapshot_row, risk
    )
    reviewed = store.decide(
        scope,
        base.CHECKER,
        reviewed.proposal.id,
        APPROVAL_KEY + ":approval:1",
        DecideActionProposalRequest(
            expectedProposalVersion=reviewed.proposal.version,
            expectedProposalHash=reviewed.proposal.proposal_hash,
            decision=ApprovalDecision.APPROVED,
            reason="已核验 AO 恢复终态、历史 occurrence 关闭与租户隔离，同意 Policy v3",
            approvalExpiresAt=reviewed.proposal.expires_at - timedelta(minutes=5),
        ),
        ("admin",),
    )
    if reviewed.proposal.status.value != "approved":
        raise RuntimeError("approved AO Policy v3 proposal required")
    return {
        "outcome": "AO_ADVISOR_BASELINE_V3_APPROVED",
        "proposalId": reviewed.proposal.id,
        "approvalRef": base._approval_ref(reviewed),
        "policy": policy,
        "payload": payload,
    }


def put(previous, profile, plane) -> dict:
    scope, router, target = base._router(
        previous, profile, plane, subject=base.ACTOR, roles=["admin"]
    )
    approved = _load("approval")
    command = {
        "idempotencyKey": POLICY_KEY,
        "caseId": base.CASE_ID,
        "expectedPolicyRevision": 2,
        "expectedCaseVersion": 4,
        "policy": approved["policy"],
        "approvalRef": approved["approvalRef"],
    }
    base.freeze_or_match(STATE / "policy-intent.json", command)
    result = router.dispatch(
        scope=scope,
        operation_id="ecommerce_growth_schedule_put",
        command=command,
        expected_runtime=target,
    )
    return {"outcome": "AO_ADVISOR_BASELINE_V3_SAVED", **result}


def observe(previous, _profile, _plane) -> dict:
    facts = _current_facts(previous)
    with previous._scope_and_connection()[1] as conn:
        controls = conn.execute(
            """SELECT authority FROM ecommerce_schedule_policy_control_receipt
                WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s
                ORDER BY created_at""",
            (*base.SCOPE.values(), base.POLICY_ID),
        ).fetchall()
        runs = conn.execute(
            """SELECT h.authority_data FROM ecommerce_investigation_run_state_head h
                 JOIN ecommerce_investigation_run r USING(org_id,project_id,run_id)
                WHERE h.org_id=%s AND h.project_id=%s AND r.case_id=%s ORDER BY h.updated_at""",
            (*base.SCOPE.values(), base.CASE_ID),
        ).fetchall()
    return {
        "outcome": "AO_ADVISOR_BASELINE_V3_OBSERVED",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "facts": facts,
        "controls": [row["authority"] for row in controls],
        "runs": [row["authority_data"] for row in runs],
    }


def disable(_previous, _profile, _plane) -> dict:
    observed = _load("observe")
    policy = observed["facts"]["policy"]
    current_occurrences = [
        row for row in observed["facts"]["occurrences"] if row["policy_revision"] == 3
    ]
    if (
        policy.get("revision") != 3
        or len(current_occurrences) != 1
        or current_occurrences[0]["status"] not in {"succeeded", "failed", "cancelled"}
        or observed["facts"]["activeRuns"] != 0
    ):
        raise RuntimeError("terminal AO Policy v3 occurrence required before disable")
    return {
        "outcome": "AO_ADVISOR_BASELINE_V3_DISABLE_READY",
        "policy": _policy(observed["facts"]["case"], enabled=False),
        "note": "a fresh approval and canonical write are required; no mutation was performed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("preflight", "approval", "put", "observe", "disable"))
    args = parser.parse_args()
    output = STATE / f"{args.action}-result.json"
    if output.exists():
        raise RuntimeError("immutable AO v3 output exists; inspect before retry")
    previous, profile, plane = setup()
    result = {
        "preflight": preflight,
        "approval": approve,
        "put": put,
        "observe": observe,
        "disable": disable,
    }[args.action](previous, profile, plane)
    base.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
