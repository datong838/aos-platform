#!/usr/bin/env python3
"""Create AJ as the formal direct replacement of detached AI."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260918/state/q-advisor-baseline/replacement-aj"
AJ_DIR = STATE / "aj"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AI_ID = "59d91f1c-efd7-4097-8ce0-1d4fa9452c0f"
AI_GENERATION = "3512c4da-841c-4bd6-a711-343c163b0632"
LOCK = "sha256:4873953acc7c69863fc034dd57b3c681eb67e05c5be2090abd913365d73daada"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AI_DISABLE_OPERATION = "127bd9f1-efbf-435c-b40d-de8dba61b8a9"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-aj-20260918"
ACTIONS = ("preflight", "create-aj", "prepare-aj", "verify-aj", "stage-aj",
           "configure-aj", "enable-aj", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "aj":
            raise ValueError("only fixed AJ installation allowed")
        value = json.loads((AJ_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AJ installation required")
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


def detached_ai(profile) -> dict:
    snapshot = profile.observe_installation(AI_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AI_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AI_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AI replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AI_DISABLE_OPERATION,)).fetchone()
        phases = [row["phase"] for row in conn.execute("""SELECT phase
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AI_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 80
            or row["cutover_group_revision"] != 107 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or phases != ["fence", "detach"]):
        raise ValueError("exact AI detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_ai(profile)
    if AJ_DIR.exists():
        raise ValueError("AJ intent already exists; inspect without resending")
    return {"outcome": "AJ_REPLACEMENT_PREFLIGHT_GREEN", "ai": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_aj(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_ai(profile))
    if AJ_DIR.exists():
        raise ValueError("AJ intent/result exists; inspect without resending")
    AJ_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AJ_DIR)
    profile._freeze(AJ_DIR / "create-intent.json",
        {"label": "aj", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AJ replacement required")
    profile._freeze(AJ_DIR / "create-result.json", result)
    return {"outcome": "AJ_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-aj" if action == "prepare" else "prepare-aj")
    return profile.lifecycle("aj", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-aj", "configure": "stage-aj", "enable": "configure-aj"}[action]
    load(predecessor)
    return profile.configure("aj", action)


def observe(profile) -> dict:
    value = {"outcome": "AJ_REPLACEMENT_OBSERVED", "ai": profile.observe_installation(AI_ID)}
    if (AJ_DIR / "create-result.json").exists():
        value["aj"] = profile.observe_installation(profile._initial("aj")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AJ replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-aj":
        return create_aj(profile)
    if action in {"prepare-aj", "verify-aj"}:
        return lifecycle(profile, action.removesuffix("-aj"))
    if action in {"stage-aj", "configure-aj", "enable-aj"}:
        return configured(profile, action.removesuffix("-aj"))
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
