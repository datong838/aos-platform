"""Receipt-first control commands for the current ecommerce reinstall rehearsal."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import sys
from typing import Any


os.environ.setdefault("AOS_DOTENV_DISABLED", "1")


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260915/state/current-ecommerce-package/install"
BUNDLE_ROOT = (
    ROOT.parent
    / ".aos-recovery-20260915/state/current-ecommerce-package/registry/signed-bundles-current-ecommerce"
)
TRUST_STATE = ROOT.parent / ".aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install"
PREDECESSOR = {
    "installationId": "97aeb2e7-59ba-40f6-89a3-fb0293bc0497",
    "revision": 5,
    "lockHash": "sha256:a4441a4383783cb2a2f32171c52eb2718f526a5f56102dc5c0e12bf79299a42b",
    "overlayRevision": "a0v-canonical-ecommerce-v1",
}
PREDECESSOR_GENERATION = "3a445eee-aa28-4459-9e5a-f12a806a94b1"
SCOPE = {"org_id": "org-org", "project_id": "dev-project"}
VERSIONS = {
    "domain.ecommerce.core": "1.3.0",
    "platform.ecommerce.niushop": "1.22.0",
    "solution.ecommerce.growth": "1.8.0",
    "solution.ecommerce.operations-base": "1.2.0",
}


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"required control module unavailable: {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _freeze(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as handle:
        json.dump(value, handle, ensure_ascii=False, default=str, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _freeze_or_match(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError("immutable intent differs")
        return
    _freeze(path, value)


def _initial(label: str) -> dict[str, Any]:
    if label not in {"a", "b", "c", "d"}:
        raise ValueError("exact install label required")
    return json.loads((STATE / label / "create-result.json").read_text(encoding="utf-8"))


def _setup_runtime_plane():
    host = _load("a0v_ecommerce_runtime_host")
    host._configure_environment(
        host.DEFAULT_CREDENTIALS,
        bundle_root=BUNDLE_ROOT,
        trust_roots_file=TRUST_STATE / "signing/trust-roots.json",
    )
    os.environ["AOS_EXTENSION_RUNTIME_HOST_ENABLED"] = "0"
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    activation = _load("a0v_ecommerce_growth_1_4_activate")
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent

    store, lifecycle = activation._services(
        runtime_worker_connection, TRUST_STATE / "signing/trust-roots.json"
    )
    dependent = EcommerceGrowthDisableDependent()
    disable = RuntimeDisableService(
        installation_store=store,
        installation_reader=lifecycle._reader,
        check_current_permission=CurrentControlPermission(
            operation=DISABLE_RUNTIME_OPERATION
        ),
        dependent=dependent,
    )
    return activation, store, lifecycle, disable, dependent


def observe_installation(installation_id: str) -> dict[str, Any]:
    from a0v_formal_text_model_renewal import database_connect

    params = (*SCOPE.values(), installation_id)
    with database_connect("aos_meta_head")() as conn:
        head = conn.execute(
            """SELECT i.installation_id,i.etag_version,r.state,r.lock_hash,r.overlay_revision
               FROM bundle_installation i JOIN bundle_installation_revision r
               ON r.installation_pk=i.installation_pk AND r.org_id=i.org_id
               AND r.project_id=i.project_id AND r.revision=i.current_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s""",
            params,
        ).fetchone()
        if head is None:
            raise ValueError("known installation missing")
        bindings = conn.execute(
            """SELECT generation,revision,execution_epoch,enabled,operation_fence,
                      desired_state,observed_state,config_ref
               FROM extension_runtime_binding
               WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
            params,
        ).fetchall()
        operations = conn.execute(
            """SELECT operation_id,kind,status,phase,revision,failure_code,
                      deadline < clock_timestamp() AS deadline_expired
               FROM extension_runtime_operation
               WHERE org_id=%s AND project_id=%s AND installation_id=%s
               ORDER BY created_at""",
            params,
        ).fetchall()
        resources = conn.execute(
            """SELECT l.resource_id,l.cleanup_state,l.observed_release
               FROM extension_runtime_resource_lease l
               JOIN extension_runtime_operation o USING(org_id,project_id,operation_id)
               WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
               ORDER BY l.resource_id""",
            params,
        ).fetchall()
        canary = conn.execute(
            """SELECT count(*) AS n FROM bundle_installation
               WHERE org_id='dev-org' AND project_id='dev-project'"""
        ).fetchone()["n"]
    return {
        "head": dict(head),
        "bindings": [dict(item) for item in bindings],
        "operations": [dict(item) for item in operations],
        "resources": [dict(item) for item in resources],
        "canaryInstallations": canary,
    }


