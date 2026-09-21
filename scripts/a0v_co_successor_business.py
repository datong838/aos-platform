#!/usr/bin/env python3
"""Register CO directly from the exact detached CN authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_co_replacement_recovery as co_replacement

successor.STATE = co_replacement.replacement.STATE / "registration-co"
successor.AV_ID = "648b267b-bb8f-4582-ab29-288279f534c7"
successor.AV_GENERATION = "db428c1b-2fe4-4869-8a69-ddffaa909ba7"
successor.LOCK = "sha256:c0181c85dff7f0989c5f64652814065b6f273b2f31e349044dc125bd7bc486e9"
successor.CONFIG = {"configurationId": "a757203c-099d-4e83-afcd-fe3f12503956", "revision": 1,
                    "hash": "sha256:e9b939576d05c2140d8e5aec574a8d21d052841251838d664e3c18b849d9e1dd"}
successor.AU_ID = "1366f4dd-47d9-42c1-b26a-759c7bd556da"
successor.AU_GENERATION = "cd0601e0-2668-496d-9f93-561d2e69a170"
successor.DETACH = "5f72b40e-543f-49e6-947c-a636a41cee99"
successor.DETACH_HASH = "sha256:46f951422c2f99c4cc63103b202ae83c8b04bff574282204f5f89f90d3fff09c"
successor.KEY = "a0v-qyh-clean-generation-co-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 245
successor.PREDECESSOR_GROUP_REVISION = 272
successor.replacement_module = lambda: co_replacement.replacement

CO_ID = successor.AV_ID
CO_GENERATION = successor.AV_GENERATION
AV_ID = CO_ID
AV_GENERATION = CO_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = co_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = co_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = co_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_co():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                co_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_co
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
            scope=scope, installation_id=CO_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CO registration readback required")
    result = {"outcome": "CURRENT_CO_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CO_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
