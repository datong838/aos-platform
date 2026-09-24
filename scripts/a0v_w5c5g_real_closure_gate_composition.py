#!/usr/bin/env python3
"""Read-only composition of existing real-closure gates; never authorizes close."""

from __future__ import annotations

import json

import a0v_w5c5c_host_role_topology as known_host
import a0v_w5c5d_registration_handshake as connector
import a0v_w5c5e_independent_closure_audit as closure_audit
import a0v_w5c5f_host_directory_authority as directory


def _frozen(reason):
    return {"outcome": "FROZEN_REAL_CLOSURE_GATE_COMPOSITION", "reason": reason,
            "automaticAction": False, "closureAuthorized": False,
            "topologyComplete": False}


def classify(value):
    """Temporal and local observations never become a transaction authority."""
    try:
        baseline = value["baseline"]
        host = value["knownHost"]
        registration = value["registration"]
        audit = value["closureAudit"]
        managed = value["managedDirectory"]
        if any(type(item) is not dict for item in
               (baseline, host, registration, audit, managed)):
            return _frozen("INCOMPLETE_GATE_RESULT")
        if audit.get("outcome") != "NOT_YET_CLOSED" or audit.get("runningRuns") != 12 \
                or audit.get("closureReceipts") != 0:
            return _frozen("ORIGINAL_GROUP_NOT_EXACTLY_UNCLOSED")
        if host.get("outcome") != (
                "KNOWN_LAUNCHER_QUIET_REGISTRATION_ROLE_READY_INCOMPLETE_TOPOLOGY") \
                or host.get("knownHostCount") != 0:
            return _frozen("KNOWN_HOST_GATE_DIFFERS")
        if registration.get("outcome") != "REGISTRATION_CONNECTOR_READ_ONLY_HANDSHAKE_GREEN" \
                or registration.get("closureAuthorized") is not False:
            return _frozen("REGISTRATION_GATE_DIFFERS")
        if managed.get("outcome") != "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY" \
                or managed.get("releasedResourceLeases") != 3 \
                or managed.get("runningOriginalRuns") != 12:
            return _frozen("MANAGED_DIRECTORY_GATE_DIFFERS")
        if any(item.get("automaticAction") is not False for item in
               (baseline, host, registration, audit, managed)):
            return _frozen("AUTOMATIC_ACTION_FLAG_DIFFERS")
        common = {"automaticAction": False, "closureAuthorized": False,
                  "topologyComplete": False, "runningOriginalRuns": 12,
                  "stalledClosureReceipts": 0,
                  "unresolved": ["FULL_MACHINE_HOST_TOPOLOGY",
                                 "FRESH_SINGLE_TRANSACTION_OWNER_GATE",
                                 "SEPARATE_REAL_CLOSURE_PLAN_AND_UNIQUE_KEY"]}
        if baseline.get("outcome") == "STALLED_WAIT_24H":
            if baseline.get("topologyComplete") is not False:
                return _frozen("BASELINE_TOPOLOGY_FLAG_DIFFERS")
            return {**common, "outcome": "REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY",
                    "eligibleStrictlyAfterUtc": baseline["eligibleStrictlyAfterUtc"]}
        if baseline.get("outcome") == "REQUIRES_SEPARATE_REAL_CLOSURE_PLAN":
            if baseline.get("topologyComplete") is not False:
                return _frozen("BASELINE_TOPOLOGY_FLAG_DIFFERS")
            return {**common, "outcome": "REAL_CLOSURE_TIME_ELIGIBLE_BUT_NOT_AUTHORIZED",
                    "eligibleStrictlyAfterUtc": baseline["eligibleStrictlyAfterUtc"]}
        return _frozen("BASELINE_TIME_GATE_DIFFERS")
    except (KeyError, TypeError, ValueError):
        return _frozen("INCOMPLETE_GATE_RESULT")


def observe():
    """Separate read-only snapshots; never claim a cross-surface atomic view."""
    prior, host_pids, role = known_host.observe()
    return {"baseline": prior, "knownHost": known_host.classify(prior, host_pids, role),
            "registration": connector.classify(connector.observe()),
            "closureAudit": closure_audit.classify(closure_audit.observe()),
            "managedDirectory": directory.classify(directory.observe())}


if __name__ == "__main__":
    try:
        result = classify(observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_REAL_CLOSURE_GATE_COMPOSITION" else 0)
