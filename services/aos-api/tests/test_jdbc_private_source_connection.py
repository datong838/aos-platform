from unittest.mock import MagicMock

import pytest

from aos_api import jdbc_connector_runtime as module
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime, SshTunnel


CONFIG = {"dbHost": "db.fixture", "database": "fixture", "username": "fixture-user", "secretRef": "fixture-secret"}


def tunnel_mock():
    tunnel = MagicMock()
    tunnel.open.return_value = 23456
    return tunnel


def connection():
    conn = MagicMock()
    conn.get_autocommit.return_value = True
    conn.cursor.return_value.__enter__.return_value.fetchall.return_value = [{"goods_id": 1}]
    return conn


@pytest.fixture
def private_environment(monkeypatch):
    tunnels, connections = {"existing": object()}, {"existing": object()}
    monkeypatch.setattr(module, "_TUNNEL_CACHE", tunnels)
    monkeypatch.setattr(module, "_CONN_CACHE", connections)
    def forbidden(*args, **kwargs): raise AssertionError("private mode must not use cache helpers")
    for name in ("_get_or_create_tunnel", "_get_or_create_conn", "_evict_cached_tunnel", "_evict_cached_conn"):
        monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(module, "_resolve_secret_value", lambda ref: "resolved-"+ref)
    return tunnels, connections


def test_private_connections_use_new_inputs_and_never_touch_cache(monkeypatch, private_environment):
    first, second = connection(), connection()
    connect = MagicMock(side_effect=[first, second])
    monkeypatch.setattr(module.pymysql, "connect", connect)
    before = [dict(cache) for cache in private_environment]
    for secret, conn in (("one", first), ("two", second)):
        with JdbcConnectorRuntime({**CONFIG, "secretRef": secret}, reuse_cache=False) as runtime:
            assert runtime.read_rows("ns_goods") == [{"goods_id": 1}]
            conn.close.assert_not_called()
        conn.close.assert_called_once_with()
        conn.rollback.assert_called_once_with()
    assert [call.kwargs["password"] for call in connect.call_args_list] == ["resolved-one", "resolved-two"]
    assert [dict(cache) for cache in private_environment] == before


def test_private_tunnel_and_connection_close_after_success(monkeypatch, private_environment):
    tunnel, conn = tunnel_mock(), connection()
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    build = MagicMock(return_value=module._CachedConn(conn=conn))
    monkeypatch.setattr(module, "_build_db_conn", build)
    runtime = JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False)
    with runtime:
        assert build.call_args.args[1:] == ("127.0.0.1", 23456)
        with pytest.raises(RuntimeError, match="already entered"): runtime.__enter__()
        assert runtime.read_rows("ns_goods")
    runtime.__exit__()
    conn.close.assert_called_once_with()
    tunnel.close.assert_called_once_with()
    assert runtime._conn is runtime._cached_conn is runtime._ssh_tunnel is None


@pytest.mark.parametrize("phase", ["db_build", "read", "read_interrupt"])
def test_private_failure_cleans_owned_resources_without_eviction(monkeypatch, private_environment, phase):
    tunnel, conn = tunnel_mock(), connection()
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    error = KeyboardInterrupt() if phase == "read_interrupt" else RuntimeError("fixture driver failure")
    if phase == "db_build":
        def build(*args): raise error
    else:
        def build(*args): return module._CachedConn(conn=conn)
        conn.cursor.return_value.__enter__.return_value.fetchall.side_effect = error
    monkeypatch.setattr(module, "_build_db_conn", build)
    with pytest.raises(type(error)):
        with JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False) as runtime:
            runtime.read_rows("ns_goods")
    tunnel.close.assert_called_once_with()
    if phase != "db_build": conn.close.assert_called_once_with()


