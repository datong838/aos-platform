#!/usr/bin/env python3
"""Cancel AY's exact stale enable, settle disable, then retire it unactivated."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ay/retire-ay"
INSTALLATION = "81df994f-23ce-4448-ac46-366aaee63924"
GENERATION = "a1069f60-46f5-41a8-bd18-61ed677eb3bd"
LOCK = "sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5"
CONFIGURATION = "ce24590a-479e-4a5e-94ab-01d138e0675c"
CONFIG_HASH = "sha256:579a652e471f626f08e25f80f19b4e9f77b91531a456dac87ef2f2220e1cff89"
STALE_ENABLE = "24a85b28-f00d-43cf-ba5d-28f064c74f6a"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
DEFINITION = "cb0dba8c-803f-5caf-8011-b763d349f2ba"
SNAPSHOT_GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
LINK_KEY = ("snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
            "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b")
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
PREFIX = "a0v-qyh-ay-stale-enable-retirement-20260919-v1"
ACTIONS = ("preflight", "request-disable", "process-disable", "retire", "audit")


def freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable AY retirement intent differs")
        return
    freeze(path, value)


def load(name: str) -> dict[str, Any]:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
    return value


def connect():
    from a0v_formal_text_model_renewal import database_connect
    return database_connect("aos_meta_head")


def installation_connect():
    identity_path = ROOT.parent / ".aos-recovery-20260912/state/installation-control-identity.json"
    if not identity_path.is_file() or identity_path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("private installation identity required")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("role") != "aos_a0v_installation_20260912" or not identity.get("password"):
        raise ValueError("exact installation identity required")
    with connect()() as authority:
        parameters = authority.info.get_parameters()
    parameters.update(user=identity["role"], password=identity["password"], dbname="aos_meta_head")

    @contextmanager
    def app_connect():
        import psycopg
        from psycopg.rows import dict_row
        with psycopg.connect(**parameters, row_factory=dict_row) as connection:
            if connection.info.dbname != "aos_meta_head":
                raise ValueError("isolated database required")
            connection.execute("SET ROLE aos_app")
            connection.commit()
            yield connection
    return app_connect


def snapshot(phase: str, operation_id: str | None = None) -> dict[str, Any]:
    if phase not in {"stale", "fencing", "settled", "retired"}:
        raise ValueError("fixed AY retirement phase required")
    with connect()() as conn:
        head = conn.execute("""SELECT i.installation_id::text,i.etag_version,i.current_revision,
          r.state,r.lock_hash,r.overlay_revision FROM bundle_installation i
          JOIN bundle_installation_revision r ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
          (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
          (INSTALLATION,)).fetchone()
        binding = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
          desired_state,observed_state,config_ref FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s""",
          (INSTALLATION, GENERATION)).fetchone()
        operations = [dict(row) for row in conn.execute("""SELECT operation_id::text,kind,status,phase,revision,
          failure_code,deadline<clock_timestamp() deadline_expired FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s ORDER BY created_at""",
          (INSTALLATION,)).fetchall()]
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
          AND operation_id IN (SELECT operation_id FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s)""",
          (INSTALLATION,)).fetchone())
        routes = [dict(row) for row in conn.execute("""SELECT handler_kind,installation_id,generation,
          execution_epoch,operation_fence,revision,cutover_group_revision
          FROM extension_operation_dispatch_binding WHERE org_id='org-org' AND project_id='dev-project'
          AND cutover_group_id=%s ORDER BY operation_id""", (GROUP,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r ON
          (r.org_id,r.project_id,r.definition_id,r.revision)=(h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (DEFINITION,)).fetchone()
        boundary = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s AND generation=%s) attempts,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s
            AND r.status='running' AND r.executor_stopped IS FALSE AND r.finished_at IS NULL) saved_runs,
          (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s) dataset_receipts,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org' AND workspace_id='dev-project'
            AND idempotency_key=%s) store_receipts,
          (SELECT count(*) FROM ecom_link WHERE org_id='org-org' AND workspace_id='dev-project') store_links,
          (SELECT count(*) FROM projection_outbox WHERE org_id='org-org' AND workspace_id='dev-project'
            AND projected IS FALSE) projection_pending,
          (SELECT count(*) FROM bundle_installation WHERE org_id='dev-org' AND project_id='dev-project') canary""",
          (INSTALLATION, GENERATION, SNAPSHOT_GROUP, SNAPSHOT_GROUP, LINK_KEY)).fetchone())
        cutovers = conn.execute("""SELECT count(*) n FROM extension_dispatch_cutover_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND target_installation_id=%s""",
          (INSTALLATION,)).fetchone()["n"]
        dispatch = conn.execute("""SELECT count(*) n FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""",
          (INSTALLATION,)).fetchone()["n"]
        retirement = []
        if phase == "retired":
            retirement = [dict(row) for row in conn.execute("""SELECT receipt_id::text,retirement_kind,
              authority_data,content_hash FROM extension_runtime_uninstall_receipt
              WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s""",
              (INSTALLATION,)).fetchall()]
        lifecycle = {"operations": 0, "receipts": 0}
        if operation_id:
            lifecycle = dict(conn.execute("""SELECT
              (SELECT count(*) FROM extension_dispatch_lifecycle_operation WHERE org_id='org-org'
                AND project_id='dev-project' AND runtime_operation_id=%s) operations,
              (SELECT count(*) FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org'
                AND project_id='dev-project' AND runtime_operation_id=%s) receipts""",
              (operation_id, operation_id)).fetchone())
    expected_head = {"installation_id": INSTALLATION,
        "etag_version": 6 if phase == "retired" else 5,
        "current_revision": 6 if phase == "retired" else 5,
        "state": "uninstalled" if phase == "retired" else "active",
        "lock_hash": LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"}
    expected_binding = {
        "stale": (3, 2, False, True, "disabled", "unknown"),
        "fencing": (4, 3, False, True, "disabled", "draining"),
        "settled": (5, 3, False, True, "disabled", "unknown"),
        "retired": (6, 3, False, True, "uninstalled", "stopped"),
    }[phase]
    binding_values = None if binding is None else (binding["revision"], binding["execution_epoch"],
        binding["enabled"], binding["operation_fence"], binding["desired_state"], binding["observed_state"])
    if (head is None or dict(head) != expected_head or binding is None or binding_values != expected_binding
            or binding["config_ref"] != {"configurationId": CONFIGURATION, "revision": 1, "hash": CONFIG_HASH}
            or resources != {"total": 3, "released": 3} or len(routes) != 9
            or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
                   or row["generation"] is not None or row["execution_epoch"] is not None
                   or row["operation_fence"] is not True or row["revision"] != 125
                   or row["cutover_group_revision"] != 152 for row in routes)
            or definition is None or dict(definition) != {"revision": 79, "state": "disabled"}
            or boundary != {"attempts": 0, "saved_runs": 12, "dataset_receipts": 12,
                            "store_receipts": 0, "store_links": 0, "projection_pending": 0, "canary": 0}
            or cutovers != 0 or dispatch != 0 or lifecycle != {"operations": 0, "receipts": 0}):
        raise ValueError("exact AY stale-enable retirement authority differs")
    if phase == "retired":
        authority = retirement[0]["authority_data"] if len(retirement) == 1 else None
        if (authority is None or retirement[0]["retirement_kind"] != "configured_unactivated"
                or authority.get("installationId") != INSTALLATION
                or authority.get("generation") != GENERATION
                or authority.get("bindingRevision") != 6
                or authority.get("disableOperationId") != operation_id
                or authority.get("releasedResourceCount") != 3
                or authority.get("successfulEnableCount") != 0
                or authority.get("dispatchCount") != 0
                or authority.get("businessExecutionCount") != 0):
            raise ValueError("exact AY configured-unactivated receipt required")
    stale = [item for item in operations if item["operation_id"] == STALE_ENABLE]
    pending = [item for item in operations if item["status"] not in {"succeeded", "failed", "cancelled"}]
    if phase == "stale":
        if (len(stale) != 1 or stale[0]["kind"] != "enable" or stale[0]["status"] != "accepted"
                or stale[0]["phase"] != "accepted" or stale[0]["deadline_expired"] is not True
                or pending != stale):
            raise ValueError("exact expired AY enable required")
    else:
        if len(stale) != 1 or stale[0]["status"] != "cancelled" or stale[0]["phase"] != "accepted":
            raise ValueError("exact AY enable cancellation required")
        disable = [item for item in operations if item["operation_id"] == operation_id and item["kind"] == "disable"]
        expected = ("running", "fencing") if phase == "fencing" else ("succeeded", "succeeded")
        if len(disable) != 1 or (disable[0]["status"], disable[0]["phase"]) != expected:
            raise ValueError("exact AY disable settlement required")
    return {"phase": phase, "head": dict(head), "binding": dict(binding), "operations": operations,
            "resources": resources, "routeCount": 9, "definition": dict(definition),
            "boundary": boundary, "cutovers": cutovers, "dispatchBindings": dispatch,
            "lifecycle": lifecycle, "retirement": retirement}


def preflight() -> dict[str, Any]:
    return {"outcome": "AY_STALE_ENABLE_RETIREMENT_PREFLIGHT_GREEN",
            "state": snapshot("stale"), "externalEffects": 0}


def request_disable() -> dict[str, Any]:
    load("preflight")
    current = profile()
    command = current.require_stale_enable_cancel(
        current.observe_installation(INSTALLATION), expected_operation_id=STALE_ENABLE)
    intent = {"installationId": INSTALLATION, **command,
              "idempotencyKey": PREFIX + "-disable"}
    freeze_or_match(STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    receipt = service.request(**SCOPE, installation_id=INSTALLATION, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"], if_match='"5"',
        target={"generation": GENERATION, "bindingRevision": 3})
    operation_id = receipt.response_json["operationId"]
    return {"outcome": "AY_STALE_ENABLE_CANCELLED_DISABLE_FENCED",
            "operationId": operation_id, "receipt": receipt.response_json,
            "replayed": receipt.replayed, "state": snapshot("fencing", operation_id)}


def process_disable() -> dict[str, Any]:
    operation_id = load("request-disable")["operationId"]
    try:
        completed = snapshot("settled", operation_id)
    except ValueError:
        completed = None
    if completed is not None:
        freeze_or_match(STATE / "process-disable-intent.json",
                        {"operationId": operation_id, "resendDisable": False})
        return {"outcome": "AY_DISABLE_SETTLED", "operationId": operation_id,
                "replayedReadback": True, "state": completed}
    snapshot("fencing", operation_id)
    current = profile()
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
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(conn, **SCOPE, operation_kind="disable", installation_id=INSTALLATION)
    if lease is None or str(lease.operation_id) != operation_id:
        raise ValueError("exact AY disable delivery required")
    freeze_or_match(STATE / "process-disable-intent.json",
                    {"operationId": operation_id, "eventId": str(lease.event_id), "resendDisable": False})
    delivery = consumer.finish_claimed(ClaimedDisableDelivery(scope, lease, UUID(INSTALLATION)))
    if delivery.operation_status != "succeeded" or delivery.delivery_status != "acknowledged":
        raise ValueError("AY disable delivery did not settle")
    return {"outcome": "AY_DISABLE_SETTLED", "operationId": operation_id,
            "deliveryStatus": delivery.delivery_status, "state": snapshot("settled", operation_id)}


def retire() -> dict[str, Any]:
    operation_id = load("process-disable")["operationId"]
    intent = {"installationId": INSTALLATION, "ifMatch": '"5"',
              "idempotencyKey": PREFIX + "-uninstall",
              "reason": "Retire exact configured but unactivated AY after stale enable cancellation"}
    freeze_or_match(STATE / "retire-intent.json", intent)
    try:
        completed = snapshot("retired", operation_id)
    except ValueError:
        completed = None
    if completed is not None:
        with connect()() as conn:
            row = conn.execute("""SELECT response_json FROM bundle_installation_command
              WHERE org_id='org-org' AND project_id='dev-project'
              AND operation='bundle_installations.uninstall' AND idempotency_key=%s""",
              (intent["idempotencyKey"],)).fetchone()
        if row is None:
            raise ValueError("AY uninstall command Receipt required")
        return {"outcome": "AY_CONFIGURED_UNACTIVATED_RETIRED", "operationId": operation_id,
                "receipt": row["response_json"], "reconciledWithoutResend": True, "state": completed}
    snapshot("settled", operation_id)
    current = profile()
    from a0v_ecommerce_invalid_baseline_uninstall import _build
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest
    store, service = _build(installation_connect(), current.TRUST_STATE / "signing/trust-roots.json")
    command = dict(installation_id=INSTALLATION,
        request=UninstallInstallationRequest(reason=intent["reason"]), **SCOPE,
        actor="a0v-ecommerce-growth-1.4-runtime-owner", roles=frozenset({"admin"}),
        markings=frozenset(), idempotency_key=intent["idempotencyKey"], if_match=intent["ifMatch"])
    first = service.uninstall(**command)
    replay = service.uninstall(**command)
    return {"outcome": "AY_CONFIGURED_UNACTIVATED_RETIRED", "operationId": operation_id,
            "receipt": first.response_json, "firstReplayed": first.replayed,
            "secondReplayed": replay.replayed, "state": snapshot("retired", operation_id)}


def audit() -> dict[str, Any]:
    operation_id = load("retire")["operationId"]
    return {"outcome": "AY_STALE_ENABLE_RETIREMENT_GREEN",
            "state": snapshot("retired", operation_id), "externalEffects": 0}


def run(action: str) -> dict[str, Any]:
    result = globals()[action.replace("-", "_")]()
    output = STATE / f"{action}-result.json"
    if not output.exists():
        freeze(output, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))
