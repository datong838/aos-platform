"""Schedule configuration and execution cursor have distinct database owners."""
from __future__ import annotations

import json
import uuid

from aos_api import data_os_store
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


def _workspace(scope: TenantScope) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org (id,name) VALUES (%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.org_id),
        )
        conn.execute(
            "INSERT INTO twa_workspace (org_id,project_id,name) "
            "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (scope.org_id, scope.project_id, scope.project_id),
        )
        conn.commit()


def test_configuration_update_preserves_newer_executor_cursor() -> None:
    suffix = uuid.uuid4().hex
    scope = TenantScope(f"org-cursor-{suffix}", f"project-cursor-{suffix}")
    schedule_id = f"schedule-{suffix}"
    old = {"id": "run-old", "status": "succeeded"}
    current = {"id": "run-current", "status": "succeeded"}
    _workspace(scope)
    try:
        data_os_store.persist_schedule(
            scope,
            {
                "id": schedule_id,
                "enabled": True,
                "name": "before",
                "lastRun": old,
            },
        )
        with connect() as conn:
            conn.execute(
                "UPDATE meta_schedule SET last_run=%s::jsonb "
                "WHERE org_id=%s AND project_id=%s AND id=%s",
                (json.dumps(current), *scope.key, schedule_id),
            )
            conn.commit()

        returned = data_os_store.persist_schedule_configuration(
            scope,
            {
                "id": schedule_id,
                "enabled": False,
                "name": "after",
                "lastRun": old,
            },
        )
        loaded = data_os_store.load_all(scope)["schedules"][schedule_id]
        assert returned == current
        assert loaded["lastRun"] == current
        assert loaded["enabled"] is False
        assert loaded["name"] == "after"
    finally:
        data_os_store.delete_schedule(scope, schedule_id)
