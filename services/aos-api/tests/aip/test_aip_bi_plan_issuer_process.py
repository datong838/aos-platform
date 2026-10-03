"""The BI listener cannot exist before its separate identity gates pass."""

from dataclasses import replace
from contextlib import nullcontext
import os

import pytest

from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


@pytest.fixture
def config(tmp_path):
    from aos_api.aip_bi_plan_issuer_process import BIIssuerProcessConfig
    socket_dir = tmp_path / "socket"; socket_dir.mkdir(mode=0o750)
    attempt_dir = tmp_path / "attempt"; attempt_dir.mkdir(mode=0o700)
    credential_dir = tmp_path / "credential"; credential_dir.mkdir(mode=0o700)
    passfile = credential_dir / "issuer.pgpass"; passfile.write_text("test-only\n")
    passfile.chmod(0o600)
    database = BIIssuerDatabaseConfig("127.0.0.1", 18435, "aos_test_bi_ti4_test", passfile)
    return BIIssuerProcessConfig(
        socket_path=socket_dir / "issuer.sock", api_uid=os.geteuid()+1,
        issuer_uid=os.geteuid(), ipc_gid=os.getegid(), database=database,
        scope=SCOPE, attempt_directory=attempt_dir,
        max_connections=1, accept_timeout=0.2)


@pytest.mark.parametrize("changes", [
    {"api_uid": os.geteuid()}, {"issuer_uid": os.geteuid()+1},
    {"ipc_gid": os.getegid()+1}, {"scope": None},
    {"max_connections": 0}, {"max_connections": 65},
    {"accept_timeout": float("nan")}, {"accept_timeout": 31},
    {"socket_path": "relative.sock"}, {"attempt_directory": "relative"},
])
def test_config_rejects_nonisolated_or_unbounded_start(config, changes):
    from aos_api.aip_bi_plan_issuer_process import BIIssuerProcessBlocked
    with pytest.raises(BIIssuerProcessBlocked):
        replace(config, **changes)
    assert not config.socket_path.exists()


def test_missing_external_oidc_cannot_create_socket(config, monkeypatch):
    from aos_api import aip_bi_plan_issuer_process as process
    monkeypatch.setattr(process, "_require_external_oidc_config",
                        lambda: (_ for _ in ()).throw(ValueError("no IdP")))
    monkeypatch.setattr(process, "connect_bi_issuer_read_only",
                        lambda *a: pytest.fail("DB opened before IdP"))
    with pytest.raises(process.BIIssuerProcessBlocked):
        with process.bi_issuer_listener(config):
            pytest.fail("listener opened")
    assert not config.socket_path.exists()


def test_missing_private_attempt_cannot_open_db_or_socket(config, monkeypatch):
    from aos_api import aip_bi_plan_issuer_process as process
    monkeypatch.setattr(process, "_require_external_oidc_config", lambda: None)
    monkeypatch.setattr(process, "connect_bi_issuer_read_only",
                        lambda *a: pytest.fail("DB opened before attempt check"))
    config.attempt_directory.rmdir()
    with pytest.raises(process.BIIssuerProcessBlocked):
        with process.bi_issuer_listener(config):
            pytest.fail("listener opened")
    assert not config.socket_path.exists()


def test_missing_bi_database_identity_cannot_create_socket(config, monkeypatch):
    from aos_api import aip_bi_plan_issuer_process as process
    monkeypatch.setattr(process, "_require_external_oidc_config", lambda: None)
    monkeypatch.setattr(process, "open_private_issuer_listener",
                        lambda *a, **kw: pytest.fail("socket opened before DB identity"))
    with pytest.raises(process.BIIssuerProcessBlocked):
        with process.bi_issuer_listener(config):
            pytest.fail("listener opened")
    assert not config.socket_path.exists()


def test_wrong_socket_directory_is_rejected_before_bind(config, monkeypatch):
    """A stub read connection only reaches the negative path ownership gate."""
    from aos_api import aip_bi_plan_issuer_process as process
    class ReadOnlyProbe:
        def execute(self, statement):
            assert statement == "SELECT 1"
    monkeypatch.setattr(process, "_require_external_oidc_config", lambda: None)
    monkeypatch.setattr(process, "connect_bi_issuer_read_only",
                        lambda *a: nullcontext(ReadOnlyProbe()))
    config.socket_path.parent.chmod(0o700)
    with pytest.raises(process.BIIssuerProcessBlocked):
        with process.bi_issuer_listener(config):
            pytest.fail("listener opened")
    assert not config.socket_path.exists()


def test_finite_process_rejects_missing_signed_source_before_listener(config, tmp_path, monkeypatch):
    from aos_api import aip_bi_plan_issuer_process as process
    monkeypatch.setattr(process, "bi_issuer_listener",
                        lambda _: pytest.fail("listener opened before signed source"))
    with pytest.raises(process.BIIssuerProcessBlocked,
                       match="BI_ISSUER_SIGNED_SOURCE_REQUIRED"):
        process.run_bi_issuer_process(
            config, release_root=tmp_path / "missing",
            trust_roots=None, source_alias="a0v-growth-113")
    assert not config.socket_path.exists()


def test_finite_process_accepts_once_and_stops_at_timeout(config, tmp_path, monkeypatch):
    from aos_api import aip_bi_plan_issuer_process as process
    config = replace(config, max_connections=2)
    class Trust:
        def snapshot(self):
            return self
    class Connection:
        closed = False
        def close(self):
            self.closed = True
    conn = Connection()
    class Listener:
        calls = 0
        def settimeout(self, value):
            assert value == config.accept_timeout
        def accept(self):
            self.calls += 1
            if self.calls == 1:
                return conn, None
            raise TimeoutError()
    listener = Listener()
    monkeypatch.setattr(process, "bi_issuer_listener", lambda _: nullcontext(listener))
    seen = []
    monkeypatch.setattr(process, "serve_one_bi_issuer_connection", lambda c, **kw:
                        (seen.append((c, kw["expected_scope"])) or True))
    result = process.run_bi_issuer_process(
        config, release_root=tmp_path, trust_roots=Trust(),
        source_alias="a0v-growth-113")
    assert result == {"accepted": 1, "processed": 1}
    assert seen == [(conn, SCOPE)] and conn.closed is True
    assert listener.calls == 2
