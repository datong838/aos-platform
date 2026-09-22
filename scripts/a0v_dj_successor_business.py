#!/usr/bin/env python3
"""Register DJ directly from the exact detached DI authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_dj_replacement_recovery as dj_replacement


successor.STATE = dj_replacement.replacement.STATE / "registration-dj"
successor.AV_ID = "aca93a08-341f-4bd6-9e94-ed7fde3aed66"
successor.AV_GENERATION = "6ce73106-f945-4d34-a818-552303fec308"
successor.LOCK = "sha256:1010c16bb85c06d0dd36e9d33d7de2922b1ab0413e155b4feadf18744c356f89"
successor.CONFIG = {"configurationId": "00eb75bf-6e26-4a02-90dd-e7852cd473ed", "revision": 1,
                    "hash": "sha256:4dcc93851a428721d3a0661389aa72b13253037e842f29ac1e9e1e8411ab4d68"}
successor.AU_ID = "c8298a5d-9d94-4c37-81c9-508e2f0faf60"
successor.AU_GENERATION = "56950fc1-4007-497a-8a09-df133a1950c1"
successor.DETACH = "6ac1c229-2368-4201-a208-4aa96a846e06"
successor.DETACH_HASH = "sha256:e31dc9ae7b95b12cbbc5ad6294030598d8459cc55835c13652928d85c2e3511d"
successor.KEY = "a0v-qyh-clean-generation-dj-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 308
successor.PREDECESSOR_GROUP_REVISION = 335
successor.replacement_module = lambda: dj_replacement.replacement

DJ_ID = successor.AV_ID
DJ_GENERATION = successor.AV_GENERATION
AV_ID = DJ_ID
AV_GENERATION = DJ_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = dj_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = dj_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = dj_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_dj():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                dj_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_dj
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
            scope=scope, installation_id=DJ_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact DJ registration readback required")
    result = {"outcome": "CURRENT_DJ_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_DJ_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