def observe() -> dict[str, Any]:
    result = {
        "outcome": "CURRENT_ECOMMERCE_INSTALLATIONS_OBSERVED",
        "at": datetime.now(timezone.utc).isoformat(),
        "predecessor": observe_installation(PREDECESSOR["installationId"]),
    }
    for label in ("a", "b", "c", "d"):
        path = STATE / label / "create-result.json"
        if path.exists():
            result[label] = observe_installation(json.loads(path.read_text())["installationId"])
    return result


def require_phase(action: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if action == "prepare":
        if (head["state"], head["etag_version"], bindings) != ("approved", 3, []):
            raise ValueError("approved install without binding required")
        return {"etag": 3, "kind": "runtime-apply"}
    if action == "verify":
        if (head["state"], head["etag_version"], bindings) != ("applied", 4, []):
            raise ValueError("applied install without committed binding required")
        return {"etag": 4, "kind": "runtime-verify"}
    if len(bindings) != 1 or head["state"] != "active" or head["etag_version"] != 5:
        raise ValueError("one active generation required")
    binding = bindings[0]
    if action == "disable":
        if binding["enabled"] is not True or binding["operation_fence"] is not False:
            raise ValueError("enabled unfenced generation required")
    elif action == "uninstall":
        if binding["enabled"] is not False or binding["operation_fence"] is not True:
            raise ValueError("disabled fenced generation required")
        if not snapshot["resources"] or any(
            item["cleanup_state"] != "released" or item["observed_release"] is not True
            for item in snapshot["resources"]
        ):
            raise ValueError("confirmed released resources required")
    else:
        raise ValueError("unsupported exact phase")
    return {
        "etag": 5,
        "generation": str(binding["generation"]),
        "bindingRevision": binding["revision"],
    }


def require_predecessor_drain(snapshot: dict[str, Any]) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if (
        str(head["installation_id"]) != PREDECESSOR["installationId"]
        or head["state"] != "active"
        or head["etag_version"] != PREDECESSOR["revision"]
        or head["lock_hash"] != PREDECESSOR["lockHash"]
        or head["overlay_revision"] != PREDECESSOR["overlayRevision"]
        or len(bindings) != 1
    ):
        raise ValueError("exact predecessor head required")
    binding = bindings[0]
    if (
        str(binding["generation"]) != PREDECESSOR_GENERATION
        or binding["revision"] != 5
        or binding["execution_epoch"] != 4
        or binding["enabled"] is not False
        or binding["operation_fence"] is not True
        or binding["desired_state"] != "enabled"
        or binding["observed_state"] != "unknown"
    ):
        raise ValueError("exact predecessor restart state required")
    if not snapshot["resources"] or any(
        item["cleanup_state"] != "released" or item["observed_release"] is not True
        for item in snapshot["resources"]
    ):
        raise ValueError("predecessor released resources required")
    if any(
        item["status"] not in {"succeeded", "failed", "cancelled"}
        for item in snapshot["operations"]
    ):
        raise ValueError("predecessor unresolved operation")
    return {
        "etag": PREDECESSOR["revision"],
        "generation": PREDECESSOR_GENERATION,
        "bindingRevision": binding["revision"],
    }


def require_stale_enable_cancel(
    snapshot: dict[str, Any], *, expected_operation_id: str
) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if head["state"] != "active" or head["etag_version"] != 5 or len(bindings) != 1:
        raise ValueError("one active installation generation required")
    binding = bindings[0]
    if (
        binding["revision"] != 3
        or binding["execution_epoch"] != 2
        or binding["enabled"] is not False
        or binding["operation_fence"] is not True
        or binding["desired_state"] != "disabled"
        or binding["observed_state"] != "unknown"
        or not binding["config_ref"]
    ):
        raise ValueError("exact post-failure binding required")
    pending = [
        item
        for item in snapshot["operations"]
        if item["status"] not in {"succeeded", "failed", "cancelled"}
    ]
    if (
        len(pending) != 1
        or str(pending[0]["operation_id"]) != expected_operation_id
        or pending[0]["kind"] != "enable"
        or pending[0]["status"] != "accepted"
        or pending[0]["phase"] != "accepted"
        or pending[0]["deadline_expired"] is not True
    ):
        raise ValueError("one exact expired enable operation required")
    if not snapshot["resources"] or any(
        item["cleanup_state"] != "released" or item["observed_release"] is not True
        for item in snapshot["resources"]
    ):
        raise ValueError("post-failure released resources required")
    return {
        "etag": 5,
        "generation": str(binding["generation"]),
        "bindingRevision": binding["revision"],
        "expiredEnableOperationId": expected_operation_id,
    }


def require_unowned_recovery_cancel(
    snapshot: dict[str, Any], *, expected_operation_id: str
) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if head["state"] != "active" or head["etag_version"] != 5 or len(bindings) != 1:
        raise ValueError("one active installation generation required")
    binding = bindings[0]
    if (
        binding["revision"] != 5
        or binding["execution_epoch"] != 3
        or binding["enabled"] is not False
        or binding["operation_fence"] is not True
        or binding["desired_state"] != "disabled"
        or binding["observed_state"] != "unknown"
        or not binding["config_ref"]
    ):
        raise ValueError("exact unowned recovery binding required")
    pending = [
        item
        for item in snapshot["operations"]
        if item["status"] not in {"succeeded", "failed", "cancelled"}
    ]
    if (
        len(pending) != 1
        or str(pending[0]["operation_id"]) != expected_operation_id
        or pending[0]["kind"] != "enable"
        or pending[0]["status"] != "accepted"
        or pending[0]["phase"] != "accepted"
    ):
        raise ValueError("one exact unowned enable operation required")
    if not snapshot["resources"] or any(
        item["cleanup_state"] != "released" or item["observed_release"] is not True
        for item in snapshot["resources"]
    ):
        raise ValueError("unowned recovery released resources required")
    return {
        "etag": 5,
        "generation": str(binding["generation"]),
        "bindingRevision": binding["revision"],
        "unownedEnableOperationId": expected_operation_id,
    }


def require_released_owner_settlement(snapshot: dict[str, Any]) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if head["state"] != "active" or head["etag_version"] != 5 or len(bindings) != 1:
        raise ValueError("one active released installation required")
    binding = bindings[0]
    if (
        binding["enabled"] is not False
        or binding["operation_fence"] is not True
        or binding["desired_state"] != "enabled"
        or binding["observed_state"] != "unknown"
        or not binding["config_ref"]
    ):
        raise ValueError("exact released owner binding required")
    if not snapshot["resources"] or any(
        item["cleanup_state"] != "released" or item["observed_release"] is not True
        for item in snapshot["resources"]
    ):
        raise ValueError("released owner resources required")
    if any(
        item["status"] not in {"succeeded", "failed", "cancelled"}
        for item in snapshot["operations"]
    ):
        raise ValueError("released owner unresolved operation")
    return {
        "etag": 5,
        "generation": str(binding["generation"]),
        "bindingRevision": binding["revision"],
    }


def replacement_ref(snapshot: dict[str, Any]) -> dict[str, Any]:
    head = snapshot["head"]
    bindings = snapshot["bindings"]
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    if head["state"] != "active" or head["etag_version"] != 5 or len(bindings) != 1:
        raise ValueError("active replacement predecessor required")
    binding = bindings[0]
    if (
        binding["enabled"] is not False
        or binding["operation_fence"] is not True
        or binding["desired_state"] != "disabled"
        or binding["observed_state"] != "unknown"
    ):
        raise ValueError("drained replacement predecessor required")
    if not snapshot["resources"] or any(
        item["cleanup_state"] != "released" or item["observed_release"] is not True
        for item in snapshot["resources"]
    ):
        raise ValueError("replacement predecessor released resources required")
    if any(
        item["status"] not in {"succeeded", "failed", "cancelled"}
        for item in snapshot["operations"]
    ):
        raise ValueError("replacement predecessor unresolved operation")
    return {
        "installationId": str(head["installation_id"]),
        "revision": head["etag_version"],
        "lockHash": head["lock_hash"],
        "overlayRevision": head["overlay_revision"],
    }


def replacement_predecessor_label(label: str) -> str:
    try:
        return {"b": "a", "d": "c"}[label]
    except KeyError as exc:
        raise ValueError("replacement install label required") from exc


def create(label: str) -> dict[str, Any]:
    target = STATE / label / "create-result.json"
    if target.exists():
        raise ValueError("create result exists; observe without resending")
    if label in {"a", "c"}:
        if label == "c":
            for retired in ("a", "b"):
                prior = observe_installation(_initial(retired)["installationId"])
                if prior["head"]["state"] != "uninstalled":
                    raise ValueError("installations A and B must be uninstalled before C")
        predecessor = observe_installation(PREDECESSOR["installationId"])
        binding = predecessor["bindings"]
        if (
            predecessor["head"]["state"] != "active"
            or predecessor["head"]["etag_version"] != 5
            or predecessor["head"]["lock_hash"] != PREDECESSOR["lockHash"]
            or len(binding) != 1
            or binding[0]["enabled"] is not False
            or binding[0]["operation_fence"] is not True
            or predecessor["canaryInstallations"] != 0
        ):
            raise ValueError("exact drained predecessor required")
        predecessor_ref = PREDECESSOR
    elif label in {"b", "d"}:
        predecessor_label = replacement_predecessor_label(label)
        predecessor = observe_installation(_initial(predecessor_label)["installationId"])
        predecessor_ref = replacement_ref(predecessor)
    else:
        raise ValueError("exact install label required")
    first_installer = _load("a0v_canonical_ecommerce_first_install")
    helper = _load("a0v_ecommerce_growth_1_5_registry_successor")
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup = helper._database_backup(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        state_dir=target.parent,
    )
    _freeze(target.parent / "create-intent.json", {
        "label": label,
        "predecessor": predecessor_ref,
        "versions": VERSIONS,
        "backup": backup,
    })
    connect = first_installer.container_database_connect_factory(
        context="colima-aos-extension",
        container="aos-a0v-recovery-pg",
        database_name="aos_meta_head",
    )
    result = first_installer.create_approved_first_installation(
        connect_factory=connect,
        state_dir=TRUST_STATE,
        core_version="1.3.0",
        adapter_version="1.22.0",
        growth_version="1.8.0",
        idempotency_prefix=f"a0v-current-ecommerce-{label}-20260915",
        current_installation_ref=predecessor_ref,
    )
    if result["installationState"] != "approved":
        raise ValueError("new approved installation required")
    _freeze(target, result)
    return {"outcome": f"CURRENT_ECOMMERCE_{label.upper()}_APPROVED", **result}


def lifecycle(label: str, action: str) -> dict[str, Any]:
    installation_id = _initial(label)["installationId"]
    snapshot = observe_installation(installation_id)
    command = require_phase(action, snapshot)
    intent = STATE / label / f"{action}-intent.json"
    _freeze(intent, {"installationId": installation_id, **command})
    activation, _store, service, _disable, _dependent = _setup_runtime_plane()
    receipt = service.request_preparation(
        **SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=f"a0v-current-ecommerce-{label}-{action}-20260915",
        if_match=f'"{command["etag"]}"',
        kind=command["kind"],
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed}


def configure(label: str, action: str) -> dict[str, Any]:
    profile = _load("a0v_ecommerce_1_7_configure")
    installation_id = _initial(label)["installationId"]
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    state_path = STATE / label / "configuration.json"
    suffix = "recover" if action == "recover" else action

    def target(recovery=False, *, sleep_recovery=False, niushop_1_4=False):
        if any((recovery, sleep_recovery, niushop_1_4)):
            raise ValueError("only current ecommerce installation allowed")
        return (
            installation_id,
            state_path,
            f"a0v-current-ecommerce-{label}-{suffix}",
            f"current-ecommerce-{label}-{suffix}",
        )

    profile.configuration_target = target
    return profile.run("enable" if action == "recover" else action)


def disable(label: str, *, suffix: str = "disable") -> dict[str, Any]:
    installation_id = _initial(label)["installationId"]
    command = require_phase("disable", observe_installation(installation_id))
    _freeze(STATE / label / f"{suffix}-intent.json", {"installationId": installation_id, **command})
    activation, _store, _lifecycle, service, _dependent = _setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=f"a0v-current-ecommerce-{label}-{suffix}-20260915",
        if_match='"5"',
        target={
            "generation": command["generation"],
            "bindingRevision": command["bindingRevision"],
        },
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed}


