#!/usr/bin/env python3
"""Validate once under refreshed exact current cutover approval."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3w_cutover_validate as prior
import a0v_w5c3ws_current_approval_refresh as refreshed
import a0v_w5c3t_cutover_prepare as prepared

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3wt-current-validate")
KEY = "a0v-w5c3wt-third-successor-current-finalize-20260924-v1"


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
        raise ValueError("W5C3WT_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    from aos_api.ecommerce_growth_cutover import CutoverFinalizeRequest
    prior_facts = prior.preflight()
    refresh = refreshed.audit()
    approval = refreshed._load("approval-result")["approvalRef"]
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        event = conn.execute("""SELECT expires_at FROM aip_action_approval_event
          WHERE org_id='org-org' AND project_id='dev-project' AND approval_event_id=%s""",
          (approval["resourceId"],)).fetchone()
        final = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_cutover_receipt
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_operation_id=%s
          AND phase IN ('validate','resume')""", (prepared.OPERATION,)).fetchone()["n"]
    if (refresh["outcome"] != "W5C3WS_REFRESH_GREEN" or event is None
            or event["expires_at"] <= datetime.now(timezone.utc) + timedelta(minutes=3)
            or final != 0 or prior_facts["outcome"] != "W5C3W_VALIDATE_PREFLIGHT_GREEN"):
        raise ValueError("W5C3WT_CURRENT_APPROVAL_GATE_DRIFT")
    request = CutoverFinalizeRequest.model_validate(
        {**prior_facts["request"], "idempotencyKey": KEY})
    return {"outcome": "W5C3WT_PREFLIGHT_GREEN",
            "request": request.model_dump(mode="json", by_alias=True),
            "requestHash": request.request_hash(),
            "hostPid": prior_facts["hostPid"],
            "businessCounts": prior_facts["businessCounts"]}


def validate():
    from aos_api.ecommerce_growth_cutover import CutoverFinalizeRequest
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3WT_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "resend": False,
                      "priorFailedKey": prior.KEY})
    request = CutoverFinalizeRequest.model_validate(before["request"])
    receipt = prepared._plane().ecommerce_growth_cutover_service.validate_activation(
        TenantScope("org-org", "dev-project"), request, actor=prepared.ACTOR)
    value = receipt.model_dump(mode="json", by_alias=True)
    _write("result", {"receipt": value})
    return {"outcome": "W5C3WT_VALIDATE_ACCEPTED", "receiptId": value["receiptId"],
            "contentHash": value["contentHash"]}


def audit():
    original = prior.STATE
    try:
        prior.STATE = STATE
        value = prior.audit()
    finally:
        prior.STATE = original
    if value["outcome"] != "W5C3W_VALIDATE_GREEN":
        raise ValueError("W5C3WT_VALIDATE_AUDIT_DRIFT")
    return {**value, "outcome": "W5C3WT_VALIDATE_GREEN"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "validate", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
