#!/usr/bin/env python3
"""Register DA directly from the exact detached CZ authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_da_replacement_recovery as da_replacement

successor.STATE = da_replacement.replacement.STATE / "registration-da"
successor.AV_ID = "f4fcdf0b-a37b-419c-9de0-14b08cd7320d"
successor.AV_GENERATION = "dbcdd8cb-c6f4-47cc-91f9-1662f54044c0"
successor.LOCK = "sha256:47e3295d76f176a553f224b23e550b403be071c96b078d0c0410cd2117b3b38e"
successor.CONFIG = {"configurationId": "2e78ce65-72a2-4815-a81c-01e2977f3cae", "revision": 1,
                    "hash": "sha256:75bae53fe4f7f21f8d416007cc5c21987b14a6e9b2977730a830afe4d95d6977"}
successor.AU_ID = "162e4c29-a24e-4c6b-8da7-9582d090d708"
successor.AU_GENERATION = "d1b0f7eb-9677-4d52-a656-a4ae28942976"
successor.DETACH = "211b6762-550a-475f-aab6-9f6086786787"
successor.DETACH_HASH = "sha256:de79f4af293f2a159d0ac76ef47392761946cf2fb6d7203b8e89143e2b4b65b7"
successor.KEY = "a0v-qyh-clean-generation-da-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 281
successor.PREDECESSOR_GROUP_REVISION = 308
successor.replacement_module = lambda: da_replacement.replacement

DA_ID = successor.AV_ID
DA_GENERATION = successor.AV_GENERATION
AV_ID = DA_ID
AV_GENERATION = DA_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = da_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = da_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = da_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_da():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                da_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_da
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
            scope=scope, installation_id=DA_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DA registration readback required")
    result = {"outcome": "CURRENT_DA_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DA_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
