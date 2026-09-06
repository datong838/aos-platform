from types import SimpleNamespace

import pytest
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.runtime_identity import (
    RuntimeDatabaseIdentity,
    probe_runtime_database_identity,
    require_isolated_runtime_identities,
)


def _identity(name, oid, *, directory=False, runtime=False, privileged=False, owner=False, authority=("127.0.0.1",5432,"aos")):
    return RuntimeDatabaseIdentity(authority, name, oid, directory, runtime, privileged, owner)


def test_three_database_planes_require_distinct_least_privilege_memberships():
    require_isolated_runtime_identities(
        directory=_identity("directory", 1, directory=True),
        runtime=_identity("runtime", 2, runtime=True),
        web=_identity("web", 3),
    )


@pytest.mark.parametrize("case", ["same", "authority", "privileged", "owner", "directory", "runtime", "web"])
def test_database_plane_preflight_rejects_aliases_and_role_overlap(case):
    directory = _identity("directory", 1, directory=True)
    runtime = _identity("runtime", 2, runtime=True)
    web = _identity("web", 3)
    if case == "same": runtime = _identity("directory", 1, runtime=True)
    if case == "authority": runtime = _identity("runtime", 2, runtime=True, authority=("127.0.0.1",5432,"other"))
    if case == "privileged": web = _identity("web", 3, privileged=True)
    if case == "owner": runtime = _identity("runtime", 2, runtime=True, owner=True)
    if case == "directory": directory = _identity("directory", 1)
    if case == "runtime": runtime = _identity("runtime", 2, directory=True, runtime=True)
    if case == "web": web = _identity("web", 3, directory=True)
    with pytest.raises(RuntimeError):
        require_isolated_runtime_identities(directory=directory, runtime=runtime, web=web)


class _Transaction:
    def __enter__(self): return self
    def __exit__(self, *_): return False


class _ProbeConnection:
    def __init__(self, row, status=TransactionStatus.IDLE):
        self.row = row
        self.info = SimpleNamespace(transaction_status=status)
        self.args = None
    def transaction(self): return _Transaction()
    def execute(self, statement, args): self.args=(statement,args); return self
    def fetchone(self): return self.row


def test_database_identity_probe_uses_observed_principal_not_dsn_text():
    row = dict(server_addr="127.0.0.1",server_port=5432,database_name="aos",
               session_user="runtime",current_user="runtime",role_oid=7,
               rolsuper=False,rolbypassrls=False,directory_member=False,
               runtime_member=True,protected_relation_count=1,
               owns_protected_relation=False)
    conn = _ProbeConnection(row)
    identity = probe_runtime_database_identity(conn, protected_relations=("extension_runtime_binding",))
    assert identity == _identity("runtime", 7, runtime=True)
    assert conn.args[1] == (["extension_runtime_binding"], ["extension_runtime_binding"])


def test_database_identity_probe_rejects_adopted_or_busy_connection():
    row = dict(server_addr="127.0.0.1",server_port=5432,database_name="aos",
               session_user="runtime",current_user="aos_runtime",role_oid=7,
               rolsuper=False,rolbypassrls=False,directory_member=False,
               runtime_member=True,protected_relation_count=1,
               owns_protected_relation=False)
    with pytest.raises(RuntimeError, match="adopted"):
        probe_runtime_database_identity(_ProbeConnection(row), protected_relations=("x",))
    with pytest.raises(RuntimeError, match="idle"):
        probe_runtime_database_identity(_ProbeConnection(row,status=TransactionStatus.INTRANS), protected_relations=("x",))


def test_database_identity_probe_rejects_missing_or_duplicate_protected_relations():
    row = dict(server_addr="127.0.0.1",server_port=5432,database_name="aos",
               session_user="runtime",current_user="runtime",role_oid=7,
               rolsuper=False,rolbypassrls=False,directory_member=False,
               runtime_member=True,protected_relation_count=0,
               owns_protected_relation=False)
    with pytest.raises(RuntimeError, match="relation is unavailable"):
        probe_runtime_database_identity(_ProbeConnection(row), protected_relations=("missing",))
    with pytest.raises(ValueError, match="duplicate"):
        probe_runtime_database_identity(
            _ProbeConnection(row), protected_relations=("duplicate", "duplicate")
        )
