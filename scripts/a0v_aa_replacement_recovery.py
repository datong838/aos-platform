#!/usr/bin/env python3
"""Create AA as the formal direct replacement of drained Z."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-aa"
AA_DIR = STATE / "aa"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
Z_ID = "cd426e3a-f5e8-45a2-b6a8-8991294b467e"
Z_GENERATION = "d49fe4fd-55c8-4688-9602-5dbff946bc36"
LOCK = "sha256:6259239db5ddff1cc5156955d445673e3063640df30c7410448aa206d826a5cf"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
Z_DISABLE_OPERATION = "e907f30d-063e-4ea4-9c1c-8fb339ce7610"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-aa-20260917"
ACTIONS = ("preflight", "create-aa", "prepare-aa", "verify-aa", "stage-aa",
           "configure-aa", "enable-aa", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "aa":
            raise ValueError("only fixed AA installation allowed")
        value = json.loads((AA_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AA installation required")
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


def detached_z(profile) -> dict:
    snapshot = profile.observe_installation(Z_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != Z_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != Z_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached Z replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (Z_DISABLE_OPERATION,)).fetchone()
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (Z_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 53
            or row["cutover_group_revision"] != 80 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or phases != ["fence", "detach"]):
        raise ValueError("exact Z detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_z(profile)
    if AA_DIR.exists():
        raise ValueError("AA intent already exists; inspect without resending")
    return {"outcome": "AA_REPLACEMENT_PREFLIGHT_GREEN", "z": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_aa(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_z(profile))
    if AA_DIR.exists():
        raise ValueError("AA intent/result exists; inspect without resending")
    AA_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AA_DIR)
    profile._freeze(AA_DIR / "create-intent.json",
        {"label": "aa", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AA replacement required")
    profile._freeze(AA_DIR / "create-result.json", result)
    return {"outcome": "AA_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-aa" if action == "prepare" else "prepare-aa")
    return profile.lifecycle("aa", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-aa", "configure": "stage-aa", "enable": "configure-aa"}[action]
    load(predecessor)
    return profile.configure("aa", action)


def observe(profile) -> dict:
    value = {"outcome": "AA_REPLACEMENT_OBSERVED", "z": profile.observe_installation(Z_ID)}
    if (AA_DIR / "create-result.json").exists():
        value["aa"] = profile.observe_installation(profile._initial("aa")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AA replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-aa":
        return create_aa(profile)
    if action in {"prepare-aa", "verify-aa"}:
        return lifecycle(profile, action.removesuffix("-aa"))
    if action in {"stage-aa", "configure-aa", "enable-aa"}:
        return configured(profile, action.removesuffix("-aa"))
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
