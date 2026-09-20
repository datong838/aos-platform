#!/usr/bin/env python3
"""Detach released BN through the formal disable Owner; never revive released resources."""
from __future__ import annotations

import argparse
import json

import a0v_ar_released_retirement as retirement
import a0v_bn_replacement_recovery as bn_replacement
import a0v_bn_successor_business as bn_successor


retirement.STATE = bn_replacement.replacement.STATE / "retire-bn"
retirement.AR_ID = bn_successor.BN_ID
retirement.GENERATION = bn_successor.BN_GENERATION
retirement.LOCK = bn_successor.LOCK
retirement.FAILED_ATTEMPTS = ()
retirement.PREFIX = "a0v-qyh-released-bn-retirement-20260920-v1"


def _profile():
    import a0v_ecommerce_current_reinstall as value
    value.BUNDLE_ROOT = bn_replacement.replacement.BUNDLE_ROOT
    value.TRUST_STATE = bn_replacement.TRUST_STATE
    original_load = value._load

    def load(name: str):
        module = original_load(name)
        if name == "a0v_ecommerce_runtime_host":
            module.DEFAULT_CREDENTIALS = bn_replacement.CREDENTIALS
        return module

    value._load = load
    return value


def _setup():
    return bn_successor.setup()


retirement.profile = _profile
retirement.setup = _setup


