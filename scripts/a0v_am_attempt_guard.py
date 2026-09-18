#!/usr/bin/env python3
"""Read the exact AM attempt boundary and emit a non-executing route."""
from __future__ import annotations

import json

import a0v_q_advisor_baseline as baseline
import a0v_u_twelve_source_snapshot as snapshot
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection


ATTEMPT = "7d6cc3aa-881d-4aff-ac30-58978d06e85d"
INSTALLATION = "fd28d180-db24-4568-a848-101fcd3aa3c5"
GENERATION = "d6bc117e-d19d-4413-beb4-02884206e290"
GROUP = "c5ff1926-45b0-56de-b6b3-07d5b7d053a1"
MANIFEST = "sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01"
LINK_KEY = (
    "snapshot-group-links:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:"
    "bc77b98d9144f128154e876db40e4ebf8850b90c0d9196a7e67d0a908de33d4b"
)


def classify(facts: dict) -> dict:
    expected = {
        "attemptId": ATTEMPT,
        "installationId": INSTALLATION,
        "generation": GENERATION,
        "operationKind": "recoverable_store",
        "definitionRevision": 53,
        "definitionState": "enabled",
        "recoveryRevision": 17,
        "manifestHash": MANIFEST,
        "members": 12,
        "datasetReceipts": 12,
        "relationships": 1,
        "linkCommands": 1,
        "linkCount": 1168,
        "devOrgCanary": 0,
    }
    if any(facts.get(key) != value for key, value in expected.items()):
        raise RuntimeError("AM guard authority differs")
    if facts.get("state") not in {"running", "succeeded", "failed"}:
        raise RuntimeError("AM guard authority differs")
    bounded = {
        "revision": (1, None),
        "runningRuns": (0, 12),
        "retirements": (0, 1),
        "linkStoreReceipts": (0, 1),
        "ecomLinks": (0, 1168),
        "linkOutbox": (0, 2),
        "projectionPending": (0, None),
        "liveResources": (0, 3),
    }
    for key, (minimum, maximum) in bounded.items():
        value = facts.get(key)
        if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
            raise RuntimeError("AM guard authority differs")
    outcomes = {
        "running": "RUNNING_NO_ACTION",
        "succeeded": "SUCCEEDED_RUN_CLOSURE",
        "failed": "FAILED_DIAGNOSE_BOUNDARY",
    }
    return {"outcome": outcomes[facts["state"]], "automaticAction": False}


