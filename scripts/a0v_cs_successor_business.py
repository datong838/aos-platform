#!/usr/bin/env python3
"""Register CS directly from the exact detached CR authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cs_replacement_recovery as cs_replacement

successor.STATE = cs_replacement.replacement.STATE / "registration-cs"
successor.AV_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"
successor.AV_GENERATION = "01a1719d-1109-440f-a233-1c5a6adb0d81"
successor.LOCK = "sha256:1b37fab980943517deeec01b88f1ebe119b6143fc7db13c42ca9e4756e3af65a"
successor.CONFIG = {"configurationId": "de040f32-54ee-4a51-82b0-09b0142c0f64", "revision": 1,
                    "hash": "sha256:78559f2d3230bc55f974141662631d2157c7ac9aabc34efb41f1c334f1d79238"}
successor.AU_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"
successor.AU_GENERATION = "a4a16448-5581-4948-b962-777ff601e855"
successor.DETACH = "14c1b753-d557-4441-bf7f-89ad5ab48be5"
successor.DETACH_HASH = "sha256:bd7ff2a43c944fe8aed88f89e9af82b511a36a8e029d86bb2428369ba3f9cc06"
successor.KEY = "a0v-qyh-clean-generation-cs-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 257
successor.PREDECESSOR_GROUP_REVISION = 284
successor.replacement_module = lambda: cs_replacement.replacement

CS_ID = successor.AV_ID
CS_GENERATION = successor.AV_GENERATION
AV_ID = CS_ID
AV_GENERATION = CS_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cs_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cs_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cs_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cs():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cs_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cs
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
            scope=scope, installation_id=CS_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CS registration readback required")
    result = {"outcome": "CURRENT_CS_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CS_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
