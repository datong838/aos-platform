"""Explicit disposable-clone check for the network active database boundary."""
from datetime import UTC, datetime, timedelta
import os
import uuid

import psycopg
import pytest

from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


CLONE = "aos_bg00bu_network_gate_testonly_20260930"
SCOPE = TenantScope("org-org", "dev-project")


def test_only_network_active_direct_insert_is_blocked_and_draft_remains_allowed():
    if os.environ.get("AOS_BG00BU_TEST_DATABASE") != CLONE:
        pytest.skip("explicit disposable BG00bu clone required")
    active_id = f"bg00bu-active-{uuid.uuid4().hex[:10]}"
    with connect(SCOPE) as conn:
        assert conn.execute("SELECT current_database() AS db").fetchone()["db"] == CLONE
        assert conn.execute("SELECT current_user AS role").fetchone()["role"] == "aos_runtime"
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_116"
        conn.execute(
            "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
            "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, active_id),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="NETWORK_ACTIVATION_CONSUMPTION_REQUIRED"):
            conn.execute(
                "INSERT INTO aip_network_policy_revision(org_id,project_id,policy_id,revision,content_hash,"
                "lifecycle,effective_from,effective_until,payload,created_by) "
                "VALUES(%s,%s,%s,1,%s,'active',%s,%s,'{}'::jsonb,'test-only')",
                (*SCOPE.key, active_id, "a" * 64, datetime.now(UTC), datetime.now(UTC) + timedelta(hours=1)),
            )
        conn.rollback()
    draft_id = f"bg00bu-draft-{uuid.uuid4().hex[:10]}"
    with connect(SCOPE) as conn:
        conn.execute(
            "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
            "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, draft_id),
        )
        conn.execute(
            "INSERT INTO aip_network_policy_revision(org_id,project_id,policy_id,revision,content_hash,"
            "lifecycle,effective_from,effective_until,payload,created_by) "
            "VALUES(%s,%s,%s,1,%s,'draft',%s,%s,'{}'::jsonb,'test-only')",
            (*SCOPE.key, draft_id, "b" * 64, datetime.now(UTC), datetime.now(UTC) + timedelta(hours=1)),
        )
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_network_policy_revision WHERE policy_id=%s", (draft_id,),
        ).fetchone()["n"] == 1
        conn.rollback()
    with connect(SCOPE) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_network_policy_revision WHERE policy_id IN (%s,%s)",
            (active_id, draft_id),
        ).fetchone()["n"] == 0
