#!/usr/bin/env python3
"""Create AS as the formal direct replacement of detached AR."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-as"
AS_DIR = STATE / "as"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AR_ID = "90e9b84e-225c-4c91-a1d4-7d2751d7c7f2"
AR_GENERATION = "b41dc281-a6f7-4357-948b-88519e8b8146"
LOCK = "sha256:5cdaa3b167e7137b6fd53819a2dd72493e01a891fc3932a17ebfda8ba801a56f"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AR_DISABLE_OPERATION = "ffe632e9-3591-4dc9-b244-cdb12e5fcf00"
AR_DETACH_RECEIPT = "ed0229cc-9771-4f00-a210-4b2a8b7cf76b"
AR_DETACH_HASH = "sha256:aaecdd9e8009ed6a0d633c78293c59109e75ddc2fb25509fe2424d71cd499f10"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-as-20260919"
ACTIONS = ("preflight", "create-as", "prepare-as", "verify-as", "stage-as",
           "configure-as", "enable-as", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "as":
            raise ValueError("only fixed AS installation allowed")
        value = json.loads((AS_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AS installation required")
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


def detached_ar(profile) -> dict:
    snapshot = profile.observe_installation(AR_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AR_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AR_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AR replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AR_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AR_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 107
            or row["cutover_group_revision"] != 134 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AR_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AR_DETACH_HASH):
        raise ValueError("exact AR detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_ar(profile)
    if AS_DIR.exists():
        raise ValueError("AS intent already exists; inspect without resending")
    return {"outcome": "AS_REPLACEMENT_PREFLIGHT_GREEN", "ar": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_as(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_ar(profile))
    if AS_DIR.exists():
        raise ValueError("AS intent/result exists; inspect without resending")
    AS_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AS_DIR)
    profile._freeze(AS_DIR / "create-intent.json",
        {"label": "as", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AS replacement required")
    profile._freeze(AS_DIR / "create-result.json", result)
    return {"outcome": "AS_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-as" if action == "prepare" else "prepare-as")
    return profile.lifecycle("as", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-as", "configure": "stage-as", "enable": "configure-as"}[action]
    load(predecessor)
    return profile.configure("as", action)


def observe(profile) -> dict:
    value = {"outcome": "AS_REPLACEMENT_OBSERVED", "ar": profile.observe_installation(AR_ID)}
    if (AS_DIR / "create-result.json").exists():
        value["as"] = profile.observe_installation(profile._initial("as")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AS replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-as":
        return create_as(profile)
    if action in {"prepare-as", "verify-as"}:
        return lifecycle(profile, action.removesuffix("-as"))
    if action in {"stage-as", "configure-as", "enable-as"}:
        return configured(profile, action.removesuffix("-as"))
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
