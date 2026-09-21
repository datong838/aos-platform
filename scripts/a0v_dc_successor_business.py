#!/usr/bin/env python3
"""Register DC directly from the exact detached DB authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dc_replacement_recovery as dc_replacement

successor.STATE = dc_replacement.replacement.STATE / "registration-dc"
successor.AV_ID = "02d39eb8-174e-432f-9776-57de7c4436c8"
successor.AV_GENERATION = "bd59503f-eb9e-4fe6-a09d-a92a3b924682"
successor.LOCK = "sha256:4c19a327b9536269eb3582b82814f3342237d8c95bb5c65c29e402d55f86aa4b"
successor.CONFIG = {"configurationId": "6c04d5a7-5f0c-42b1-84ad-527cd8798cb2", "revision": 1,
                    "hash": "sha256:5a2c9823aeb2af8e8c57209022649ed035f2035526ac9a5e8b6375f3847b387e"}
successor.AU_ID = "aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8"
successor.AU_GENERATION = "c1ae6205-0743-483c-82e3-1d1c95b1ab31"
successor.DETACH = "eceafbf4-d492-43d5-b036-d49e054de133"
successor.DETACH_HASH = "sha256:4a74a25a361e745a41bddde502105c030399a716d2f5f6f9ed5f01fa36c4aa54"
successor.KEY = "a0v-qyh-clean-generation-dc-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 287
successor.PREDECESSOR_GROUP_REVISION = 314
successor.replacement_module = lambda: dc_replacement.replacement

DC_ID = successor.AV_ID
DC_GENERATION = successor.AV_GENERATION
AV_ID = DC_ID
AV_GENERATION = DC_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dc_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dc_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dc_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dc():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dc_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dc
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
            scope=scope, installation_id=DC_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DC registration readback required")
    result = {"outcome": "CURRENT_DC_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DC_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
