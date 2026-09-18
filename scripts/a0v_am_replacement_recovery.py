#!/usr/bin/env python3
"""Create AM as the formal direct replacement of detached AL."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260918/state/q-advisor-baseline/replacement-am"
AM_DIR = STATE / "am"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AL_ID = "071e1c31-c464-4735-952e-17adf0ac97f7"
AL_GENERATION = "d50a7eed-18e1-491a-9323-ab3ca693dc3a"
LOCK = "sha256:49d7d8b367e19f3c7f8c920d061757477af9a0bf6bc3847101ca7ce348006608"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AL_DISABLE_OPERATION = "c9328938-3b56-4a8d-ac38-54f7abf70416"
AL_DETACH_RECEIPT = "bd92aa48-77b6-4c34-82f9-0ede171083b3"
AL_DETACH_HASH = "sha256:b8990ed467aed1bdfc40e5fb56e4455e2ece7114045f37a15f8f4099a313e1df"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-am-20260918"
ACTIONS = ("preflight", "create-am", "prepare-am", "verify-am", "stage-am",
           "configure-am", "enable-am", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "am":
            raise ValueError("only fixed AM installation allowed")
        value = json.loads((AM_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AM installation required")
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


def detached_al(profile) -> dict:
    snapshot = profile.observe_installation(AL_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AL_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AL_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AL replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AL_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AL_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 89
            or row["cutover_group_revision"] != 116 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AL_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AL_DETACH_HASH):
        raise ValueError("exact AL detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_al(profile)
    if AM_DIR.exists():
        raise ValueError("AM intent already exists; inspect without resending")
    return {"outcome": "AM_REPLACEMENT_PREFLIGHT_GREEN", "al": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_am(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_al(profile))
    if AM_DIR.exists():
        raise ValueError("AM intent/result exists; inspect without resending")
    AM_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AM_DIR)
    profile._freeze(AM_DIR / "create-intent.json",
        {"label": "am", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AM replacement required")
    profile._freeze(AM_DIR / "create-result.json", result)
    return {"outcome": "AM_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-am" if action == "prepare" else "prepare-am")
    return profile.lifecycle("am", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-am", "configure": "stage-am", "enable": "configure-am"}[action]
    load(predecessor)
    return profile.configure("am", action)


def observe(profile) -> dict:
    value = {"outcome": "AM_REPLACEMENT_OBSERVED", "al": profile.observe_installation(AL_ID)}
    if (AM_DIR / "create-result.json").exists():
        value["am"] = profile.observe_installation(profile._initial("am")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AM replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-am":
        return create_am(profile)
    if action in {"prepare-am", "verify-am"}:
        return lifecycle(profile, action.removesuffix("-am"))
    if action in {"stage-am", "configure-am", "enable-am"}:
        return configured(profile, action.removesuffix("-am"))
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
