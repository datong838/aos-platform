#!/usr/bin/env python3
"""Create DM directly from the exact detached DL authority."""
from __future__ import annotations

import argparse
import json

import a0v_dl_replacement_recovery as predecessor


canonical = predecessor.canonical
replacement = predecessor.replacement
replacement.STATE = canonical.BASE / "replacement-dm"
replacement.AV_DIR = replacement.STATE / "dm"
replacement.AU_ID = "83453fb3-8c39-422c-845b-e152551e0a30"
replacement.AU_GENERATION = "f3a1f381-5aeb-4494-a155-164e0ef9e0f5"
replacement.LOCK = "sha256:b2985931a11c73d1b6dd1a0b0befd93f8b9f18f5ec2017c486ffc0db63e080dc"
replacement.AU_DISABLE_OPERATION = "71083a3f-9594-4f6a-9467-8095ac05630e"
replacement.AU_DETACH_RECEIPT = "dac9f81b-dca8-4d1b-b82c-1d561d9dafb8"
replacement.AU_DETACH_HASH = "sha256:75fb102aba48b8f999b8b8b241f49dfd6b0b8544f05b1cfeecc0d177e5ba6b19"
replacement.PREFIX = "a0v-qyh-clean-dm-20260922"
replacement.PREDECESSOR_ROUTE_REVISION = 317
replacement.PREDECESSOR_GROUP_REVISION = 344
replacement.DEFINITION_REVISION = 256
replacement.PREDECESSOR_BINDING_REVISION = 9
replacement.PREDECESSOR_EXECUTION_EPOCH = 5
replacement.INSTALLATION_LABEL = "dm"
PREDECESSOR_ETAG = 7


def detached_au(profile) -> dict:
    """DL post-reset predecessor: etag7 and six released leases (old+new prepare)."""
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
            or len(snapshot["resources"]) != 6
            or any(row["cleanup_state"] != "released" or row["observed_release"] is not True
                   for row in snapshot["resources"])
            or any(row["status"] not in {"succeeded", "failed", "cancelled"}
                   for row in snapshot["operations"])
            or snapshot["canaryInstallations"] != 0):
        raise ValueError("exact detached DL replacement predecessor required")
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
        raise ValueError("exact detached DL disable lifecycle required")
    return snapshot


def preflight(profile):
    value = detached_au(profile)
    if replacement.AV_DIR.exists():
        raise ValueError("DM intent already exists; inspect without resending")
    return {"outcome": "DM_REPLACEMENT_PREFLIGHT_GREEN", "au": value,
            "versions": replacement.VERSIONS, "externalEffects": 0}


replacement.detached_au = detached_au
replacement.preflight = preflight


def create_av(profile):
    """Same as AV create, but predecessor DL is etag7."""
    replacement.load("preflight")
    snap = detached_au(profile)
    head = snap["head"]
    bindings = snap["bindings"]
    if (snap.get("canaryInstallations") != 0 or head["state"] != "active"
            or head["etag_version"] != PREDECESSOR_ETAG or len(bindings) != 1):
        raise ValueError("active DL replacement predecessor required")
    binding = bindings[0]
    if (binding["enabled"] is not False or binding["operation_fence"] is not True
            or binding["desired_state"] != "disabled" or binding["observed_state"] != "unknown"):
        raise ValueError("drained DL replacement predecessor required")
    predecessor = {
        "installationId": str(head["installation_id"]),
        "revision": head["etag_version"],
        "lockHash": head["lock_hash"],
        "overlayRevision": head["overlay_revision"],
    }
    if replacement.AV_DIR.exists():
        raise ValueError("DM intent/result exists; inspect without resending")
    replacement.AV_DIR.mkdir(parents=True, exist_ok=False, mode=0o700)
    helper = profile._load("a0v_ecommerce_growth_1_5_registry_successor")
    installer = profile._load("a0v_canonical_ecommerce_first_install")
    backup = helper._database_backup(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, state_dir=replacement.AV_DIR)
    profile._freeze(replacement.AV_DIR / "create-intent.json",
        {"label": "dm", "predecessor": predecessor, "versions": replacement.VERSIONS, "backup": backup})
    connect = installer.container_database_connect_factory(context=helper.DOCKER_CONTEXT,
        container=helper.DATABASE_CONTAINER, database_name=helper.DATABASE_NAME)
    result = installer.create_approved_first_installation(connect_factory=connect,
        state_dir=profile.TRUST_STATE, core_version=replacement.VERSIONS["domain.ecommerce.core"],
        adapter_version=replacement.VERSIONS["platform.ecommerce.niushop"],
        growth_version=replacement.VERSIONS["solution.ecommerce.growth"],
        operations_version=replacement.VERSIONS["solution.ecommerce.operations-base"],
        idempotency_prefix=replacement.PREFIX, current_installation_ref=predecessor)
    if result["installationState"] != "approved":
        raise ValueError("approved DM replacement required")
    profile._freeze(replacement.AV_DIR / "create-result.json", result)
    return {"outcome": "DM_REPLACEMENT_APPROVED", **result}


_original_run = replacement.run
PREPARE_AFTER_FAILED_KEY = "a0v-current-ecommerce-dm-prepare-after-failed-20260922"
PREPARE_AFTER_RESET_KEY = "a0v-current-ecommerce-dm-prepare-after-reset-20260922"


