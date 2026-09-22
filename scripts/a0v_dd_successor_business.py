#!/usr/bin/env python3
"""Register DD directly from the exact detached DC authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dd_replacement_recovery as dd_replacement

successor.STATE = dd_replacement.replacement.STATE / "registration-dd"
successor.AV_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"
successor.AV_GENERATION = "422d2d5b-752a-4182-b1e8-831a8f63c2a1"
successor.LOCK = "sha256:9d83e86209865176f599127f34a38887e21715ac6095a75e963515dca96c5ea4"
successor.CONFIG = {"configurationId": "2147976a-5704-4781-8953-deeb41b3879d", "revision": 1,
                    "hash": "sha256:949432f9b86ef1e5314ed165c3aaa9cd28e0de21de80b287e527580364cceba2"}
successor.AU_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"
successor.AU_GENERATION = "bd59503f-eb9e-4fe6-a09d-a92a3b924682"
successor.DETACH = "c1e5de00-55dc-4eb0-bb57-21524e784c53"
successor.DETACH_HASH = "sha256:35973282a15a5ee626e3ef2429b0a5935ec5ca37a0ec3e496bced3d6f91d4e4d"
successor.KEY = "a0v-qyh-clean-generation-dd-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 290
successor.PREDECESSOR_GROUP_REVISION = 317
successor.replacement_module = lambda: dd_replacement.replacement

DD_ID = successor.AV_ID
DD_GENERATION = successor.AV_GENERATION
AV_ID = DD_ID
AV_GENERATION = DD_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dd_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dd_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dd_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dd():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dd_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dd
        return launcher

    product_api.load_launcher = load_launcher
    return successor.setup()


def current_request():
    return successor.current_request()


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
            scope=scope, installation_id=DD_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DD registration readback required")
    result = {"outcome": "CURRENT_DD_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DD_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
