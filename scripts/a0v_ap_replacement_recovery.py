#!/usr/bin/env python3
"""Create AP as the formal direct replacement of detached AO."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-ap"
AP_DIR = STATE / "ap"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AO_ID = "d4186607-c93f-4fd0-8daa-46e349184ab9"
AO_GENERATION = "00bb99df-d436-483d-86df-496718c6f129"
LOCK = "sha256:bd07e609a0fa815ea1f2e6d3e287ab395385a548470560bd1f7fd3a8681371a8"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AO_DISABLE_OPERATION = "44d42ccb-07a2-437a-8405-ea703f812803"
AO_DETACH_RECEIPT = "c98d7a33-2653-42a8-86f1-05f26c09217e"
AO_DETACH_HASH = "sha256:b4e2969a445b0459dd0e43376d600ab87a515374774e3434d31a28eb014c29f9"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-ap-20260919"
ACTIONS = ("preflight", "create-ap", "prepare-ap", "verify-ap", "stage-ap",
           "configure-ap", "enable-ap", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "ap":
            raise ValueError("only fixed AP installation allowed")
        value = json.loads((AP_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AP installation required")
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


def detached_ao(profile) -> dict:
    snapshot = profile.observe_installation(AO_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AO_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AO_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AO replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AO_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AO_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 98
            or row["cutover_group_revision"] != 125 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AO_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AO_DETACH_HASH):
        raise ValueError("exact AO detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_ao(profile)
    if AP_DIR.exists():
        raise ValueError("AP intent already exists; inspect without resending")
    return {"outcome": "AP_REPLACEMENT_PREFLIGHT_GREEN", "ao": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_ap(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_ao(profile))
    if AP_DIR.exists():
        raise ValueError("AP intent/result exists; inspect without resending")
    AP_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AP_DIR)
    profile._freeze(AP_DIR / "create-intent.json",
        {"label": "ap", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AP replacement required")
    profile._freeze(AP_DIR / "create-result.json", result)
    return {"outcome": "AP_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-ap" if action == "prepare" else "prepare-ap")
    return profile.lifecycle("ap", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-ap", "configure": "stage-ap", "enable": "configure-ap"}[action]
    load(predecessor)
    return profile.configure("ap", action)


def observe(profile) -> dict:
    value = {"outcome": "AP_REPLACEMENT_OBSERVED", "ao": profile.observe_installation(AO_ID)}
    if (AP_DIR / "create-result.json").exists():
        value["ap"] = profile.observe_installation(profile._initial("ap")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AP replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-ap":
        return create_ap(profile)
    if action in {"prepare-ap", "verify-ap"}:
        return lifecycle(profile, action.removesuffix("-ap"))
    if action in {"stage-ap", "configure-ap", "enable-ap"}:
        return configured(profile, action.removesuffix("-ap"))
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
