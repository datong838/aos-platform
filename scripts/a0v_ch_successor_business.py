#!/usr/bin/env python3
"""Register CH directly from the exact detached CG authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_ch_replacement_recovery as ch_replacement

successor.STATE = ch_replacement.replacement.STATE / "registration-ch"
successor.AV_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"
successor.AV_GENERATION = "0521ccf8-304a-45b3-b820-dc6ebd64b51b"
successor.LOCK = "sha256:0a550a6efdbd48ea06b35f7559d83b6840dfaae117b6bfd6fa9dbf46733c9ea6"
successor.CONFIG = {"configurationId": "e37e8c76-c50e-467a-8c69-4679b11fdeb7", "revision": 1,
                    "hash": "sha256:ad7a86bb06752105da203133049e3cf0ab9a059f5a569684562aca0d6b96ca35"}
successor.AU_ID = "8f42819c-0fc7-48cf-a5c4-9ba96894a6f5"
successor.AU_GENERATION = "3ed300fa-5fff-4949-9fb0-1926412e51ae"
successor.DETACH = "3d65b065-8ad4-4a97-983f-f14ca0ada8cb"
successor.DETACH_HASH = "sha256:bbf8fb158183e1821129384611658468d0a6d28838068c6ad45960b2b36dc025"
successor.KEY = "a0v-qyh-clean-generation-ch-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 224
successor.PREDECESSOR_GROUP_REVISION = 251
successor.replacement_module = lambda: ch_replacement.replacement

CH_ID = successor.AV_ID
CH_GENERATION = successor.AV_GENERATION
AV_ID = CH_ID
AV_GENERATION = CH_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = ch_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = ch_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = ch_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_ch():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                ch_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_ch
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
            scope=scope, installation_id=CH_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CH registration readback required")
    result = {"outcome": "CURRENT_CH_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CH_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
