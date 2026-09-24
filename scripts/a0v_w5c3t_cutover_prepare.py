#!/usr/bin/env python3
"""Prepare the exact nine-route cutover once, without committing routes."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3s_cutover_approval_recovery as approved
import a0v_w5c3o_uninstalled_ds_register as registered
import a0v_w5c3n_route_authority_inventory as inventory_wave
import a0v_w5c3m_natural_enable as enabled
import a0v_w5c3pr_approval_permission_inventory as recovery

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3t-cutover-prepare")
KEY = "a0v-w5c3t-third-successor-cutover-prepare-20260924-v1"
OPERATION = str(uuid5(NAMESPACE_URL, KEY))
ACTOR = registered.ACTOR


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
        raise ValueError("W5C3T_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _approval():
    path = approved.STATE / "result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5C3T_APPROVAL_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _plane():
    registered.stage.prior.configuration._configure()
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(registration_connect=registration_connection)


def preflight():
    from aos_api.aip_action_store import AipActionStore
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import _approval_ref
    result = approved.audit()
    approval = _approval()
    facts = inventory_wave.inventory()
    runtime = enabled.observe()
    proposal = AipActionStore(recovery.head_action_connection).get_proposal(
        TenantScope("org-org", "dev-project"), approval["proposalId"])
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        operation = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_dispatch_cutover_operation
            WHERE org_id='org-org' AND project_id='dev-project'
            AND idempotency_key=%s) AS key_count,
          (SELECT count(*) FROM extension_dispatch_cutover_operation
            WHERE org_id='org-org' AND project_id='dev-project'
            AND cutover_operation_id=%s) AS id_count""",
            (KEY, OPERATION)).fetchone())
    if (result["outcome"] != "W5C3S_APPROVAL_GREEN"
            or proposal.proposal.status.value != "approved"
            or proposal.proposal.expires_at <= datetime.now(timezone.utc)
            or _approval_ref(proposal, expected_count=2) != approval["approvalRef"]
            or approval["approvalRef"]["receiptId"] is not None
            or approval["payload"]["targetInstallationId"] != registered.INSTALLATION
            or approval["payload"]["expectedGroupRevision"] != 365
            or approval["policy"]["externalEffectsAllowed"] is not False
            or approval["policy"]["fallbackAllowed"] is not False
            or facts["prior"]["hostPid"] != runtime["host"]["pid"]
            or len(facts["routes"]) != 9
            or any(row["revision"] != 338 or row["cutover_group_revision"] != 365
                   or row["handler_kind"] != "legacy" or row["operation_fence"] is not True
                   for row in facts["routes"])
            or facts["oldSchedules"] != {"total": 12, "enabled": 0}
            or runtime["counts"]["attempts"] != 0
            or runtime["counts"]["canary"] != 0
            or operation != {"key_count": 0, "id_count": 0}):
        raise ValueError("W5C3T_PREPARE_GATE_DRIFT")
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
    request = CutoverPrepareRequest(
        cutoverOperationId=UUID(OPERATION), idempotencyKey=KEY,
        approvalRef={key: value for key, value in approval["approvalRef"].items()
                     if key != "receiptId"},
        checkpoint={"legacyEntry": "canonical-router", "version": 1},
        occurrenceWatermark=None, pendingTargetReceiptRefs=[],
        **{key: value for key, value in approval["payload"].items()
           if key != "operationIds"})
    return {"outcome": "W5C3T_PREPARE_PREFLIGHT_GREEN",
            "request": request.model_dump(mode="json", by_alias=True),
            "requestHash": request.request_hash(),
            "hostPid": runtime["host"]["pid"],
            "businessCounts": runtime["counts"]["business"]}


def prepare():
    from aos_api.ecommerce_growth_cutover import CutoverPrepareRequest
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3T_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False})
    request = CutoverPrepareRequest.model_validate(before["request"])
    receipt = _plane().ecommerce_growth_cutover_service.prepare_activation(
        TenantScope("org-org", "dev-project"), request, actor=ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("result", {"receipt": value})
    return {"outcome": "W5C3T_PREPARE_ACCEPTED", "receipt": value}


def audit():
    intent, receipt = _load("intent"), _load("result")["receipt"]
    facts = inventory_wave.inventory()
    runtime = enabled.observe()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        row = conn.execute("""SELECT cutover_operation_id::text,status,
          expected_group_revision,target_group_revision,request_hash
          FROM extension_dispatch_cutover_operation WHERE org_id='org-org'
          AND project_id='dev-project' AND idempotency_key=%s""", (KEY,)).fetchone()
        receipts = [dict(item) for item in conn.execute("""SELECT receipt_id::text,
          phase,content_hash FROM extension_dispatch_cutover_receipt
          WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_operation_id=%s""", (OPERATION,)).fetchall()]
    if (row is None or dict(row) != {"cutover_operation_id": OPERATION,
            "status": "prepared", "expected_group_revision": 365,
            "target_group_revision": 366, "request_hash": intent["requestHash"]}
            or len(receipts) != 1 or receipts[0]["phase"] != "prepare"
            or receipts[0]["receipt_id"] != receipt["receiptId"]
            or receipts[0]["content_hash"] != receipt["contentHash"]
            or facts["routes"][0]["cutover_group_revision"] != 365
            or facts["oldSchedules"] != {"total": 12, "enabled": 0}
            or facts["prior"]["hostPid"] != intent["hostPid"]
            or runtime["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3T_PREPARE_AUDIT_DRIFT")
    return {"outcome": "W5C3T_PREPARE_GREEN", "operationId": OPERATION,
            "prepareReceiptId": receipt["receiptId"],
            "targetGroupRevision": 366, "routesStillLegacy": 9,
            "schedulesEnabled": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "prepare", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
