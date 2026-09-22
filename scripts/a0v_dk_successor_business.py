#!/usr/bin/env python3
"""Register DK directly from the exact detached DJ authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dk_replacement_recovery as dk_replacement


successor.STATE = dk_replacement.replacement.STATE / "registration-dk"
successor.AV_ID = "b651f4d7-b2a3-4032-a0d2-9b43743deb07"
successor.AV_GENERATION = "fb16d08b-8fcb-4eb0-8c13-7698d16b83b4"
successor.LOCK = "sha256:d696720fe77538523f00f0e3dd8685b38ecbed06f53c4a70e5c7a8c7b2f7eff2"
successor.CONFIG = {"configurationId": "7478e277-6f9d-4ccb-b258-49b33da8f29e", "revision": 1,
                    "hash": "sha256:e9da431335ba49fbbf7c93c3010a95381a72cdca297643415bca5585467de02a"}
successor.AU_ID = "aca93a08-341f-4bd6-9e94-ed7fde3aed66"
successor.AU_GENERATION = "6ce73106-f945-4d34-a818-552303fec308"
successor.DETACH = "5f4ea80e-31f3-4357-b80b-def70eb6cb03"
successor.DETACH_HASH = "sha256:865b94d856a1d753227f88cd90c285cf3a21d63ab07dc4a8707f0fd0bbce08da"
successor.KEY = "a0v-qyh-clean-generation-dk-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 311
successor.PREDECESSOR_GROUP_REVISION = 338
successor.replacement_module = lambda: dk_replacement.replacement

DK_ID = successor.AV_ID
DK_GENERATION = successor.AV_GENERATION
AV_ID = DK_ID
AV_GENERATION = DK_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dk_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dk_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dk_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dk():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dk_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dk
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
            scope=scope, installation_id=DK_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DK registration readback required")
    result = {"outcome": "CURRENT_DK_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DK_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
