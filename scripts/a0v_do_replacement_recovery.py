#!/usr/bin/env python3
"""Create DO directly from the exact detached DN authority."""
from __future__ import annotations

import argparse
import json

import a0v_dn_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-do"
replacement.AV_DIR = replacement.STATE / "do"
replacement.AU_ID = "2cb67f0a-0970-4d75-9c4a-a19d68563a3e"
replacement.AU_GENERATION = "e8b25248-98fc-475b-bf9e-1e7e3e803ec7"
replacement.LOCK = "sha256:ddc55f6f4f7b5ccb6729b983df4ec98895d99642fbdaf349e61cccf83c26e4a4"
replacement.AU_DISABLE_OPERATION = "0c5e0d6d-f22f-4490-9f57-45c7cb16922d"
replacement.AU_DETACH_RECEIPT = "35a465a7-ef65-479d-9534-9850a82044b6"
replacement.AU_DETACH_HASH = "sha256:8adfdd0dbe1bdb14c09649f1255f532fc7628bc6414c98ede5e5f2022f2e34a8"
replacement.PREFIX = "a0v-qyh-clean-do-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 323
replacement.PREDECESSOR_GROUP_REVISION = 350
replacement.DEFINITION_REVISION = 262
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "do"
PREDECESSOR_ETAG = 5


def detached_au(profile) -> dict:
    """DN stock predecessor: etag5 and three released leases after terminal retirement."""
    snapshot = profile.observe_installation(replacement.AU_ID)
    head, bindings = snapshot["head"], snapshot["bindings"]
    if (str(head["installation_id"]) != replacement.AU_ID or head["state"] != "active"
            or head["etag_version"] != PREDECESSOR_ETAG or head["lock_hash"] != replacement.LOCK
            or len(bindings) != 1
            or str(bindings[0]["generation"]) != replacement.AU_GENERATION
            or (bindings[0]["revision"], bindings[0]["execution_epoch"]) != (
                replacement.PREDECESSOR_BINDING_REVISION, replacement.PREDECESSOR_EXECUTION_EPOCH)
            or bindings[0]["enabled"] is not False or bindings[0]["operation_fence"] is not True
            or bindings[0]["desired_state"] != "disabled" or bindings[0]["observed_state"] != "unknown"
            or len(snapshot["resources"]) != 3
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached DN replacement predecessor required")
    from a0v_formal_text_model_renewal import database_connect
    with database_connect("aos_meta_head")() as conn:
        routes = conn.execute("""SELECT handler_kind,installation_id,generation,execution_epoch,
          operation_fence,revision,cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s""",
          (replacement.GROUP,)).fetchall()
        operation = conn.execute("""SELECT status,phase FROM extension_runtime_operation
          WHERE org_id='org-org' AND project_id='dev-project' AND operation_id=%s""",
          (replacement.AU_DISABLE_OPERATION,)).fetchone()
        lifecycle = [dict(row) for row in conn.execute("""SELECT receipt_id::text,phase,content_hash
          FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
          AND runtime_operation_id=%s ORDER BY created_at""",
          (replacement.AU_DISABLE_OPERATION,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state
          FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          ("cb0dba8c-803f-5caf-8011-b763d349f2ba",)).fetchone()
    if (len(routes) != 9 or any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
            or row["generation"] is not None or row["execution_epoch"] is not None
            or row["operation_fence"] is not True
            or row["revision"] != replacement.PREDECESSOR_ROUTE_REVISION
            or row["cutover_group_revision"] != replacement.PREDECESSOR_GROUP_REVISION
            for row in routes)
            or operation is None or dict(operation) != {"status": "succeeded", "phase": "succeeded"}
            or len(lifecycle) != 2
            or lifecycle[0]["phase"] != "fence" or lifecycle[1]["phase"] != "detach"
            or lifecycle[1]["receipt_id"] != replacement.AU_DETACH_RECEIPT
            or lifecycle[1]["content_hash"] != replacement.AU_DETACH_HASH
            or definition is None
            or dict(definition) != {"revision": replacement.DEFINITION_REVISION, "state": "disabled"}):
        raise ValueError("exact detached DN disable lifecycle required")
    return snapshot


def preflight(profile):
    value = detached_au(profile)
    if replacement.AV_DIR.exists():
        raise ValueError("DO intent already exists; inspect without resending")
    return {"outcome": "DO_REPLACEMENT_PREFLIGHT_GREEN", "au": value,
            "versions": replacement.VERSIONS, "externalEffects": 0}


def create_av(profile):
    """Same as AV create, but predecessor DN is etag5."""
    replacement.load("preflight")
    snap = detached_au(profile)
    head = snap["head"]
    bindings = snap["bindings"]
    if (snap.get("canaryInstallations") != 0 or head["state"] != "active"
            or head["etag_version"] != PREDECESSOR_ETAG or len(bindings) != 1):
        raise ValueError("active DN replacement predecessor required")
    binding = bindings[0]
    if (binding["enabled"] is not False or binding["operation_fence"] is not True
            or binding["desired_state"] != "disabled" or binding["observed_state"] != "unknown"):
        raise ValueError("drained DN replacement predecessor required")
    predecessor_ref = {
        "installationId": str(head["installation_id"]),
        "revision": head["etag_version"],
        "lockHash": head["lock_hash"],
        "overlayRevision": head["overlay_revision"],
    }
    if replacement.AV_DIR.exists():
        raise ValueError("DO intent/result exists; inspect without resending")
    replacement.AV_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=replacement.AV_DIR)
    profile._freeze(replacement.AV_DIR / "create-intent.json",
        {"label": "do", "predecessor": predecessor_ref, "versions": replacement.VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=replacement.VERSIONS["domain.ecommerce.core"],
        adapter_version=replacement.VERSIONS["platform.ecommerce.niushop"],
        growth_version=replacement.VERSIONS["solution.ecommerce.growth"],
        operations_version=replacement.VERSIONS["solution.ecommerce.operations-base"],
        idempotency_prefix=replacement.PREFIX, current_installation_ref=predecessor_ref)
    if result["installationState"] != "approved":
        raise ValueError("approved DO replacement required")
    profile._freeze(replacement.AV_DIR / "create-result.json", result)
    return {"outcome": "DO_REPLACEMENT_APPROVED", **result}


_original_run = replacement.run


def run(action: str) -> dict:
    profile = replacement.load_profile()
    if action == "preflight":
        value = preflight(profile)
    elif action == "create-av":
        value = create_av(profile)
    else:
        value = _original_run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DO_").replace("DN_", "DO_").replace("DM_", "DO_")}


replacement.detached_au = detached_au
replacement.preflight = preflight


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=replacement.ACTIONS)
    args = parser.parse_args()
    output = replacement.STATE / f"{args.action}-result.json"
    if output.exists():
        raise ValueError(f"immutable {args.action} output exists")
    result = run(args.action)
    replacement.freeze(output, result)
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
