#!/usr/bin/env python3
"""Register DF directly from the exact detached DE authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_df_replacement_recovery as df_replacement


successor.STATE = df_replacement.replacement.STATE / "registration-df"
successor.AV_ID = "a0639f78-af04-4249-97f6-d8507de45f44"
successor.AV_GENERATION = "ec18c8c6-2694-44c1-a9c9-ea79ea606e45"
successor.LOCK = "sha256:42e81bdde355a2e2578ed4aebfb0302ad47584c614bc6f8a1e92495a8be61988"
successor.CONFIG = {"configurationId": "d57519f4-1f05-4432-a6ee-ffc134086b8f", "revision": 1,
                    "hash": "sha256:fe11784e566bbd846065a7b6d8da48715ab87de90370dce279fb24200a2d5ffe"}
successor.AU_ID = "5d993078-18ec-4302-9286-7081a1463cc0"
successor.AU_GENERATION = "f5181ad4-e304-4533-aa4a-0f30b3c6dac3"
successor.DETACH = "3cda5059-7651-42ec-8c2a-bf60e3e1dbc1"
successor.DETACH_HASH = "sha256:51d2e740fe62d7e614d73c1c3786b91d2f030d37882a7127f1db14070c884208"
successor.KEY = "a0v-qyh-clean-generation-df-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 296
successor.PREDECESSOR_GROUP_REVISION = 323
successor.replacement_module = lambda: df_replacement.replacement

DF_ID = successor.AV_ID
DF_GENERATION = successor.AV_GENERATION
AV_ID = DF_ID
AV_GENERATION = DF_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = df_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = df_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = df_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_df():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                df_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_df
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
            scope=scope, installation_id=DF_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DF registration readback required")
    result = {"outcome": "CURRENT_DF_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DF_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
