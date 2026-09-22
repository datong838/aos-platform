#!/usr/bin/env python3
"""Read DH's exact single natural recovery attempt without executing work."""
from __future__ import annotations
import json
import a0v_cb_attempt_guard as guard
import a0v_dh_saved_snapshot_recovery as recovery
import a0v_dh_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

ATTEMPT_ID = "40429d74-6faf-4895-8b2a-b0cc69df35a3"
OPERATION_KEY = f"snapshot-group-completion:{recovery.GROUP}"
IDEMPOTENCY_KEY = f"snapshot-group:{recovery.GROUP}:1"
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"
LINK_KEY = guard.LINK_KEY
guard.successor = successor
guard.recovery = recovery
successor.CB_ID = successor.DH_ID
successor.CB_GENERATION = successor.DH_GENERATION
guard.ATTEMPT_ID = ATTEMPT_ID
guard.OPERATION_KEY = OPERATION_KEY
guard.IDEMPOTENCY_KEY = IDEMPOTENCY_KEY
guard.REQUEST_HASH = REQUEST_HASH


def read_facts(conn):
    facts = guard.read_facts(conn)
    facts["routes"] = conn.execute("""SELECT count(*) n FROM extension_operation_dispatch_binding
      WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s
        AND execution_epoch=3 AND operation_fence IS FALSE
        AND revision=303 AND cutover_group_revision=330""",
        (successor.DH_ID, successor.DH_GENERATION)).fetchone()["n"]
    return facts


def classify(facts):
    if (facts.get("attemptId") != ATTEMPT_ID or facts.get("attemptCount") != 1
            or facts.get("revision") != 4
            or facts.get("definitionRevision") != 243 or facts.get("recoveryRevision") != 80
            or facts.get("routes") != 9):
        raise RuntimeError("DH guard authority differs")
    predecessor_view = {
        **facts,
        "revision": 4,
        "definitionRevision": 150,
        "definitionState": "enabled",
        "recoveryRevision": 49,
    }
    result = guard.classify(predecessor_view)
    return {**result, "outcome": "FAILED_FREEZE_BOUNDARY"}


def main():
    try:
        successor.setup()
        with consumer_connection(runtime_worker_connection, guard.shared.baseline.SCOPE) as conn:
            facts = read_facts(conn)
        print(json.dumps(facts | classify(facts), ensure_ascii=False, indent=2, default=str))
        return 0
    except Exception as error:
        print(json.dumps({"outcome": "SAFE_BLOCKED", "automaticAction": False,
                          "errorType": type(error).__name__}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
