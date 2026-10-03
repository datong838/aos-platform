"""BI issuer must never inherit the ordinary API or runtime PostgreSQL login."""

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _private(tmp_path):
    parent = tmp_path / "issuer"; parent.mkdir(mode=0o700)
    secret = parent / "issuer.pgpass"; secret.write_text("local-test-placeholder\n")
    secret.chmod(0o600)
    return secret


def _config(tmp_path, **changes):
    from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
    raw = dict(host="127.0.0.1", port=18435, database="aos_test_bi_ti4_test",
               passfile=_private(tmp_path))
    raw.update(changes)
    return BIIssuerDatabaseConfig(**raw)


@pytest.mark.parametrize("changes", [
    {"host": "example.com"}, {"port": 0}, {"database": "aos-current;drop"},
])
def test_bi_db_config_requires_exact_local_database(tmp_path, changes):
    from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseBlocked
    with pytest.raises(BIIssuerDatabaseBlocked):
        _config(tmp_path, **changes)


def test_bi_db_config_rejects_unprotected_credential(tmp_path):
    from aos_api.aip_bi_plan_issuer_connection import (
        BIIssuerDatabaseBlocked, BIIssuerDatabaseConfig,
    )
    secret = _private(tmp_path)
    secret.chmod(0o644)
    with pytest.raises(BIIssuerDatabaseBlocked):
        BIIssuerDatabaseConfig("127.0.0.1", 18435, "aos_test_bi_ti4_test", secret)


def test_actual_disposable_owner_login_cannot_pass_bi_identity(tmp_path):
    from aos_api.aip_bi_plan_issuer_connection import (
        BIIssuerDatabaseBlocked, _require_identity,
    )
    config = _config(tmp_path)
    with psycopg.connect(get_dsn(), row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        with pytest.raises(BIIssuerDatabaseBlocked):
            _require_identity(conn, config, SCOPE, read_only=True)


def test_pg_environment_override_blocks_before_connection(tmp_path, monkeypatch):
    from aos_api.aip_bi_plan_issuer_connection import (
        BIIssuerDatabaseBlocked, connect_bi_issuer_read_only,
    )
    config = _config(tmp_path)
    monkeypatch.setenv("PGPASSWORD", "untrusted-test-value")
    with pytest.raises(BIIssuerDatabaseBlocked):
        with connect_bi_issuer_read_only(config, SCOPE):
            raise AssertionError("connection must not open")


def test_credential_is_rechecked_on_each_connection(tmp_path):
    from aos_api.aip_bi_plan_issuer_connection import (
        BIIssuerDatabaseBlocked, connect_bi_issuer_read_only,
    )
    config = _config(tmp_path)
    config.passfile.chmod(0o644)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with connect_bi_issuer_read_only(config, SCOPE):
            raise AssertionError("connection must not open")
