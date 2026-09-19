#!/usr/bin/env python3
"""Create AR as the formal direct replacement of detached AQ."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ar"
AR_DIR = STATE / "ar"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AQ_ID = "d6839bf3-55b5-474c-aa21-49966e15db3d"
AQ_GENERATION = "b31be2a7-36fd-4348-9ff8-10939cc3d1cd"
LOCK = "sha256:7e338c1ae340333ca42f8f52c9e383b96255a9f9a6d9afc68ae9cb60f83e4f8d"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AQ_DISABLE_OPERATION = "e45d1c14-ebe0-43e0-bd24-75feb26a9a69"
AQ_DETACH_RECEIPT = "5de8ea90-3a52-4556-af26-8c008044cb77"
AQ_DETACH_HASH = "sha256:201556d70b44750c0fed8ad71aa09c718b27faf6aa5aeb5d2f36fe4a4ddb098e"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-ar-20260919"
ACTIONS = ("preflight", "create-ar", "prepare-ar", "verify-ar", "stage-ar",
           "configure-ar", "enable-ar", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "ar":
            raise ValueError("only fixed AR installation allowed")
        value = json.loads((AR_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AR installation required")
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


def detached_aq(profile) -> dict:
    snapshot = profile.observe_installation(AQ_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AQ_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AQ_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AQ replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AQ_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AQ_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 104
            or row["cutover_group_revision"] != 131 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AQ_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AQ_DETACH_HASH):
        raise ValueError("exact AQ detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_aq(profile)
    if AR_DIR.exists():
        raise ValueError("AR intent already exists; inspect without resending")
    return {"outcome": "AR_REPLACEMENT_PREFLIGHT_GREEN", "aq": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_ar(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_aq(profile))
    if AR_DIR.exists():
        raise ValueError("AR intent/result exists; inspect without resending")
    AR_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AR_DIR)
    profile._freeze(AR_DIR / "create-intent.json",
        {"label": "ar", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AR replacement required")
    profile._freeze(AR_DIR / "create-result.json", result)
    return {"outcome": "AR_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-ar" if action == "prepare" else "prepare-ar")
    return profile.lifecycle("ar", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-ar", "configure": "stage-ar", "enable": "configure-ar"}[action]
    load(predecessor)
    return profile.configure("ar", action)


def observe(profile) -> dict:
    value = {"outcome": "AR_REPLACEMENT_OBSERVED", "aq": profile.observe_installation(AQ_ID)}
    if (AR_DIR / "create-result.json").exists():
        value["ar"] = profile.observe_installation(profile._initial("ar")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AR replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-ar":
        return create_ar(profile)
    if action in {"prepare-ar", "verify-ar"}:
        return lifecycle(profile, action.removesuffix("-ar"))
    if action in {"stage-ar", "configure-ar", "enable-ar"}:
        return configured(profile, action.removesuffix("-ar"))
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
