#!/usr/bin/env python3
"""Create AU as the formal direct replacement of detached AT."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT.parent / ".aos-recovery-20260919/state/q-advisor-baseline/replacement-au"
AU_DIR = STATE / "au"
BUNDLE_ROOT = ROOT.parent / ".aos-recovery-20260916/state/event-complete-package/registry/signed-bundles-event-complete"
AT_ID = "631e6d01-a5bb-4865-95eb-07d5665ed957"
AT_GENERATION = "63ea2c87-f185-4b02-b792-1e3073db4a1b"
LOCK = "sha256:03580e6e723938a9521bb1e0a08aa3c1da99ea4552737b65ac37ccd07389391f"
GROUP = "6a402d31-83ad-546c-807f-508c87498ce1"
AT_DISABLE_OPERATION = "5d69615c-2e9f-4ad5-8725-14a9e1fefd76"
AT_DETACH_RECEIPT = "3046e81b-fedb-4431-9493-ff79bc50820b"
AT_DETACH_HASH = "sha256:dc09ee0ceb07994f37641f6fa7b9a8f2caec0229faaf58028c00a6bb83297322"
VERSIONS = {"domain.ecommerce.core": "1.4.0", "platform.ecommerce.niushop": "1.23.0",
            "solution.ecommerce.growth": "1.10.0", "solution.ecommerce.operations-base": "1.2.0"}
PREFIX = "a0v-qyh-clean-au-20260919"
ACTIONS = ("preflight", "create-au", "prepare-au", "verify-au", "stage-au",
           "configure-au", "enable-au", "observe")


def load_profile():
    spec = importlib.util.spec_from_file_location("au_base_profile", ROOT / "scripts/a0v_ecommerce_current_reinstall.py")
    profile = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(profile)
    profile.STATE = STATE
    profile.BUNDLE_ROOT = BUNDLE_ROOT
    profile.VERSIONS = dict(VERSIONS)

    def initial(label: str):
        if label != "au":
            raise ValueError("only fixed AU installation allowed")
        value = json.loads((AU_DIR / "create-result.json").read_text(encoding="utf-8"))
        identity = value.get("installationId")
        try:
            canonical = str(UUID(identity)) if isinstance(identity, str) else None
        except ValueError:
            canonical = None
        if canonical != identity:
            raise ValueError("canonical AU installation required")
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


def detached_at(profile) -> dict:
    snapshot = profile.observe_installation(AT_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != AT_ID or head["state"] != "active"
            or head["etag_version"] != 5 or head["lock_hash"] != LOCK or len(bindings) != 1
            or str(bindings[0]["generation"]) != AT_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (8, 4)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached AT replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""", (GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (AT_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""", (AT_DISABLE_OPERATION,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state
          FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          ("cb0dba8c-803f-5caf-8011-b763d349f2ba",)).fetchone()
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True or row["revision"] != 113
            or row["cutover_group_revision"] != 140 for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or [row["phase"] for row in lifecycle] != ["fence", "detach"]
            or lifecycle[1]["receipt_id"] != AT_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != AT_DETACH_HASH
            or definition is None or dict(definition) != {"revision": 73, "state": "disabled"}):
        raise ValueError("exact AT detach Receipt and disabled definition required")
    return snapshot


def preflight(profile) -> dict:
    value = detached_at(profile)
    if AU_DIR.exists():
        raise ValueError("AU intent already exists; inspect without resending")
    return {"outcome": "AU_REPLACEMENT_PREFLIGHT_GREEN", "at": value,
            "versions": VERSIONS, "externalEffects": 0}


def create_au(profile) -> dict:
    load("preflight")
    predecessor = profile.replacement_ref(detached_at(profile))
    if AU_DIR.exists():
        raise ValueError("AU intent/result exists; inspect without resending")
    AU_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=AU_DIR)
    profile._freeze(AU_DIR / "create-intent.json",
        {"label": "au", "predecessor": predecessor, "versions": VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=VERSIONS["domain.ecommerce.core"],
        adapter_version=VERSIONS["platform.ecommerce.niushop"],
        growth_version=VERSIONS["solution.ecommerce.growth"],
        idempotency_prefix=PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved AU replacement required")
    profile._freeze(AU_DIR / "create-result.json", result)
    return {"outcome": "AU_REPLACEMENT_APPROVED", **result}


def lifecycle(profile, action: str) -> dict:
    load("create-au" if action == "prepare" else "prepare-au")
    return profile.lifecycle("au", action)


def configured(profile, action: str) -> dict:
    predecessor = {"stage": "verify-au", "configure": "stage-au", "enable": "configure-au"}[action]
    load(predecessor)
    return profile.configure("au", action)


def observe(profile) -> dict:
    value = {"outcome": "AU_REPLACEMENT_OBSERVED", "at": profile.observe_installation(AT_ID)}
    if (AU_DIR / "create-result.json").exists():
        value["au"] = profile.observe_installation(profile._initial("au")["installationId"])
    return value


def run(action: str):
    if action not in ACTIONS:
        raise ValueError("unsupported AU replacement action")
    profile = load_profile()
    if action == "preflight":
        return preflight(profile)
    if action == "create-au":
        return create_au(profile)
    if action in {"prepare-au", "verify-au"}:
        return lifecycle(profile, action.removesuffix("-au"))
    if action in {"stage-au", "configure-au", "enable-au"}:
        return configured(profile, action.removesuffix("-au"))
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
