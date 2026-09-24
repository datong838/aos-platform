#!/usr/bin/env python3
"""Register the enabled third installation against DS's exact uninstall/detach."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c3n_route_authority_inventory as inventory_wave
import a0v_w5c3kr_config_stage_recovery as stage
import a0v_w5c3m_natural_enable as enabled
import a0v_w5_ds_successor_business as legacy

ROOT = Path(__file__).resolve().parents[1]
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5c3o-uninstalled-ds-register")
KEY = "a0v-w5c3o-third-successor-registration-20260924-v1"
INSTALLATION = "407059df-6f1f-4927-acd7-8e388692838e"
GENERATION = "7571af17-e2bb-4437-9f04-75812bae56c0"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
DETACH = "d64e1b84-bdf9-4d15-b740-16673fcd651a"
DETACH_HASH = "sha256:85f803080a8d348da90040540c5cc1d3fef48bbee857db3598265eaf0a37dd9c"
LOCK = "sha256:820eb34977f56544428e3ecde4fbbca637d6a8ad9cdbd66d223cbf35d58f7380"
ACTOR = legacy.ACTOR


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
        raise ValueError("W5C3O_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _inflight_and_key():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        return dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND state='running') AS running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a
            JOIN automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) AS unresolved,
          (SELECT count(*) FROM extension_runtime_operation
            WHERE org_id='org-org' AND project_id='dev-project'
            AND status NOT IN ('succeeded','failed','cancelled')) AS pending,
          (SELECT count(*) FROM extension_dispatch_successor_registration_receipt
            WHERE org_id='org-org' AND project_id='dev-project'
          AND idempotency_key=%s) AS key_count""", (KEY,)).fetchone())


def _service():
    stage.prior.configuration._configure()
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.ecommerce_growth_registration_connection import registration_connection
    return build_runtime_control_plane(
        registration_connect=registration_connection).first_dispatch_registration_service


def request_from(facts, *, config_ref, old_head):
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    routes = facts["routes"]
    parent = facts["currentDetachAuthority"]
    if (facts["prior"]["installationId"] != INSTALLATION
            or facts["prior"]["bindingRevision"] != 4
            or facts["prior"]["executionEpoch"] != 3
            or not facts["uninstalledSuccessorGuardLoaded"]
            or facts["newInstallationSuccessorReceipts"]
            or facts["newInstallationSelections"]
            or facts["newInstallationControls"] != {"revisions": 0, "pipelines": 0}
            or facts["oldSchedules"] != {"total": 12, "enabled": 0}
            or str(old_head["installation_id"]) != legacy.DS_ID
            or old_head["state"] != "uninstalled"
            or parent["old_active_revision"] is not None
            or parent is None or parent["receipt_id"] != DETACH
            or parent["content_hash"] != DETACH_HASH
            or parent["status"] != "detached"
            or parent["lifecycle_status"] != "detached"
            or parent["fenced_group_revision"] != 364
            or parent["disable_status"] != "succeeded"
            or parent["disable_phase"] != "succeeded"
            or parent["enabled"] is not False
            or parent["operation_fence"] is not True
            or parent["desired_state"] != "uninstalled"
            or parent["observed_state"] != "stopped"
            or parent["unsafe_resources"] != 0
            or len(routes) != 9
            or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
            or any(row["handler_kind"] != "legacy" or row["operation_fence"] is not True
                   or row["installation_id"] is not None or row["generation"] is not None
                   or row["execution_epoch"] is not None or row["revision"] != 338
                   or row["cutover_group_revision"] != 365 for row in routes)):
        raise ValueError("W5C3O_AUTHORITY_DRIFT")
    snapshot = [{"operationId": row["operation_id"], "handlerKind": row["handler_kind"],
                 "installationId": row["installation_id"], "generation": row["generation"],
                 "executionEpoch": row["execution_epoch"], "operationFence": row["operation_fence"],
                 "revision": row["revision"], "cutoverGroupId": row["cutover_group_id"],
                 "cutoverGroupRevision": row["cutover_group_revision"]} for row in routes]
    if snapshot != parent["dispatch_snapshot"]:
        raise ValueError("W5C3O_DETACH_SNAPSHOT_DRIFT")
    return SuccessorDispatchRegistrationRequest.model_validate({
        "schemaVersion": "aos.ecommerce.successor-dispatch-registration/v1",
        "expectedGroupRevision": 365,
        "predecessorDetachReceiptRef": {"resourceType": "DispatchDisableDetachReceipt",
            "resourceId": DETACH, "revision": 1, "contentHash": DETACH_HASH},
        "registration": {"schemaVersion": "aos.ecommerce.first-dispatch-registration/v1",
            "installationRef": {"installationId": INSTALLATION, "revision": 5,
                "lockHash": LOCK, "overlayRevision": "a0v-canonical-ecommerce-v1"},
            "generation": GENERATION, "bindingRevision": 4, "executionEpoch": 3,
            "configRef": config_ref, "groupId": GROUP, "idempotencyKey": KEY}})


