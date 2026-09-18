#!/usr/bin/env python3
"""Create AK as the formal direct replacement of detached AJ."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260918/state/q-advisor-baseline/replacement-ak"
AK_DIR = STATE / "ak"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AJ_ID = "cc6b62cf-1d0c-4f6c-bf6f-5cfc80679244"
AJ_GENERATION = "6dc4f34a-5cc6-4b20-bfb8-8a002a7dcd76"
LOCK = "sha256:20bd5896e1144a63a98fb96a684122b70331441c6e6966267d73af9aa18da49b"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AJ_DISABLE_OPERATION = "b8a18338-f792-4c21-949e-70a0db4853a3"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-ak-20260918"
ACTIONS = ("preflight", "create-ak", "prepare-ak", "verify-ak", "stage-ak",
           "configure-ak", "enable-ak", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "ak":
            raise ValueError("only fixed AK installation allowed")
        value = json.loads((AK_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AK installation required")
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


def detached_aj(profile) -> dict:
    snapshot = profile.observe_installation(AJ_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AJ_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AJ_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AJ replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AJ_DISABLE_OPERATION,)).fetchone()
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AJ_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 83
            or row["cutover_group_revision"] != 110 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or phases != ["fence", "detach"]):
        raise ValueError("exact AJ detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_aj(profile)
    if AK_DIR.exists():
        raise ValueError("AK intent already exists; inspect without resending")
    return {"outcome": "AK_REPLACEMENT_PREFLIGHT_GREEN", "aj": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_ak(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_aj(profile))
    if AK_DIR.exists():
        raise ValueError("AK intent/result exists; inspect without resending")
    AK_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AK_DIR)
    profile._freeze(AK_DIR / "create-intent.json",
        {"label": "ak", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AK replacement required")
    profile._freeze(AK_DIR / "create-result.json", result)
    return {"outcome": "AK_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-ak" if action == "prepare" else "prepare-ak")
    return profile.lifecycle("ak", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-ak", "configure": "stage-ak", "enable": "configure-ak"}[action]
    load(predecessor)
    return profile.configure("ak", action)


def observe(profile) -> dict:
    value = {"outcome": "AK_REPLACEMENT_OBSERVED", "aj": profile.observe_installation(AJ_ID)}
    if (AK_DIR / "create-result.json").exists():
        value["ak"] = profile.observe_installation(profile._initial("ak")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AK replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-ak":
        return create_ak(profile)
    if action in {"prepare-ak", "verify-ak"}:
        return lifecycle(profile, action.removesuffix("-ak"))
    if action in {"stage-ak", "configure-ak", "enable-ak"}:
        return configured(profile, action.removesuffix("-ak"))
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
