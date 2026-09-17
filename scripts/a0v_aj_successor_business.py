"""Register AJ from AI's exact detach Receipt after replacement enable."""

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260918/state/q-advisor-baseline/replacement-aj/registration-aj"
AJ_ID = "cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
AJ_GENERATION = "6dc4f34a-5cc6-4b20-bfb8-8a002a7dcd76"
LOCK = "sha256:20bd5896e1144a63a98fb96a684122b70331441c6e6966267d73af9aa18da49b"
CONFIG = {"configurationId": "307f81a0-f4dc-47d6-aa2e-5fa0f641318c", "revision": 1,
          "hash": "sha256:05f9c2f79f4f70e156df384d7531e9669106ce4cee3e125e999e157fe6f1f8cf"}
AI_ID = "59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
AI_GENERATION = "3512c4da-841c-4bd6-a711-343c163b0632"
DETACH = "5256f0d1-292c-4890-b127-3c17086c59e4"
DETACH_HASH = "sha256:0f72fb6a530585bbdd4ac2896aa37fb04acbee6976a5463648c4d2a1bf49ab83"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
KEY = "a0v-qyh-clean-generation-aj-successor-v1"
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
    if (str(head["installation_id"]) != AJ_ID or head["etag_version"] != 5 or head["state"] != "active"
            or head["lock_hash"] != LOCK or len(bindings) != 1 or w["canaryInstallations"] != 0
            or len(w["resources"]) != 3
            or any(row["cleanup_state"] != "pending" or row["observed_release"] is not False for row in w["resources"])
            or len(w["operations"]) != 4 or any(row["status"] != "succeeded" for row in w["operations"])):
        raise ValueError("exact live AJ installation required")
    binding = bindings[0]
    if (str(binding["generation"]) != AJ_GENERATION or binding["revision"] != 4
            or binding["execution_epoch"] != 3 or binding["enabled"] is not True
            or binding["operation_fence"] is not False or binding["desired_state"] != "enabled"
            or binding["observed_state"] != "ready" or binding["config_ref"] != CONFIG):
        raise ValueError("exact ready AJ binding required")
    old = v["bindings"]
    if (str(v["head"]["installation_id"]) != AI_ID or v["head"]["state"] != "active"
            or len(old) != 1 or str(old[0]["generation"]) != AI_GENERATION
            or (old[0]["revision"], old[0]["execution_epoch"]) != (9, 5)
            or old[0]["enabled"] is not False or old[0]["operation_fence"] is not True
            or old[0]["desired_state"] != "disabled" or old[0]["observed_state"] != "unknown"):
        raise ValueError("exact detached AI predecessor required")
    if (str(parent["receipt_id"]) != DETACH or parent["phase"] != "detach"
            or parent["content_hash"] != DETACH_HASH
            or canonical_sha256(parent["authority_data"]) != DETACH_HASH):
        raise ValueError("exact AI detach Receipt required")
    if (len(routes) != len(ECOMMERCE_GROWTH_OPERATIONS)
            or [row["operation_id"] for row in routes] != sorted(ECOMMERCE_GROWTH_OPERATIONS)
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True or row["revision"] != 80
                   or row["cutover_group_revision"] != 107 for row in routes)):
        raise ValueError("exact detached AI route group required")
    return SuccessorDispatchRegistrationRequest.model_validate({
        "schemaVersion": "aos.ecommerce.successor-dispatch-registration/v1",
        "expectedGroupRevision": 107,
        "predecessorDetachReceiptRef": {"resourceType": "DispatchDisableDetachReceipt",
            "resourceId": DETACH, "revision": 1, "contentHash": DETACH_HASH},
        "registration": {"schemaVersion": "aos.ecommerce.first-dispatch-registration/v1",
            "installationRef": {"installationId": AJ_ID, "revision": 5, "lockHash": LOCK,
                                "overlayRevision": head["overlay_revision"]},
            "generation": AJ_GENERATION, "bindingRevision": 4, "executionEpoch": 3,
            "configRef": CONFIG, "groupId": GROUP, "idempotencyKey": KEY}})


def current_request():
    import a0v_aj_replacement_recovery as replacement
    from a0v_formal_text_model_renewal import database_connect
    profile = replacement.load_profile()
    w, v = profile.observe_installation(AJ_ID), profile.observe_installation(AI_ID)
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
        raise ValueError("AI detach and drained tenant required")
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
    receipt = (service.read_successor_receipt(scope=scope, installation_id=AJ_ID,
        idempotency_key=KEY, actor=ACTOR) if existed else
        service.register_successor(scope=scope, request=request, actor=ACTOR))
    replayed = True if existed else receipt["replayed"]
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact AJ registration readback required")
    result = {"outcome": "CURRENT_AJ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_AJ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