def preview():
    facts = inventory_wave.inventory()
    observed = enabled.observe()
    old = enabled.ds._current().observe_installation(legacy.DS_ID)
    with stage._configured():
        config_ref = stage.prior._load("result")["configRef"]
        staged_document = stage.prior._load("intent")["document"]
    stage.prior.configuration._configure()
    current_document = stage.prior.configuration._document().model_dump(mode="json")
    counts = _inflight_and_key()
    if (counts != {"running": 0, "unresolved": 0, "pending": 0, "key_count": 0}
            or observed["installation"]["lock_hash"] != LOCK
            or observed["installation"]["overlay_revision"] != "a0v-canonical-ecommerce-v1"
            or observed["binding"][0]["config_ref"] != config_ref
            or current_document != staged_document
            or observed["host"]["pid"] != facts["prior"]["hostPid"]):
        raise ValueError("W5C3O_RUNTIME_OR_INFLIGHT_DRIFT")
    request = request_from(facts, config_ref=config_ref, old_head=old["head"])
    from aos_api.tenant_scope import TenantScope
    service = _service()
    with service._transaction(TenantScope("org-org", "dev-project")) as conn:
        authority = service.validate_current_authority_in_transaction(conn,
            scope=TenantScope("org-org", "dev-project"), request=request.registration,
            actor=ACTOR)
    if authority.get("currentConfigurationValidated") is not True or authority.get(
            "currentReleaseValidated") is not True:
        raise ValueError("W5C3O_REGISTRATION_OWNER_AUTHORITY_MISSING")
    return {"outcome": "W5C3O_REGISTRATION_PREVIEW_GREEN",
            "request": request.model_dump(mode="json", by_alias=True),
            "requestHash": request.request_hash(), "hostPid": observed["host"]["pid"],
            "businessCounts": observed["counts"]["business"]}


def register():
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from aos_api.tenant_scope import TenantScope
    if STATE.exists():
        raise ValueError("W5C3O_INTENT_EXISTS_RECONCILE_FIRST")
    value = preview()
    _write("intent", {**value, "resend": False})
    request = SuccessorDispatchRegistrationRequest.model_validate(value["request"])
    service = _service()
    receipt = service.register_successor(scope=TenantScope("org-org", "dev-project"),
        request=request, actor=ACTOR)
    if receipt["requestHash"] != value["requestHash"] or receipt["replayed"] is not False:
        raise ValueError("W5C3O_REGISTRATION_RECEIPT_DRIFT")
    _write("result", {"receipt": receipt})
    return {"outcome": "W5C3O_REGISTRATION_ACCEPTED", "receiptId": receipt["receiptId"],
            "requestHash": receipt["requestHash"]}


def audit():
    intent, receipt = _load("intent"), _load("result")["receipt"]
    facts = inventory_wave.inventory()
    if (receipt["requestHash"] != intent["requestHash"]
            or receipt["executable"] is not False
            or len(facts["newInstallationSuccessorReceipts"]) != 1
            or facts["newInstallationSuccessorReceipts"][0]["receipt_id"] != receipt["receiptId"]
            or facts["newInstallationSuccessorReceipts"][0]["content_hash"] != receipt["contentHash"]
            or facts["prior"]["hostPid"] != intent["hostPid"]
            or enabled.observe()["counts"]["business"] != intent["businessCounts"]):
        raise ValueError("W5C3O_REGISTRATION_AUDIT_DRIFT")
    return {"outcome": "W5C3O_REGISTRATION_GREEN", "receiptId": receipt["receiptId"],
            "requestHash": receipt["requestHash"], "routeGroupRevision": 365,
            "schedulesEnabled": 0, "canary": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preview", "register", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
