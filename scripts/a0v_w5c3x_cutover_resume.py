#!/usr/bin/env python3
"""Resume validated third-successor cutover once under current approval."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3wt_current_validate as validated
import a0v_w5c3ws_current_approval_refresh as refreshed
import a0v_w5c3t_cutover_prepare as prepared
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3x-cutover-resume")


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
        raise ValueError("W5C3X_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from aos_api.ecommerce_growth_cutover import CutoverFinalizeRequest, CutoverExactRef
    previous = validated.audit()
    refresh = refreshed._load("refresh-result")["receipt"]
    approval = refreshed._load("approval-result")["approvalRef"]
    validate_receipt = validated._load("result")["receipt"]
    request = CutoverFinalizeRequest.model_validate(validated._load("intent")["request"])
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        state = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_dispatch_cutover_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s AND phase='resume') AS resumes,
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved,
          (SELECT expires_at FROM aip_action_approval_event WHERE org_id='org-org'
            AND project_id='dev-project' AND approval_event_id=%s) AS approval_expires""",
            (prepared.OPERATION, approval["resourceId"])).fetchone())
    if (previous["outcome"] != "W5C3WT_VALIDATE_GREEN"
            or validate_receipt["receiptId"] != previous["validateReceiptId"]
            or validate_receipt["contentHash"] != "sha256:fdae83e17b454085cacd82eef5f1528921ae9726fad7577aca0c1954913017a2"
            or refresh["receiptId"] != "54edc041-047c-45f5-aabe-8d289e5601b8"
            or request.request_hash() != validated._load("intent")["requestHash"]
            or state["resumes"] != 0 or state["running"] != 0 or state["unresolved"] != 0
            or state["approval_expires"] is None
            or state["approval_expires"] <= datetime.now(timezone.utc) + timedelta(minutes=3)
            or runtime["host"]["pid"] != validated._load("intent")["hostPid"]
            or not enabled.configured._held(runtime["resources"])
            or runtime["counts"]["business"] != validated._load("intent")["businessCounts"]):
        raise ValueError("W5C3X_RESUME_GATE_DRIFT")
    exact = CutoverExactRef(resourceType="CutoverValidateReceipt",
        resourceId=validate_receipt["receiptId"], revision=1,
        contentHash=validate_receipt["contentHash"])
    return {"outcome": "W5C3X_RESUME_PREFLIGHT_GREEN",
            "request": request.model_dump(mode="json", by_alias=True),
            "requestHash": request.request_hash(),
            "validateReceiptRef": exact.model_dump(mode="json", by_alias=True),
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def resume():
    from aos_api.ecommerce_growth_cutover import CutoverFinalizeRequest, CutoverExactRef
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3X_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    request = CutoverFinalizeRequest.model_validate(before["request"])
    exact = CutoverExactRef.model_validate(before["validateReceiptRef"])
    receipt = prepared._plane().ecommerce_growth_cutover_service.resume_activation(
        TenantScope("org-org", "dev-project"), request,
        validate_receipt_ref=exact, actor=prepared.ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("result", {"receipt": value})
    return {"outcome": "W5C3X_RESUME_ACCEPTED", "receiptId": value["receiptId"],
            "contentHash": value["contentHash"]}


def audit():
    intent, receipt = _load("intent"), _load("result")["receipt"]
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        operation = dict(conn.execute("""SELECT status FROM extension_dispatch_cutover_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_operation_id=%s""",
          (prepared.OPERATION,)).fetchone())
        phases = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,
          content_hash,request_hash FROM extension_dispatch_cutover_receipt
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s AND phase IN ('validate','resume') ORDER BY created_at""",
          (prepared.OPERATION,)).fetchall()]
        routes = [dict(row) for row in conn.execute("""SELECT handler_kind,
          installation_id::text,generation::text,execution_epoch,
          operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s""",
          (prepared.registered.GROUP,)).fetchall()]
        gate = [dict(row) for row in conn.execute("""SELECT cutover_operation_id::text,
          claim_paused,revision FROM extension_dispatch_claim_gate WHERE org_id='org-org'
          AND project_id='dev-project' AND cutover_group_id=%s""",
          (prepared.registered.GROUP,)).fetchall()]
    if (operation != {"status": "resumed"}
            or len(phases) != 2 or [row["phase"] for row in phases] != ["validate", "resume"]
            or phases[1] != {"receipt_id": receipt["receiptId"], "phase": "resume",
                             "content_hash": receipt["contentHash"],
                             "request_hash": intent["requestHash"]}
            or len(routes) != 9
            or any(row["handler_kind"] != "extension"
                   or row["installation_id"] != prepared.registered.INSTALLATION
                   or row["generation"] != prepared.registered.GENERATION
                   or row["execution_epoch"] != 3 or row["operation_fence"] is not False
                   or row["revision"] != 339 or row["cutover_group_revision"] != 366
                   for row in routes)
            or gate != [{"cutover_operation_id": prepared.OPERATION,
                         "claim_paused": False, "revision": 2}]
            or runtime["binding"][0]["revision"] != 6
            or runtime["binding"][0]["enabled"] is not True
            or runtime["binding"][0]["operation_fence"] is not False
            or runtime["host"]["pid"] != intent["hostPid"]
            or runtime["counts"]["schedules"] != {"total": 12, "enabled": 0}
            or runtime["counts"]["canary"] != 0
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3X_RESUME_AUDIT_DRIFT")
    return {"outcome": "W5C3X_RESUME_GREEN", "operationId": prepared.OPERATION,
            "resumeReceiptId": receipt["receiptId"], "routesExtension": 9,
            "runtimeRevision": 6, "claimsPaused": False, "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "resume", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
