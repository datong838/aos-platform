#!/usr/bin/env python3
"""Read-only: DQ definition head + schedules status for W4 decision."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a0v_w4_dq_config_refresh as w4

w4._configure()
md = w4._database()
from aos_api.tenant_scope import TenantScope

scope = TenantScope("org-org", "dev-project")
with md(scope) as conn:
    defs = conn.execute("""SELECT definition_id, revision, state, installation_id::text
        FROM pipeline_snapshot_schedule_definition_head
        WHERE org_id=%s AND project_id=%s
        ORDER BY definition_id""", scope.key).fetchall()
    for d in defs:
        row = dict(d)
        row["installation_id"] = str(row["installation_id"])
        print("DEF:", json.dumps(row, ensure_ascii=False, default=str))
    # schedules for DQ definition
    dqs = conn.execute("""SELECT definition_id FROM pipeline_snapshot_schedule_definition_head
        WHERE org_id=%s AND project_id=%s AND state='enabled'""", scope.key).fetchall()
    print("ENABLED_DEFS:", [d["definition_id"] for d in dqs])
    # last 3 schedule rows (m.* columns check)
    sch = conn.execute("""SELECT table_name FROM information_schema.tables
        WHERE table_schema='public' AND table_name LIKE '%snapshot_schedule%'""").fetchall()
    print("TABLES:", [t["table_name"] for t in sch])
