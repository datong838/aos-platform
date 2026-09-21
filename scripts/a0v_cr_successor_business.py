#!/usr/bin/env python3
"""Register CR directly from the exact detached CQ authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cr_replacement_recovery as cr_replacement

successor.STATE = cr_replacement.replacement.STATE / "registration-cr"
successor.AV_ID = "913cb7a1-4912-471a-abbf-452e3ce999a9"
successor.AV_GENERATION = "a4a16448-5581-4948-b962-777ff601e855"
successor.LOCK = "sha256:c3513e45b002c90a810034eab554ed58c6aba4123be24349bbba0f7d24777334"
successor.CONFIG = {"configurationId": "6b8252ba-99c7-46bb-9618-69f107834707", "revision": 1,
                    "hash": "sha256:81dfc50ef7a2885770c70adc46669e84af6a0d9a645b2e816ef61c2418f5a3cb"}
successor.AU_ID = "fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80"
successor.AU_GENERATION = "ae8a1005-99fb-48c5-9dfe-8f76590bc0c8"
successor.DETACH = "2d8a382b-90f1-46c3-9100-c2310a949914"
successor.DETACH_HASH = "sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432"
successor.KEY = "a0v-qyh-clean-generation-cr-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 11
successor.PREDECESSOR_EXECUTION_EPOCH = 6
successor.PREDECESSOR_ROUTE_REVISION = 254
successor.PREDECESSOR_GROUP_REVISION = 281
successor.replacement_module = lambda: cr_replacement.replacement

CR_ID = successor.AV_ID
CR_GENERATION = successor.AV_GENERATION
AV_ID = CR_ID
AV_GENERATION = CR_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cr_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cr_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cr_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cr():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cr_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cr
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
            scope=scope, installation_id=CR_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CR registration readback required")
    result = {"outcome": "CURRENT_CR_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CR_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