def settle_released(label: str) -> dict[str, Any]:
    installation_id = _initial(label)["installationId"]
    command = require_released_owner_settlement(observe_installation(installation_id))
    _freeze(
        STATE / label / "settle-released-intent.json",
        {"installationId": installation_id, **command},
    )
    activation, _store, _lifecycle, service, _dependent = _setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=f"a0v-current-ecommerce-{label}-settle-released-20260915",
        if_match='"5"',
        target={
            "generation": command["generation"],
            "bindingRevision": command["bindingRevision"],
        },
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed}


def drain_predecessor() -> dict[str, Any]:
    from uuid import UUID
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_consumer import (
        ClaimedDisableDelivery,
        RuntimeDisableConsumer,
    )
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.tenant_scope import TenantScope

    snapshot = observe_installation(PREDECESSOR["installationId"])
    command = require_predecessor_drain(snapshot)
    _freeze(
        STATE / "predecessor-drain-intent.json",
        {"installationId": PREDECESSOR["installationId"], **command},
    )
    activation, store, _lifecycle, service, _dependent = _setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=PREDECESSOR["installationId"],
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key="a0v-current-ecommerce-predecessor-drain-20260915",
        if_match='"5"',
        target={
            "generation": command["generation"],
            "bindingRevision": command["bindingRevision"],
        },
    )
    operation_id = UUID(receipt.response_json["operationId"])
    consumer = RuntimeDisableConsumer(
        connect=runtime_worker_connection,
        installation_store=store,
        check_current_permission=CurrentControlPermission(
            operation=DISABLE_RUNTIME_OPERATION
        ),
        check_drained=GenerationDrainReader(),
        dependent=EcommerceGrowthDisableDependent(),
    )
    scope = TenantScope(**SCOPE)
    with consumer._connection(SCOPE) as conn:
        lease = consumer.outbox.claim(
            conn,
            **SCOPE,
            operation_kind="disable",
            installation_id=PREDECESSOR["installationId"],
        )
    if lease is None or lease.operation_id != operation_id:
        raise ValueError("exact predecessor disable delivery required")
    delivery = consumer.finish_claimed(
        ClaimedDisableDelivery(scope, lease, UUID(PREDECESSOR["installationId"]))
    )
    if delivery.operation_id != operation_id or delivery.operation_status != "succeeded":
        raise ValueError("predecessor disable did not settle")
    return {
        "command": command,
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "delivery": {
            "operationId": str(delivery.operation_id),
            "operationStatus": delivery.operation_status,
            "deliveryStatus": delivery.delivery_status,
        },
    }