def test_private_close_errors_do_not_expose_exception_text(monkeypatch, private_environment):
    conn, tunnel = connection(), tunnel_mock()
    conn.close.side_effect = RuntimeError("private-fixture-close-material")
    tunnel.close.side_effect = RuntimeError("private-fixture-tunnel-material")
    monkeypatch.setattr(module, "_build_db_conn", lambda *args: module._CachedConn(conn=conn))
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    log = MagicMock()
    monkeypatch.setattr(module, "log", log)
    with pytest.raises(RuntimeError, match="PRIVATE_RESOURCE_CLEANUP_FAILED"):
        with JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False): pass
    assert "private-fixture" not in repr(log.mock_calls)
    assert [call.args for call in log.warning.call_args_list] == [("PRIVATE_DB_CLOSE_FAILED",), ("PRIVATE_TUNNEL_CLOSE_FAILED",)]


def test_ssh_open_interruption_cleans_tunnel(monkeypatch):
    tunnel = SshTunnel(ssh_host="ssh.fixture", ssh_port=22, ssh_user="fixture-user",
        remote_host="db.fixture", remote_port=3306, ssh_password="fixture-password")
    monkeypatch.setattr(module, "_allocate_local_port", lambda: 23456)
    def fail(): raise KeyboardInterrupt()
    monkeypatch.setattr(tunnel, "_open_with_password", fail)
    close = MagicMock()
    monkeypatch.setattr(tunnel, "close", close)
    with pytest.raises(KeyboardInterrupt): tunnel.open()
    close.assert_called_once_with()


def test_password_ssh_targets_configured_remote_host(monkeypatch):
    tunnel = SshTunnel(ssh_host="ssh.fixture", ssh_port=22, ssh_user="fixture-user",
        remote_host="db.fixture", remote_port=3307, ssh_password="fixture-password")
    monkeypatch.setattr(module, "_allocate_local_port", lambda: 23456)
    popen = MagicMock()
    monkeypatch.setattr(module.subprocess, "Popen", popen)
    monkeypatch.setattr(tunnel, "_wait_ready", lambda: 23456)
    try:
        assert tunnel.open() == 23456
        command = popen.call_args.args[0]
        assert command[command.index("-L")+1] == "127.0.0.1:23456:db.fixture:3307"
    finally:
        tunnel.close()


@pytest.mark.parametrize("value", [0, 1, None, "false"])
def test_cache_mode_is_explicit_boolean(value):
    with pytest.raises(ValueError, match="boolean"): JdbcConnectorRuntime(CONFIG, reuse_cache=value)


def test_close_interruption_still_attempts_owned_tunnel(monkeypatch, private_environment):
    conn, tunnel = connection(), tunnel_mock()
    conn.close.side_effect = KeyboardInterrupt()
    monkeypatch.setattr(module, "_build_db_conn", lambda *args: module._CachedConn(conn=conn))
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    with pytest.raises(KeyboardInterrupt):
        with JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False): pass
    tunnel.close.assert_called_once_with()


@pytest.mark.parametrize("entry", ["close", "wait_ready"])
def test_tunnel_terminate_timeout_forces_kill_and_reap(monkeypatch, entry):
    tunnel = SshTunnel(ssh_host="ssh.fixture", ssh_port=22, ssh_user="fixture-user",
        remote_host="db.fixture", remote_port=3306, ssh_password="fixture-password")
    process = MagicMock()
    process.wait.side_effect = [module.subprocess.TimeoutExpired("fixture", 5), 0]
    process.stderr.read.return_value = b""
    tunnel._proc = process
    monkeypatch.setattr(module, "_TUNNEL_READY_RETRIES", 0)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    if entry == "close": tunnel.close()
    else:
        with pytest.raises(RuntimeError, match="failed to become ready"): tunnel._wait_ready()
    process.kill.assert_called_once_with()
    assert process.wait.call_count == 2 and tunnel._proc is None


