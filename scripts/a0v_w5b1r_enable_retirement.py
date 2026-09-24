#!/usr/bin/env python3
"""Formally cancel one unconsumed DS enable through the original disable Owner."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import a0v_w5b_ds_settlement as base
from a0v_formal_text_model_renewal import database_connect

STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5b1r-enable-retirement")
CONFIG_STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
                "20260924-w5b1-ds-config")
KEY = "a0v-w5b1r-retire-unconsumed-enable-20260924-v1"
ENABLE_OPERATION = "1d5b0071-3067-456f-8ab5-ee1f666abd83"
SCOPE = base.SCOPE


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    fd = os.open(STATE / (name + ".json"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5B1R_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def preflight():
    state = base.snapshot()
    installation = state["installation"]
    binding = installation["bindings"]
    staged = json.loads((CONFIG_STATE / "stage.json").read_text())["configRef"]
    with database_connect("aos_meta_head")() as conn:
        enable = conn.execute("""SELECT kind,status,phase,expected_binding_revision,
          deadline < clock_timestamp() AS expired FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
          (*SCOPE.values(), ENABLE_OPERATION)).fetchone()
        outbox = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER(WHERE b.delivered_at IS NOT NULL) AS delivered,
          coalesce(max(b.attempt),0) AS attempts,
          count(*) FILTER(WHERE b.claim_until IS NOT NULL) AS claimed
          FROM extension_runtime_outbox b JOIN extension_runtime_event e
          USING(org_id,project_id,event_id) WHERE e.org_id=%s AND e.project_id=%s
          AND e.operation_id=%s AND b.consumer_id='runtime-reconciler'""",
          (*SCOPE.values(), ENABLE_OPERATION)).fetchone()
        receipt = conn.execute("""SELECT count(*) AS n FROM bundle_installation_command
          WHERE org_id=%s AND project_id=%s AND idempotency_key=%s""",
          (*SCOPE.values(), KEY)).fetchone()["n"]
        pending = conn.execute("""SELECT count(*) AS n FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND installation_id=%s
          AND status NOT IN ('succeeded','failed','cancelled')""",
          (*SCOPE.values(), base.DS_ID)).fetchone()["n"]
    if (installation["head"]["state"] != "active"
            or installation["head"]["etag_version"] != 5
            or installation["head"]["lock_hash"] != base.LOCK
            or len(binding) != 1 or binding[0]["revision"] != 11
            or binding[0]["execution_epoch"] != 6
            or binding[0]["desired_state"] != "disabled"
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or binding[0]["config_ref"] != staged
            or enable is None or dict(enable) != {"kind": "enable", "status": "accepted",
                "phase": "accepted", "expected_binding_revision": 11, "expired": True}
            or dict(outbox) != {"total": 1, "delivered": 0, "attempts": 0, "claimed": 0}
            or pending != 1 or receipt != 0
            or state["schedules"] != {"total": 12, "enabled": 0}
            or state["activeAttempts"] != 0 or state["canaryBindings"] != 0
            or state["oldDefinition"] is None
            or state["oldDefinition"]["state"] != "disabled"
            or state["newDefinition"] is not None
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in installation["resources"])):
        raise ValueError("W5B1R_EFFECT_FREE_ENABLE_GATE_DRIFT")
    return {"outcome": "W5B1R_PREFLIGHT_GREEN", "oldEnableOperation": ENABLE_OPERATION,
            "bindingRevision": 11, "executionEpoch": 6, "outboxAttempt": 0,
            "activeAttempts": 0, "schedulesEnabled": 0}


def request_disable():
    if STATE.exists():
        raise ValueError("W5B1R_EXISTING_STATE_RECONCILE_FIRST")
    before = preflight()
    _write("intent", {"installationId": base.DS_ID, "generation": base.GENERATION,
                      "bindingRevision": 11, "etag": 5, "oldEnableOperation": ENABLE_OPERATION,
                      "idempotencyKey": KEY, "before": before})
    current = base._current()
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    receipt = service.request(**SCOPE, installation_id=base.DS_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS, idempotency_key=KEY,
        if_match='"5"', target={"generation": base.GENERATION, "bindingRevision": 11})
    result = {"outcome": "W5B1R_DISABLE_ACCEPTED", "receipt": receipt.response_json,
              "replayed": receipt.replayed}
    _write("request-result", result)
    return result


def process_disable():
    request = _load("request-result")
    if (STATE / "process-intent.json").exists() or (STATE / "process-result.json").exists():
        raise ValueError("W5B1R_PROCESS_BOUNDARY_UNKNOWN_RECONCILE_FIRST")
    operation_id = UUID(request["receipt"]["operationId"])
    current = base._current()
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope
    _activation, store, _lifecycle, _service, _dependent = current._setup_runtime_plane()
    consumer = RuntimeDisableConsumer(connect=runtime_worker_connection, installation_store=store,
        check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION),
        check_drained=GenerationDrainReader(), dependent=EcommerceGrowthDisableDependent())
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable",
                                       installation_id=base.DS_ID)
    if lease is None:
        result = audit()
        _write("process-result", {"outcome": "W5B1R_CONCURRENT_SETTLEMENT_RECONCILED",
                                  "operationId": result["disableOperation"],
                                  "processedByThisExecutor": False, "resendDisable": False})
        return result
    if lease.operation_id != operation_id:
        raise ValueError("W5B1R_EXACT_DISABLE_LEASE_REQUIRED_RECONCILE_FIRST")
    _write("process-intent", {"operationId": str(operation_id), "eventId": str(lease.event_id),
                              "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(
        TenantScope(**SCOPE), lease, UUID(base.DS_ID)))
    result = {"outcome": "W5B1R_DISABLE_SETTLED", "operationId": str(delivery.operation_id),
              "operationStatus": delivery.operation_status,
              "deliveryStatus": delivery.delivery_status}
    _write("process-result", result)
    return result


def audit():
    request = _load("request-result")
    disable_id = request["receipt"]["operationId"]
    state = base.snapshot()
    binding = state["installation"]["bindings"][0]
    with database_connect("aos_meta_head")() as conn:
        rows = conn.execute("""SELECT operation_id::text,kind,status FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id IN (%s,%s)""",
          (*SCOPE.values(), ENABLE_OPERATION, disable_id)).fetchall()
        outbox = conn.execute("""SELECT count(*) AS total,
          count(*) FILTER (WHERE b.delivered_at IS NOT NULL) AS delivered
          FROM extension_runtime_outbox b JOIN extension_runtime_event e
          USING(org_id,project_id,event_id) WHERE e.org_id=%s AND e.project_id=%s
          AND e.operation_id=%s AND b.consumer_id='runtime-reconciler'""",
          (*SCOPE.values(), disable_id)).fetchone()
    operations = {row["operation_id"]: (row["kind"], row["status"]) for row in rows}
    if (operations.get(ENABLE_OPERATION) != ("enable", "cancelled")
            or operations.get(disable_id) != ("disable", "succeeded")
            or outbox["total"] < 1 or outbox["total"] != outbox["delivered"]
            or binding["desired_state"] != "disabled"
            or binding["enabled"] is not False or binding["operation_fence"] is not True
            or binding["config_ref"]["revision"] != 2
            or state["schedules"] != {"total": 12, "enabled": 0}
            or state["activeAttempts"] != 0 or state["canaryBindings"] != 0
            or state["oldDefinition"] is None
            or state["oldDefinition"]["state"] != "disabled"):
        raise ValueError("W5B1R_RETIREMENT_AUDIT_NOT_GREEN")
    return {"outcome": "W5B1R_ENABLE_RETIRED_GREEN", "oldEnableOperation": ENABLE_OPERATION,
            "oldEnableStatus": "cancelled", "disableOperation": disable_id,
            "disableStatus": "succeeded", "bindingRevision": binding["revision"],
            "executionEpoch": binding["execution_epoch"], "configRevision": 2,
            "deliveredEvents": outbox["delivered"], "activeAttempts": 0,
            "schedulesEnabled": 0, "canaryBindings": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request_disable", "process_disable", "audit"))
    print(json.dumps(globals()[parser.parse_args().phase](), ensure_ascii=False, default=str))
