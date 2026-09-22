#!/usr/bin/env python3
"""Create AB as the formal direct replacement of drained AA."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-ab"
AB_DIR = STATE / "ab"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AA_ID = "d0476259-7e04-4cf6-ba94-9d7da1c73db0"
AA_GENERATION = "44236c8a-cf56-451c-b620-21c63e48d87e"
LOCK = "sha256:bb484830d142b122bea47770a49724b404e2ffa8f5296d0e5083d80da70017f1"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AA_DISABLE_OPERATION = "139b08cd-211d-4595-b3bb-90527fe6f2f5"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-ab-20260917"
ACTIONS = ("preflight", "create-ab", "prepare-ab", "verify-ab", "stage-ab",
           "configure-ab", "enable-ab", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "ab":
            raise ValueError("only fixed AB installation allowed")
        value = json.loads((AB_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AB installation required")
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


def detached_aa(profile) -> dict:
    snapshot = profile.observe_installation(AA_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AA_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AA_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AA replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AA_DISABLE_OPERATION,)).fetchone()
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AA_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 56
            or row["cutover_group_revision"] != 83 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or phases != ["fence", "detach"]):
        raise ValueError("exact AA detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_aa(profile)
    if AB_DIR.exists():
        raise ValueError("AB intent already exists; inspect without resending")
    return {"outcome": "AB_REPLACEMENT_PREFLIGHT_GREEN", "aa": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_ab(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_aa(profile))
    if AB_DIR.exists():
        raise ValueError("AB intent/result exists; inspect without resending")
    AB_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AB_DIR)
    profile._freeze(AB_DIR / "create-intent.json",
        {"label": "ab", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AB replacement required")
    profile._freeze(AB_DIR / "create-result.json", result)
    return {"outcome": "AB_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-ab" if action == "prepare" else "prepare-ab")
    return profile.lifecycle("ab", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-ab", "configure": "stage-ab", "enable": "configure-ab"}[action]
    load(predecessor)
    return profile.configure("ab", action)


def observe(profile) -> dict:
    value = {"outcome": "AB_REPLACEMENT_OBSERVED", "aa": profile.observe_installation(AA_ID)}
    if (AB_DIR / "create-result.json").exists():
        value["ab"] = profile.observe_installation(profile._initial("ab")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AB replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-ab":
        return create_ab(profile)
    if action in {"prepare-ab", "verify-ab"}:
        return lifecycle(profile, action.removesuffix("-ab"))
    if action in {"stage-ab", "configure-ab", "enable-ab"}:
        return configured(profile, action.removesuffix("-ab"))
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
