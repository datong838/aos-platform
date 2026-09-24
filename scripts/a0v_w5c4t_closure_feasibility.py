#!/usr/bin/env python3
"""Read-only exact W5c4t closure eligibility; never closes or resumes a group."""

from __future__ import annotations

from datetime import datetime, timedelta
import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4s_disable_failed_definition as prior


DEFINITION = prior.DEFINITION
HASH = "sha256:d3c28bf5ea17e299fe598b662da238aeecbb3f0f4227c96da3b44a8f4f49c32d"
GROUP = prior.GROUP
ATTEMPT = prior.ATTEMPT
EFFECTS = {"groupClaims": 1, "groupInputs": 1, "groupMembers": 12,
           "sourceClaims": 12, "ingressCommands": 12,
           "derivedCommands": 0, "datasetReceipts": 0}
FACTS = {"storeReceipts": 26, "liveLinks": 0, "pending": 0,
         "canary": 0, "stalledReceipts": 0, "unacceptedReceipts": 0}


def _frozen(reason):
    return {"outcome": "FROZEN_FEASIBILITY_BOUNDARY", "reason": reason,
            "automaticAction": False}


def _time(value):
    observed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if not isinstance(observed, datetime) or observed.utcoffset() is None:
        raise ValueError("timezone-aware DB time required")
    return observed


def classify(value):
    """Classify only the exact failed group; eligible never authorizes apply."""
    try:
        if (value["head"] != {"revision": 4, "state": "disabled", "content_hash": HASH}
                or value["claims"] != [{"group_id": GROUP, "trigger": "cron",
                                         "scheduled_for": "2026-09-24 20:00:00+00:00"}]
                or value["attempts"] != [{"attempt_id": ATTEMPT, "state": "failed",
                      "terminal_reason_code": "RECOVERABLE_EXECUTION_EXCEPTION",
                      "terminal_error_type": "PermissionError"}]
                or value["effects"] != EFFECTS or value["facts"] != FACTS
                or value["runs"]["n"] != 12 or value["runs"]["stalled"] != 12):
            return _frozen("GROUP_AUTHORITY_OR_EFFECTS_DIFFERS")
        latest = _time(value["runs"]["latest_started"])
        now = _time(value["observedAt"])
        eligible_after = latest + timedelta(hours=24)
        if now < latest:
            return _frozen("DATABASE_TIME_PRECEDES_RUN")
        common = {"automaticAction": False,
                  "unacceptedPath": "UNACCEPTED_PATH_REJECTED_EFFECTS",
                  "eligibleStrictlyAfterUtc": eligible_after.isoformat(),
                  "groupId": GROUP, "attemptId": ATTEMPT}
        if now <= eligible_after:
            return {**common, "outcome": "STALLED_WAIT_24H"}
        return {**common, "outcome": "STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY"}
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return _frozen(type(error).__name__)


def observe():
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        head = conn.execute("""SELECT revision,state,content_hash FROM
          pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
          AND project_id='dev-project' AND definition_id=%s""", (DEFINITION,)).fetchone()
        claims = [dict(row) for row in conn.execute("""SELECT group_id::text,trigger,
          scheduled_for FROM pipeline_snapshot_schedule_claim WHERE org_id='org-org'
          AND project_id='dev-project' AND request->'definitionRef'->>'resourceId'=%s
          ORDER BY created_at""", ("snapshot-schedule-" + DEFINITION,)).fetchall()]
        attempts = [dict(row) for row in conn.execute("""SELECT attempt_id::text,state,
          terminal_reason_code,terminal_error_type FROM extension_runtime_execution_attempt
          WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s
          AND generation=%s ORDER BY accepted_at""",
          (prior.prior.prepared.registered.INSTALLATION,
           prior.prior.prepared.registered.GENERATION)).fetchall()]
        runs = dict(conn.execute("""SELECT count(*) AS n,max(r.started_at) AS latest_started,
          count(*) FILTER(WHERE r.status='running' AND r.finished_at IS NULL
            AND r.executor_id='' AND r.executor_stopped IS FALSE
            AND r.rows_written=0 AND r.error_code='' AND r.error_message=''
            AND s.enabled IS FALSE) AS stalled
          FROM pipeline_snapshot_schedule_member m JOIN meta_schedule_run r
            ON (r.org_id,r.project_id,r.id)=(m.org_id,m.project_id,m.run_id)
          JOIN meta_schedule s ON (s.org_id,s.project_id,s.id)=
            (m.org_id,m.project_id,m.schedule_id)
          WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s""",
          (GROUP,)).fetchone())
        effects = {}
        for key, table in (("groupClaims", "pipeline_snapshot_group_claim"),
                           ("groupInputs", "pipeline_snapshot_group_input"),
                           ("groupMembers", "pipeline_snapshot_group_member")):
            effects[key] = conn.execute("SELECT count(*) AS n FROM " + table +
                " WHERE org_id='org-org' AND project_id='dev-project' AND group_id=%s",
                (GROUP,)).fetchone()["n"]
        for key, table in (("sourceClaims", "pipeline_controlled_source_claim"),
                           ("ingressCommands", "ecommerce_ingress_command"),
                           ("derivedCommands", "ecommerce_ingress_derived_command"),
                           ("datasetReceipts", "ecommerce_ingress_dataset_receipt")):
            effects[key] = conn.execute("SELECT count(*) AS n FROM " + table + " x "
                "JOIN pipeline_snapshot_schedule_member m ON "
                "(m.org_id,m.project_id,m.run_id)=(x.org_id,x.project_id,x.run_id) "
                "WHERE m.org_id='org-org' AND m.project_id='dev-project' AND m.group_id=%s",
                (GROUP,)).fetchone()["n"]
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
            AS "unacceptedReceipts" """, (GROUP, GROUP)).fetchone())
    for claim in claims:
        claim["scheduled_for"] = str(claim["scheduled_for"])
    return {"observedAt": now, "head": dict(head) if head else None,
            "claims": claims, "attempts": attempts, "runs": runs,
            "effects": effects, "facts": facts}


if __name__ == "__main__":
    value = classify(observe())
    print(json.dumps(value, ensure_ascii=False, default=str))
    raise SystemExit(2 if value["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY" else 0)
