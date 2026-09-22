#!/usr/bin/env python3
"""Register DE directly from the exact detached DD authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_de_replacement_recovery as de_replacement


successor.STATE = de_replacement.replacement.STATE / "registration-de"
successor.AV_ID = "5d993078-18ec-4302-9286-7081a1463cc0"
successor.AV_GENERATION = "f5181ad4-e304-4533-aa4a-0f30b3c6dac3"
successor.LOCK = "sha256:46f9998335c83c6e82131e6c767925fe3a8bbb48c06035a30f6ac19ba54b9b15"
successor.CONFIG = {"configurationId": "f1e64ecc-0cde-40a4-8da4-fba1a50a24ea", "revision": 1,
                    "hash": "sha256:7618a9dda5a4c5cc7f85a1b72fb9b0ad22087ce23f127267e1686a3b18c63c8b"}
successor.AU_ID = "6e05658b-5d0a-40ae-ab8e-81fcca5269db"
successor.AU_GENERATION = "422d2d5b-752a-4182-b1e8-831a8f63c2a1"
successor.DETACH = "5211f8d4-e02a-4d06-b806-c1c5144505e8"
successor.DETACH_HASH = "sha256:ca77ede8b7156b5dc8a3c0de3598c0807a4cfb06719c94039c444a526eb58f16"
successor.KEY = "a0v-qyh-clean-generation-de-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 293
successor.PREDECESSOR_GROUP_REVISION = 320
successor.replacement_module = lambda: de_replacement.replacement

DE_ID = successor.AV_ID
DE_GENERATION = successor.AV_GENERATION
AV_ID = DE_ID
AV_GENERATION = DE_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = de_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = de_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = de_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_de():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                de_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_de
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
            scope=scope, installation_id=DE_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DE registration readback required")
    result = {"outcome": "CURRENT_DE_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DE_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
