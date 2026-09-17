#!/usr/bin/env python3
"""Renew approval and write baseline Policy v2 after audited v1 pre-target closure."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import a0v_q_advisor_baseline as base


STATE = base.STATE / "v2"
APPROVAL_KEY = "a0v-s-advisor-baseline-schedule-approval-20260917-v2"
POLICY_KEY = "a0v-s-advisor-baseline-policy-put-20260917-v2"
CLOSURE_KEY = "a0v-s-baseline-pre-target-close-20260917"


def _load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise RuntimeError(f"private v2 {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def _current(previous) -> tuple[dict, dict, dict]:
    with previous._scope_and_connection()[1] as conn:
        case = conn.execute("""SELECT r.authority_data FROM ecommerce_investigation_case_head h
          JOIN ecommerce_investigation_case_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
            AND r.case_id=h.case_id AND r.revision=h.current_revision
          WHERE h.org_id=%s AND h.project_id=%s AND h.case_id=%s""",
          (*base.SCOPE.values(), base.CASE_ID)).fetchone()
        policy = conn.execute("""SELECT authority_data FROM ecommerce_investigation_schedule_policy_head
          WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s""",
          (*base.SCOPE.values(), base.POLICY_ID)).fetchone()
        closure = conn.execute("""SELECT authority_data,content_hash
          FROM ecommerce_unaccepted_analysis_closure_receipt
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*base.SCOPE.values(), CLOSURE_KEY)).fetchone()
    if case is None or policy is None or closure is None:
        raise RuntimeError("current v1 baseline and closure authority required")
    return case["authority_data"], policy["authority_data"], dict(closure)


def prepare(previous, preflight, _plane) -> dict:
    current = preflight.run("preflight")
    case, policy, closure = _current(previous)
    if (
        current.get("outcome") != "PRODUCT_CURRENT_PREFLIGHT_GREEN"
        or case.get("revision") != 3 or case.get("version") != 3
        or policy.get("revision") != 1 or policy.get("version") != 1
        or policy.get("caseRef", {}).get("revision") != 2
        or case.get("schedulePolicyRef", {}).get("revision") != 1
        or closure["authority_data"].get("businessAccepted") is not False
        or closure["authority_data"].get("priorOccurrence", {}).get("status") != "needs_attention"
        or closure["authority_data"].get("targetEvidence", {}).get("receiptCount") != 0
        or closure["authority_data"].get("targetEvidence", {}).get("runCount") != 0
    ):
        raise RuntimeError("exact closed v1 baseline authority required")
    return {
        "outcome": "S_ADVISOR_BASELINE_V2_PREPARED",
        "case": case, "policy": policy,
        "closureReceipt": {"receiptId": closure["authority_data"]["receiptId"],
                           "contentHash": closure["content_hash"]},
        "installationRef": current["currentInstallationRef"],
        "runtimeBinding": current["runtimeBinding"],
    }


def _policy(case: dict) -> dict:
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
        "enabled": True,
        "overlapPolicy": "skip",
        "timezone": "Asia/Shanghai",
        "weeklyDay": None,
        "localTime": None,
    }


def approve(previous, _preflight, _plane) -> dict:
    from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_budget_reservation_store import canonical_hash
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.tenant_scope import TenantScope

    prepared = _load("prepare")
    policy = _policy(prepared["case"])
    payload = {
        "caseId": base.CASE_ID,
        "schedulePolicyId": base.POLICY_ID,
        "expectedPolicyRevision": 1,
        "expectedCaseVersion": 3,
        "policyHash": canonical_hash(policy, prefixed=True),
    }
    intent = {"maker": base.MAKER, "checker": base.CHECKER, "payload": payload}
    base.freeze_or_match(STATE / "approval-intent.json", intent)
    scope = TenantScope(**base.SCOPE)
    store = AipActionStore(previous._web_connection)
    snapshot = store.action_type_snapshot(scope, "ecommerce_growth_schedule_put")
    body = CreateActionProposalRequest(
        actionTypeId="ecommerce_growth_schedule_put",
        purpose="栖月汇经营参谋基线计划 v1 已知前置失败后的受控续签",
        payload=payload,
        expiresAt=datetime.now(timezone.utc) + timedelta(hours=2),
    )
    risk = classify_action_risk("ecommerce_growth_schedule_put", snapshot, payload, body.risk_hint)
    reviewed = store.create_proposal(
        scope, base.MAKER, APPROVAL_KEY + ":proposal", body, snapshot, risk,
    )
    reviewed = store.decide(
        scope, base.CHECKER, reviewed.proposal.id, APPROVAL_KEY + ":approval:1",
        DecideActionProposalRequest(
            expectedProposalVersion=reviewed.proposal.version,
            expectedProposalHash=reviewed.proposal.proposal_hash,
            decision=ApprovalDecision.APPROVED,
            reason="已核验 v1 无目标受理并完成不可变 closure，同意 Policy v2 自然重试",
            approvalExpiresAt=reviewed.proposal.expires_at - timedelta(minutes=5),
        ),
        ("admin",),
    )
    if reviewed.proposal.status.value != "approved":
        raise RuntimeError("approved v2 schedule proposal required")
    return {"outcome": "S_ADVISOR_BASELINE_V2_APPROVED", "proposalId": reviewed.proposal.id,
            "approvalRef": base._approval_ref(reviewed), "policy": policy, "payload": payload}


def put(previous, preflight, plane) -> dict:
    scope, router, target = base._router(
        previous, preflight, plane, subject=base.ACTOR, roles=["admin"],
    )
    approved = _load("approval")
    command = {
        "idempotencyKey": POLICY_KEY,
        "caseId": base.CASE_ID,
        "expectedPolicyRevision": 1,
        "expectedCaseVersion": 3,
        "policy": approved["policy"],
        "approvalRef": approved["approvalRef"],
    }
    base.freeze_or_match(STATE / "policy-intent.json", command)
    result = router.dispatch(
        scope=scope, operation_id="ecommerce_growth_schedule_put",
        command=command, expected_runtime=target,
    )
    return {"outcome": "S_ADVISOR_BASELINE_V2_SAVED", **result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "approval", "put"))
    args = parser.parse_args()
    output = STATE / f"{args.action}-result.json"
    if output.exists():
        raise RuntimeError("immutable v2 output exists; inspect before retry")
    previous, preflight, plane = base.setup()
    result = {"prepare": prepare, "approval": approve, "put": put}[args.action](
        previous, preflight, plane,
    )
    base.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    os.environ.setdefault("AOS_DOTENV_DISABLED", "1")
    main()
