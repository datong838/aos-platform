#!/usr/bin/env python3
"""W4 AU retirement: harvest the dead-letter enable op and fence AU.

The 2026-09-22 17:09 enable (operation 7679fe93) targeted binding rev11 but its
preparation leases were released by the 08:42 disable; commit_enabled can never
pass _deadline_valid. RuntimeDisableService.request cancels accepted
configure/enable operations whose target matches the disable target, fences the
binding, and detaches dispatch routes - one atomic transaction.

Phases (idempotent by frozen state files):
  preflight - read-only: AU binding/dead-letter facts
  disable   - cancel dead-letter enable + fence AU (nine-route hook no-ops: AU has no routes)
  process   - claim + finish the disable delivery (drain + observed=unknown)
  audit     - read-only: no unresolved ops, binding drained
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-au-retirement"
AU_ID = "d2d3c478-f9d9-4489-92b7-1de57f546452"
AU_GENERATION = "b15f1733-89dd-4684-9475-9fba095a1d74"
DEAD_LETTER_ENABLE = "7679fe93-5914-4a73-9f2b-9ceea6cbed02"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
KEY = "a0v-w4-au-retirement-20260923"
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"


def _configure():
    os.environ.update({
        "AOS_DOTENV_DISABLED": "1",
        "AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE": str(BASE / "bm-runtime-credentials/runtime-host-identities.json"),
        "AOS_EXTENSION_RUNTIME_HOST_ENABLED": "0",
        "AOS_EXTENSION_OCI_CONTEXT": "colima-aos-extension",
        "AOS_BUNDLE_ROOT": str(BASE / "bn-canonical-alias-registry/signed-bundles"),
        "AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE": str(BASE / "bn-registration-credentials/registration-main-identity.json"),
    })
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    sys.path.insert(0, str(ROOT / "scripts"))


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / f"{name}.json"
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _load(name):
    path = STATE / f"{name}.json"
    if not path.is_file():
        raise RuntimeError(f"frozen {name} required (run earlier phases first)")
    return json.loads(path.read_text(encoding="utf-8"))


def _observe():
    import a0v_dq_replacement_recovery as dq_replacement
    profile = dq_replacement.replacement.load_profile()
    return profile.observe_installation(AU_ID)


def _plane():
    import a0v_dq_replacement_recovery as dq_replacement
    profile = dq_replacement.replacement.load_profile()
    return profile._setup_runtime_plane()


def preflight():
    _configure()
    observed = _observe()
    head, bindings = observed["head"], observed["bindings"]
    if (str(head["installation_id"]) != AU_ID or head["state"] != "active" or len(bindings) != 1):
        raise RuntimeError(f"active AU required: {dict(head) if head else None}")
    binding = bindings[0]
    pending = [item for item in observed["operations"]
               if item["status"] not in {"succeeded", "failed", "cancelled"}]
    if (str(binding["generation"]) != AU_GENERATION
            or binding["desired_state"] != "disabled"
            or binding["observed_state"] != "unknown"
            or binding["operation_fence"] is not True):
        raise RuntimeError(f"fenced AU binding required: {dict(binding)}")
    if (len(pending) != 1 or str(pending[0]["operation_id"]) != DEAD_LETTER_ENABLE
            or pending[0]["kind"] != "enable" or pending[0]["phase"] != "accepted"):
        raise RuntimeError(f"one exact dead-letter enable required: {[dict(p) for p in pending]}")
    if not observed["resources"] or any(
            item["cleanup_state"] != "released" or item["observed_release"] is not True
            for item in observed["resources"]):
        raise RuntimeError("released AU resources required")
    frozen = {
        "etag": head["etag_version"],
        "bindingRevision": binding["revision"],
        "generation": AU_GENERATION,
        "deadLetterEnable": DEAD_LETTER_ENABLE,
        "deadLetterExpired": pending[0]["deadline_expired"],
    }
    _write("preflight", frozen)
    return {"outcome": "W4_AU_PREFLIGHT_GREEN", **frozen}


def disable():
    _configure()
    frozen = _load("preflight")
    activation, _store, _lifecycle, service, _dependent = _plane()
    receipt = service.request(**SCOPE, installation_id=AU_ID, actor=ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=KEY + "-disable-v1",
        if_match=f'"{frozen["etag"]}"',
        target={"generation": AU_GENERATION, "bindingRevision": frozen["bindingRevision"]})
    operation_id = receipt.response_json["operationId"]
    _write("disable", {"operationId": operation_id, "receipt": receipt.response_json,
                       "replayed": receipt.replayed})
    return {"outcome": "W4_AU_DISABLE_ACCEPTED", "operationId": operation_id,
            "replayed": receipt.replayed, "phase": receipt.response_json.get("phase")}


def process():
    _configure()
    operation_id = _load("disable")["operationId"]
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    _activation, store, _lifecycle, _service, _dependent = _plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=AU_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise RuntimeError("exact AU disable delivery required")
    _write("process-intent", {"operationId": operation_id, "eventId": str(lease.event_id)})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(AU_ID)))
    if (str(delivery.operation_id) != operation_id or delivery.operation_status != "succeeded"
            or delivery.delivery_status != "acknowledged"):
        raise RuntimeError(f"AU disable delivery did not settle: {delivery.delivery_status}")
    _write("process", {"operationId": operation_id, "deliveryStatus": delivery.delivery_status})
    return {"outcome": "W4_AU_DISABLE_SETTLED", "operationId": operation_id,
            "deliveryStatus": delivery.delivery_status}


def audit():
    _configure()
    observed = _observe()
    binding = observed["bindings"][0]
    pending = [item for item in observed["operations"]
               if item["status"] not in {"succeeded", "failed", "cancelled"}]
    dead_letter = [item for item in observed["operations"]
                   if str(item["operation_id"]) == DEAD_LETTER_ENABLE]
    result = {
        "outcome": "W4_AU_AUDIT",
        "pending": len(pending),
        "deadLetterStatus": dead_letter[0]["status"] if dead_letter else "missing",
        "binding": {"desired": binding["desired_state"], "observed": binding["observed_state"],
                    "fenced": binding["operation_fence"], "epoch": binding["execution_epoch"]},
    }
    if (len(pending) != 0 or not dead_letter or dead_letter[0]["status"] != "cancelled"
            or binding["desired_state"] != "disabled" or binding["observed_state"] != "unknown"):
        raise RuntimeError(f"AU retirement incomplete: {result}")
    _write("audit", result)
    return result


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "disable", "process", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
