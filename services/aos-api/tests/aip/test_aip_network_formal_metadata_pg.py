"""Exact formal metadata and reserved-ID checks on an explicit disposable clone."""

import os
import uuid

import psycopg
import pytest

from aos_api.aip_network_policy_action_producer import _ACTION, _OBJECT
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope


CLONE = "aos_bg00bw_metadata_testonly_20260930"
SCOPE = TenantScope("org-org", "dev-project")


def test_formal_network_metadata_and_reserved_role_boundary():
    if os.environ.get("AOS_BG00BW_TEST_DATABASE") != CLONE:
        pytest.skip("explicit BG00bw disposable clone required")
    with psycopg.connect(get_dsn()) as owner:
        assert owner.info.dbname == CLONE
        assert owner.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "a0v_117"
        obj = owner.execute(
            "SELECT id,name,description,published,properties,required_markings "
            "FROM meta_object_type WHERE id=%s", (_OBJECT["id"],),
        ).fetchone()
        assert obj == (_OBJECT["id"], _OBJECT["name"], _OBJECT["description"],
                       _OBJECT["published"], _OBJECT["properties"], _OBJECT["requiredMarkings"])
        action = owner.execute(
            "SELECT id,name,object_type,parameters,required_markings,submission_criteria "
            "FROM meta_action_type WHERE id=%s", (_ACTION["id"],),
        ).fetchone()
        assert action == (_ACTION["id"], _ACTION["name"], _ACTION["objectType"],
                          _ACTION["parameters"], _ACTION["requiredMarkings"],
                          _ACTION["submissionCriteria"])
    with connect(SCOPE) as runtime:
        identity = runtime.execute("SELECT current_database() AS database,current_user AS role").fetchone()
        assert (identity["database"], identity["role"]) == (CLONE, "aos_runtime")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("UPDATE meta_object_type SET name='drift' WHERE id=%s", (_OBJECT["id"],))
        runtime.rollback()
    with connect(SCOPE) as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("DELETE FROM meta_object_type WHERE id=%s", (_OBJECT["id"],))
        runtime.rollback()
    with connect(SCOPE) as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("INSERT INTO meta_object_type(id,name) VALUES(%s,'drift')", (_OBJECT["id"],))
        runtime.rollback()
    with connect(SCOPE) as runtime:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            runtime.execute("UPDATE meta_action_type SET name='drift' WHERE id=%s", (_ACTION["id"],))
        runtime.rollback()
    ordinary = f"bg00bw-ordinary-{uuid.uuid4().hex[:8]}"
    with connect(SCOPE) as runtime:
        runtime.execute("INSERT INTO meta_object_type(id,name) VALUES(%s,'ordinary')", (ordinary,))
        assert runtime.execute("SELECT count(*) AS n FROM meta_object_type WHERE id=%s", (ordinary,)).fetchone()["n"] == 1
        runtime.rollback()
    with psycopg.connect(get_dsn()) as owner:
        assert owner.execute("SELECT count(*) FROM meta_object_type WHERE id=%s", (ordinary,)).fetchone()[0] == 0
        assert owner.execute(
            "SELECT t.tgenabled FROM pg_trigger t WHERE t.tgrelid='public.aip_network_policy_revision'::regclass "
            "AND t.tgname='aip_network_active_insert_guard'",
        ).fetchone() == ("O",)
