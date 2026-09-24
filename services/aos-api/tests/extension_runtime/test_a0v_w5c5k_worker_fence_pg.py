"""Disposable-PG worker fence primitive; no production worker is wired."""

from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

from test_a0v_w5c5i_host_lease_pg import host_lease_case, _acquire


@pytest.fixture
def fence_case(host_lease_case):
    admin_dsn, directory_dsn, org, project, host = host_lease_case
    role = "aos_fence_runtime_" + uuid4().hex[:12]
    password = "isolated-" + uuid4().hex[:12]
    parts = conninfo_to_dict(admin_dsn)
    runtime_dsn = make_conninfo(**{**parts, "user": role, "password": password})
    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS NOINHERIT")
                      .format(sql.Identifier(role), sql.Literal(password)))
        admin.execute(sql.SQL("GRANT aos_runtime TO {}").format(sql.Identifier(role)))
    try:
        yield admin_dsn, directory_dsn, runtime_dsn, org, project, host
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))


def _fence(dsn, org, project, token, epoch):
    with psycopg.connect(dsn, autocommit=True) as conn:
        with conn.transaction():
            conn.execute("SET ROLE aos_runtime")
            conn.execute("SELECT set_config('aos.org_id',%s,true),"
                         "set_config('aos.project_id',%s,true)", (org, project))
            return conn.execute(
                "SELECT extension_runtime_host_lease_worker_fence_a0v_094(%s,%s,%s,%s)",
                (org, project, token, epoch),
            ).fetchone()[0]


def test_exact_current_holder_and_runtime_role_only(fence_case):
    admin, directory, runtime, org, project, _ = fence_case
    token = uuid4()
    epoch, expiry = _acquire(directory, org, project, token)
    assert _fence(runtime, org, project, token, epoch) == expiry
    with psycopg.connect(runtime, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM extension_runtime_host_lease_a0v_093")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        _fence(directory, org, project, token, epoch)
    with psycopg.connect(admin, autocommit=True) as conn:
        assert conn.execute("SELECT has_function_privilege('aos_extension_directory',"
            "'public.extension_runtime_host_lease_worker_fence_a0v_094(text,text,uuid,bigint)',"
            "'EXECUTE')").fetchone()[0] is False


def test_missing_wrong_and_expired_holder_fail_closed(fence_case):
    admin, directory, runtime, org, project, _ = fence_case
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _fence(runtime, org, project, uuid4(), 1)
    token = uuid4()
    epoch, _ = _acquire(directory, org, project, token)
    for wrong_token, wrong_epoch in ((uuid4(), epoch), (token, epoch + 1)):
        with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
            _fence(runtime, org, project, wrong_token, wrong_epoch)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("UPDATE extension_runtime_host_lease_a0v_093 "
                     "SET expires_at=clock_timestamp()-interval '1 second' "
                     "WHERE org_id=%s AND project_id=%s", (org, project))
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _fence(runtime, org, project, token, epoch)


def test_scope_and_assignment_drift_rejected(fence_case):
    admin, directory, runtime, org, project, _ = fence_case
    token = uuid4()
    epoch, _ = _acquire(directory, org, project, token)
    with psycopg.connect(runtime, autocommit=True) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("SET ROLE aos_runtime")
                conn.execute("SELECT set_config('aos.org_id',%s,true),"
                             "set_config('aos.project_id',%s,true)", (org, "other-project"))
                conn.execute("SELECT extension_runtime_host_lease_worker_fence_a0v_094(%s,%s,%s,%s)",
                             (org, project, token, epoch))
    with psycopg.connect(admin, autocommit=True) as conn:
        assert conn.execute("SELECT extension_runtime_set_host_assignment("
                            "%s,%s,NULL,'revoked',1,'test',%s,%s)",
                            (org, project, "revoke-" + project,
                             "sha256:" + "c" * 64)).fetchone()[0] == 2
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _fence(runtime, org, project, token, epoch)


def test_directory_role_oid_drift_rejected(fence_case):
    admin, directory, runtime, org, project, host = fence_case
    token = uuid4()
    epoch, _ = _acquire(directory, org, project, token)
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute("UPDATE extension_runtime_host_identity SET database_role_oid=0 "
                     "WHERE host_id=%s", (host,))
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        _fence(runtime, org, project, token, epoch)


def test_guard_blocks_release_until_worker_transaction_exits(fence_case):
    _, directory, runtime, org, project, _ = fence_case
    token = uuid4()
    epoch, _ = _acquire(directory, org, project, token)
    with psycopg.connect(runtime, autocommit=True) as worker:
        with worker.transaction():
            worker.execute("SET ROLE aos_runtime")
            worker.execute("SELECT set_config('aos.org_id',%s,true),"
                           "set_config('aos.project_id',%s,true)", (org, project))
            worker.execute("SELECT extension_runtime_host_lease_worker_fence_a0v_094(%s,%s,%s,%s)",
                           (org, project, token, epoch))
            with psycopg.connect(directory, autocommit=True) as holder:
                holder.execute("SET lock_timeout='200ms'")
                holder.execute("SET ROLE aos_extension_directory")
                holder.execute("SELECT set_config('aos.org_id',%s,false),"
                               "set_config('aos.project_id',%s,false)", (org, project))
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    holder.execute("SELECT extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
                                   (org, project, token, epoch))
    with psycopg.connect(directory, autocommit=True) as holder:
        holder.execute("SET ROLE aos_extension_directory")
        holder.execute("SELECT set_config('aos.org_id',%s,false),"
                       "set_config('aos.project_id',%s,false)", (org, project))
        holder.execute("SELECT extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
                       (org, project, token, epoch))
