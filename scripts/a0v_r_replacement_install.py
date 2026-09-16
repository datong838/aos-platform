"""Recover Q replacement through interrupted R and a clean active S."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-r"
R_DIR = STATE / "r"
S_DIR = STATE / "s"
BUNDLE_ROOT = (
    ROOT.parent
    / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
)
Q_ID = "9c49b383-e04d-41b4-8276-8b8bc6db49a8"
Q_GENERATION = "98aea676-ee71-4d42-a6c8-6634960efe5e"
Q_LOCK = "sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8"
Q_DISABLE_OPERATION = "c4a48488-9088-4db9-b71e-7811ae7c3d8a"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
VERSIONS = {
    "domain.ecommerce.core": "1.4.0",
    "platform.ecommerce.niushop": "1.23.0",
    "solution.ecommerce.growth": "1.10.0",
    "solution.ecommerce.operations-base": "1.2.0",
}
PREFIX = "a0v-q-advisor-clean-r-20260917"
ACTIONS = (
    "preflight",
    "create-r",
    "uninstall-q",
    "prepare-r",
    "verify-r",
    "reset-r",
    "create-s",
    "uninstall-r",
    "prepare-s",
    "verify-s",
    "stage-s",
    "configure-s",
    "enable-s",
    "observe",
)


def load_profile():
    spec = importlib.util.spec_from_file_location(
        "advisor_r_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py"
    )
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label not in {"r", "s"}:
            raise ValueError("only fixed R/S installation allowed")
        directory = R_DIR if label == "r" else S_DIR
        value = json.loads((directory / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        if not isinstance(identity, str) or str(UUID(identity)) != identity:
            raise ValueError("canonical R/S installation required")
        return value

    profile._initial = initial
    return profile


def freeze(path: Path, value: dict) -> None:
    profile = load_profile()
    profile._freeze(path, value)


def load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def detached_q(profile) -> dict:
    snapshot = profile.observe_installation(Q_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (
        str(head["installation_id"]) != Q_ID
        or head["state"] != "active"
        or head["etag_version"] != 5
        or head["lock_hash"] != Q_LOCK
        or len(bindings) != 1
        or str(bindings[0]["generation"]) != Q_GENERATION
        or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
        or bindings[0]["enabled"] is not False
        or bindings[0]["operation_fence"] is not True
        or bindings[0]["desired_state"] != "disabled"
        or bindings[0]["observed_state"] != "unknown"
        or len(snapshot["resources"]) != 3
        or any(
            row["cleanup_state"] != "released" or row["observed_release"] is not True
            for row in snapshot["resources"]
        )
        or any(row["status"] not in {"succeeded", "failed", "cancelled"} for row in snapshot["operations"])
        or snapshot["canaryInstallations"] != 0
    ):
        raise ValueError("exact detached Q installation required")
    from a0v_formal_text_model_renewal import database_connect

    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute(
            """SELECT handler_kind,installation_id,generation,execution_epoch,operation_fence,
                      cutover_group_revision FROM extension_operation_dispatch_binding
                 WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""",
            (GROUP,),
        ).fetchall()
        operation = conn.execute(
            """SELECT status,phase FROM extension_runtime_operation WHERE org_id='org-org'
                 AND project_id='dev-project' AND operation_id=%s""",
            (Q_DISABLE_OPERATION,),
        ).fetchone()
        phases = [
            row["phase"]
            for row in conn.execute(
                """SELECT phase FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org'
                     AND project_id='dev-project' AND runtime_operation_id=%s ORDER BY created_at""",
                (Q_DISABLE_OPERATION,),
            ).fetchall()
        ]
    if (
        len(routes) != 9
        or any(
            row["handler_kind"] != "legacy"
            or row["installation_id"] is not None
            or row["generation"] is not None
            or row["execution_epoch"] is not None
            or row["operation_fence"] is not True
            or row["cutover_group_revision"] != 59
            for row in routes
        )
        or operation is None
        or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
        or phases != ["fence", "detach"]
    ):
        raise ValueError("exact Q detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    q = detached_q(profile)
    if R_DIR.exists():
        raise ValueError("R intent already exists; inspect without resending")
    return {
        "outcome": "R_REPLACEMENT_PREFLIGHT_GREEN",
        "q": q,
        "versions": VERSIONS,
        "externalEffects": 0,
    }


def create_r(profile) -> dict:
    load("preflight")
    q = detached_q(profile)
    predecessor = profile.replacement_ref(q)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    if R_DIR.exists():
        raise ValueError("R intent/result exists; inspect without resending")
    R_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    backup = helper._database_backup(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        state_dir=R_DIR,
    )
    profile._freeze(
        R_DIR / "create-intent.json",
        {"label": "r", "predecessor": predecessor, "versions": VERSIONS, "backup": backup},
    )
    connect = installer.container_database_connect_factory(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        database_name=helper.DATABASE_NAME,
    )
    result = installer.create_approved_first_installation(
        connect_factory=connect,
        state_dir=profile.TRUST_STATE,
        core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX,
        current_installation_ref=predecessor,
    )
    if result["installationState"] != "approved":
        raise ValueError("approved R replacement required")
    profile._freeze(R_DIR / "create-result.json", result)
    return {"outcome": "R_REPLACEMENT_APPROVED", **result}


def uninstall_q(profile) -> dict:
    load("create-r")
    detached_q(profile)
    r = profile.observe_installation(profile._initial("r")["installationId"])
    if (r["head"]["state"], r["head"]["etag_version"], r["bindings"]) != ("approved", 3, []):
        raise ValueError("approved unprepared R required before Q uninstall")
    intent = {
        "installationId": Q_ID,
        "etag": 5,
        "generation": Q_GENERATION,
        "bindingRevision": 9,
        "runtimeOperationId": Q_DISABLE_OPERATION,
        "successorInstallationId": str(r["head"]["installation_id"]),
        "idempotencyKey": PREFIX + "-uninstall-q",
    }
    profile._freeze_or_match(STATE / "uninstall-q-intent.json", intent)
    legacy = profile._load("a0v_ecommerce_invalid_baseline_uninstall")
    store, service = legacy._build(
        profile._installation_connection,
        profile.TRUST_STATE / "signing/trust-roots.json",
    )
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest

    receipt = service.uninstall(
        **profile.SCOPE,
        installation_id=Q_ID,
        request=UninstallInstallationRequest(
            reason="Q resources were released on reboot and its routes detached before clean R"
        ),
        actor="a0v-ecommerce-growth-1.4-runtime-owner",
        roles=["admin"],
        markings=[],
        idempotency_key=intent["idempotencyKey"],
        if_match='"5"',
    )
    record = store.get_installation(**profile.SCOPE, installation_id=Q_ID)
    if record.state != "uninstalled" or record.etag_version != 6 or record.active_revision is not None:
        raise ValueError("Q uninstall readback differs")
    return {
        "outcome": "Q_FORMALLY_UNINSTALLED_BEFORE_R_PREPARE",
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": record.state,
        "etag": record.etag_version,
    }


def lifecycle(profile, action: str) -> dict:
    load("uninstall-q" if action == "prepare" else "prepare-r")
    return profile.lifecycle("r", action)


def interrupted_r(profile, *, resettable: bool) -> dict:
    snapshot = profile.observe_installation(profile._initial("r")["installationId"])
    head, operations = snapshot["head"], snapshot["operations"]
    expected = ("applied", 4) if resettable else ("approved", 5)
    verify = [row for row in operations if row["kind"] == "runtime-verify"]
    if (
        (head["state"], head["etag_version"]) != expected
        or head["lock_hash"] != profile._initial("r")["lockHash"]
        or snapshot["bindings"]
        or len(snapshot["resources"]) != 3
        or any(
            row["cleanup_state"] != "released" or row["observed_release"] is not True
            for row in snapshot["resources"]
        )
        or len(operations) != 2
        or {row["kind"] for row in operations} != {"runtime-apply", "runtime-verify"}
        or len(verify) != 1
        or (
            resettable
            and not (
                verify[0]["status"] == "accepted"
                and verify[0]["phase"] == "accepted"
                and verify[0]["deadline_expired"] is True
            )
        )
        or (
            not resettable
            and any(row["status"] not in {"succeeded", "failed", "cancelled"} for row in operations)
        )
        or snapshot["canaryInstallations"] != 0
    ):
        raise ValueError("exact resettable or terminal R interruption required")
    return snapshot


def reset_r(profile) -> dict:
    load("verify-r")
    current = interrupted_r(profile, resettable=True)
    installation_id = str(current["head"]["installation_id"])
    verify_id = str(next(row["operation_id"] for row in current["operations"] if row["kind"] == "runtime-verify"))
    profile._freeze_or_match(
        STATE / "reset-r-intent.json",
        {"installationId": installation_id, "etag": 4, "verifyOperationId": verify_id},
    )
    activation, _store, lifecycle_service, _disable, _dependent = profile._setup_runtime_plane()
    receipt = lifecycle_service.reset_preparation(
        **profile.SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=PREFIX + "-reset-r",
        if_match='"4"',
    )
    interrupted_r(profile, resettable=False)
    return {
        "outcome": "R_INTERRUPTED_PREPARATION_RESET",
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": "approved",
        "revision": 5,
    }


def create_s(profile) -> dict:
    load("reset-r")
    r = interrupted_r(profile, resettable=False)
    if S_DIR.exists():
        raise ValueError("S intent/result exists; inspect without resending")
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    S_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    backup = helper._database_backup(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        state_dir=S_DIR,
    )
    profile._freeze(
        S_DIR / "create-intent.json",
        {
            "label": "s",
            "predecessor": None,
            "interruptedInstallationId": str(r["head"]["installation_id"]),
            "versions": VERSIONS,
            "backup": backup,
        },
    )
    connect = installer.container_database_connect_factory(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        database_name=helper.DATABASE_NAME,
    )
    result = installer.create_approved_first_installation(
        connect_factory=connect,
        state_dir=profile.TRUST_STATE,
        core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX + "-clean-s",
    )
    if result["installationState"] != "approved":
        raise ValueError("clean S installation required")
    profile._freeze(S_DIR / "create-result.json", result)
    return {"outcome": "S_CLEAN_INSTALLATION_APPROVED_AFTER_R_INTERRUPTION", **result}


def uninstall_r(profile) -> dict:
    load("create-s")
    r = interrupted_r(profile, resettable=False)
    s = profile.observe_installation(profile._initial("s")["installationId"])
    if (s["head"]["state"], s["head"]["etag_version"], s["bindings"]) != ("approved", 3, []):
        raise ValueError("approved unprepared S required before R uninstall")
    installation_id = str(r["head"]["installation_id"])
    profile._freeze_or_match(
        STATE / "uninstall-r-intent.json",
        {
            "installationId": installation_id,
            "etag": 5,
            "successorInstallationId": str(s["head"]["installation_id"]),
        },
    )
    legacy = profile._load("a0v_ecommerce_invalid_baseline_uninstall")
    store, service = legacy._build(
        profile._installation_connection,
        profile.TRUST_STATE / "signing/trust-roots.json",
    )
    from aos_api.asset_registry.composition_contracts import UninstallInstallationRequest

    receipt = service.uninstall(
        **profile.SCOPE,
        installation_id=installation_id,
        request=UninstallInstallationRequest(
            reason="R verify lost Q active baseline after Q uninstall; recover through clean S"
        ),
        actor="a0v-ecommerce-growth-1.4-runtime-owner",
        roles=["admin"],
        markings=[],
        idempotency_key=PREFIX + "-uninstall-r",
        if_match='"5"',
    )
    record = store.get_installation(**profile.SCOPE, installation_id=installation_id)
    if record.state != "uninstalled" or record.active_revision is not None:
        raise ValueError("R uninstall readback differs")
    return {
        "outcome": "R_INTERRUPTED_INSTALLATION_UNINSTALLED",
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": record.state,
        "successorInstallationId": str(s["head"]["installation_id"]),
    }


def lifecycle_s(profile, action: str) -> dict:
    load("uninstall-r" if action == "prepare" else "prepare-s")
    return profile.lifecycle("s", action)


def configure_s(profile, action: str) -> dict:
    predecessor = {"stage": "verify-s", "configure": "stage-s", "enable": "configure-s"}[action]
    load(predecessor)
    return profile.configure("s", action)


def observe(profile) -> dict:
    result = {
        "outcome": "R_REPLACEMENT_OBSERVED",
        "q": profile.observe_installation(Q_ID),
    }
    if (R_DIR / "create-result.json").exists():
        result["r"] = profile.observe_installation(profile._initial("r")["installationId"])
    if (S_DIR / "create-result.json").exists():
        result["s"] = profile.observe_installation(profile._initial("s")["installationId"])
    return result


def run(action: str, profile) -> dict:
    if action not in ACTIONS:
        raise ValueError("unsupported R replacement action")
    if action == "preflight":
        return preflight(profile)
    if action == "create-r":
        return create_r(profile)
    if action == "uninstall-q":
        return uninstall_q(profile)
    if action == "reset-r":
        return reset_r(profile)
    if action == "create-s":
        return create_s(profile)
    if action == "uninstall-r":
        return uninstall_r(profile)
    if action in {"prepare-r", "verify-r"}:
        return lifecycle(profile, action.split("-")[0])
    if action in {"prepare-s", "verify-s"}:
        return lifecycle_s(profile, action.split("-")[0])
    if action in {"stage-s", "configure-s", "enable-s"}:
        return configure_s(profile, action.split("-")[0])
    return observe(profile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    profile = load_profile()
    result = run(args.action, profile)
    path = STATE / f"{args.action}-result.json"
    if args.action != "observe" and not path.exists():
        profile._freeze(path, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