def snapshot(phase: str, operation_id: str | None = None) -> dict:
    if phase not in {"released", "accepted", "detached"}:
        raise ValueError("fixed BN retirement phase required")
    detached = phase == "detached"
    with retirement.connect()() as conn:
        head = conn.execute("""SELECT i.installation_id::text,i.etag_version,r.state,r.lock_hash,r.overlay_revision
          FROM bundle_installation i JOIN bundle_installation_revision r
            ON (r.org_id,r.project_id,r.installation_pk,r.revision)=
               (i.org_id,i.project_id,i.installation_pk,i.current_revision)
          WHERE i.org_id='org-org' AND i.project_id='dev-project' AND i.installation_id=%s""",
          (retirement.AR_ID,)).fetchone()
        runtime = conn.execute("""SELECT revision,execution_epoch,enabled,operation_fence,
          desired_state,observed_state FROM extension_runtime_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s""",
          (retirement.AR_ID, retirement.GENERATION)).fetchone()
        resources = dict(conn.execute("""SELECT count(*) total,count(*) FILTER
          (WHERE cleanup_state='released' AND observed_release) released
          FROM extension_runtime_resource_lease WHERE org_id='org-org' AND project_id='dev-project'
          AND generation=%s""", (retirement.GENERATION,)).fetchone())
        routes = [dict(row) for row in conn.execute("""SELECT operation_id,handler_kind,
          installation_id::text,generation::text,execution_epoch,operation_fence,revision,
          cutover_group_revision FROM extension_operation_dispatch_binding
          WHERE org_id='org-org' AND project_id='dev-project' AND cutover_group_id=%s
          ORDER BY operation_id""", (retirement.GROUP,)).fetchall()]
        definition = conn.execute("""SELECT h.revision,r.state FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id='org-org' AND h.project_id='dev-project' AND h.definition_id=%s""",
          (retirement.DEFINITION,)).fetchone()
        safety = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND state='running') running,
          (SELECT count(*) FROM automation_occurrence_dispatch_attempt a JOIN automation_occurrence o
            USING(org_id,project_id,occurrence_id) WHERE a.org_id='org-org' AND a.project_id='dev-project'
            AND o.installation_id=%s AND o.generation=%s AND a.status IN ('claimed','unknown')) unresolved,
          (SELECT count(*) FROM extension_runtime_operation WHERE org_id='org-org' AND project_id='dev-project'
            AND installation_id=%s AND status NOT IN ('succeeded','failed','cancelled')) runtime_pending,
          (SELECT count(*) FROM extension_operation_dispatch_binding WHERE org_id='dev-org'
            AND project_id='dev-project') canary""",
          (retirement.AR_ID, retirement.GENERATION, retirement.AR_ID)).fetchone())
        boundary = dict(conn.execute("""SELECT
          (SELECT count(*) FROM extension_runtime_execution_attempt WHERE org_id='org-org'
            AND project_id='dev-project' AND installation_id=%s AND generation=%s) attempts,
          (SELECT count(*) FROM pipeline_snapshot_schedule_member WHERE org_id='org-org'
            AND project_id='dev-project' AND group_id=%s) members,
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
          (retirement.AR_ID, retirement.GENERATION, retirement.SNAPSHOT_GROUP,
           retirement.SNAPSHOT_GROUP, retirement.SNAPSHOT_GROUP, retirement.LINK_KEY)).fetchone())
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
    expected_head = {"installation_id": retirement.AR_ID, "etag_version": 5, "state": "active",
                     "lock_hash": retirement.LOCK, "overlay_revision": "a0v-canonical-ecommerce-v1"}
    expected_runtime = ({"revision": 9, "execution_epoch": 5, "enabled": False,
        "operation_fence": True, "desired_state": "disabled", "observed_state": "unknown"}
        if detached else {"revision": 7, "execution_epoch": 4, "enabled": False,
        "operation_fence": True, "desired_state": "enabled", "observed_state": "unknown"})
    expected_safety = {"running": 0, "unresolved": 0,
                       "runtime_pending": 1 if phase == "accepted" else 0, "canary": 0}
    expected_boundary = {"attempts": 0, "members": 12, "saved_runs": 12,
        "dataset_receipts": 12, "store_receipts": 0, "store_links": 0, "projection_pending": 0}
    if (head is None or dict(head) != expected_head or runtime is None or dict(runtime) != expected_runtime
            or resources != {"total": 3, "released": 3} or len(routes) != 9
            or definition is None or dict(definition) != {"revision": 118, "state": "disabled"}
            or safety != expected_safety or boundary != expected_boundary):
        raise ValueError("exact released BN retirement authority differs")
    if detached:
        if any(row["handler_kind"] != "legacy" or row["installation_id"] is not None
               or row["generation"] is not None or row["execution_epoch"] is not None
               or row["operation_fence"] is not True or row["revision"] != 167
               or row["cutover_group_revision"] != 194 for row in routes):
            raise ValueError("exact detached BN routes required")
    elif any(row["handler_kind"] != "extension" or row["installation_id"] != retirement.AR_ID
             or row["generation"] != retirement.GENERATION or row["execution_epoch"] != 3
             or row["operation_fence"] is not False or row["revision"] != 165
             or row["cutover_group_revision"] != 192 for row in routes):
        raise ValueError("exact attached BN routes required")
    if phase == "accepted" and (operation is None or operation["kind"] != "disable"
            or operation["status"] != "accepted" or operation["phase"] != "accepted"
            or operation["expected_binding_revision"] != 7
            or lifecycle != {"operations": 0, "receipts": 0, "phases": []}):
        raise ValueError("exact accepted BN disable required")
    if detached and (operation is None or operation["status"] != "succeeded"
            or operation["phase"] != "succeeded"
            or lifecycle != {"operations": 1, "receipts": 2, "phases": ["fence", "detach"]}):
        raise ValueError("exact detached BN lifecycle required")
    return {"phase": phase, "runtime": dict(runtime), "resources": resources,
            "routeCount": 9, "groupRevision": 194 if detached else 192,
            "definition": dict(definition), "safety": safety, "attempts": [],
            "boundary": boundary, "operation": None if operation is None else dict(operation),
            "lifecycle": lifecycle}


retirement.snapshot = snapshot


def process_disable() -> dict:
    operation_id = retirement.load("request-disable")["operationId"]
    completed = snapshot("detached", operation_id)
    intent = json.loads((retirement.STATE / "process-disable-intent.json").read_text(encoding="utf-8"))
    if (intent.get("operationId") != operation_id or intent.get("resendDisable") is not False
            or not isinstance(intent.get("eventId"), str)):
        raise ValueError("exact BN committed disable intent required")
    return {"outcome": "BN_NINE_ROUTES_DETACHED", "operationId": operation_id,
            "claimedByHost": False, "resendDisable": False, "recoveredAfterCommit": True,
            "eventId": intent["eventId"], "state": completed}


def audit() -> dict:
    operation_id = retirement.load("process-disable")["operationId"]
    return {"outcome": "BN_RELEASED_RETIREMENT_GREEN",
            "state": snapshot("detached", operation_id), "externalEffects": 0}


retirement.process_disable = process_disable
retirement.audit = audit


def run(action: str) -> dict:
    _setup()
    result = retirement.run(action)
    return json.loads(json.dumps(result, default=str).replace("AR_", "BN_"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=retirement.ACTIONS)
    args = parser.parse_args()
    print(json.dumps(run(args.action), ensure_ascii=False, default=str, indent=2))
