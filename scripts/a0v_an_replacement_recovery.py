#!/usr/bin/env python3
"""Create AN as the formal direct replacement of detached AM."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-an"
AN_DIR = STATE / "an"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AM_ID = "fd28d180-db24-4568-a848-101fcd3aa3c5"
AM_GENERATION = "d6bc117e-d19d-4413-beb4-02884206e290"
LOCK = "sha256:f2bcef04d615b0c6a19b2a0465be392130eb6a85627135a8c58a1177901942cc"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AM_DISABLE_OPERATION = "6d94d641-6fc3-4edd-801c-69114d633c0c"
AM_DETACH_RECEIPT = "af6fe6a5-2e88-4b7d-8756-0bc977871a5d"
AM_DETACH_HASH = "sha256:6f20be3f146e1f126c110b367bc43ba685d9450c9317d5f4950d29d69e07a709"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-an-20260919"
ACTIONS = ("preflight", "create-an", "prepare-an", "verify-an", "stage-an",
           "configure-an", "enable-an", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "an":
            raise ValueError("only fixed AN installation allowed")
        value = json.loads((AN_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AN installation required")
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


def detached_am(profile) -> dict:
    snapshot = profile.observe_installation(AM_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AM_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AM_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AM replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AM_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AM_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 92
            or row["cutover_group_revision"] != 119 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AM_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AM_DETACH_HASH):
        raise ValueError("exact AM detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_am(profile)
    if AN_DIR.exists():
        raise ValueError("AN intent already exists; inspect without resending")
    return {"outcome": "AN_REPLACEMENT_PREFLIGHT_GREEN", "am": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_an(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_am(profile))
    if AN_DIR.exists():
        raise ValueError("AN intent/result exists; inspect without resending")
    AN_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AN_DIR)
    profile._freeze(AN_DIR / "create-intent.json",
        {"label": "an", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AN replacement required")
    profile._freeze(AN_DIR / "create-result.json", result)
    return {"outcome": "AN_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-an" if action == "prepare" else "prepare-an")
    return profile.lifecycle("an", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-an", "configure": "stage-an", "enable": "configure-an"}[action]
    load(predecessor)
    return profile.configure("an", action)


def observe(profile) -> dict:
    value = {"outcome": "AN_REPLACEMENT_OBSERVED", "am": profile.observe_installation(AM_ID)}
    if (AN_DIR / "create-result.json").exists():
        value["an"] = profile.observe_installation(profile._initial("an")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AN replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-an":
        return create_an(profile)
    if action in {"prepare-an", "verify-an"}:
        return lifecycle(profile, action.removesuffix("-an"))
    if action in {"stage-an", "configure-an", "enable-an"}:
        return configured(profile, action.removesuffix("-an"))
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
