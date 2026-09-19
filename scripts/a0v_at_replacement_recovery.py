#!/usr/bin/env python3
"""Create AT as the formal direct replacement of detached AS."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-at"
AT_DIR = STATE / "at"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AS_ID = "5d0a6d5a-4024-430f-831b-2af15b5ca889"
AS_GENERATION = "4cc2dc84-a452-4bac-aa56-0b1519a9826a"
LOCK = "sha256:cc6a1e994ef880b04dfca9536910287a3ed63f6a4069c1f80c09a7565612b799"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AS_DISABLE_OPERATION = "410d2bcd-3c56-4ea5-af0f-e599a08bc1ba"
AS_DETACH_RECEIPT = "ae435475-8932-444b-ab41-9660fb966eaf"
AS_DETACH_HASH = "sha256:e8d53430e6a52ea3d287d373dc48cd47b7052cffca6c89c531cb8990434d666b"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-at-20260919"
ACTIONS = ("preflight", "create-at", "prepare-at", "verify-at", "stage-at",
           "configure-at", "enable-at", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "at":
            raise ValueError("only fixed AT installation allowed")
        value = json.loads((AT_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AT installation required")
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


def detached_as(profile) -> dict:
    snapshot = profile.observe_installation(AS_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AS_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AS_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AS replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AS_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AS_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 110
            or row["cutover_group_revision"] != 137 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AS_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AS_DETACH_HASH):
        raise ValueError("exact AS detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_as(profile)
    if AT_DIR.exists():
        raise ValueError("AT intent already exists; inspect without resending")
    return {"outcome": "AT_REPLACEMENT_PREFLIGHT_GREEN", "as": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_at(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_as(profile))
    if AT_DIR.exists():
        raise ValueError("AT intent/result exists; inspect without resending")
    AT_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AT_DIR)
    profile._freeze(AT_DIR / "create-intent.json",
        {"label": "at", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AT replacement required")
    profile._freeze(AT_DIR / "create-result.json", result)
    return {"outcome": "AT_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-at" if action == "prepare" else "prepare-at")
    return profile.lifecycle("at", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-at", "configure": "stage-at", "enable": "configure-at"}[action]
    load(predecessor)
    return profile.configure("at", action)


def observe(profile) -> dict:
    value = {"outcome": "AT_REPLACEMENT_OBSERVED", "as": profile.observe_installation(AS_ID)}
    if (AT_DIR / "create-result.json").exists():
        value["at"] = profile.observe_installation(profile._initial("at")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AT replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-at":
        return create_at(profile)
    if action in {"prepare-at", "verify-at"}:
        return lifecycle(profile, action.removesuffix("-at"))
    if action in {"stage-at", "configure-at", "enable-at"}:
        return configured(profile, action.removesuffix("-at"))
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
