#!/usr/bin/env python3
"""Approve only the non-effect nine-route successor cutover."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3o_uninstalled_ds_register as registered
import a0v_w5c3n_route_authority_inventory as inventory_wave
import a0v_w5c3m_natural_enable as enabled

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3p-cutover-approval")
KEY = "a0v-w5c3p-third-successor-cutover-approval-20260924-v1"
POLICY_ID = "a0v-w5c3p-third-successor-cutover-20260924"


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
        raise ValueError("W5C3P_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def material(registration):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    receipt = registration["receipt"]
    if (receipt["receiptId"] != "7861c44a-94b4-4e7a-8898-1d9f70a3d214"
            or receipt["requestHash"] != registered._load("intent")["requestHash"]
            or receipt["executable"] is not False):
        raise ValueError("W5C3P_EXACT_REGISTRATION_REQUIRED")
    policy = {"schemaVersion": "aos.runtime-cutover-policy/v1", "policyId": POLICY_ID,
        "revision": 1, "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "targetInstallationId": registered.INSTALLATION,
        "externalEffectsAllowed": False, "fallbackAllowed": False,
        "checkpoint": {"legacyEntry": "canonical-router", "version": 1}}
    payload = {"cutoverGroupId": registered.GROUP, "expectedGroupRevision": 365,
        "targetInstallationId": registered.INSTALLATION,
        "targetGeneration": registered.GENERATION,
        "targetExecutionEpoch": 3, "targetRuntimeRevision": 4,
        "operationIds": sorted(ECOMMERCE_GROWTH_OPERATIONS),
        "policyRef": {"resourceType": "RuntimeCutoverPolicyRevision",
            "resourceId": POLICY_ID, "revision": 1,
            "contentHash": canonical_sha256(policy)},
        "registrationReceiptRef": {"resourceType": "SuccessorDispatchRegistrationReceipt",
            "resourceId": receipt["receiptId"], "revision": 1,
            "contentHash": receipt["contentHash"]}}
    return payload, policy


def preflight():
    registration = registered.audit()
    facts = inventory_wave.inventory()
    observed = enabled.observe()
    payload, policy = material(registered._load("result"))
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        counts = dict(conn.execute("""SELECT
          (SELECT count(*) FROM aip_action_proposal WHERE org_id='org-org'
            AND project_id='dev-project' AND idempotency_key=%s) AS proposals,
          (SELECT count(*) FROM extension_dispatch_cutover_operation
            WHERE org_id='org-org' AND project_id='dev-project'
            AND target_installation_id=%s) AS cutovers""",
            (KEY + ":proposal", registered.INSTALLATION)).fetchone())
    if (registration["receiptId"] != payload["registrationReceiptRef"]["resourceId"]
            or facts["prior"]["hostPid"] != observed["host"]["pid"]
            or facts["newInstallationSuccessorReceipts"][0]["receipt_id"] != registration["receiptId"]
            or len(facts["routes"]) != 9
            or any(row["revision"] != 338 or row["cutover_group_revision"] != 365
                   or row["handler_kind"] != "legacy" or row["operation_fence"] is not True
                   for row in facts["routes"])
            or facts["oldSchedules"] != {"total": 12, "enabled": 0}
            or observed["counts"]["attempts"] != 0
            or observed["counts"]["canary"] != 0
            or counts != {"proposals": 0, "cutovers": 0}):
        raise ValueError("W5C3P_APPROVAL_GATE_DRIFT")
    return {"outcome": "W5C3P_APPROVAL_PREFLIGHT_GREEN", "payload": payload,
            "policy": policy, "hostPid": observed["host"]["pid"],
            "businessCounts": observed["counts"]["business"]}


def approve():
    if STATE.exists():
        raise ValueError("W5C3P_INTENT_EXISTS_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {**before, "idempotencyKey": KEY, "resend": False})
    from a0v_qyh_current_product_event_first_chain import _approve
    bundle, ref = _approve("ecommerce_growth_cutover", before["payload"], KEY)
    result = {"proposalId": bundle.proposal.id, "approvalRef": ref,
              "payload": before["payload"], "policy": before["policy"]}
    _write("result", result)
    return {"outcome": "W5C3P_CUTOVER_APPROVED", "proposalId": result["proposalId"],
            "approvalRef": ref}


def audit():
    from aos_api.aip_action_store import AipActionStore
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import _web_connection, _approval_ref
    intent, result = _load("intent"), _load("result")
    scope = TenantScope("org-org", "dev-project")
    bundle = AipActionStore(_web_connection).get_proposal(scope, result["proposalId"])
    approval_ref = _approval_ref(bundle, expected_count=2)
    facts = inventory_wave.inventory()
    observed = enabled.observe()
    if (bundle.proposal.status.value != "approved"
            or approval_ref != result["approvalRef"]
            or result["payload"] != intent["payload"]
            or result["policy"] != intent["policy"]
            or result["policy"]["externalEffectsAllowed"] is not False
            or result["policy"]["fallbackAllowed"] is not False
            or facts["prior"]["hostPid"] != intent["hostPid"]
            or facts["routes"][0]["cutover_group_revision"] != 365
            or facts["oldSchedules"] != {"total": 12, "enabled": 0}
            or observed["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3P_APPROVAL_AUDIT_DRIFT")
    return {"outcome": "W5C3P_APPROVAL_GREEN", "proposalId": result["proposalId"],
            "approvalRef": approval_ref, "routeGroupRevision": 365,
            "schedulesEnabled": 0}


def reconcile():
    intent = _load("intent")
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        proposal = [dict(row) for row in conn.execute("""SELECT proposal_id::text,status,
          idempotency_key FROM aip_action_proposal WHERE org_id='org-org'
          AND project_id='dev-project' AND idempotency_key=%s""",
          (KEY + ":proposal",)).fetchall()]
        cutover = conn.execute("""SELECT count(*) AS n FROM extension_dispatch_cutover_operation
          WHERE org_id='org-org' AND project_id='dev-project'
          AND target_installation_id=%s""", (registered.INSTALLATION,)).fetchone()["n"]
    facts = inventory_wave.inventory()
    if (proposal or cutover or facts["routes"][0]["cutover_group_revision"] != 365
            or intent["payload"]["targetInstallationId"] != registered.INSTALLATION):
        raise ValueError("W5C3P_APPROVAL_BOUNDARY_NOT_EMPTY")
    return {"outcome": "W5C3P_APPROVAL_PREWRITE_REJECTED", "proposals": 0,
            "cutovers": 0, "routeGroupRevision": 365}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "approve", "audit", "reconcile"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
