"""Isolated PostgreSQL rejection gates; no original or fixture group is closed."""

import os
from uuid import uuid4

import psycopg
from psycopg import IsolationLevel
from psycopg.types.json import Jsonb
import pytest

from test_a0v_w5c4w_stalled_owner_contract import request


def call(*, maintainer, serializable, actor="fixture-admin", maintainer_session=False):
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        if serializable:
            conn.isolation_level = IsolationLevel.SERIALIZABLE
        if maintainer_session:
            conn.execute("SET SESSION AUTHORIZATION aos_extension_maintainer")
        conn.execute("SELECT set_config('aos.org_id','dev-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        if maintainer:
            conn.execute("SET LOCAL ROLE aos_extension_maintainer")
        wire = request(groupId=str(uuid4()), idempotencyKey="w5c4x-fixture-reject")
        conn.execute("SELECT public.pipeline_snapshot_stalled_group_close_a0v_091(%s,%s)",
                     (Jsonb(wire), actor))


@pytest.mark.parametrize("maintainer,serializable", ((False, True), (True, False)))
def test_stalled_owner_rejects_missing_role_or_isolation(maintainer, serializable):
    with pytest.raises(psycopg.Error) as caught:
        call(maintainer=maintainer, serializable=serializable)
    assert caught.value.sqlstate == "42501"


def test_stalled_owner_rejects_absent_current_admin():
    with pytest.raises(psycopg.Error) as caught:
        call(maintainer=True, serializable=True, maintainer_session=True)
    assert caught.value.sqlstate == "42501"
    assert caught.value.diag.message_primary == "current stalled snapshot closure administrator required"


def test_stalled_owner_rejects_missing_exact_original_claim():
    actor = "fixture-stalled-admin-" + uuid4().hex
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES('dev-org','isolated fixture') "
                     "ON CONFLICT(id) DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) "
                     "VALUES('dev-org','dev-project','isolated fixture') "
                     "ON CONFLICT(org_id,project_id) DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) "
                     "VALUES('dev-org','dev-project',%s,'admin')", (actor,))
    with pytest.raises(psycopg.Error) as caught:
        call(maintainer=True, serializable=True, actor=actor, maintainer_session=True)
    assert caught.value.sqlstate == "40001"
    assert caught.value.diag.message_primary == "exact snapshot schedule claim required"


def test_rejected_calls_leave_no_closure_receipt():
    with psycopg.connect(os.environ["AOS_DATABASE_URL"]) as conn:
        conn.execute("SELECT set_config('aos.org_id','dev-org',true),"
                     "set_config('aos.project_id','dev-project',true)")
        count = conn.execute("SELECT count(*) FROM pipeline_snapshot_stalled_group_closure_receipt "
                             "WHERE org_id='dev-org' AND project_id='dev-project'").fetchone()[0]
    assert count == 0
