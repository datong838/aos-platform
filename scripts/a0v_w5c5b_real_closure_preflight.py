#!/usr/bin/env python3
"""Read-only advisory for the exact stalled group; never applies closure."""

from __future__ import annotations

import json

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c4t_closure_feasibility as base


prior = base.prior
ACTOR = prior.prior.prepared.ACTOR


def _frozen(reason):
    return {"outcome": "FROZEN_REAL_CLOSURE_PREFLIGHT", "reason": reason,
            "automaticAction": False}


def classify(baseline, detail):
    """A positive advisory still requires a separate plan and fresh SQL gate."""
    routed = base.classify(baseline)
    if routed["outcome"] == "FROZEN_FEASIBILITY_BOUNDARY":
        return _frozen("BASELINE_DRIFT")
    try:
        if (detail["head"] != baseline["head"]
                or detail["claims"] != baseline["claims"]
                or len(detail["attempts"]) != 1
                or detail["attempts"][0]["operation_kind"] != "recoverable_store"
                or [(a["attempt_id"], a["state"], a["terminal_reason_code"],
                     a["terminal_error_type"]) for a in detail["attempts"]]
                   != [(a["attempt_id"], a["state"], a["terminal_reason_code"],
                        a["terminal_error_type"]) for a in baseline["attempts"]]
                or detail["runs"] != [{"status": "running", "executor_stopped": False,
                                       "finished_at": None, "n": 12}]
                or detail["member_revisions"] != [{"revision": 4, "n": 12}]
                or detail["key_revisions"] != [{"revision": 4,
                     "content_hash": base.HASH, "previous_hash": prior.HASH}]
                or detail["facts"] != {"members": 12, "enabled": 0,
                                       "receipts": 26, "links": 0, "pending": 0,
                                       "canary": 0, "key_count": 1}
                or detail["host_alive"] is not False
                or detail["worker_pid"] != prior.WORKER_PID
                or detail["actor_admin"] is not True):
            return _frozen("DISABLE_OR_ACTOR_OR_NAMED_TOPOLOGY_DRIFT")
    except (KeyError, TypeError, ValueError):
        return _frozen("INCOMPLETE_DETAIL")
    if routed["outcome"] == "STALLED_WAIT_24H":
        return {**routed, "next": "READ_ONLY_RECHECK", "topologyComplete": False}
    if routed["outcome"] == "STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY":
        return {**routed, "outcome": "REQUIRES_SEPARATE_REAL_CLOSURE_PLAN",
                "topologyComplete": False,
                "remaining": ["unique maintainer key and intent", "all-host topology",
                              "fresh serializable Owner gate and independent audit"]}
    return _frozen("UNKNOWN_BASELINE_OUTCOME")


def observe():
    baseline = base.observe()
    detail = prior._read()
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        detail["actor_admin"] = conn.execute("""SELECT EXISTS(
            SELECT 1 FROM meta_membership WHERE org_id='org-org'
              AND project_id='dev-project' AND subject=%s
              AND lower(role) IN ('admin','owner')) AS allowed""",
            (ACTOR,)).fetchone()["allowed"]
    return baseline, detail


if __name__ == "__main__":
    try:
        result = classify(*observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False, default=str))
    raise SystemExit(2 if result["outcome"] == "FROZEN_REAL_CLOSURE_PREFLIGHT" else 0)
