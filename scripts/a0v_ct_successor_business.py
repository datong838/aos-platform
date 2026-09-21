#!/usr/bin/env python3
"""Register CT directly from the exact detached CS authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_ct_replacement_recovery as ct_replacement

successor.STATE = ct_replacement.replacement.STATE / "registration-ct"
successor.AV_ID = "b4847c85-b452-4c87-bf56-8a57bc9f8d25"
successor.AV_GENERATION = "0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6"
successor.LOCK = "sha256:c450112c2c3d926d714dee8764c1c28b0f6940fca70555f0733902ad69e53988"
successor.CONFIG = {"configurationId": "666a0e20-fc0e-4321-aa52-66946ca223bd", "revision": 1,
                    "hash": "sha256:9cba3d0f2c1b60bb438edffd320e064517bc17dea551dc642d98cc3b95920e24"}
successor.AU_ID = "ff72acba-1e59-4da3-b92a-18737e18e9d2"
successor.AU_GENERATION = "01a1719d-1109-440f-a233-1c5a6adb0d81"
successor.DETACH = "13c4d61c-ea9b-4f13-94d7-12e21e8a09a4"
successor.DETACH_HASH = "sha256:f745d09717dbf72734a3792e67b2f9b88c692f23fe7c03fd903291bccfcb99a6"
successor.KEY = "a0v-qyh-clean-generation-ct-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 260
successor.PREDECESSOR_GROUP_REVISION = 287
successor.replacement_module = lambda: ct_replacement.replacement

CT_ID = successor.AV_ID
CT_GENERATION = successor.AV_GENERATION
AV_ID = CT_ID
AV_GENERATION = CT_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = ct_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = ct_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = ct_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_ct():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                ct_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_ct
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
            scope=scope, installation_id=CT_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CT registration readback required")
    result = {"outcome": "CURRENT_CT_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CT_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
