#!/usr/bin/env python3
"""Reset interrupted T and activate a predecessor-free clean U."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-t"
T_DIR = STATE / "t"
U_DIR = STATE / "u"
BUNDLE_ROOT = (
    ROOT.parent
    / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
)
T_ID = "b6f774c6-d544-45ab-bcfa-7cd8b824c1ed"
T_LOCK = "sha256:78529f029c196f3841adedd8ee4ef0689ce25d2dde58c3d1df43203865237eac"
T_VERIFY_OPERATION = "bb953ef8-f925-492c-bfcc-82a2e684159e"
VERSIONS = {
    "domain.ecommerce.core": "1.4.0",
    "platform.ecommerce.niushop": "1.23.0",
    "solution.ecommerce.growth": "1.10.0",
    "solution.ecommerce.operations-base": "1.2.0",
}
PREFIX = "a0v-qyh-t-interruption-u-20260917"
ACTIONS = (
    "recovery-preflight",
    "reset-t",
    "create-u",
    "uninstall-t",
    "prepare-u",
    "verify-u",
    "stage-u",
    "configure-u",
    "enable-u",
    "observe",
)


def load_profile():
    spec = importlib.util.spec_from_file_location(
        "t_recovery_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py"
    )
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "u":
            raise ValueError("only fixed U installation allowed")
        value = json.loads((U_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical U installation required")
        return value

    profile._initial = initial
    return profile


def freeze(path: Path, value: dict) -> None:
    load_profile()._freeze(path, value)


def load(name: str) -> dict:
    path = STATE / f"{name}-result.json"
    if not path.is_file() or path.stat().st_mode & 0o777 != 0o600:
        raise ValueError(f"private {name} result required")
    return json.loads(path.read_text(encoding="utf-8"))


def interrupted_t(profile, *, resettable: bool) -> dict:
    snapshot = profile.observe_installation(T_ID)
    head, operations = snapshot["head"], snapshot["operations"]
    expected = ("applied", 4) if resettable else ("approved", 5)
    verify = [row for row in operations if row["kind"] == "runtime-verify"]
    if (
        (head["state"], head["etag_version"]) != expected
        or head["lock_hash"] != T_LOCK
        or snapshot["bindings"]
        or len(snapshot["resources"]) != 3
        or any(
            row["cleanup_state"] != "released" or row["observed_release"] is not True
            for row in snapshot["resources"]
        )
        or len(operations) != 2
        or {row["kind"] for row in operations} != {"runtime-apply", "runtime-verify"}
        or len(verify) != 1
        or str(verify[0]["operation_id"]) != T_VERIFY_OPERATION
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
        raise ValueError("exact resettable or terminal T interruption required")
    return snapshot


def preflight(profile) -> dict:
    snapshot = interrupted_t(profile, resettable=True)
    if U_DIR.exists():
        raise ValueError("U intent already exists; inspect without resending")
    return {
        "outcome": "T_INTERRUPTION_RECOVERY_PREFLIGHT_GREEN",
        "t": snapshot,
        "verifyOperationId": T_VERIFY_OPERATION,
        "versions": VERSIONS,
        "externalEffects": 0,
    }


def reset_t(profile) -> dict:
    load("recovery-preflight")
    interrupted_t(profile, resettable=True)
    profile._freeze_or_match(
        STATE / "reset-t-intent.json",
        {"installationId": T_ID, "etag": 4, "verifyOperationId": T_VERIFY_OPERATION},
    )
    activation, _store, lifecycle, _disable, _dependent = profile._setup_runtime_plane()
    receipt = lifecycle.reset_preparation(
        **profile.SCOPE,
        installation_id=T_ID,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=PREFIX + "-reset-t",
        if_match='"4"',
    )
    interrupted_t(profile, resettable=False)
    return {
        "outcome": "T_INTERRUPTED_PREPARATION_RESET",
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": "approved",
        "revision": 5,
    }


def create_u(profile) -> dict:
    load("reset-t")
    interrupted_t(profile, resettable=False)
    if U_DIR.exists():
        raise ValueError("U intent/result exists; inspect without resending")
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    U_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    backup = helper._database_backup(
        context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER,
        state_dir=U_DIR,
    )
    profile._freeze(
        U_DIR / "create-intent.json",
        {
            "label": "u",
            "predecessor": None,
            "interruptedInstallationId": T_ID,
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
        idempotency_prefix=PREFIX + "-clean-u",
    )
    if result["installationState"] != "approved":
        raise ValueError("clean U installation required")
    profile._freeze(U_DIR / "create-result.json", result)
    return {"outcome": "U_CLEAN_INSTALLATION_APPROVED_AFTER_T_INTERRUPTION", **result}


def uninstall_t(profile) -> dict:
    load("create-u")
    interrupted_t(profile, resettable=False)
    u = profile.observe_installation(profile._initial("u")["installationId"])
    if (u["head"]["state"], u["head"]["etag_version"], u["bindings"]) != (
        "approved", 3, []
    ):
        raise ValueError("approved unprepared U required before T uninstall")
    profile._freeze_or_match(
        STATE / "uninstall-t-intent.json",
        {
            "installationId": T_ID,
            "etag": 5,
            "successorInstallationId": str(u["head"]["installation_id"]),
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
        installation_id=T_ID,
        request=UninstallInstallationRequest(
            reason="T verify lost S active baseline after S uninstall; recover through clean U"
        ),
        actor="a0v-ecommerce-growth-1.4-runtime-owner",
        roles=["admin"],
        markings=[],
        idempotency_key=PREFIX + "-uninstall-t",
        if_match='"5"',
    )
    record = store.get_installation(**profile.SCOPE, installation_id=T_ID)
    if record.state != "uninstalled" or record.active_revision is not None:
        raise ValueError("T uninstall readback differs")
    return {
        "outcome": "T_INTERRUPTED_INSTALLATION_UNINSTALLED",
        "receipt": receipt.response_json,
        "replayed": receipt.replayed,
        "state": record.state,
        "successorInstallationId": str(u["head"]["installation_id"]),
    }


def lifecycle_u(profile, action: str) -> dict:
    load("uninstall-t" if action == "prepare" else "prepare-u")
    return profile.lifecycle("u", action)


def configure_u(profile, action: str) -> dict:
    predecessor = {"stage": "verify-u", "configure": "stage-u", "enable": "configure-u"}[action]
    load(predecessor)
    return profile.configure("u", action)


def observe(profile) -> dict:
    result = {"outcome": "T_INTERRUPTION_RECOVERY_OBSERVED", "t": profile.observe_installation(T_ID)}
    if (U_DIR / "create-result.json").exists():
        result["u"] = profile.observe_installation(profile._initial("u")["installationId"])
    return result


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported T interruption recovery action")
    profile = load_profile()
    if action == "recovery-preflight":
        return preflight(profile)
    if action == "reset-t":
        return reset_t(profile)
    if action == "create-u":
        return create_u(profile)
    if action == "uninstall-t":
        return uninstall_t(profile)
    if action in {"prepare-u", "verify-u"}:
        return lifecycle_u(profile, action.removesuffix("-u"))
    if action in {"stage-u", "configure-u", "enable-u"}:
        return configure_u(profile, action.removesuffix("-u"))
    return observe(profile)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=ACTIONS)
    args = parser.parse_args()
    output = STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    value = run(args.action)
    freeze(output, value)
    print(json.dumps(value, ensure_ascii=False, default=str, indent=2))
