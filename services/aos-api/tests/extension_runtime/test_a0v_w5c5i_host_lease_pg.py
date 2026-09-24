"""Disposable PG contract for opt-in Host leases; production Host remains unwired."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest


@pytest.fixture
def host_lease_case():
    suffix = uuid4().hex[:12]
    role = "aos_lease_test_" + suffix
    password = "isolated-" + suffix
    org, project, host = "dev-org", "lease-" + suffix, "host-" + suffix
    dsn = os.environ["AOS_DATABASE_URL"]  # session-scoped disposable aos_test_* database
    parts = conninfo_to_dict(dsn)
    role_dsn = make_conninfo(**{**parts, "user": role, "password": password})
    with psycopg.connect(dsn, autocommit=True) as admin:
        assert admin.info.dbname.startswith("aos_test_")
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOINHERIT")
                      .format(sql.Identifier(role), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT aos_extension_directory TO {}").format(sql.Identifier(role)))
        admin.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES(%s,%s,'lease-test')",
                      (org, project))
        assert admin.execute("SELECT extension_runtime_bind_host_identity(%s,%s,true,0,'test',%s,%s)",
                             (role, host, "bind-" + suffix, "sha256:" + "a" * 64)).fetchone()[0] == 1
        assert admin.execute("SELECT extension_runtime_set_host_assignment(%s,%s,%s,'assigned',0,'test',%s,%s)",
                             (org, project, host, "assign-" + suffix,
                              "sha256:" + "b" * 64)).fetchone()[0] == 1
    try:
        yield dsn, role_dsn, org, project, host
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def _scope(conn, org, project):
    conn.execute("SET ROLE aos_extension_directory")
    conn.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",
                 (org, project))


def _acquire(dsn, org, project, token, ttl=30):
    with psycopg.connect(dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        return conn.execute("SELECT epoch,expires_at FROM "
                            "extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,%s)",
                            (org, project, token, ttl)).fetchone()


def test_empty_by_default_and_exact_holder_lifecycle(host_lease_case):
    admin_dsn, role_dsn, org, project, host = host_lease_case
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SELECT count(*) FROM extension_runtime_host_lease_a0v_093 "
                             "WHERE org_id=%s AND project_id=%s", (org, project)).fetchone()[0] == 0
    token = uuid4()
    epoch, expiry = _acquire(role_dsn, org, project, token)
    assert epoch == 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        saved_hash = admin.execute("SELECT token_hash FROM extension_runtime_host_lease_a0v_093 "
                                   "WHERE org_id=%s AND project_id=%s", (org, project)).fetchone()[0]
        assert saved_hash.startswith("sha256:") and str(token) not in saved_hash
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM extension_runtime_host_lease_a0v_093")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            conn.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,30)",
                         (org, project, uuid4()))
        newer = conn.execute("SELECT extension_runtime_host_lease_renew_a0v_093(%s,%s,%s,%s,30)",
                             (org, project, token, epoch)).fetchone()[0]
        assert newer >= expiry
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            conn.execute("SELECT extension_runtime_host_lease_renew_a0v_093(%s,%s,%s,%s,30)",
                         (org, project, uuid4(), epoch))
        conn.execute("SELECT extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
                     (org, project, token, epoch))
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            conn.execute("SELECT extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
                         (org, project, token, epoch))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE extension_runtime_host_lease_a0v_093 SET epoch=999")
    assert _acquire(role_dsn, org, project, uuid4())[0] == 2
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SELECT event_kind FROM extension_runtime_host_lease_event_a0v_093 "
                             "WHERE org_id=%s AND project_id=%s ORDER BY event_id",
                             (org, project)).fetchall() == [
                                 ("acquire",), ("renew",), ("release",), ("acquire",)]
        with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
            admin.execute("DELETE FROM extension_runtime_host_lease_event_a0v_093 "
                          "WHERE org_id=%s AND project_id=%s", (org, project))


def test_concurrent_acquire_has_one_winner(host_lease_case):
    _, role_dsn, org, project, _ = host_lease_case

    def attempt(_):
        try:
            return _acquire(role_dsn, org, project, uuid4())[0]
        except psycopg.errors.LockNotAvailable:
            return "held"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2)), key=str) == [1, "held"]


def test_expired_takeover_increments_epoch_and_old_holder_is_fenced(host_lease_case):
    admin_dsn, role_dsn, org, project, _ = host_lease_case
    old_token = uuid4()
    assert _acquire(role_dsn, org, project, old_token)[0] == 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                      "SET expires_at=clock_timestamp()-interval '1 second' "
                      "WHERE org_id=%s AND project_id=%s", (org, project))
    new_token = uuid4()
    assert _acquire(role_dsn, org, project, new_token)[0] == 2
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        for statement in (
            "SELECT extension_runtime_host_lease_renew_a0v_093(%s,%s,%s,%s,30)",
            "SELECT extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
        ):
            with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
                conn.execute(statement, (org, project, old_token, 1))


def test_scope_and_assignment_drift_fail_closed(host_lease_case):
    admin_dsn, role_dsn, org, project, host = host_lease_case
    token = uuid4()
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, "other-project")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,30)",
                         (org, project, token))
    assert _acquire(role_dsn, org, project, token)[0] == 1
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        assert admin.execute("SELECT extension_runtime_set_host_assignment(%s,%s,NULL,'revoked',1,'test',%s,%s)",
                             (org, project, "revoke-" + project,
                              "sha256:" + "c" * 64)).fetchone()[0] == 2
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            conn.execute("SELECT extension_runtime_host_lease_renew_a0v_093(%s,%s,%s,1,30)",
                         (org, project, token))


def test_runtime_role_and_superuser_cannot_bypass_directory_login(host_lease_case):
    admin_dsn, role_dsn, org, project, _ = host_lease_case
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("SELECT set_config('aos.org_id',%s,false),set_config('aos.project_id',%s,false)",
                      (org, project))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            admin.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,30)",
                          (org, project, uuid4()))
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            conn.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,31)",
                         (org, project, uuid4()))


def test_role_oid_drift_rejects_new_host_lease(host_lease_case):
    admin_dsn, role_dsn, org, project, _ = host_lease_case
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute("UPDATE extension_runtime_host_identity SET database_role_oid=0 "
                      "WHERE host_id=(SELECT host_id FROM extension_runtime_host_assignment "
                      "WHERE org_id=%s AND project_id=%s)", (org, project))
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        _scope(conn, org, project)
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            conn.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,30)",
                         (org, project, uuid4()))


def test_no_scope_cannot_acquire_and_runtime_role_has_no_execute(host_lease_case):
    admin_dsn, role_dsn, org, project, _ = host_lease_case
    with psycopg.connect(role_dsn, autocommit=True) as conn:
        conn.execute("SET ROLE aos_extension_directory")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,30)",
                         (org, project, uuid4()))
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        granted = admin.execute("SELECT has_function_privilege('aos_runtime',"
            "'public.extension_runtime_host_lease_acquire_a0v_093(text,text,uuid,integer)',"
            "'EXECUTE')").fetchone()[0]
        assert granted is False
