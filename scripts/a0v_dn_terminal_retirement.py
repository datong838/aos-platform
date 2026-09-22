#!/usr/bin/env python3
"""Retire DN's exact single failed terminal attempt through the formal disable Owner."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_dn_replacement_recovery as dn_replacement
import a0v_dn_successor_business as successor


retirement.STATE = successor.STATE.parent / "retire-dn"
retirement.AR_ID = successor.DN_ID
retirement.GENERATION = successor.DN_GENERATION
retirement.LOCK = successor.LOCK
retirement.FAILED_ATTEMPTS = (
    ("a2107628-439a-4aff-861a-cf80abd1df09", 4, "failed",
     "RECOVERABLE_EXECUTION_EXCEPTION", "IngressJournalConflict"),
)
retirement.PREFIX = "a0v-qyh-terminal-dn-retirement-20260922-v1"
retirement.DEFINITION_REVISION = 262
retirement.ACTIVE_ROUTE_REVISION = 321
retirement.ACTIVE_GROUP_REVISION = 348
retirement.DETACHED_ROUTE_REVISION = 323
retirement.DETACHED_GROUP_REVISION = 350
INSTALLATION_ETAG = 5


def setup():
    return successor.setup()


def profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = dn_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = dn_replacement.canonical.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = dn_replacement.canonical.CREDENTIALS
        return module

    value._load = load
    return value


def snapshot(phase: str, operation_id: str | None = None):
    """Same as AR released snapshot, but DN stock installation etag is 5."""
    import a0v_ar_released_retirement as ar
    if phase not in {"released", "accepted", "detached"}:
        raise ValueError("fixed DM retirement phase required")
    detached = phase == "detached"
    with ar.connect()() as conn:
        head = conn.execute("""SELECT i.installation_id::text,i.etag_version,r.state,r.lock_hash,r.overlay_revision
          FROM bundle_installation i JOIN bundle_installation_revision r
            ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
               (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
          (ar.AR_ID,)).fetchone()
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,desired_state,observed_state
          FROM extension_runtime_binding WHERE org_id='org-org' AND project_id='dev-project'
           AND installation_id=%s AND generation=%s""", (ar.AR_ID, ar.GENERATION)).fetchone()
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
           AND generation=%s""", (ar.GENERATION,)).fetchone())
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (ar.GROUP,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (ar.DEFINITION,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
            AND installation_id=%s AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary""", (ar.AR_ID, ar.GENERATION, ar.AR_ID)).fetchone())
        attempt_ids = [item[0] for item in ar.FAILED_ATTEMPTS]
        attempts = [dict(row) for row in conn.execute("""SELECT attempt_id::text,revision,state,
          terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s
            AND operation_kind='recoverable_store' ORDER BY accepted_at,attempt_id""",
          (ar.AR_ID, ar.GENERATION)).fetchall()]
        boundary = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s AND generation=%s
            AND attempt_id<>ALL(%s::uuid[])) unexpected_attempts,
          (SELECT count(*) FROM pipeline_snapshot_schedule_member
            WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s) members,
          (SELECT count(*) FROM meta_schedule_run r JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s
              AND r.status='running' AND r.executor_stopped IS FALSE AND r.finished_at IS NULL) saved_runs,
          (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d JOIN pipeline_snapshot_schedule_member m
            ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s) dataset_receipts,
          (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org'
            AND workspace_id='dev-project' AND idempotency_key=%s) store_receipts,
          (SELECT count(*) FROM ecom_link WHERE org_id='org-org' AND workspace_id='dev-project') store_links,
          (SELECT count(*) FROM projection_outbox WHERE org_id='org-org' AND workspace_id='dev-project'
            AND projected IS FALSE) projection_pending""",
          (ar.AR_ID, ar.GENERATION, attempt_ids, ar.SNAPSHOT_GROUP, ar.SNAPSHOT_GROUP,
           ar.SNAPSHOT_GROUP, ar.LINK_KEY)).fetchone())
        operation = None
        lifecycle = {"operations": 0, "receipts": 0, "phases": []}
        if operation_id is not None:
            operation = conn.execute("""SELECT operation_id::text,kind,status,phase,revision,
              expected_binding_revision FROM extension_runtime_operation WHERE org_id='org-org'
              AND project_id='dev-project' AND operation_id=%s""", (operation_id,)).fetchone()
            phases = [row["phase"] for row in conn.execute("""SELECT phase
              FROM extension_dispatch_lifecycle_receipt WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s ORDER BY created_at""", (operation_id,)).fetchall()]
            lifecycle = {"operations": conn.execute("""SELECT count(*) n
              FROM extension_dispatch_lifecycle_operation WHERE org_id='org-org' AND project_id='dev-project'
              AND runtime_operation_id=%s""", (operation_id,)).fetchone()["n"],
              "receipts": len(phases), "phases": phases}
    expected_attempts = [
        {"attempt_id": attempt_id, "revision": revision, "state": state,
         "terminal_reason_code": reason, "terminal_error_type": error}
        for attempt_id, revision, state, reason, error in ar.FAILED_ATTEMPTS
    ]
    expected_head = {"installation_id": ar.AR_ID, "etag_version": INSTALLATION_ETAG, "state": "active",
                     "lock_hash": ar.LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"}
    expected_runtime = ({"revision": 9, "execution_epoch": 5, "enabled": False,
                         "operation_fence": True, "desired_state": "disabled", "observed_state": "unknown"}
                        if detached else
                        {"revision": 7, "execution_epoch": 4, "enabled": False,
                         "operation_fence": True, "desired_state": "enabled", "observed_state": "unknown"})
    expected_safety = {"running": 0, "unresolved": 0,
                       "runtime_pending": 0 if phase != "accepted" else 1, "canary": 0}
    if (head is None or dict(head) != expected_head or runtime is None or dict(runtime) != expected_runtime
            or resources != {"total": 3, "released": 3}
            or len(routes) != 9 or definition is None
            or dict(definition) != {"revision": ar.DEFINITION_REVISION, "state": "disabled"}
            or safety != expected_safety or attempts != expected_attempts
            or boundary != {"unexpected_attempts": 0, "members": 12, "saved_runs": 12,
                            "dataset_receipts": 12, "store_receipts": 0,
                            "store_links": 0, "projection_pending": 0}):
        raise ValueError("exact released DN retirement authority differs")
    if detached:
        if any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
               or row["generation"] is not None or row["execution_epoch"] is not None
               or row["operation_fence"] is not True or row["revision"] != ar.DETACHED_ROUTE_REVISION
               or row["cutover_group_revision"] != ar.DETACHED_GROUP_REVISION for row in routes):
            raise ValueError("exact detached DN routes required")
    elif any(row["handler_kind"] != "extension" or row["installation_id"] != ar.AR_ID
             or row["generation"] != ar.GENERATION or row["execution_epoch"] != 3
             or row["operation_fence"] is not False or row["revision"] != ar.ACTIVE_ROUTE_REVISION
             or row["cutover_group_revision"] != ar.ACTIVE_GROUP_REVISION for row in routes):
        raise ValueError("exact attached DN routes required")
    if phase == "accepted" and (operation is None or operation["kind"] != "disable"
            or operation["status"] != "accepted" or operation["phase"] != "accepted"
            or operation["expected_binding_revision"] != 7
            or lifecycle != {"operations": 0, "receipts": 0, "phases": []}):
        raise ValueError("exact accepted DN disable required")
    if detached and (operation is None or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded"
            or lifecycle != {"operations": 1, "receipts": 2, "phases": ["fence", "detach"]}):
        raise ValueError("exact detached DN lifecycle required")
    return {"phase": phase, "runtime": dict(runtime), "resources": resources,
            "routeCount": 9, "groupRevision": ar.DETACHED_GROUP_REVISION if detached else ar.ACTIVE_GROUP_REVISION,
            "definition": dict(definition), "safety": safety,
            "attempts": attempts, "boundary": boundary,
            "operation": None if operation is None else dict(operation), "lifecycle": lifecycle}


