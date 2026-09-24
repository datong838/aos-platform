#!/usr/bin/env python3
"""Read-only protected connector handshake; no closure, source read or key."""

from __future__ import annotations

import json
import os

from a0v_formal_text_model_renewal import database_connect
import a0v_w4_stalled_close as established
import a0v_w5c4t_closure_feasibility as boundary


ROLE = "aos_ecommerce_registration_control"
TARGET_DB = "aos_meta_head"
CREDENTIAL_FILE = (established.ROOT.parent / ".aos-recovery-20260920/state/"
                   "q-advisor-baseline/bn-registration-credentials/registration-main-identity.json")


def classify(value):
    if (type(value) is not dict or value.get("targetDatabase") != TARGET_DB
            or value.get("connectorDatabase") != TARGET_DB
            or value.get("sessionUser") != ROLE or value.get("currentUser") != ROLE
            or value.get("roleAfterScope") != "aos_runtime"
            or value.get("definition") != {"revision": 4, "state": "disabled",
                                           "content_hash": boundary.HASH}
            or value.get("groupCount") != 1 or value.get("closureReceipts") != 0):
        return {"outcome": "FROZEN_REGISTRATION_HANDSHAKE", "automaticAction": False}
    return {"outcome": "REGISTRATION_CONNECTOR_READ_ONLY_HANDSHAKE_GREEN",
            "automaticAction": False, "database": TARGET_DB, "role": ROLE,
            "topologyComplete": False, "closureAuthorized": False}


def observe():
    from aos_api.ecommerce_growth_registration_connection import registration_connection

    with database_connect(TARGET_DB)() as meta:
        meta.execute("SET TRANSACTION READ ONLY")
        target = meta.execute("SELECT current_database() AS db").fetchone()["db"]
    previous = os.environ.get("AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE")
    os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = str(CREDENTIAL_FILE)
    try:
        with registration_connection() as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            login = conn.execute("""SELECT current_database() AS db,
                session_user AS session_user,current_user AS current_user""").fetchone()
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id','org-org',true),"
                         "set_config('aos.project_id','dev-project',true)")
            current_role = conn.execute("SELECT current_user AS role").fetchone()["role"]
            definition = conn.execute("""SELECT revision,state,content_hash FROM
                pipeline_snapshot_schedule_definition_head WHERE org_id='org-org'
                AND project_id='dev-project' AND definition_id=%s""",
                (boundary.DEFINITION,)).fetchone()
            group_count = conn.execute("""SELECT count(*) AS n FROM
                pipeline_snapshot_schedule_claim WHERE org_id='org-org'
                AND project_id='dev-project' AND group_id=%s""",
                (boundary.GROUP,)).fetchone()["n"]
            receipts = conn.execute("""SELECT count(*) AS n FROM
                pipeline_snapshot_stalled_group_closure_receipt WHERE org_id='org-org'
                AND project_id='dev-project' AND group_id=%s""",
                (boundary.GROUP,)).fetchone()["n"]
    finally:
        if previous is None:
            os.environ.pop("AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE", None)
        else:
            os.environ["AOS_ECOMMERCE_REGISTRATION_CREDENTIAL_FILE"] = previous
    return {"targetDatabase": target, "connectorDatabase": login["db"],
            "sessionUser": login["session_user"], "currentUser": login["current_user"],
            "roleAfterScope": current_role, "definition": dict(definition) if definition else None,
            "groupCount": group_count, "closureReceipts": receipts}


if __name__ == "__main__":
    try:
        result = classify(observe())
    except Exception as error:
        result = {"outcome": "FROZEN_REGISTRATION_HANDSHAKE",
                  "reason": "OBSERVATION_" + type(error).__name__, "automaticAction": False}
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(2 if result["outcome"] == "FROZEN_REGISTRATION_HANDSHAKE" else 0)