def test_failed_process_reap_retains_owner_for_retry():
    tunnel = SshTunnel(ssh_host="ssh.fixture", ssh_port=22, ssh_user="fixture-user",
        remote_host="db.fixture", remote_port=3306, ssh_password="fixture-password")
    process = MagicMock()
    process.wait.side_effect = module.subprocess.TimeoutExpired("fixture", 5)
    tunnel._proc = process
    with pytest.raises(RuntimeError, match="SSH_PROCESS_CLEANUP_FAILED"): tunnel.close()
    assert tunnel._proc is process
    process.wait.side_effect = None
    process.wait.return_value = 0
    tunnel.close()
    assert tunnel._proc is None


def test_private_failed_close_retains_owner_and_blocks_read_until_cleanup(monkeypatch, private_environment):
    conn = connection()
    conn.close.side_effect = RuntimeError("fixture close failed")
    monkeypatch.setattr(module, "_build_db_conn", lambda *args: module._CachedConn(conn=conn))
    runtime = JdbcConnectorRuntime(CONFIG, reuse_cache=False)
    runtime.__enter__()
    with pytest.raises(RuntimeError, match="PRIVATE_RESOURCE_CLEANUP_FAILED"): runtime.__exit__()
    assert runtime._conn is conn
    with pytest.raises(RuntimeError, match="cleanup is pending"): runtime.read_rows("ns_goods")
    conn.close.side_effect = None
    runtime.__exit__()
    assert runtime._conn is None and not runtime._private_cleanup_pending


def test_private_owns_tunnel_before_open_failure_and_can_retry_cleanup(monkeypatch, private_environment):
    tunnel = tunnel_mock()
    tunnel.open.side_effect = RuntimeError("fixture open failure")
    tunnel.close.side_effect = [RuntimeError("fixture cleanup failure"), None]
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    runtime = JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False)
    with pytest.raises(RuntimeError, match="PRIVATE_RESOURCE_CLEANUP_FAILED"): runtime.__enter__()
    assert runtime._ssh_tunnel is tunnel
    runtime.__exit__()
    assert runtime._ssh_tunnel is None and tunnel.close.call_count == 2


@pytest.mark.parametrize("phase", ["enter", "read", "exit"])
def test_original_interruption_survives_cleanup_failure(monkeypatch, private_environment, phase):
    conn, tunnel = connection(), tunnel_mock()
    conn.close.side_effect = RuntimeError("fixture close failure")
    tunnel.close.side_effect = RuntimeError("fixture tunnel cleanup failure")
    if phase == "enter": tunnel.open.side_effect = KeyboardInterrupt()
    if phase == "read": conn.cursor.return_value.__enter__.return_value.fetchall.side_effect = KeyboardInterrupt()
    monkeypatch.setattr(module, "_construct_ssh_tunnel", lambda config: tunnel)
    monkeypatch.setattr(module, "_build_db_conn", lambda *args: module._CachedConn(conn=conn))
    with pytest.raises(KeyboardInterrupt):
        with JdbcConnectorRuntime({**CONFIG, "sshHost": "ssh.fixture"}, reuse_cache=False) as runtime:
            if phase == "read": runtime.read_rows("ns_goods")
            if phase == "exit": raise KeyboardInterrupt()
    assert tunnel.close.called


def test_ssh_original_interruption_survives_cleanup_failure(monkeypatch):
    tunnel = SshTunnel(ssh_host="ssh.fixture", ssh_port=22, ssh_user="fixture-user",
        remote_host="db.fixture", remote_port=3306, ssh_password="fixture-password")
    monkeypatch.setattr(module, "_allocate_local_port", lambda: 23456)
    def interrupt(): raise KeyboardInterrupt()
    monkeypatch.setattr(tunnel, "_open_with_password", interrupt)
    monkeypatch.setattr(tunnel, "close", MagicMock(side_effect=RuntimeError("fixture cleanup failure")))
    with pytest.raises(KeyboardInterrupt): tunnel.open()
