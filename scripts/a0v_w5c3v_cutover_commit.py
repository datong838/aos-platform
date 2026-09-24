#!/usr/bin/env python3
"""Atomically commit the prepared nine-route cutover once."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3u_cutover_pause as paused
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3s_cutover_approval_recovery as approved
import a0v_w5c3pr_approval_permission_inventory as recovery
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3v-cutover-commit")


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
        raise ValueError("W5C3V_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from aos_api.aip_action_store import AipActionStore
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import _approval_ref
    previous = paused.audit()
    approval = prepared._approval()
    proposal = AipActionStore(recovery.head_action_connection).get_proposal(
        TenantScope("org-org", "dev-project"), approval["proposalId"])
    request = paused._load("intent")["request"]
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_dispatch_cutover_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s AND phase='commit') AS commits,
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved""",
            (prepared.OPERATION,)).fetchone())
    if (previous["outcome"] != "W5C3U_PAUSE_GREEN"
            or proposal.proposal.status.value != "approved"
            or proposal.proposal.expires_at <= datetime.now(timezone.utc)
            or _approval_ref(proposal, expected_count=2) != approval["approvalRef"]
            or request["idempotencyKey"] != paused.KEY
            or request["cutoverOperationId"] != prepared.OPERATION
            or runtime["binding"][0]["revision"] != 5
            or runtime["binding"][0]["operation_fence"] is not True
            or runtime["host"]["pid"] != paused._load("intent")["hostPid"]
            or state != {"commits": 0, "running": 0, "unresolved": 0}):
        raise ValueError("W5C3V_COMMIT_GATE_DRIFT")
    return {"outcome": "W5C3V_COMMIT_PREFLIGHT_GREEN", "request": request,
            "requestHash": paused._load("intent")["requestHash"],
            "pauseReceiptId": paused._load("result")["receipt"]["receiptId"],
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def commit():
    from aos_api.ecommerce_growth_cutover import CutoverCommitRequest
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3V_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    request = CutoverCommitRequest.model_validate(before["request"])
    if request.request_hash() != before["requestHash"]:
        raise ValueError("W5C3V_EXACT_PAUSE_REQUEST_REQUIRED")
    receipt = prepared._plane().ecommerce_growth_cutover_service.commit_activation(
        TenantScope("org-org", "dev-project"), request, actor=prepared.ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("result", {"receipt": value})
    return {"outcome": "W5C3V_COMMIT_ACCEPTED", "receiptId": value["receiptId"],
            "contentHash": value["contentHash"]}


def audit():
    intent, receipt = _load("intent"), _load("result")["receipt"]
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        operation = dict(conn.execute("""SELECT status FROM extension_dispatch_cutover_operation
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s""", (prepared.OPERATION,)).fetchone())
        phases = [dict(row) for row in conn.execute("""SELECT receipt_id::text,
          phase,content_hash,request_hash FROM extension_dispatch_cutover_receipt
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s AND phase IN ('prepare','pause','commit')
          ORDER BY created_at""", (prepared.OPERATION,)).fetchall()]
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,
          operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (prepared.registered.GROUP,)).fetchall()]
        gate = [dict(row) for row in conn.execute("""SELECT cutover_operation_id::text,
          claim_paused FROM extension_dispatch_claim_gate WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s""",
          (prepared.registered.GROUP,)).fetchall()]
    if (operation != {"status": "committed"}
            or [row["phase"] for row in phases] != ["prepare", "pause", "commit"]
            or phases[2]["receipt_id"] != receipt["receiptId"]
            or phases[2]["content_hash"] != receipt["contentHash"]
            or phases[2]["request_hash"] != intent["requestHash"]
            or len(routes) != 9
            or any(row["handler_kind"] != "extension"
                   or row["installation_id"] != prepared.registered.INSTALLATION
                   or row["generation"] != prepared.registered.GENERATION
                   or row["execution_epoch"] != 3 or row["operation_fence"] is not False
                   or row["revision"] != 339 or row["cutover_group_revision"] != 366
                   for row in routes)
            or gate != [{"cutover_operation_id": prepared.OPERATION,
                         "claim_paused": True}]
            or runtime["binding"][0]["revision"] != 5
            or runtime["binding"][0]["operation_fence"] is not True
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["schedules"] != {"total": 12, "enabled": 0}
            or runtime["counts"]["canary"] != 0
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3V_COMMIT_AUDIT_DRIFT")
    return {"outcome": "W5C3V_COMMIT_GREEN", "operationId": prepared.OPERATION,
            "commitReceiptId": receipt["receiptId"], "routeRevision": 339,
            "groupRevision": 366, "routesExtension": 9,
            "claimsPaused": True, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "commit", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
