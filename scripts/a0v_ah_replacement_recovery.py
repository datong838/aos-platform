#!/usr/bin/env python3
"""Create AH as the formal direct replacement of drained AG."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260917/state/q-advisor-baseline/replacement-ah"
AH_DIR = STATE / "ah"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AG_ID = "37d36900-5b9a-4cd0-9108-4ef5ded25d58"
AG_GENERATION = "31192641-3558-4cf2-9ad9-ea2375c69900"
LOCK = "sha256:3ea2a4acfb87da83a0a9add21ce312e6a7fc1e67a2ea59d2be64f9e5c20feedb"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AG_DISABLE_OPERATION = "45789d11-145e-4b4b-84a2-13e6d6fed5b6"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-ah-20260917"
ACTIONS = ("preflight", "create-ah", "prepare-ah", "verify-ah", "stage-ah",
           "configure-ah", "enable-ah", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "ah":
            raise ValueError("only fixed AH installation allowed")
        value = json.loads((AH_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AH installation required")
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


def detached_ag(profile) -> dict:
    snapshot = profile.observe_installation(AG_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AG_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AG_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AG replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AG_DISABLE_OPERATION,)).fetchone()
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AG_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 74
            or row["cutover_group_revision"] != 101 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or phases != ["fence", "detach"]):
        raise ValueError("exact AG detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_ag(profile)
    if AH_DIR.exists():
        raise ValueError("AH intent already exists; inspect without resending")
    return {"outcome": "AH_REPLACEMENT_PREFLIGHT_GREEN", "ag": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_ah(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_ag(profile))
    if AH_DIR.exists():
        raise ValueError("AH intent/result exists; inspect without resending")
    AH_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AH_DIR)
    profile._freeze(AH_DIR / "create-intent.json",
        {"label": "ah", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AH replacement required")
    profile._freeze(AH_DIR / "create-result.json", result)
    return {"outcome": "AH_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-ah" if action == "prepare" else "prepare-ah")
    return profile.lifecycle("ah", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-ah", "configure": "stage-ah", "enable": "configure-ah"}[action]
    load(predecessor)
    return profile.configure("ah", action)


def observe(profile) -> dict:
    value = {"outcome": "AH_REPLACEMENT_OBSERVED", "ag": profile.observe_installation(AG_ID)}
    if (AH_DIR / "create-result.json").exists():
        value["ah"] = profile.observe_installation(profile._initial("ah")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AH replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-ah":
        return create_ah(profile)
    if action in {"prepare-ah", "verify-ah"}:
        return lifecycle(profile, action.removesuffix("-ah"))
    if action in {"stage-ah", "configure-ah", "enable-ah"}:
        return configured(profile, action.removesuffix("-ah"))
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
