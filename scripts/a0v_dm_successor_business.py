#!/usr/bin/env python3
"""Register DM directly from the exact detached DL authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dm_replacement_recovery as dm_replacement


successor.STATE = dm_replacement.replacement.STATE / "registration-dm"
successor.AV_ID = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
successor.AV_GENERATION = "4da719c7-1144-4867-bbdc-8a70362ba5f0"
successor.LOCK = "sha256:169e90f7a54fc17af057799741e199c424e8cdf9d790157cc7645a9c7001c16a"
successor.CONFIG = {"configurationId": "3ca3f8ce-c5a0-4c45-a9fa-0df0fdbc6b38", "revision": 1,
                    "hash": "sha256:6668b26d7f9016740b97e5891cb3c97b2bc8a8c0a8edc3bd2201ff7af8e4d4ef"}
successor.AU_ID = "83453fb3-8c39-422c-845b-e152551e0a30"
successor.AU_GENERATION = "f3a1f381-5aeb-4494-a155-164e0ef9e0f5"
successor.DETACH = "dac9f81b-dca8-4d1b-b82c-1d561d9dafb8"
successor.DETACH_HASH = "sha256:75fb102aba48b8f999b8b8b241f49dfd6b0b8544f05b1cfeecc0d177e5ba6b19"
successor.KEY = "a0v-qyh-clean-generation-dm-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 317
successor.PREDECESSOR_GROUP_REVISION = 344
successor.replacement_module = lambda: dm_replacement.replacement

DM_ID = successor.AV_ID
DM_GENERATION = successor.AV_GENERATION
AV_ID = DM_ID
AV_GENERATION = DM_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dm_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dm_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dm_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dm():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dm_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dm
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def current_request():
    """DM after Host-loss reset: etag7, seven ops (failed prepare + OWNER_LOST verify + live)."""
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
            or len(w["operations"]) != 7
            or sum(1 for row in w["operations"] if row["status"] == "succeeded") != 5
            or sum(1 for row in w["operations"]
                   if row["kind"] == "runtime-verify" and row.get("failure_code") == "PREPARATION_OWNER_LOST") != 1
            or sum(1 for row in w["operations"]
                   if row["kind"] == "runtime-apply" and row.get("failure_code") == "RESOURCE_CLEANUP_UNCERTAIN") != 1):
        raise ValueError("exact live DM installation after preparation-reset required")
    binding = bindings[0]
    if (str(binding["generation"]) != AV_GENERATION or binding["revision"] != 4
            or binding["execution_epoch"] != 3 or binding["enabled"] is not True
            or binding["operation_fence"] is not False or binding["desired_state"] != "enabled"
            or binding["observed_state"] != "ready" or binding["config_ref"] != CONFIG):
        raise ValueError("exact ready DM binding required")
    old = v["bindings"]
    if (str(v["head"]["installation_id"]) != successor.AU_ID or v["head"]["state"] != "active"
            or len(old) != 1 or str(old[0]["generation"]) != successor.AU_GENERATION
            or (old[0]["revision"], old[0]["execution_epoch"]) != (
                successor.PREDECESSOR_BINDING_REVISION, successor.PREDECESSOR_EXECUTION_EPOCH)
            or old[0]["enabled"] is not False or old[0]["operation_fence"] is not True
            or old[0]["desired_state"] != "disabled" or old[0]["observed_state"] != "unknown"):
        raise ValueError("exact detached DL predecessor required")
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
        raise ValueError("DL detach and drained tenant required")
    parent = dict(parent)
    if (str(parent["receipt_id"]) != successor.DETACH or parent["phase"] != "detach"
            or parent["content_hash"] != successor.DETACH_HASH
            or canonical_sha256(parent["authority_data"]) != successor.DETACH_HASH):
        raise ValueError("exact DL detach Receipt required")
    if (len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
            or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True
                   or row["revision"] != successor.PREDECESSOR_ROUTE_REVISION
                   or row["cutover_group_revision"] != successor.PREDECESSOR_GROUP_REVISION
                   for row in routes)):
        raise ValueError("exact detached DL route group required")
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
            scope=scope, installation_id=DM_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DM registration readback required")
    result = {"outcome": "CURRENT_DM_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DM_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
