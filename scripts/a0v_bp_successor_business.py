#!/usr/bin/env python3
"""Register BP directly from the exact detached BO authority."""
from __future__ import annotations

import argparse
import json
import os

import a0v_av_successor_business as successor
import a0v_bp_replacement_recovery as bp_replacement


successor.STATE = bp_replacement.replacement.STATE / "registration-bp"
successor.AV_ID = "17ba9792-9f24-42e4-9557-4d84547c7d97"
successor.AV_GENERATION = "4f1bddfa-74a0-4fcb-b25e-f363139eed83"
successor.LOCK = "sha256:d77d4dd49d57e0106483b4f4f90e7101dcc1ac70d1b6843ead31a4174ee74a2c"
successor.CONFIG = {"configurationId": "23ae2a57-4164-4315-8898-95620f417628", "revision": 1,
                    "hash": "sha256:231f211055ade42ffc6ca11488caa5ae79cd4bc0960f2bc21f7830c8bf20ca16"}
successor.AU_ID = "307399a0-21bb-4d55-95b2-8b0fee238913"
successor.AU_GENERATION = "030bf59c-c998-4ee6-aedb-11d8d7d5831a"
successor.DETACH = "01853eba-d3d7-4e2a-a5c5-a6c346e1679c"
successor.DETACH_HASH = "sha256:dfc96a07480ea85f910260822b97536a6569154966dfc2e2db855f7860ac48d1"
successor.KEY = "a0v-qyh-clean-generation-bp-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 170
successor.PREDECESSOR_GROUP_REVISION = 197
successor.replacement_module = lambda: bp_replacement.replacement

BP_ID = successor.AV_ID
BP_GENERATION = successor.AV_GENERATION
AV_ID = BP_ID
AV_GENERATION = BP_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = bp_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = bp_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = bp_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_bp():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                bp_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")
        launcher.configure_environment = configure_bp
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
            scope=scope, installation_id=BP_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact BP registration readback required")
    result = {"outcome": "CURRENT_BP_SUCCESSOR_REGISTERED", "request": material,
              "receipt": receipt, "replayed": not reconciled_absent}
    if not (STATE / "register-result.json").exists():
        freeze(STATE / "register-result.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preview", "register"])
    args = parser.parse_args()
    plane = setup(); request = current_request()
    result = ({"outcome": "CURRENT_BP_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()} if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
