#!/usr/bin/env python3
"""Independent, read-only DB audit of one stalled closure; never applies it."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4t_closure_feasibility as frozen
from aos_api.asset_registry.canonical_json import canonical_sha256


REASON = "STALLED_EXECUTOR_ABANDONED_WITH_EFFECTS"
EFFECT_KEYS = {"groupClaims": "groupClaimCount", "groupInputs": "groupInputCount",
               "groupMembers": "groupMemberCount", "sourceClaims": "sourceClaimCount",
               "ingressCommands": "ingressCommandCount",
               "derivedCommands": "derivedCommandCount",
               "datasetReceipts": "datasetReceiptCount"}


def _frozen(reason):
    return {"outcome": "FROZEN_INDEPENDENT_CLOSURE_AUDIT", "reason": reason,
            "automaticAction": False}


def classify(value):
    """A Receipt and every terminal Run must agree; absence is not success."""
    try:
        if (value["head"] != {"revision": 4, "state": "disabled",
                              "content_hash": frozen.HASH}
                or [{key: claim[key] for key in ("group_id", "trigger", "scheduled_for")}
                    for claim in value["claims"]] != [
                    {"group_id": frozen.GROUP, "trigger": "cron",
                     "scheduled_for": "2026-09-24 20:00:00+00:00"}]
                or value["attempts"] != [{"attempt_id": frozen.ATTEMPT,
                   "state": "failed", "terminal_reason_code": "RECOVERABLE_EXECUTION_EXCEPTION",
                   "terminal_error_type": "PermissionError"}]
                or value["effects"] != frozen.EFFECTS
                or value["facts"] != {**frozen.FACTS, "stalledReceipts": value["receiptCount"]}
                or value["runs"]["n"] != 12 or value["receiptCount"] not in (0, 1)):
            return _frozen("GROUP_OR_BUSINESS_BOUNDARY_DRIFT")
        if value["receiptCount"] == 0:
            if value["receipt"] is not None or value["runs"] != {
                    "n": 12, "running": 12, "closed": 0, "schedulesEnabled": 0}:
                return _frozen("NO_RECEIPT_BUT_RUN_STATE_DIFFERS")
            return {"outcome": "NOT_YET_CLOSED", "automaticAction": False,
                    "runningRuns": 12, "closureReceipts": 0}
        receipt = value["receipt"]
        if value["runs"] != {"n": 12, "running": 0, "closed": 12,
                             "schedulesEnabled": 0} or type(receipt) is not dict:
            return _frozen("PARTIAL_TERMINAL_OR_RECEIPT")
        body = receipt["authority_data"]
        request = body["request"]
        evidence = body["effectEvidence"]
        if (receipt["content_hash"] != canonical_sha256(body)
                or receipt["request_hash"] != canonical_sha256(request)
                or body["requestHash"] != receipt["request_hash"]
                or body["receiptId"] != receipt["receipt_id"]
                or body["actor"] != receipt["actor"]
                or body["businessAccepted"] is not False
                or body["schemaVersion"] != "aos.pipeline-snapshot.stalled-group-closure-receipt/v1"
                or body["tenant"] != {"orgId": "org-org", "projectId": "dev-project"}
                or body["priorScheduleClaim"] != value["claims"][0]["record"]
                or request["schemaVersion"] != "aos.pipeline-snapshot.stalled-group-closure/v1"
                or request["groupId"] != frozen.GROUP
                or request["reasonCode"] != REASON
                or request["idempotencyKey"] != receipt["idempotency_key"]
                or request["originalDefinitionRef"] !=
                   value["claims"][0]["request"]["definitionRef"]
                or request["currentDisabledDefinitionRef"] != {
                    "resourceType": "SnapshotScheduleDefinitionRevision",
                    "resourceId": "snapshot-schedule-" + frozen.DEFINITION,
                    "revision": 4, "contentHash": frozen.HASH}
                or body["runEvidence"]["memberCount"] != 12
                or body["runEvidence"]["stalledRunCount"] != 12
                or body["runEvidence"]["staleOver24hCount"] != 12
                or any(evidence.get(wire) != value["effects"][key]
                       for key, wire in EFFECT_KEYS.items())):
            return _frozen("RECEIPT_CONTENT_OR_EFFECTS_DIFFERS")
        return {"outcome": "INDEPENDENT_STALLED_CLOSURE_AUDIT_GREEN",
                "automaticAction": False, "businessAccepted": False,
                "closedRuns": 12, "closureReceipts": 1,
                "receiptId": receipt["receipt_id"],
                "contentHash": receipt["content_hash"]}
    except (KeyError, TypeError, ValueError, OverflowError):
        return _frozen("INCOMPLETE_AUDIT_FACTS")


def observe():
    """One repeatable-read transaction; counts only, never source rows."""
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        head = conn.execute("""SELECT revision,state,content_hash FROM
            pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
            AND project_id='dev-project' AND definition_id=%s""",
            (frozen.DEFINITION,)).fetchone()
        claims = [dict(row) for row in conn.execute("""SELECT group_id::text,trigger,
            scheduled_for,request,record FROM pipeline_snapshot_schedule_claim WHERE org_id='org-org'
            AND project_id='dev-project' AND request->'definitionRef'->>'resourceId'=%s
            ORDER BY created_at""", ("snapshot-schedule-" + frozen.DEFINITION,)).fetchall()]
        attempts = [dict(row) for row in conn.execute("""SELECT attempt_id::text,state,
            terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt
            WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
            AND generation=%s ORDER BY accepted_at""",
            (frozen.prior.prior.prepared.registered.INSTALLATION,
             frozen.prior.prior.prepared.registered.GENERATION)).fetchall()]
        runs = dict(conn.execute("""SELECT count(*) AS n,
            count(*) FILTER(WHERE r.status='running' AND r.finished_at IS NULL
                AND r.executor_id='' AND NOT r.executor_stopped AND r.rows_written=0
                AND r.error_code='' AND r.error_message='') AS running,
            count(*) FILTER(WHERE r.status='failed' AND r.finished_at IS NOT NULL
                AND r.executor_id='pipeline-live-v1' AND r.executor_stopped
                AND r.rows_written=0 AND r.error_code=%s
                AND r.error_message='executor never started; stalled group closed under audited maintenance authority') AS closed,
            count(*) FILTER(WHERE s.enabled) AS "schedulesEnabled"
            FROM pipeline_snapshot_schedule_member m JOIN meta_schedule_run r
                ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
            JOIN meta_schedule s ON (s.org_id,s.project_id,s.id)=
                (m.org_id,m.project_id,m.schedule_id)
            WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s""",
            (REASON, frozen.GROUP)).fetchone())
        effects = {}
        for key, table in (("groupClaims", "pipeline_snapshot_group_claim"),
                           ("groupInputs", "pipeline_snapshot_group_input"),
                           ("groupMembers", "pipeline_snapshot_group_member")):
            effects[key] = conn.execute("SELECT count(*) AS n FROM " + table +
                " WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s",
                (frozen.GROUP,)).fetchone()["n"]
        for key, table in (("sourceClaims", "pipeline_controlled_source_claim"),
                           ("ingressCommands", "ecommerce_ingress_command"),
                           ("derivedCommands", "ecommerce_ingress_derived_command"),
                           ("datasetReceipts", "ecommerce_ingress_dataset_receipt")):
            effects[key] = conn.execute("SELECT count(*) AS n FROM " + table + " x "
                "JOIN pipeline_snapshot_schedule_member m ON "
                "(m.org_id,m.project_id,m.run_id)=(x.org_id,x.project_id,x.run_id) "
                "WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s",
                (frozen.GROUP,)).fetchone()["n"]
        receipts = conn.execute("""SELECT receipt_id::text,content_hash,request_hash,idempotency_key,
            actor,authority_data FROM pipeline_snapshot_stalled_group_closure_receipt
            WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s""",
            (frozen.GROUP,)).fetchall()
        facts = dict(conn.execute("""SELECT
            (SELECT count(*) FROM ecom_ingest_receipt WHERE org_id='org-org'
                AND workspace_id='dev-project') AS "storeReceipts",
            (SELECT count(*) FROM ecom_link WHERE org_id='org-org'
                AND workspace_id='dev-project' AND deleted_at IS NULL) AS "liveLinks",
            (SELECT count(*) FROM projection_outbox WHERE org_id='org-org'
                AND workspace_id='dev-project' AND projected IS FALSE) AS pending,
            (SELECT count(*) FROM extension_runtime_binding WHERE org_id='dev-org'
                AND project_id='dev-project') AS canary,
            (SELECT count(*) FROM pipeline_snapshot_stalled_group_closure_receipt
                WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s)
                AS "stalledReceipts",
            (SELECT count(*) FROM pipeline_snapshot_unaccepted_group_closure_receipt
                WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s)
                AS "unacceptedReceipts"
                """, (frozen.GROUP, frozen.GROUP)).fetchone())
    for claim in claims:
        claim["scheduled_for"] = str(claim["scheduled_for"])
    return {"head": dict(head) if head else None, "claims": claims,
            "attempts": attempts, "runs": runs, "effects": effects,
            "receiptCount": len(receipts),
            "receipt": dict(receipts[0]) if len(receipts) == 1 else None,
            "facts": facts}


if __name__ == "__main__":
    try:
        result = classify(observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_INDEPENDENT_CLOSURE_AUDIT" else 0)
