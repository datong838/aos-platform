#!/usr/bin/env python3
"""Read CG's exact single natural recovery attempt without executing work."""
from __future__ import annotations
import json
import a0v_cb_attempt_guard as guard
import a0v_cg_saved_snapshot_recovery as recovery
import a0v_cg_successor_business as successor
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection

ATTEMPT_ID = "f7b2fc7f-9bce-4102-8f5b-48ec8879ae55"
OPERATION_KEY = f"snapshot-group-completion:{recovery.GROUP}"
IDEMPOTENCY_KEY = f"snapshot-group:{recovery.GROUP}:1"
REQUEST_HASH = "sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7"
LINK_KEY = guard.LINK_KEY
guard.successor = successor
guard.recovery = recovery
successor.CB_ID = successor.CG_ID
successor.CB_GENERATION = successor.CG_GENERATION
guard.ATTEMPT_ID = ATTEMPT_ID
guard.OPERATION_KEY = OPERATION_KEY
guard.IDEMPOTENCY_KEY = IDEMPOTENCY_KEY
guard.REQUEST_HASH = REQUEST_HASH


def read_facts(conn):
    facts = guard.read_facts(conn)
    facts["routes"] = conn.execute("""SELECT count(*) n FROM extension_operation_dispatch_binding
      WHERE org_id='org-org' AND project_id='dev-project' AND installation_id=%s AND generation=%s
        AND execution_epoch=3 AND operation_fence IS FALSE
        AND revision=222 AND cutover_group_revision=249""",
        (successor.CG_ID, successor.CG_GENERATION)).fetchone()["n"]
    return facts


def classify(facts):
    if (facts.get("attemptId") != ATTEMPT_ID or facts.get("attemptCount") != 1
            or facts.get("definitionRevision") != 165 or facts.get("recoveryRevision") != 54
            or facts.get("routes") != 9):
        raise RuntimeError("CG guard authority differs")
    predecessor_view = {**facts, "definitionRevision": 150, "recoveryRevision": 49}
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
