#!/usr/bin/env python3
"""Register DL directly from the exact detached DK authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dl_replacement_recovery as dl_replacement


successor.STATE = dl_replacement.replacement.STATE / "registration-dl"
successor.AV_ID = "83453fb3-8c39-422c-845b-e152551e0a30"
successor.AV_GENERATION = "f3a1f381-5aeb-4494-a155-164e0ef9e0f5"
successor.LOCK = "sha256:b2985931a11c73d1b6dd1a0b0befd93f8b9f18f5ec2017c486ffc0db63e080dc"
successor.CONFIG = {"configurationId": "3b84ed40-5bcd-4106-a4b2-c1e2359ea5f2", "revision": 1,
                    "hash": "sha256:e96070b75b737b9dbbb301347a7fc70441e2b6a53c9d9d98f35c739e35f21952"}
successor.AU_ID = "b651f4d7-b2a3-4032-a0d2-9b43743deb07"
successor.AU_GENERATION = "fb16d08b-8fcb-4eb0-8c13-7698d16b83b4"
successor.DETACH = "c2cdc20d-7efd-4896-87f6-8afe7c7878ca"
successor.DETACH_HASH = "sha256:0e686f8422c64c3ea7bb19813854a9f653dc6e601bbd363afd468257e5e1045e"
successor.KEY = "a0v-qyh-clean-generation-dl-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 314
successor.PREDECESSOR_GROUP_REVISION = 341
successor.replacement_module = lambda: dl_replacement.replacement

DL_ID = successor.AV_ID
DL_GENERATION = successor.AV_GENERATION
AV_ID = DL_ID
AV_GENERATION = DL_GENERATION
LOCK = successor.LOCK
CONFIG = successor.CONFIG
GROUP = successor.GROUP
KEY = successor.KEY
ACTOR = successor.ACTOR
STATE = successor.STATE


def setup():
    import a0v_event_complete_product_api as product_api
    original_load_launcher = product_api.load_launcher

    def load_launcher():
        launcher = original_load_launcher()
        launcher.DEFAULT_CREDENTIALS = dl_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dl_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dl_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dl():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dl_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dl
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def current_request():
    """Post-reset DL: etag7, six ops (incl. PREPARATION_OWNER_LOST verify), three live leases."""
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    from a0v_formal_text_model_renewal import database_connect
    replacement = successor.replacement_module()
    profile = replacement.load_profile()
    w, v = profile.observe_installation(AV_ID), profile.observe_installation(successor.AU_ID)
    head, bindings = w["head"], w["bindings"]
    live_resources = [row for row in w["resources"]
                      if row.get("cleanup_state") == "pending" and row.get("observed_release") is False]
    if (str(head["installation_id"]) != AV_ID or head["etag_version"] != 7 or head["state"] != "active"
            or head["lock_hash"] != LOCK or len(bindings) != 1 or w["canaryInstallations"] != 0
            or len(live_resources) != 3
            or len(w["operations"]) != 6
            or sum(1 for row in w["operations"] if row["status"] == "succeeded") != 5
            or sum(1 for row in w["operations"]
                   if row["kind"] == "runtime-verify" and row.get("failure_code") == "PREPARATION_OWNER_LOST") != 1):
        raise ValueError("exact live DL installation after preparation-reset required")
    binding = bindings[0]
    if (str(binding["generation"]) != AV_GENERATION or binding["revision"] != 4
            or binding["execution_epoch"] != 3 or binding["enabled"] is not True
            or binding["operation_fence"] is not False or binding["desired_state"] != "enabled"
            or binding["observed_state"] != "ready" or binding["config_ref"] != CONFIG):
        raise ValueError("exact ready DL binding required")
    old = v["bindings"]
    if (str(v["head"]["installation_id"]) != successor.AU_ID or v["head"]["state"] != "active"
            or len(old) != 1 or str(old[0]["generation"]) != successor.AU_GENERATION
            or (old[0]["revision"], old[0]["execution_epoch"]) != (
                successor.PREDECESSOR_BINDING_REVISION, successor.PREDECESSOR_EXECUTION_EPOCH)
            or old[0]["enabled"] is not False or old[0]["operation_fence"] is not True
            or old[0]["desired_state"] != "disabled" or old[0]["observed_state"] != "unknown"):
        raise ValueError("exact detached DK predecessor required")
    with database_connect("aos_meta_head")() as conn:
        parent = conn.execute("""SELECT receipt_id,phase,authority_data,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND receipt_id=%s""", (successor.DETACH,)).fetchone()
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id,generation,execution_epoch,operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s ORDER BY operation_id""", (GROUP,)).fetchall()]
        inflight = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
            AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending""").fetchone())
    if parent is None or inflight != {"running": 0, "unresolved": 0, "runtime_pending": 0}:
        raise ValueError("DK detach and drained tenant required")
    parent = dict(parent)
    if (str(parent["receipt_id"]) != successor.DETACH or parent["phase"] != "detach"
            or parent["content_hash"] != successor.DETACH_HASH
            or canonical_sha256(parent["authority_data"]) != successor.DETACH_HASH):
        raise ValueError("exact DK detach Receipt required")
    if (len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
            or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True
                   or row["revision"] != successor.PREDECESSOR_ROUTE_REVISION
                   or row["cutover_group_revision"] != successor.PREDECESSOR_GROUP_REVISION
                   for row in routes)):
        raise ValueError("exact detached DK route group required")
    return SuccessorDispatchRegistrationRequest.model_validate({
        "schemaVersion": "aos.ecommerce.successor-dispatch-registration/v1",
        "expectedGroupRevision": successor.PREDECESSOR_GROUP_REVISION,
        "predecessorDetachReceiptRef": {"resourceType": "DispatchDisableDetachReceipt",
            "resourceId": successor.DETACH, "revision": 1, "contentHash": successor.DETACH_HASH},
        "registration": {"schemaVersion": "aos.ecommerce.first-dispatch-registration/v1",
            "installationRef": {"installationId": AV_ID, "revision": 7, "lockHash": LOCK,
                                "overlayRevision": head["overlay_revision"]},
            "generation": AV_GENERATION, "bindingRevision": 4, "executionEpoch": 3,
            "configRef": CONFIG, "groupId": GROUP, "idempotencyKey": KEY}})


def register(plane, request):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match
    scope = TenantScope("org-org", "dev-project")
    material = request.model_dump(mode="json", by_alias=True)
    intent = STATE / "register-intent.json"
    freeze_or_match(intent, material)
    service = plane.first_dispatch_registration_service
    try:
        receipt = service.read_successor_receipt(
            scope=scope, installation_id=DL_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DL registration readback required")
    result = {"outcome": "CURRENT_DL_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_DL_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
