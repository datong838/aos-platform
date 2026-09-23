#!/usr/bin/env python3
"""Read-only: dump recent operations and events for the DQ installation."""
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
    cols = conn.execute("""SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='extension_runtime_event' ORDER BY ordinal_position""").fetchall()
    print("EVENT_COLS:", [c["column_name"] for c in cols])
    ops = conn.execute("""SELECT operation_id::text, kind, phase, status, requested_by, created_at::text
        FROM extension_runtime_operation
        WHERE org_id=%s AND project_id=%s AND installation_id=%s
        ORDER BY created_at DESC LIMIT 8""", ("org-org", "dev-project", w4.INSTALLATION)).fetchall()
    print("OP_COUNT:", len(ops))
    for o in ops:
        print("OP", json.dumps(dict(o), ensure_ascii=False))
    evs = conn.execute("""SELECT e.sequence, e.type, e.operation_id::text, e.occurred_at::text,
        left(e.payload::text, 140) AS p
        FROM extension_runtime_event e
        WHERE e.org_id=%s AND e.project_id=%s AND e.operation_id IN (
            SELECT operation_id FROM extension_runtime_operation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s)
        ORDER BY e.occurred_at DESC LIMIT 14""", ("org-org", "dev-project", "org-org", "dev-project", w4.INSTALLATION)).fetchall()
    for e in evs:
        print("EV", json.dumps(dict(e), ensure_ascii=False))