def cancel_stale_enable_a() -> dict[str, Any]:
    installation_id = _initial("a")["installationId"]
    original = json.loads((STATE / "enable-a-command.json").read_text(encoding="utf-8"))
    operation_id = str(original["receipt"]["operationId"])
    command = require_stale_enable_cancel(
        observe_installation(installation_id), expected_operation_id=operation_id
    )
    _freeze(
        STATE / "a/cancel-stale-enable-intent.json",
        {"installationId": installation_id, **command},
    )
    activation, _store, _lifecycle, service, _dependent = _setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key="a0v-current-ecommerce-a-cancel-stale-enable-20260915",
        if_match='"5"',
        target={
            "generation": command["generation"],
            "bindingRevision": command["bindingRevision"],
        },
    )
    return {
        "command": command,
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
    }


def cancel_unowned_recovery_a() -> dict[str, Any]:
    installation_id = _initial("a")["installationId"]
    original = json.loads((STATE / "recover-a-command.json").read_text(encoding="utf-8"))
    operation_id = str(original["receipt"]["operationId"])
    command = require_unowned_recovery_cancel(
        observe_installation(installation_id), expected_operation_id=operation_id
    )
    _freeze(
        STATE / "a/cancel-unowned-recovery-intent.json",
        {"installationId": installation_id, **command},
    )
    activation, _store, _lifecycle, service, _dependent = _setup_runtime_plane()
    receipt = service.request(
        **SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key="a0v-current-ecommerce-a-cancel-unowned-recovery-20260915",
        if_match='"5"',
        target={
            "generation": command["generation"],
            "bindingRevision": command["bindingRevision"],
        },
    )
    return {
        "command": command,
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
    }


