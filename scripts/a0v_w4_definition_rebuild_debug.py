#!/usr/bin/env python3
"""Read-only: inspect DQ definition 268 members/bindings currency for W4 rebuild decision."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a0v_w4_dq_config_refresh as w4

w4._configure()

DQ_INSTALLATION = "29e553b2-3afc-4b15-b860-f79104f3491a"
DQ_GENERATION = "b8d6900d-b4a3-43d8-8891-a4b1d02abd3c"

md = w4._database()
from aos_api.tenant_scope import TenantScope

scope = TenantScope("org-org", "dev-project")
with md(scope) as conn:
    # find latest configure revision with settings across full history
    rows = conn.execute("""SELECT revision, request FROM pipeline_snapshot_schedule_definition_revision
        WHERE org_id=%s AND project_id=%s AND definition_id=%s ORDER BY revision DESC""",
        (*scope.key, "cb0dba8c-803f-5caf-8011-b763d349f2ba")).fetchall()
    body = None
    print("TOTAL_REVISIONS:", len(rows))
    for r in rows:
        if r["request"].get("settings"):
            body = r["request"]
            print("USING_REVISION:", r["revision"], "intent:", r["request"].get("intent"))
            break
    if body is None:
        print("NO_SETTINGS_REVISION")
        sys.exit(0)
    print("DEF268_INTENT:", body.get("intent"))
    print("DEF268_MEMBERS:", len(body.get("settings", {}).get("members", [])))
    print("DEF268_CRON:", body.get("settings", {}).get("cron"))
    print("DEF268_POLICYREF:", json.dumps(body.get("settings", {}).get("policyRef"), default=str)[:120])
    # binding currency: check pipeline_schedule_control_binding latest per member
    members = body.get("settings", {}).get("members", [])
    print("DEF268_ACTOR:", body.get("actor"))
    print("DEF268_REVREF:", json.dumps({k: str(v)[:50] for k, v in body.get("expectedRef", {}).items()}) if body.get("expectedRef") else None)
    # schedules belong to this definition
    cur = conn.execute("""SELECT count(*) AS n FROM pipeline_snapshot_schedule_current_member
        WHERE org_id=%s AND project_id=%s AND definition_id=%s""",
        (*scope.key, "cb0dba8c-803f-5caf-8011-b763d349f2ba")).fetchone()
    print("CURRENT_MEMBERS:", cur["n"])
    runs = conn.execute("""SELECT count(*) AS n FROM meta_schedule_run r
        JOIN pipeline_snapshot_schedule_current_member c
          ON (c.org_id,c.project_id,c.schedule_id)=(r.org_id,r.project_id,r.schedule_id)
        WHERE r.org_id=%s AND r.project_id=%s AND c.definition_id=%s
          AND (r.status='running' OR r.executor_stopped IS NOT TRUE)""",
        (*scope.key, "cb0dba8c-803f-5caf-8011-b763d349f2ba")).fetchone()
    print("ACTIVE_RUNS:", runs["n"])
    from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    with consumer_connection(runtime_worker_connection, dict(org_id="org-org", project_id="dev-project")) as conn2:
        mismatch = []
        for m in members:
            ref = m["bindingRef"]
            sid = str(ref["resourceId"]).replace("schedule-control-", "")
            latest = PipelineScheduleControlOwner.read_latest(conn2, scope=scope, schedule_id=sid)
            if latest is None or str(latest.ref.revision) != str(ref.get("revision")) or str(latest.ref.resource_id) != str(ref.get("resourceId")):
                mismatch.append(sid[:13])
        print("BINDING_CURRENCY_MISMATCH:", mismatch if mismatch else "NONE")
