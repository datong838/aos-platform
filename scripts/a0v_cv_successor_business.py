#!/usr/bin/env python3
"""Register CV directly from the exact detached CU authority."""
from __future__ import annotations
import argparse
import json
import os
import a0v_av_successor_business as successor
import a0v_cv_replacement_recovery as cv_replacement

successor.STATE = cv_replacement.replacement.STATE / "registration-cv"
successor.AV_ID = "f94149ca-a01e-4a20-836f-3f5132e0dbb7"
successor.AV_GENERATION = "82aec2b8-072d-4f2e-9624-f9539c8890a6"
successor.LOCK = "sha256:9d8d72cdaad153c6e085ead8a3c28c4507fc226b421e0d60be8a100ac38318df"
successor.CONFIG = {"configurationId": "0646dad4-cdf5-4217-a6f2-a566ff2791fe", "revision": 1,
                    "hash": "sha256:eada1c5456c0708ff05f7d81b1056d0d00da7441147b1f2bc58bf9d2004a20a4"}
successor.AU_ID = "2c2d5506-1f80-4557-bf4b-00ead0258002"
successor.AU_GENERATION = "bcaa7ea0-62b1-4238-8615-28db45e3014e"
successor.DETACH = "ee918fb3-05db-4ed0-a678-0554225bb427"
successor.DETACH_HASH = "sha256:bdb72a10abfd3412182543a079b8c4bc813d0c7641186f6558aaa66560eff36e"
successor.KEY = "a0v-qyh-clean-generation-cv-successor-v1"
successor.PREDECESSOR_BINDING_REVISION = 9
successor.PREDECESSOR_EXECUTION_EPOCH = 5
successor.PREDECESSOR_ROUTE_REVISION = 266
successor.PREDECESSOR_GROUP_REVISION = 293
successor.replacement_module = lambda: cv_replacement.replacement

CV_ID = successor.AV_ID
CV_GENERATION = successor.AV_GENERATION
AV_ID = CV_ID
AV_GENERATION = CV_GENERATION
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
        launcher.DEFAULT_CREDENTIALS = cv_replacement.canonical.CREDENTIALS
        launcher.BUNDLE_ROOT = cv_replacement.replacement.BUNDLE_ROOT
        launcher.TRUST_ROOTS = cv_replacement.canonical.TRUST_STATE / "signing/trust-roots.json"
        configure = launcher.configure_environment

        def configure_cv():
            configure()
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(
                cv_replacement.canonical.BASE / "bn-registration-credentials/registration-main-identity.json")

        launcher.configure_environment = configure_cv
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
            scope=scope, installation_id=CV_ID, idempotency_key=KEY, actor=ACTOR)
    except LookupError:
        receipt = None
    reconciled_absent = receipt is None
    if reconciled_absent:
        receipt = service.register_successor(scope=scope, request=request, actor=ACTOR)
    if not receipt or receipt["requestHash"] != request.request_hash():
        raise ValueError("exact CV registration readback required")
    result = {"outcome": "CURRENT_CV_SUCCESSOR_REGISTERED", "request": material,
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
    result = ({"outcome": "CURRENT_CV_SUCCESSOR_REQUEST_PREVIEW",
               "request": request.model_dump(mode="json", by_alias=True),
               "requestHash": request.request_hash()}
              if args.mode == "preview" else register(plane, request))
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