@contextmanager
def _installation_connection():
    import psycopg
    from psycopg.rows import dict_row

    path = ROOT.parent / ".aos-recovery-20260912/state/installation-control-identity.json"
    if path.stat().st_mode & 0o777 != 0o600:
        raise ValueError("private installation identity required")
    identity = json.loads(path.read_text())
    if identity["role"] != "aos_a0v_installation_20260912":
        raise ValueError("exact installation identity required")
    with psycopg.connect(
        host="127.0.0.1",
        port=18435,
        dbname="aos_meta_head",
        user=identity["role"],
        password=identity["password"],
        row_factory=dict_row,
    ) as conn:
        conn.execute("SET ROLE aos_app")
        conn.commit()
        yield conn


def uninstall(label: str) -> dict[str, Any]:
    installation_id = _initial(label)["installationId"]
    snapshot = observe_installation(installation_id)
    command = require_phase("uninstall", snapshot)
    if label == "a":
        successor = observe_installation(_initial("b")["installationId"])
        if successor["head"]["state"] != "uninstalled":
            raise ValueError("installation B must be uninstalled before A")
    _freeze_or_match(
        STATE / label / "uninstall-intent.json",
        {"installationId": installation_id, **command},
    )
    legacy = _load("a0v_ecommerce_invalid_baseline_uninstall")
    store, service = legacy._build(
        _installation_connection,
        TRUST_STATE / "signing/trust-roots.json",
    )
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest

    receipt = service.uninstall(
        **SCOPE,
        installation_id=installation_id,
        request=UninstallInstallationRequest(
            reason=f"Current ecommerce installation {label.upper()} rehearsal completed after confirmed cleanup"
        ),
        actor="a0v-ecommerce-growth-1.4-runtime-owner",
        roles=["admin"],
        markings=[],
        idempotency_key=f"a0v-current-ecommerce-{label}-uninstall-20260915",
        if_match='"5"',
    )
    record = store.get_installation(**SCOPE, installation_id=installation_id)
    if record.state != "uninstalled" or record.active_revision is not None:
        raise ValueError("uninstall readback differs")
    return {"receipt": receipt.response_json, "replayed": receipt.replayed, "state": record.state}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "observe", "create-a", "prepare-a", "verify-a", "stage-a", "configure-a",
            "enable-a", "drain-predecessor", "cancel-stale-enable-a",
            "cancel-unowned-recovery-a", "disable-a",
            "recover-a", "disable-a-final",
            "uninstall-a", "create-b", "prepare-b", "verify-b", "stage-b",
            "configure-b", "enable-b", "disable-b", "uninstall-b", "create-c",
            "prepare-c", "verify-c", "stage-c", "configure-c", "enable-c",
            "disable-c", "settle-c", "create-d", "prepare-d", "verify-d", "stage-d",
            "configure-d", "enable-d",
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("immutable output exists; observe before retry")
    if args.action == "observe":
        result = observe()
    elif args.action.startswith("create-"):
        result = create(args.action[-1])
    elif args.action in {
        "prepare-a", "verify-a", "prepare-b", "verify-b", "prepare-c", "verify-c",
        "prepare-d", "verify-d",
    }:
        action, label = args.action.split("-")
        result = lifecycle(label, action)
    elif args.action == "drain-predecessor":
        result = drain_predecessor()
    elif args.action == "cancel-stale-enable-a":
        result = cancel_stale_enable_a()
    elif args.action == "cancel-unowned-recovery-a":
        result = cancel_unowned_recovery_a()
    elif args.action == "disable-a":
        result = disable("a")
    elif args.action == "disable-a-final":
        result = disable("a", suffix="disable-final")
    elif args.action == "disable-b":
        result = disable("b")
    elif args.action == "disable-c":
        result = disable("c")
    elif args.action == "settle-c":
        result = settle_released("c")
    elif args.action in {"uninstall-a", "uninstall-b"}:
        result = uninstall(args.action[-1])
    else:
        action, label = args.action.split("-")
        result = configure(label, action)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    _freeze(args.output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
