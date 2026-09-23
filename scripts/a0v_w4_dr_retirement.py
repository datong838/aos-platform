#!/usr/bin/env python3
"""W4 DR retirement: retire the fenced DQ installation through the governed
runtime disable + nine-route detach (EcommerceGrowthDisableDependent).

Phases (idempotent by frozen state files):
  preflight  - read-only: DQ binding/resources/ops facts
  disable    - runtime disable request (tenant + nine-route detach)
  process    - claim + finish the disable delivery (routes detached)
  audit      - read-only: routes legacy/fenced + detach receipt present
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/replacement-dq/w4-dr-retirement"
DQ_ID = "29e553b2-3afc-4b15-b860-f79104f3491a"
DQ_GENERATION = "b8d6900d-b4a3-43d8-8891-a4b1d02abd3c"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
ACTOR = "a0v-ecommerce-growth-1.4-runtime-owner"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
KEY = "a0v-w4-dr-retirement-20260923"
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
EXPECTED_INSTALLATION_ETAG = 5


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


def _profile():
    import a0v_ecommerce_current_reinstall as profile
    return profile


def _observe():
    profile = _profile()
    return profile.observe_installation(DQ_ID)


def _snapshot(label: str):
    observed = _observe()
    return {"label": label, "at": _now(), "observed": observed}


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def preflight():
    _configure()
    observed = _observe()
    head, bindings = observed["head"], observed["bindings"]
    if (observed["canaryInstallations"] != 0 or str(head["installation_id"]) != DQ_ID
            or head["state"] != "active" or head["etag_version"] != EXPECTED_INSTALLATION_ETAG
            or len(bindings) != 1):
        raise RuntimeError(f"DQ head facts differ: etag={head.get('etag_version')} state={head.get('state')}")
    binding = bindings[0]
    frozen = {
        "head": {"etag": head["etag_version"], "state": head["state"], "lockHash": head["lock_hash"]},
        "binding": {k: str(v) for k, v in binding.items() if k in
                    ("generation", "revision", "execution_epoch", "desired_state", "observed_state")},
        "fenced": bool(binding["operation_fence"]),
        "enabled": bool(binding["enabled"]),
    }
    if (str(binding["generation"]) != DQ_GENERATION
            or binding["desired_state"] != "enabled"
            or binding["observed_state"] != "unknown"
            or binding["operation_fence"] is not True
            or binding["enabled"] is not False):
        raise RuntimeError(f"exact fenced DQ binding required: {frozen['binding']}")
    if not observed["resources"] or any(
            item["cleanup_state"] != "released" or item["observed_release"] is not True
            for item in observed["resources"]):
        raise RuntimeError("released DQ resources required")
    if any(item["status"] not in {"succeeded", "failed", "cancelled"} for item in observed["operations"]):
        raise RuntimeError("DQ unresolved operation present")
    _write("preflight", frozen)
    return {"outcome": "W4_DR_PREFLIGHT_GREEN", **frozen}


def disable():
    _configure()
    preflighted = _load("preflight")
    observed = _observe()
    binding = observed["bindings"][0]
    if (observed["head"]["etag_version"] != preflighted["head"]["etag"]
            or binding["revision"] != int(preflighted["binding"]["revision"])):
        raise RuntimeError("DQ drifted since preflight")
    import a0v_dq_replacement_recovery as dq_replacement
    current = dq_replacement.replacement.load_profile()
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    intent = {"installationId": DQ_ID, "etag": preflighted["head"]["etag"],
              "generation": DQ_GENERATION, "bindingRevision": int(preflighted["binding"]["revision"]),
              "idempotencyKey": KEY + "-disable-v1"}
    receipt = service.request(**SCOPE, installation_id=DQ_ID, actor=ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"],
        if_match=f'"{preflighted["head"]["etag"]}"',
        target={"generation": DQ_GENERATION, "bindingRevision": int(preflighted["binding"]["revision"])})
    operation_id = receipt.response_json["operationId"]
    _write("disable", {"operationId": operation_id, "receipt": receipt.response_json,
                       "replayed": receipt.replayed, "intent": intent})
    return {"outcome": "W4_DR_DISABLE_ACCEPTED", "operationId": operation_id,
            "replayed": receipt.replayed, "state": _snapshot("accepted")}


def process():
    _configure()
    operation_id = _load("disable")["operationId"]
    import a0v_dq_replacement_recovery as dq_replacement
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    current = dq_replacement.replacement.load_profile()
    _activation, store, _lifecycle, _service, _dependent = current._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=DQ_ID)
    if lease is None or str(lease.operation_id) != operation_id:
        raise RuntimeError("exact DQ disable delivery required")
    _write("process-intent", {"operationId": operation_id, "eventId": str(lease.event_id)})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(DQ_ID)))
    if (str(delivery.operation_id) != operation_id or delivery.operation_status != "succeeded"
            or delivery.delivery_status != "acknowledged"):
        raise RuntimeError(f"DQ disable delivery did not settle: {delivery.delivery_status}")
    _write("process", {"operationId": operation_id, "deliveryStatus": delivery.delivery_status})
    return {"outcome": "W4_DR_ROUTES_DETACHED", "operationId": operation_id,
            "deliveryStatus": delivery.delivery_status, "state": _snapshot("detached")}


def audit():
    _configure()
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, SCOPE) as conn:
        routes = [dict(r) for r in conn.execute("""SELECT operation_id, handler_kind,
            installation_id::text AS inst, execution_epoch, operation_fence, revision, cutover_group_revision
            FROM extension_operation_dispatch_binding
            WHERE org_id=%s AND project_id=%s AND cutover_group_id=%s ORDER BY operation_id""",
            (*SCOPE.values(), GROUP)).fetchall()]
        receipts = [dict(r) for r in conn.execute("""SELECT receipt_id::text, phase, created_at::text
            FROM extension_dispatch_lifecycle_receipt
            WHERE org_id=%s AND project_id=%s ORDER BY created_at DESC LIMIT 2""",
            (*SCOPE.values(),)).fetchall()]
    legacy_fenced = [r for r in routes if r["handler_kind"] == "legacy" and r["operation_fence"] is True
                     and r["inst"] is None]
    detach_receipts = [r for r in receipts if r["phase"] == "detach"]
    result = {"outcome": "W4_DR_AUDIT", "routes": len(routes), "legacyFenced": len(legacy_fenced),
              "detachReceipts": len(detach_receipts), "recentReceipts": receipts}
    if len(routes) != 9 or len(legacy_fenced) != 9 or not detach_receipts:
        raise RuntimeError(f"nine legacy fenced routes + detach receipt required: {result}")
    _write("audit", result)
    return result


if __name__ == "__main__":
    _configure()
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "disable", "process", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, sort_keys=True, default=str))