def prepare_after_reset(profile) -> dict:
    """Re-prepare approved@etag5 DM after unbound applied reset (Host loss)."""
    installation_id = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
    snapshot = profile.observe_installation(installation_id)
    head = snapshot["head"]
    if (head["state"], head["etag_version"], snapshot.get("bindings")) != ("approved", 5, []):
        raise ValueError("approved DM@etag5 without binding required after reset")
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    ops = snapshot.get("operations") or []
    if not any(o.get("kind") == "runtime-verify" and o.get("failure_code") == "PREPARATION_OWNER_LOST"
               for o in ops):
        raise ValueError("exact PREPARATION_OWNER_LOST verify required before after-reset prepare")
    if any(row.get("cleanup_state") != "released" or row.get("observed_release") is not True
           for row in snapshot.get("resources") or []):
        raise ValueError("all DM resources must be released before after-reset prepare")
    command = {"etag": 5, "kind": "runtime-apply"}
    intent = replacement.AV_DIR / "prepare-intent.json"
    if intent.exists() or (replacement.STATE / "prepare-av-result.json").exists():
        raise ValueError("DM prepare after-reset intent/result exists; inspect without resending")
    profile._freeze(intent, {"installationId": installation_id, **command,
                             "idempotencyKey": PREPARE_AFTER_RESET_KEY,
                             "afterReset": True})
    activation, _store, service, _disable, _dependent = profile._setup_runtime_plane()
    receipt = service.request_preparation(
        **profile.SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=PREPARE_AFTER_RESET_KEY,
        if_match='"5"',
        kind=command["kind"],
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed,
            "outcome": "DM_PREPARE_AFTER_RESET_ACCEPTED"}


def prepare_after_failed(profile) -> dict:
    """Re-prepare approved DM after settled failed prepare; new idempotency key only."""
    installation_id = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
    snapshot = profile.observe_installation(installation_id)
    command = profile.require_phase("prepare", snapshot)
    ops = snapshot.get("operations") or []
    if (len(ops) != 1 or ops[0]["kind"] != "runtime-apply" or ops[0]["status"] != "failed"
            or ops[0]["phase"] != "preparing"
            or str(ops[0]["operation_id"]) != "ec7a706f-d592-4139-9b54-67073fab064d"):
        raise ValueError("exact settled failed DM prepare required before retry")
    if any(row.get("cleanup_state") != "released" or row.get("observed_release") is not True
           for row in snapshot.get("resources") or []):
        raise ValueError("all DM prepare resources must be released before retry")
    intent = replacement.AV_DIR / "prepare-intent.json"
    if intent.exists() or (replacement.STATE / "prepare-av-result.json").exists():
        raise ValueError("DM prepare retry intent/result exists; inspect without resending")
    profile._freeze(intent, {"installationId": installation_id, **command,
                             "idempotencyKey": PREPARE_AFTER_FAILED_KEY,
                             "afterFailedOperation": "ec7a706f-d592-4139-9b54-67073fab064d"})
    activation, _store, service, _disable, _dependent = profile._setup_runtime_plane()
    receipt = service.request_preparation(
        **profile.SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=PREPARE_AFTER_FAILED_KEY,
        if_match=f'"{command["etag"]}"',
        kind=command["kind"],
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed,
            "outcome": "DM_PREPARE_AFTER_FAILED_ACCEPTED"}


def verify_after_reset(profile) -> dict:
    """Verify applied DM after after-reset prepare (etag is not the stock @4)."""
    installation_id = "5103c27a-753e-4cad-85cb-9fa35dc0574d"
    snapshot = profile.observe_installation(installation_id)
    head = snapshot["head"]
    if head["state"] != "applied" or snapshot.get("bindings") not in ([], None):
        raise ValueError("applied DM without binding required for verify")
    if snapshot.get("canaryInstallations") != 0:
        raise ValueError("canary installation drift")
    etag = head["etag_version"]
    if type(etag) is not int or etag < 4:
        raise ValueError("applied DM etag required")
    command = {"etag": etag, "kind": "runtime-verify"}
    intent = replacement.AV_DIR / "verify-intent.json"
    if intent.exists() or (replacement.STATE / "verify-av-result.json").exists():
        raise ValueError("DM verify intent/result exists; inspect without resending")
    profile._freeze(intent, {"installationId": installation_id, **command})
    activation, _store, service, _disable, _dependent = profile._setup_runtime_plane()
    receipt = service.request_preparation(
        **profile.SCOPE,
        installation_id=installation_id,
        actor=activation.ACTOR,
        roles=activation.ROLES,
        markings=activation.MARKINGS,
        idempotency_key=f"a0v-current-ecommerce-dm-verify-after-reset-r{etag}-20260922",
        if_match=f'"{etag}"',
        kind=command["kind"],
    )
    return {"command": command, "receipt": receipt.response_json, "replayed": receipt.replayed,
            "outcome": "DM_VERIFY_AFTER_RESET_ACCEPTED"}


def run(action: str) -> dict:
    profile = replacement.load_profile()
    if action == "preflight":
        value = preflight(profile)
    elif action == "create-av":
        value = create_av(profile)
    elif action == "prepare-av":
        snap = profile.observe_installation("5103c27a-753e-4cad-85cb-9fa35dc0574d")
        head = snap.get("head") or {}
        ops = snap.get("operations") or []
        if head.get("state") == "approved" and head.get("etag_version") == 5:
            value = prepare_after_reset(profile)
        elif (len(ops) == 1 and ops[0].get("status") == "failed"
                and str(ops[0].get("operation_id")) == "ec7a706f-d592-4139-9b54-67073fab064d"):
            value = prepare_after_failed(profile)
        else:
            value = _original_run(action)
    elif action == "verify-av":
        snap = profile.observe_installation("5103c27a-753e-4cad-85cb-9fa35dc0574d")
        head = snap.get("head") or {}
        if head.get("state") == "applied" and head.get("etag_version") != 4:
            value = verify_after_reset(profile)
        else:
            value = _original_run(action)
    else:
        value = _original_run(action)
    return {**value, "outcome": value.get("outcome", "").replace("AV_", "DM_").replace("DL_", "DM_")}


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
