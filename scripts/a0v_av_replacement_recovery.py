#!/usr/bin/env python3
"""Create AV as the formal direct replacement of detached AU."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-av"
AV_DIR = STATE / "av"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AU_ID = "eddc89f9-1e91-4e42-be4e-7d81dc941c1d"
AU_GENERATION = "01a5eb0a-f41f-40f7-ba00-b5db23a7806f"
LOCK = "sha256:6192980457e1ff735b57af6352f0e60f989f6d566830a2d690641dd5035fa60f"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AU_DISABLE_OPERATION = "51bdbc84-901f-448d-87e8-5a655790e0d3"
AU_DETACH_RECEIPT = "7e223943-906f-4efe-8d4b-da7fc2424e48"
AU_DETACH_HASH = "sha256:a3155cdf8c5fe13995faac9de8f6d8eedbf83609239303f09d9fcee8119bdfb1"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-av-20260919"
ACTIONS = ("preflight", "create-av", "prepare-av", "verify-av", "stage-av",
           "configure-av", "enable-av", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("au_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "av":
            raise ValueError("only fixed AV installation allowed")
        value = json.loads((AV_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AV installation required")
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


def detached_au(profile) -> dict:
    snapshot = profile.observe_installation(AU_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AU_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AU_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (9, 5)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AU replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AU_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AU_DISABLE_OPERATION,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state
          FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          ("cb0dba8c-803f-5caf-8011-b763d349f2ba",)).fetchone()
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 116
            or row["cutover_group_revision"] != 143 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AU_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AU_DETACH_HASH
            or definition is None or dict(definition) != {"revision": 73, "state": "disabled"}):
        raise ValueError("exact AU detach Receipt and disabled definition required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_au(profile)
    if AV_DIR.exists():
        raise ValueError("AV intent already exists; inspect without resending")
    return {"outcome": "AV_REPLACEMENT_PREFLIGHT_GREEN", "au": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_av(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_au(profile))
    if AV_DIR.exists():
        raise ValueError("AV intent/result exists; inspect without resending")
    AV_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AV_DIR)
    profile._freeze(AV_DIR / "create-intent.json",
        {"label": "av", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AV replacement required")
    profile._freeze(AV_DIR / "create-result.json", result)
    return {"outcome": "AV_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-av" if action == "prepare" else "prepare-av")
    return profile.lifecycle("av", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-av", "configure": "stage-av", "enable": "configure-av"}[action]
    load(predecessor)
    return profile.configure("av", action)


def observe(profile) -> dict:
    value = {"outcome": "AV_REPLACEMENT_OBSERVED", "au": profile.observe_installation(AU_ID)}
    if (AV_DIR / "create-result.json").exists():
        value["av"] = profile.observe_installation(profile._initial("av")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AV replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-av":
        return create_av(profile)
    if action in {"prepare-av", "verify-av"}:
        return lifecycle(profile, action.removesuffix("-av"))
    if action in {"stage-av", "configure-av", "enable-av"}:
        return configured(profile, action.removesuffix("-av"))
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
