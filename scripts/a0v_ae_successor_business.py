"""Register AE from AD's exact detach Receipt after replacement enable."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-ae/registration-ae"
AE_ID = "d02f90f2-eb0e-4859-ad58-35b17ddbcd6a"
AE_GENERATION = "36a57887-4f28-45e7-8515-2d94a343b5ed"
LOCK = "sha256:13bdff6abe0893fd76adb0735dac7c005d989de6367c8322727e67142e1c0b9a"
CONFIG = {"configurationId": "ccfbc451-e594-42a9-958d-f7bae72c1a86", "revision": 1,
          "hash": "sha256:13b477bc045568b9dd8e5ce7b2c74de0ecbdaee3bc357ecf45e06ab8ba13d53a"}
AD_ID = "42d9f8bd-11b0-4f8d-8c4d-75458ab23c94"
AD_GENERATION = "7a2f5483-8ff6-4672-b174-f273885e99d0"
DETACH = "9723047a-7922-4f3a-af11-384aec92752e"
DETACH_HASH = "sha256:54b36baba57f7d0e5f91b3629577c8757eae7c887d435d0ef44d76f05ba204c9"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
KEY = "a0v-qyh-clean-generation-ae-successor-v1"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"


def setup():
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    sys.path.insert(0, str(ROOT / "scripts"))
    import a0v_aa_successor_business as prior
    return prior.setup()


def request_from(w, v, parent, routes):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    from aos_api.ecommerce_growth_host_composition import ECOMMERCE_GROWTH_OPERATIONS
    from aos_api.ecommerce_growth_successor_registration import SuccessorDispatchRegistrationRequest
    head, bindings = w["head"], w["bindings"]
    if (str(head["installation_id"]) != AE_ID or head["etag_version"] != 5 or head["state"] != "active"
            or head["lock_hash"] != LOCK or len(bindings) != 1 or w["canaryInstallations"] != 0
            or len(w["resources"]) != 3
            or any(row["cleanup_state"] != "pending" or row["observed_release"] is not False for row in w["resources"])
            or len(w["operations"]) != 4 or any(row["status"] != "succeeded" for row in w["operations"])):
        raise ValueError("exact live AE installation required")
    binding = bindings[0]
    if (str(binding["generation"]) != AE_GENERATION or binding["revision"] != 4
            or binding["execution_epoch"] != 3 or binding["enabled"] is not True
            or binding["operation_fence"] is not False or binding["desired_state"] != "enabled"
            or binding["observed_state"] != "ready" or binding["config_ref"] != CONFIG):
        raise ValueError("exact ready AE binding required")
    old = v["bindings"]
    if (str(v["head"]["installation_id"]) != AD_ID or v["head"]["state"] != "active"
            or len(old) != 1 or str(old[0]["generation"]) != AD_GENERATION
            or (old[0]["revision"], old[0]["execution_epoch"]) != (9, 5)
            or old[0]["enabled"] is not False or old[0]["operation_fence"] is not True
            or old[0]["desired_state"] != "disabled" or old[0]["observed_state"] != "unknown"):
        raise ValueError("exact drained AD predecessor required")
    if (str(parent["receipt_id"]) != DETACH or parent["phase"] != "detach"
            or parent["content_hash"] != DETACH_HASH
            or canonical_sha256(parent["authority_data"]) != DETACH_HASH):
        raise ValueError("exact AD detach Receipt required")
    if (len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
            or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True or row["revision"] != 65
                   or row["cutover_group_revision"] != 92 for row in routes)):
        raise ValueError("exact detached AD route group required")
    return SuccessorDispatchRegistrationRequest.model_validate({
        "schemaVersion": "aos.ecommerce.successor-dispatch-registration/v1",
        "expectedGroupRevision": 92,
        "predecessorDetachReceiptRef": {"resourceType": "DispatchDisableDetachReceipt",
            "resourceId": DETACH, "revision": 1, "contentHash": DETACH_HASH},
        "registration": {"schemaVersion": "aos.ecommerce.first-dispatch-registration/v1",
            "installationRef": {"installationId": AE_ID, "revision": 5, "lockHash": LOCK,
                                "overlayRevision": head["overlay_revision"]},
            "generation": AE_GENERATION, "bindingRevision": 4, "executionEpoch": 3,
            "configRef": CONFIG, "groupId": GROUP, "idempotencyKey": KEY}})


def current_request():
    import a0v_ae_replacement_recovery as replacement
    from a0v_formal_text_model_renewal import database_connect
    profile = replacement.load_profile()
    w, v = profile.observe_installation(AE_ID), profile.observe_installation(AD_ID)
    with database_connect("aos_meta_head")() as conn:
        parent = conn.execute("""SELECT receipt_id,phase,authority_data,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND receipt_id=%s""", (DETACH,)).fetchone()
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
        raise ValueError("AD detach and drained tenant required")
    return request_from(w, v, dict(parent), routes)


def register(plane, request):
    from aos_api.tenant_scope import TenantScope
    from a0v_qyh_current_product_event_first_chain import freeze, freeze_or_match
    scope = TenantScope("org-org", "dev-project")
    material = request.model_dump(mode="json", by_alias=True)
    intent = STATE / "register-intent.json"
    existed = intent.exists()
    freeze_or_match(intent, material)
    service = plane.first_dispatch_registration_service
    receipt = (service.read_successor_receipt(scope=scope, installation_id=AE_ID,
        idempotency_key=KEY, actor=ACTOR) if existed else
        service.register_successor(scope=scope, request=request, actor=ACTOR))
    replayed = True if existed else receipt["replayed"]
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact AE registration readback required")
    result = {"outcome": "CURRENT_AE_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": replayed}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup()
    request = current_request()
    result = ({"outcome": "CURRENT_AE_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