def request_disable():
    import a0v_ar_released_retirement as ar
    from a0v_qyh_current_product_event_first_chain import freeze_or_match
    ar.load("preflight")
    snapshot("released")
    current = ar.profile()
    observed = current.observe_installation(ar.AR_ID)
    head = observed["head"]
    bindings = observed["bindings"]
    if (observed.get("canaryInstallations") != 0 or head["state"] != "active"
            or head["etag_version"] != INSTALLATION_ETAG or len(bindings) != 1):
        raise ValueError("one active released DN installation required")
    binding = bindings[0]
    if (binding["enabled"] is not False or binding["operation_fence"] is not True
            or binding["desired_state"] != "enabled" or binding["observed_state"] != "unknown"
            or not binding["config_ref"]):
        raise ValueError("exact released DN owner binding required")
    if not observed["resources"] or any(
            item["cleanup_state"] != "released" or item["observed_release"] is not True
            for item in observed["resources"]):
        raise ValueError("released DN owner resources required")
    if any(item["status"] not in {"succeeded", "failed", "cancelled"}
           for item in observed["operations"]):
        raise ValueError("released DN owner unresolved operation")
    command = {"etag": INSTALLATION_ETAG, "generation": str(binding["generation"]),
               "bindingRevision": binding["revision"]}
    intent = {"installationId": ar.AR_ID, **command,
              "idempotencyKey": ar.PREFIX + "-settle-released"}
    freeze_or_match(ar.STATE / "request-disable-intent.json", intent)
    activation, _store, _lifecycle, service, _dependent = current._setup_runtime_plane()
    receipt = service.request(**ar.SCOPE, installation_id=ar.AR_ID, actor=activation.ACTOR,
        roles=activation.ROLES, markings=activation.MARKINGS,
        idempotency_key=intent["idempotencyKey"], if_match=f'"{INSTALLATION_ETAG}"',
        target={"generation": ar.GENERATION, "bindingRevision": command["bindingRevision"]})
    operation_id = receipt.response_json["operationId"]
    return {"outcome": "AR_RELEASED_DISABLE_ACCEPTED", "operationId": operation_id,
            "receipt": receipt.response_json, "replayed": receipt.replayed,
            "state": snapshot("accepted", operation_id)}


retirement.setup = setup
retirement.profile = profile
retirement.snapshot = snapshot
retirement.request_disable = request_disable


def run(action: str) -> dict:
    result = retirement.run(action)
    outcome = result.get("outcome", "").replace("AR_RELEASED", "DN_TERMINAL").replace(
        "AR_NINE", "DN_NINE")
    return {**result, "outcome": outcome}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, indent=2, default=str))
