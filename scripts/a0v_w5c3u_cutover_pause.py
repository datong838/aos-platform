#!/usr/bin/env python3
"""Pause exact cutover claims once; leave all nine routes legacy/fenced."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from uuid import UUID

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3u-cutover-pause")
KEY = "a0v-w5c3u-third-successor-cutover-commit-20260924-v1"


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
        raise ValueError("W5C3U_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from aos_api.ecommerce_growth_cutover import CutoverCommitRequest
    prior = prepared.audit()
    receipt = prepared._load("result")["receipt"]
    if (prior["outcome"] != "W5C3T_PREPARE_GREEN"
            or receipt["receiptId"] != prior["prepareReceiptId"]
            or receipt["contentHash"] !=
            "sha256:34750026f38a50e7aceaab78a8a9a53ddd1cb43d038941ce63c5aa656f4e63bc"):
        raise ValueError("W5C3U_PREPARE_RECEIPT_DRIFT")
    request = CutoverCommitRequest(cutoverOperationId=UUID(prepared.OPERATION),
        idempotencyKey=KEY, prepareReceiptRef={"resourceType": "CutoverPrepareReceipt",
        "resourceId": receipt["receiptId"], "revision": 1,
        "contentHash": receipt["contentHash"]})
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        rows = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_dispatch_cutover_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s AND phase='pause') AS pause_receipts,
          (SELECT count(*) FROM extension_dispatch_claim_gate
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_group_id=%s) AS claim_gates,
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved""",
            (prepared.OPERATION, prepared.registered.GROUP)).fetchone())
    if rows != {"pause_receipts": 0, "claim_gates": 0,
                "running": 0, "unresolved": 0}:
        raise ValueError("W5C3U_CLAIM_GATE_DRIFT")
    return {"outcome": "W5C3U_PAUSE_PREFLIGHT_GREEN",
            "request": request.model_dump(mode="json", by_alias=True),
            "requestHash": request.request_hash(), "hostPid": prepared._load("intent")["hostPid"],
            "businessCounts": prepared._load("intent")["businessCounts"]}


def pause():
    from aos_api.ecommerce_growth_cutover import CutoverCommitRequest
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3U_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    request = CutoverCommitRequest.model_validate(before["request"])
    receipt = prepared._plane().ecommerce_growth_cutover_service.begin_activation_commit(
        TenantScope("org-org", "dev-project"), request, actor=prepared.ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("result", {"receipt": value})
    return {"outcome": "W5C3U_PAUSE_ACCEPTED", "receiptId": value["receiptId"],
            "contentHash": value["contentHash"]}


def audit():
    intent, receipt = _load("intent"), _load("result")["receipt"]
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        routes = [dict(row) for row in conn.execute("""SELECT handler_kind,
          installation_id::text,generation::text,execution_epoch,
          operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s""",
          (prepared.registered.GROUP,)).fetchall()]
        operation = dict(conn.execute("""SELECT status FROM extension_dispatch_cutover_operation
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s""", (prepared.OPERATION,)).fetchone())
        phase = [dict(row) for row in conn.execute("""SELECT receipt_id::text,
          phase,content_hash,request_hash FROM extension_dispatch_cutover_receipt
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s AND phase='pause'""",
          (prepared.OPERATION,)).fetchall()]
        gate = [dict(row) for row in conn.execute("""SELECT cutover_operation_id::text,
          claim_paused,revision FROM extension_dispatch_claim_gate
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s""", (prepared.registered.GROUP,)).fetchall()]
    if (operation != {"status": "draining"}
            or len(phase) != 1 or phase[0]["receipt_id"] != receipt["receiptId"]
            or phase[0]["content_hash"] != receipt["contentHash"]
            or phase[0]["request_hash"] != intent["requestHash"]
            or gate != [{"cutover_operation_id": prepared.OPERATION,
                         "claim_paused": True, "revision": 1}]
            or len(routes) != 9
            or any(row != {"handler_kind": "legacy", "installation_id": None,
                    "generation": None, "execution_epoch": None,
                    "operation_fence": True, "revision": 338,
                    "cutover_group_revision": 365} for row in routes)
            or len(runtime["binding"]) != 1
            or runtime["binding"][0]["revision"] != 5
            or runtime["binding"][0]["execution_epoch"] != 3
            or runtime["binding"][0]["enabled"] is not False
            or runtime["binding"][0]["operation_fence"] is not True
            or runtime["binding"][0]["desired_state"] != "enabled"
            or runtime["binding"][0]["observed_state"] != "ready"
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["schedules"] != {"total": 12, "enabled": 0}
            or runtime["counts"]["canary"] != 0
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3U_PAUSE_AUDIT_DRIFT")
    return {"outcome": "W5C3U_PAUSE_GREEN", "operationId": prepared.OPERATION,
            "pauseReceiptId": receipt["receiptId"], "routesStillLegacy": 9,
            "groupRevision": 365, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "pause", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
