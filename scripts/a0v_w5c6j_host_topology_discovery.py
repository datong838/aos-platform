#!/usr/bin/env python3
"""Read-only local/managed Host signals; never proves all-machine quietness."""

from __future__ import annotations

import json
import subprocess

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c5c_host_role_topology as local
import a0v_w5c5f_host_directory_authority as directory


def _frozen(reason):
    return {"outcome": "FROZEN_HOST_TOPOLOGY_DISCOVERY", "reason": reason,
            "automaticAction": False, "topologyComplete": False,
            "closureAuthorized": False}


def classify(value):
    """No finite local/managed observation authorizes full-fleet closure."""
    try:
        pids = value["knownLauncherPids"]
        managed = value["managedDirectory"]
        sessions = value["databaseSessions"]
        if (type(pids) is not list or any(type(pid) is not int or pid <= 0 for pid in pids)
                or len(set(pids)) != len(pids)
                or type(managed) is not dict
                or managed.get("outcome") != "MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY"
                or type(sessions) is not dict
                or any(type(sessions.get(key)) is not int or sessions[key] < 0
                       for key in ("knownLoginSessions", "remoteClientSessions", "unknownClientSessions"))
                or sessions["remoteClientSessions"] + sessions["unknownClientSessions"]
                   > sessions["knownLoginSessions"]):
            return _frozen("INCOMPLETE_OR_DRIFTED_TOPOLOGY_INPUT")
        observed = bool(pids or sessions["knownLoginSessions"])
        return {"outcome": ("OBSERVED_HOST_OR_SESSION_NO_CLOSURE" if observed
                            else "LOCAL_AND_MANAGED_SIGNALS_ONLY_INCOMPLETE_TOPOLOGY"),
                "automaticAction": False, "topologyComplete": False,
                "closureAuthorized": False, "knownLauncherCount": len(pids),
                "knownLoginSessions": sessions["knownLoginSessions"],
                "remoteClientSessions": sessions["remoteClientSessions"],
                "unknownClientSessions": sessions["unknownClientSessions"],
                "reason": "UNMANAGED_OR_OTHER_MACHINE_HOSTS_NOT_EXCLUDED"}
    except (KeyError, TypeError, ValueError):
        return _frozen("INCOMPLETE_OR_DRIFTED_TOPOLOGY_INPUT")


def observe():
    """Return counts only; never process argv, SQL text, client IP, or secrets."""
    process_output = subprocess.check_output(
        ["ps", "-axo", "pid=,comm=,args="], text=True, errors="replace", timeout=10)
    pids = local.known_host_pids(process_output)
    managed = directory.classify(directory.observe())
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        row = conn.execute("""SELECT count(*) AS known_login_sessions,
            count(*) FILTER(WHERE a.client_addr IS NOT NULL
                AND a.client_addr NOT IN (inet '127.0.0.1',inet '::1')) AS remote_client_sessions,
            count(*) FILTER(WHERE a.client_addr IS NULL) AS unknown_client_sessions
            FROM pg_stat_activity a
            WHERE a.datname=current_database() AND a.pid<>pg_backend_pid()
              AND (a.usename='aos_ecommerce_registration_control'
                OR EXISTS(SELECT 1 FROM extension_runtime_host_identity i
                          WHERE i.database_role::text=a.usename))""").fetchone()
    return {"knownLauncherPids": pids, "managedDirectory": managed,
            "databaseSessions": {
                "knownLoginSessions": int(row["known_login_sessions"]),
                "remoteClientSessions": int(row["remote_client_sessions"]),
                "unknownClientSessions": int(row["unknown_client_sessions"]),
            }}


if __name__ == "__main__":
    try:
        result = classify(observe())
    except Exception as error:
        result = _frozen("OBSERVATION_" + type(error).__name__)
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] in (
        "FROZEN_HOST_TOPOLOGY_DISCOVERY", "OBSERVED_HOST_OR_SESSION_NO_CLOSURE") else 0)
