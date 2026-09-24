#!/usr/bin/env python3
"""One-shot original-Owner settlement for the released DS runtime binding."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
STATE = (ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline/"
         "20260924-w5b0-ds-settlement")
DS_ID = "c6812824-a0c3-4adc-9ebc-d56178ae135c"
GENERATION = "b59582cc-2abf-472d-8f59-bfc8be1138c8"
LOCK = "sha256:1b8468b86496b277a0ecd3a802379b3640e5ed1ec76e9ec420b9d15089013938"
KEY = "a0v-w5b0-ds-settle-released-20260924-v1"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}


def _write(name, value):
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE, 0o700)
    path = STATE / (name + ".json")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(value, output, ensure_ascii=False, default=str, indent=2)
        output.write("\n")
        output.flush()
        os.fsync(output.fileno())


def _load(name):
    path = STATE / (name + ".json")
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("W5B0_PRIVATE_RESULT_REQUIRED")
    return json.loads(path.read_text())


def _current():
    import a0v_ecommerce_current_reinstall as current
    from a0v_w5_definition_rebuild import _configure, BASE
    _configure()
    current.BUNDLE_ROOT = BASE / "bn-canonical-alias-registry/signed-bundles"
    current.TRUST_STATE = BASE / "bm-trust-root-rotation"
    original = current._load
    def load(name):
        module = original(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = BASE / "bm-runtime-credentials/runtime-host-identities.json"
        return module
    current._load = load
    return current


def snapshot():
    from a0v_formal_text_model_renewal import database_connect
    from a0v_w5_definition_rebuild import _head_ref, OLD_DEFINITION, DEFINITION
    current = _current()
    observed = current.observe_installation(DS_ID)
    with database_connect("aos_meta_head")() as conn:
        schedule = conn.execute("""SELECT count(*) AS total,count(*) FILTER (WHERE s.enabled) AS enabled
          FROM meta_schedule s WHERE s.org_id=%s AND s.project_id=%s
          AND s.pipeline_id IN (SELECT DISTINCT pipeline_id FROM pipeline_source_selection_revision
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s)""",
            (*SCOPE.values(), *SCOPE.values(), DS_ID, GENERATION)).fetchone()
        attempts = conn.execute("""SELECT count(*) AS n FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND installation_id=%s
          AND state IN ('running','claimed','unknown')""", (*SCOPE.values(), DS_ID)).fetchone()["n"]
        canary = conn.execute("""SELECT count(*) AS n FROM extension_runtime_binding
          WHERE org_id='dev-org' AND project_id='dev-project'""").fetchone()["n"]
    return {"installation": observed, "schedules": dict(schedule), "activeAttempts": attempts,
            "canaryBindings": canary, "oldDefinition": _head_ref(OLD_DEFINITION),
            "newDefinition": _head_ref(DEFINITION)}


def require_released(value):
    from a0v_ecommerce_current_reinstall import require_released_owner_settlement
    installation = value["installation"]
    command = require_released_owner_settlement(installation)
    binding = installation["bindings"][0]
    if (installation["head"]["lock_hash"] != LOCK
            or command != {"etag": 5, "generation": GENERATION, "bindingRevision": 7}
            or binding["execution_epoch"] != 4
            or value["schedules"] != {"total": 12, "enabled": 0}
            or value["activeAttempts"] != 0 or value["canaryBindings"] != 0
            or value["oldDefinition"] is None
            or value["oldDefinition"]["state"] != "disabled"
            or value["newDefinition"] is not None):
        raise ValueError("W5B0_RELEASED_PRECONDITION_DRIFT")
    return command


def preflight():
    value = snapshot()
    command = require_released(value)
    return {"outcome": "W5B0_RELEASED_PREFLIGHT_GREEN", "command": command,
            "resources": len(value["installation"]["resources"]),
            "terminalOperations": len(value["installation"]["operations"]),
            "schedules": value["schedules"], "activeAttempts": 0}


def request_disable():
    if STATE.exists():
        raise ValueError("W5B0_EXISTING_STATE_RECONCILE_FIRST")
    value = snapshot()
    command = require_released(value)
    intent = {"installationId": DS_ID, "generation": GENERATION,
              "bindingRevision": command["bindingRevision"], "etag": command["etag"],
              "idempotencyKey": KEY, "before": value}
    _write("intent", intent)
    current = _current()
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    receipt = service.request(**SCOPE, installation_id=DS_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS, idempotency_key=KEY,
        if_match='"5"', target={"generation": GENERATION, "bindingRevision": 7})
    result = {"outcome": "W5B0_DISABLE_ACCEPTED", "receipt": receipt.response_json,
              "replayed": receipt.replayed}
    _write("request-result", result)
    return result


def process_disable():
    request = _load("request-result")
    if (STATE / "process-intent.json").exists() or (STATE / "process-result.json").exists():
        raise ValueError("W5B0_PROCESS_BOUNDARY_UNKNOWN_RECONCILE_FIRST")
    operation_id = UUID(request["receipt"]["operationId"])
    current = _current()
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
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=DS_ID)
    if lease is None or lease.operation_id != operation_id:
        raise ValueError("W5B0_EXACT_DISABLE_LEASE_REQUIRED_RECONCILE_FIRST")
    _write("process-intent", {"operationId": str(operation_id), "eventId": str(lease.event_id),
                              "attempt": lease.attempt, "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(
        TenantScope(**SCOPE), lease, UUID(DS_ID)))
    result = {"outcome": "W5B0_DISABLE_SETTLED", "operationId": str(delivery.operation_id),
              "operationStatus": delivery.operation_status,
              "deliveryStatus": delivery.delivery_status}
    _write("process-result", result)
    return result


def audit():
    request = _load("request-result")
    operation_id = request["receipt"]["operationId"]
    from a0v_formal_text_model_renewal import database_connect
    value = snapshot()
    binding = value["installation"]["bindings"][0]
    with database_connect("aos_meta_head")() as conn:
        operation = conn.execute("""SELECT kind,status,phase FROM extension_runtime_operation
          WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
          (*SCOPE.values(), operation_id)).fetchone()
        outbox = conn.execute("""SELECT count(*) AS total,count(*) FILTER (WHERE b.delivered_at IS NOT NULL) AS delivered
          FROM extension_runtime_outbox b JOIN extension_runtime_event e
          ON (e.org_id,e.project_id,e.event_id)=(b.org_id,b.project_id,b.event_id)
          WHERE e.org_id=%s AND e.project_id=%s AND e.operation_id=%s
            AND b.consumer_id='runtime-reconciler'""",
          (*SCOPE.values(), operation_id)).fetchone()
    if (operation is None or operation["kind"] != "disable"
            or operation["status"] != "succeeded"
            or binding["desired_state"] != "disabled"
            or binding["enabled"] is not False or binding["operation_fence"] is not True
            or value["schedules"] != {"total": 12, "enabled": 0}
            or value["activeAttempts"] != 0 or value["canaryBindings"] != 0
            or outbox["total"] < 1 or outbox["total"] != outbox["delivered"]
            or any(r["cleanup_state"] != "released" or r["observed_release"] is not True
                   for r in value["installation"]["resources"])):
        raise ValueError("W5B0_SETTLEMENT_AUDIT_NOT_GREEN")
    return {"outcome": "W5B0_DS_SETTLEMENT_GREEN", "operationId": operation_id,
            "bindingRevision": binding["revision"], "executionEpoch": binding["execution_epoch"],
            "operationStatus": operation["status"], "deliveredEvents": outbox["delivered"],
            "schedules": value["schedules"], "activeAttempts": 0, "canaryBindings": 0}


def reconcile():
    """Record a concurrent formal consumer's completed delivery without claiming again."""
    if (STATE / "process-intent.json").exists() or (STATE / "process-result.json").exists():
        raise ValueError("W5B0_PROCESS_BOUNDARY_UNKNOWN_RECONCILE_FIRST")
    observed = audit()
    result = {"outcome": "W5B0_DISABLE_ALREADY_SETTLED", "operationId": observed["operationId"],
              "processedByThisExecutor": False, "resendDisable": False,
              "operationStatus": observed["operationStatus"],
              "deliveredEvents": observed["deliveredEvents"]}
    _write("process-result", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("preflight", "request_disable", "process_disable", "reconcile", "audit"))
    phase = parser.parse_args().phase
    print(json.dumps(globals()[phase](), ensure_ascii=False, default=str))
