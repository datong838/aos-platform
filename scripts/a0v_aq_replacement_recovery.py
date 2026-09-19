#!/usr/bin/env python3
"""Create AQ as the formal direct replacement of detached AP."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-aq"
AQ_DIR = STATE / "aq"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AP_ID = "733a1366-c61d-4800-9310-4d5d8057ced7"
AP_GENERATION = "0640c5ce-f384-457c-94d2-3355faa39f46"
LOCK = "sha256:048a98bc7dca660c371b1f7cda9530ba73aa691b5f92d3f9f9b6b5b67868d56f"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AP_DISABLE_OPERATION = "feefe9f4-0dba-442f-a87a-e6b90509c583"
AP_DETACH_RECEIPT = "bef5442a-eb6d-43bd-b304-6a11ba8463ae"
AP_DETACH_HASH = "sha256:ff3ee5af04d0470b74891dcc8b664afa005358c8ded067ebfe9e6273e0120902"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-aq-20260919"
ACTIONS = ("preflight", "create-aq", "prepare-aq", "verify-aq", "stage-aq",
           "configure-aq", "enable-aq", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("v_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "aq":
            raise ValueError("only fixed AQ installation allowed")
        value = json.loads((AQ_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AQ installation required")
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


def detached_ap(profile) -> dict:
    snapshot = profile.observe_installation(AP_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AP_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AP_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AP replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AP_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AP_DISABLE_OPERATION,)).fetchall()]
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 101
            or row["cutover_group_revision"] != 128 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AP_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AP_DETACH_HASH):
        raise ValueError("exact AP detach Receipt required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_ap(profile)
    if AQ_DIR.exists():
        raise ValueError("AQ intent already exists; inspect without resending")
    return {"outcome": "AQ_REPLACEMENT_PREFLIGHT_GREEN", "ap": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_aq(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_ap(profile))
    if AQ_DIR.exists():
        raise ValueError("AQ intent/result exists; inspect without resending")
    AQ_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AQ_DIR)
    profile._freeze(AQ_DIR / "create-intent.json",
        {"label": "aq", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AQ replacement required")
    profile._freeze(AQ_DIR / "create-result.json", result)
    return {"outcome": "AQ_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-aq" if action == "prepare" else "prepare-aq")
    return profile.lifecycle("aq", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-aq", "configure": "stage-aq", "enable": "configure-aq"}[action]
    load(predecessor)
    return profile.configure("aq", action)


def observe(profile) -> dict:
    value = {"outcome": "AQ_REPLACEMENT_OBSERVED", "ap": profile.observe_installation(AP_ID)}
    if (AQ_DIR / "create-result.json").exists():
        value["aq"] = profile.observe_installation(profile._initial("aq")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AQ replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-aq":
        return create_aq(profile)
    if action in {"prepare-aq", "verify-aq"}:
        return lifecycle(profile, action.removesuffix("-aq"))
    if action in {"stage-aq", "configure-aq", "enable-aq"}:
        return configured(profile, action.removesuffix("-aq"))
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
