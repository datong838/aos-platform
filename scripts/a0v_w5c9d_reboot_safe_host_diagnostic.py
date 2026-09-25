#!/usr/bin/env python3
"""Reboot-safe local Host diagnostic; never authorizes real closure."""

from __future__ import annotations

import json
import subprocess

import a0v_w5c4t_closure_feasibility as boundary
import a0v_w5c5c_host_role_topology as known_host
import a0v_w5c5f_host_directory_authority as directory


_NO_AUTHORITY = {"automaticAction": False, "closureAuthorized": False,
                 "topologyComplete": False}
_DIRECTORY_OUTCOME = "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY"
_TIME_GATES = {"STALLED_WAIT_24H": "WAIT_24H",
               "STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY": "ELIGIBLE_NO_AUTHORITY"}


def _frozen(reason: str) -> dict:
    return {**_NO_AUTHORITY, "outcome": "FROZEN_LOCAL_HOST_DIAGNOSTIC", "reason": reason}


def classify(baseline: dict, managed: dict, local_pids: list[int]) -> dict:
    """Local quietness and the elapsed time are never a fleet or Owner grant."""
    if not isinstance(baseline, dict) or not isinstance(managed, dict):
        return _frozen("INCOMPLETE_OBSERVATION")
    if (baseline.get("outcome") not in _TIME_GATES
            or baseline.get("automaticAction") is not False):
        return _frozen("ORIGINAL_GROUP_OR_TIME_GATE_DIFFERS")
    if (managed.get("outcome") != _DIRECTORY_OUTCOME
            or managed.get("automaticAction") is not False
            or managed.get("closureAuthorized") is not False
            or managed.get("runningOriginalRuns") != 12
            or managed.get("releasedResourceLeases") != 3):
        return _frozen("MANAGED_DIRECTORY_OR_RUNS_DIFFERS")
    if (type(local_pids) is not list
            or any(type(pid) is not int or pid <= 0 for pid in local_pids)
            or local_pids):
        return _frozen("KNOWN_LOCAL_HOST_PRESENT_OR_UNKNOWN")
    return {**_NO_AUTHORITY, "outcome": "LOCAL_QUIET_NO_GLOBAL_AUTHORITY",
            "timeGate": _TIME_GATES[baseline["outcome"]],
            "knownLocalHostCount": 0, "runningOriginalRuns": 12,
            "unresolved": ["FULL_MACHINE_HOST_TOPOLOGY",
                           "FRESH_SINGLE_TRANSACTION_OWNER_GATE",
                           "SEPARATE_REAL_CLOSURE_PLAN_AND_UNIQUE_KEY"]}


def observe() -> tuple[dict, dict, list[int]]:
    """Separate read-only snapshots; not a cross-surface atomic authority."""
    baseline = boundary.classify(boundary.observe())
    managed = directory.classify(directory.observe())
    processes = subprocess.check_output(
        ["ps", "-axo", "pid=,comm=,args="], text=True, errors="replace", timeout=10)
    return baseline, managed, known_host.known_host_pids(processes)


if __name__ == "__main__":
    try:
        result = classify(*observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_LOCAL_HOST_DIAGNOSTIC" else 0)
