#!/usr/bin/env python3
"""Read-only known-launcher and registration-role audit; never closes work."""

from __future__ import annotations

import json
from pathlib import Path
import shlex
import subprocess

from a0v_formal_text_model_renewal import database_connect
import a0v_w5c5b_real_closure_preflight as prior


ROLE = "aos_ecommerce_registration_control"
HOST_SCRIPT = "scripts/a0v_ecommerce_runtime_host.py"
ABS_HOST_SCRIPT = str(Path(__file__).resolve().parents[1] / HOST_SCRIPT)


def known_host_pids(output):
    """Count only Python argv executing the exact known launcher, not grep text."""
    found = []
    for line in output.splitlines():
        fields = line.strip().split(None, 2)
        if len(fields) != 3 or not fields[0].isdigit():
            continue
        pid, comm, args = fields
        if not Path(comm).name.lower().startswith("python"):
            continue
        try:
            argv = shlex.split(args)
        except ValueError:
            continue
        if not argv or not Path(argv[0]).name.lower().startswith("python"):
            continue
        index = 1
        while index < len(argv) and argv[index] in ("-u", "-B", "-I", "-s", "-S"):
            index += 1
        if index < len(argv) and argv[index] in (HOST_SCRIPT, ABS_HOST_SCRIPT):
            found.append(int(pid))
    return sorted(set(found))


def classify(preflight, host_pids, role):
    """Complete proof is impossible here: other launchers/hosts remain unobserved."""
    if preflight.get("outcome") not in ("STALLED_WAIT_24H",
                                        "REQUIRES_SEPARATE_REAL_CLOSURE_PLAN"):
        return {"outcome": "FROZEN_HOST_ROLE_TOPOLOGY", "reason": "BASE_PREFLIGHT_DRIFT",
                "automaticAction": False}
    expected_flags = {"rolcanlogin": True, "rolsuper": False,
                      "rolbypassrls": False, "rolcreaterole": False,
                      "rolcreatedb": False, "rolreplication": False,
                      "rolinherit": False}
    if (type(host_pids) is not list or any(type(pid) is not int or pid <= 0 for pid in host_pids)
            or len(set(host_pids)) != len(host_pids) or len(host_pids) != 0):
        return {"outcome": "FROZEN_HOST_ROLE_TOPOLOGY", "reason": "KNOWN_HOST_PROCESS_PRESENT_OR_UNKNOWN",
                "automaticAction": False}
    if (type(role) is not dict or role.get("flags") != expected_flags
            or role.get("memberships") != ["aos_extension_maintainer", "aos_runtime"]
            or role.get("adminOptions") != 0):
        return {"outcome": "FROZEN_HOST_ROLE_TOPOLOGY", "reason": "REGISTRATION_ROLE_DRIFT",
                "automaticAction": False}
    return {"outcome": "KNOWN_LAUNCHER_QUIET_REGISTRATION_ROLE_READY_INCOMPLETE_TOPOLOGY",
            "automaticAction": False, "knownHostCount": 0,
            "registrationRole": ROLE, "topologyComplete": False,
            "registrationConnectionVerified": False,
            "next": "SEPARATE_REAL_PLAN_MUST_CHECK_ALL_HOSTS_AND_CONNECTOR"}


def observe():
    baseline = prior.classify(*prior.observe())
    processes = subprocess.check_output(
        ["ps", "-axo", "pid=,comm=,args="], text=True, errors="replace", timeout=10)
    host_pids = known_host_pids(processes)
    with database_connect("aos_meta_head")() as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        flags = conn.execute("""SELECT rolcanlogin,rolsuper,rolbypassrls,
            rolcreaterole,rolcreatedb,rolreplication,rolinherit
            FROM pg_roles WHERE rolname=%s""", (ROLE,)).fetchone()
        members = [row["rolname"] for row in conn.execute("""SELECT rolname
            FROM pg_roles WHERE rolname<>%s AND pg_has_role(%s,oid,'member')
            ORDER BY rolname""", (ROLE, ROLE)).fetchall()]
        admin = conn.execute("""SELECT count(*) AS n FROM pg_auth_members m
            JOIN pg_roles r ON r.oid=m.member WHERE r.rolname=%s
            AND m.admin_option""", (ROLE,)).fetchone()["n"]
    return baseline, host_pids, {"flags": dict(flags) if flags else None,
                                 "memberships": members, "adminOptions": admin}


if __name__ == "__main__":
    try:
        result = classify(*observe())
    except Exception as error:
        result = {"outcome": "FROZEN_HOST_ROLE_TOPOLOGY",
                  "reason": "OBSERVATION_" + type(error).__name__, "automaticAction": False}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_HOST_ROLE_TOPOLOGY" else 0)
