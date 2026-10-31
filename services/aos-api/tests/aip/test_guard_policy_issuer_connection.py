from pathlib import Path

import pytest


class Result:
    def __init__(self, row=None): self.row = row
    def fetchone(self): return self.row


class FakeConnection:
    def __init__(self, row):
        self.row = row
        self.read_only = None
        self.isolation_level = None
        self.statements = []
        self.commits = 0

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        return Result(self.row if "current_database()" in statement else None)
    def commit(self): self.commits += 1
    def rollback(self): pass


def private_config(tmp_path):
    from aos_api.aip_guard_policy_issuer_connection import GuardIssuerDatabaseConfig
    tmp_path.chmod(0o700)
    passfile = tmp_path / "pgpass"
    passfile.write_text("not-a-real-secret\n")
    passfile.chmod(0o600)
    return GuardIssuerDatabaseConfig(host="127.0.0.1", port=15432,
        database="aos_guard_isolated", passfile=passfile)


def identity(*, read_only):
    return {
        "db": "aos_guard_isolated", "login": "aos_guard_approval_issuer", "role": "aos_runtime",
        "org_id": "org-org", "project_id": "dev-project",
        "isolation": "repeatable read" if read_only else "serializable",
        "statement_timeout_ms": 10000, "lock_timeout_ms": 5000, "idle_timeout_ms": 10000,
        "rolcanlogin": True, "rolsuper": False, "rolbypassrls": False, "rolinherit": False,
        "rolcreatedb": False, "rolcreaterole": False, "rolreplication": False,
        "owner_member": False, "extra_roles": False,
    }


@pytest.mark.parametrize("read_only", [True, False])
def test_guard_connection_binds_exact_role_scope_and_transaction(tmp_path, monkeypatch, read_only):
    from aos_api.tenant_scope import TenantScope
    from aos_api import aip_guard_policy_issuer_connection as target
    config = private_config(tmp_path)
    conn = FakeConnection(identity(read_only=read_only))
    monkeypatch.setattr(target, "connect", lambda **kwargs: conn)
    for name in target._FORBIDDEN: monkeypatch.delenv(name, raising=False)
    with target.connect_guard_issuer(config, TenantScope("org-org", "dev-project"), read_only) as opened:
        assert opened.read_only is read_only
        assert any("SET LOCAL ROLE aos_runtime" in statement for statement, _ in conn.statements)
        if not read_only:
            opened.commit()
            assert conn.commits == 1
            assert sum("SET LOCAL ROLE aos_runtime" in statement for statement, _ in conn.statements) == 2


def test_guard_connection_rejects_privilege_or_environment_drift(tmp_path, monkeypatch):
    from aos_api.tenant_scope import TenantScope
    from aos_api import aip_guard_policy_issuer_connection as target
    config = private_config(tmp_path)
    unsafe = identity(read_only=True)
    unsafe["rolsuper"] = True
    monkeypatch.setattr(target, "connect", lambda **kwargs: FakeConnection(unsafe))
    for name in target._FORBIDDEN: monkeypatch.delenv(name, raising=False)
    with pytest.raises(target.GuardIssuerDatabaseBlocked, match="IDENTITY_REQUIRED"):
        with target.connect_guard_issuer(config, TenantScope("org-org", "dev-project"), True): pass
    monkeypatch.setenv("PGOPTIONS", "-c role=aos_app")
    with pytest.raises(target.GuardIssuerDatabaseBlocked, match="EXACT_CONNECTION_REQUIRED"):
        with target.connect_guard_issuer(config, TenantScope("org-org", "dev-project"), True): pass


def test_guard_connection_config_rejects_non_private_passfile(tmp_path):
    from aos_api.aip_guard_policy_issuer_connection import GuardIssuerDatabaseBlocked, GuardIssuerDatabaseConfig
    tmp_path.chmod(0o700)
    passfile = tmp_path / "pgpass"
    passfile.write_text("x")
    passfile.chmod(0o644)
    with pytest.raises(GuardIssuerDatabaseBlocked, match="PRIVATE_CREDENTIAL_REQUIRED"):
        GuardIssuerDatabaseConfig(host="127.0.0.1", port=15432,
            database="aos_guard_isolated", passfile=passfile)
