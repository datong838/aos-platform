#!/usr/bin/env python3
"""Renew exact cutover approval in the committed, claims-paused window."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_qyh_current_product_event_first_chain as aip
import a0v_w5c3v_cutover_commit as committed
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3pr_approval_permission_inventory as recovery

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3ws-current-approval-refresh")
APPROVAL_KEY = "a0v-w5c3ws-third-successor-current-approval-20260924-v1"
REFRESH_KEY = "a0v-w5c3ws-third-successor-postcommit-refresh-20260924-v1"


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C3WS_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _facts():
    previous = committed.audit()
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_dispatch_cutover_approval_refresh_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s) AS refreshes,
          (SELECT count(*) FROM extension_dispatch_cutover_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s AND phase IN ('validate','resume')) AS final_receipts,
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved,
          (SELECT count(*) FROM aip_action_proposal WHERE org_id='org-org'
            AND project_id='dev-project' AND idempotency_key=%s) AS new_proposals""",
            (prepared.OPERATION, prepared.OPERATION, APPROVAL_KEY + ":proposal")).fetchone())
    if (previous["outcome"] != "W5C3V_COMMIT_GREEN"
            or runtime["host"]["pid"] != committed._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])
            or runtime["counts"]["business"] != committed._load("intent")["businessCounts"]
            or state["final_receipts"] != 0 or state["running"] != 0
            or state["unresolved"] != 0):
        raise ValueError("W5C3WS_FROZEN_GATE_DRIFT")
    return {"runtime": runtime, "state": state}


def approve():
    if STATE.exists():
        raise ValueError("W5C3WS_INTENT_EXISTS_RECONCILE_FIRST")
    facts = _facts()
    old = prepared._approval()
    if (facts["state"]["refreshes"] != 0 or facts["state"]["new_proposals"] != 0
            or old["policy"]["externalEffectsAllowed"] is not False
            or old["policy"]["fallbackAllowed"] is not False):
        raise ValueError("W5C3WS_NEW_APPROVAL_GATE_DRIFT")
    _write("approval-intent", {"key": APPROVAL_KEY, "payload": old["payload"],
                                "policy": old["policy"], "resend": False})
    old_connect = aip._web_connection
    aip._web_connection = recovery.head_action_connection
    try:
        bundle, ref = aip._approve("ecommerce_growth_cutover", old["payload"], APPROVAL_KEY)
    finally:
        aip._web_connection = old_connect
    result = {"proposalId": bundle.proposal.id, "approvalRef": ref,
              "payload": old["payload"], "policy": old["policy"]}
    _write("approval-result", result)
    return {"outcome": "W5C3WS_APPROVED", "proposalId": result["proposalId"],
            "approvalRef": ref}


def refresh():
    from aos_api.aip_action_store import AipActionStore
    from aos_api.ecommerce_growth_cutover import CutoverApprovalRefreshRequest
    from aos_api.tenant_scope import TenantScope
    if (STATE / "refresh-intent.json").exists():
        raise ValueError("W5C3WS_REFRESH_INTENT_EXISTS_RECONCILE_FIRST")
    facts = _facts()
    approval = _load("approval-result")
    bundle = AipActionStore(recovery.head_action_connection).get_proposal(
        TenantScope("org-org", "dev-project"), approval["proposalId"])
    ref = aip._approval_ref(bundle, expected_count=2)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        event = conn.execute("""SELECT expires_at FROM aip_action_approval_event
          WHERE org_id='org-org' AND project_id='dev-project' AND approval_event_id=%s""",
          (ref["resourceId"],)).fetchone()
    if (facts["state"]["refreshes"] != 0 or facts["state"]["new_proposals"] != 1
            or bundle.proposal.status.value != "approved"
            or ref != approval["approvalRef"] or event is None
            or event["expires_at"] <= datetime.now(timezone.utc) + timedelta(minutes=5)):
        raise ValueError("W5C3WS_APPROVAL_EVENT_DRIFT_OR_TOO_SHORT")
    prepare_receipt = prepared._load("result")["receipt"]
    request = CutoverApprovalRefreshRequest(
        cutoverOperationId=prepared.OPERATION, idempotencyKey=REFRESH_KEY,
        prepareReceiptRef={"resourceType": "CutoverPrepareReceipt",
            "resourceId": prepare_receipt["receiptId"], "revision": 1,
            "contentHash": prepare_receipt["contentHash"]},
        approvalRef={key: value for key, value in ref.items() if key != "receiptId"})
    _write("refresh-intent", {"request": request.model_dump(mode="json", by_alias=True),
                              "requestHash": request.request_hash(), "resend": False,
                              "businessCounts": facts["runtime"]["counts"]["business"]})
    receipt = prepared._plane().ecommerce_growth_cutover_service.refresh_activation_approval(
        TenantScope("org-org", "dev-project"), request, actor=prepared.ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("refresh-result", {"receipt": value})
    return {"outcome": "W5C3WS_REFRESH_ACCEPTED", "receiptId": value["receiptId"],
            "contentHash": value["contentHash"]}


def audit():
    intent, result = _load("refresh-intent"), _load("refresh-result")["receipt"]
    facts = _facts()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = [dict(row) for row in conn.execute("""SELECT receipt_id::text,request_hash,
          content_hash,new_approval_ref FROM extension_dispatch_cutover_approval_refresh_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_operation_id=%s""",
          (prepared.OPERATION,)).fetchall()]
    if (facts["state"]["refreshes"] != 1 or len(rows) != 1
            or rows[0]["receipt_id"] != result["receiptId"]
            or rows[0]["request_hash"] != intent["requestHash"]
            or rows[0]["content_hash"] != result["contentHash"]
            or rows[0]["new_approval_ref"] != intent["request"]["approvalRef"]
            or facts["runtime"]["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3WS_REFRESH_AUDIT_DRIFT")
    return {"outcome": "W5C3WS_REFRESH_GREEN", "receiptId": result["receiptId"],
            "operationId": prepared.OPERATION, "claimsPaused": True,
            "routesExtension": 9, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("approve", "refresh", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
