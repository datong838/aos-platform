#!/usr/bin/env python3
"""Register CI directly from the exact detached CH authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_ci_replacement_recovery as ci_replacement

successor.STATE = ci_replacement.replacement.STATE / "registration-ci"
successor.AV_ID = "1b9f500d-48a0-4f2c-8284-3db26e5cd4e7"
successor.AV_GENERATION = "8de8994b-ad87-4039-a851-d944153bca08"
successor.LOCK = "sha256:06757616841bff14cebd4175476baa08d8ebd1fd81a5ce06cd1b2abb968af759"
successor.CONFIG = {"configurationId": "d89f31f4-e9ee-4026-bb0a-b3d9e14e17f0", "revision": 1,
                    "hash": "sha256:2aaf0762c81e038b67bc2a10b0b30b5acb28a731c1324063577a4a94c28b468e"}
successor.AU_ID = "990f96f7-764e-4002-b691-fc5eb8d4335c"
successor.AU_GENERATION = "0521ccf8-304a-45b3-b820-dc6ebd64b51b"
successor.DETACH = "bef972d2-2c5f-4cd3-9448-b7e94ff7594d"
successor.DETACH_HASH = "sha256:c1537c4af534489422e2fbe819d7ed079db9c25c9d1702d214c77097af8ffdac"
successor.KEY = "a0v-qyh-clean-generation-ci-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 227
successor.PREDECESSOR_GROUP_REVISION = 254
successor.replacement_module = lambda: ci_replacement.replacement

CI_ID = successor.AV_ID
CI_GENERATION = successor.AV_GENERATION
AV_ID = CI_ID
AV_GENERATION = CI_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = ci_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = ci_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = ci_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_ci():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                ci_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_ci
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
            scope=scope, installation_id=CI_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CI registration readback required")
    result = {"outcome": "CURRENT_CI_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CI_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