def read_facts(conn) -> dict:
    scope = ("org-org", "dev-project")
    attempt = conn.execute(
        """SELECT attempt_id::text,installation_id::text,generation::text,
          operation_kind,state,revision,heartbeat_at,lease_until,completed_at
          FROM extension_runtime_execution_attempt
          WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
        (*scope, ATTEMPT),
    ).fetchone()
    if attempt is None:
        raise RuntimeError("AM guard authority differs")
    definition = conn.execute(
        """SELECT h.revision,r.state
          FROM pipeline_snapshot_schedule_definition_head h
          JOIN pipeline_snapshot_schedule_definition_revision r
            ON (r.org_id,r.project_id,r.definition_id,r.revision)=
               (h.org_id,h.project_id,h.definition_id,h.revision)
          WHERE h.org_id=%s AND h.project_id=%s AND h.definition_id=%s""",
        (*scope, snapshot.DEFINITION_ID),
    ).fetchone()
    recovery = conn.execute(
        """SELECT revision,body->>'inputManifestHash' manifest_hash
          FROM pipeline_snapshot_group_recovery_receipt
          WHERE org_id=%s AND project_id=%s AND group_id=%s
          ORDER BY revision DESC LIMIT 1""",
        (*scope, GROUP),
    ).fetchone()
    boundary = conn.execute(
        """SELECT
          (SELECT count(*) FROM pipeline_snapshot_schedule_member
            WHERE org_id=%s AND project_id=%s AND group_id=%s) members,
          (SELECT count(*) FROM meta_schedule_run r
            JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.run_id)=(r.org_id,r.project_id,r.id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s
              AND r.status='running' AND r.executor_stopped IS FALSE
              AND r.finished_at IS NULL) running_runs,
          (SELECT count(*) FROM ecommerce_ingress_dataset_receipt d
            JOIN pipeline_snapshot_schedule_member m
              ON (m.org_id,m.project_id,m.run_id)=(d.org_id,d.project_id,d.run_id)
            WHERE m.org_id=%s AND m.project_id=%s AND m.group_id=%s) dataset_receipts,
          (SELECT count(*) FROM pipeline_snapshot_group_relationship
            WHERE org_id=%s AND project_id=%s AND group_id=%s) relationships,
          (SELECT count(*) FROM pipeline_snapshot_group_link_command
            WHERE org_id=%s AND project_id=%s AND group_id=%s) link_commands,
          (SELECT coalesce(max(link_count),0) FROM pipeline_snapshot_group_link_command
            WHERE org_id=%s AND project_id=%s AND group_id=%s) link_count,
          (SELECT count(*) FROM pipeline_snapshot_group_retirement
            WHERE org_id=%s AND project_id=%s AND group_id=%s) retirements,
          (SELECT count(*) FROM ecom_ingest_receipt
            WHERE org_id=%s AND workspace_id=%s AND idempotency_key=%s) link_store_receipts,
          (SELECT count(*) FROM ecom_link
            WHERE org_id=%s AND workspace_id=%s) ecom_links,
          (SELECT count(*) FROM projection_outbox
            WHERE org_id=%s AND workspace_id=%s AND event_source='authoritative_store'
              AND change_kind=ANY(ARRAY['links_written','links_tombstoned'])) link_outbox,
          (SELECT count(*) FROM projection_outbox
            WHERE org_id=%s AND workspace_id=%s AND projected IS FALSE) projection_pending,
          (SELECT count(*) FROM extension_runtime_resource_lease
            WHERE org_id=%s AND project_id=%s AND generation=%s
              AND cleanup_state='pending' AND observed_release IS FALSE) live_resources,
          (SELECT count(*) FROM extension_runtime_binding
            WHERE org_id='dev-org' AND project_id='dev-project') dev_org_canary""",
        (*scope, GROUP, *scope, GROUP, *scope, GROUP, *scope, GROUP,
         *scope, GROUP, *scope, GROUP, *scope, GROUP,
         *scope, LINK_KEY, *scope, *scope, *scope, *scope, GENERATION),
    ).fetchone()
    controls = conn.execute(
        """WITH latest AS (
          SELECT DISTINCT ON (pipeline_id) pipeline_id,payload
          FROM pipeline_runtime_control_revision
          WHERE org_id=%s AND project_id=%s AND generation=%s
          ORDER BY pipeline_id,revision DESC)
          SELECT count(*) members,
            min((payload->'draft'->>'expiresAt')::timestamptz) expires_at,
            extract(epoch FROM min((payload->'draft'->>'expiresAt')::timestamptz)
              - clock_timestamp())::bigint seconds_remaining
          FROM latest""",
        (*scope, GENERATION),
    ).fetchone()
    if definition is None or recovery is None or controls is None or controls["members"] != 12:
        raise RuntimeError("AM guard authority differs")
    return {
        "attemptId": attempt["attempt_id"],
        "installationId": attempt["installation_id"],
        "generation": attempt["generation"],
        "operationKind": attempt["operation_kind"],
        "state": attempt["state"],
        "revision": attempt["revision"],
        "heartbeatAt": attempt["heartbeat_at"],
        "leaseUntil": attempt["lease_until"],
        "completedAt": attempt["completed_at"],
        "definitionRevision": definition["revision"],
        "definitionState": definition["state"],
        "recoveryRevision": recovery["revision"],
        "manifestHash": recovery["manifest_hash"],
        "controlExpiresAt": controls["expires_at"],
        "controlSecondsRemaining": controls["seconds_remaining"],
        "members": boundary["members"],
        "runningRuns": boundary["running_runs"],
        "datasetReceipts": boundary["dataset_receipts"],
        "relationships": boundary["relationships"],
        "linkCommands": boundary["link_commands"],
        "linkCount": boundary["link_count"],
        "retirements": boundary["retirements"],
        "linkStoreReceipts": boundary["link_store_receipts"],
        "ecomLinks": boundary["ecom_links"],
        "linkOutbox": boundary["link_outbox"],
        "projectionPending": boundary["projection_pending"],
        "liveResources": boundary["live_resources"],
        "devOrgCanary": boundary["dev_org_canary"],
    }


def main() -> int:
    try:
        baseline.setup()
        with consumer_connection(runtime_worker_connection, baseline.SCOPE) as conn:
            facts = read_facts(conn)
        result = facts | classify(facts)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print(json.dumps({
            "outcome": "SAFE_BLOCKED",
            "automaticAction": False,
            "errorType": type(error).__name__,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
