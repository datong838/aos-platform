"""D2.6 子任务 D: 通用 JDBC 连接器运行时单测 — SSH 隧道 + JDBC 连接 + Schema 发现 + 行流读取。

覆盖 JdbcConnectorRuntime 类（通用 SSH 隧道 + JDBC 连接器运行时）：

1. 构造与配置解析：从 dict config 初始化 ssh/db 连接参数
2. SSH 隧道建立（subprocess ssh -L）：mock subprocess.Popen 验证命令构造
3. JDBC 连接建立：mock pymysql.connect 验证 host/port 切换（隧道模式 → 127.0.0.1:local_port）
4. discover_schemas()：mock cursor 返回 information_schema 数据，验证 schema/table/column 树
5. read_rows()：mock cursor 返回行流，验证 SQL 构造与游标增量
6. __exit__：验证连接/隧道清理
7. 直连模式（无 sshHost）：跳过隧道，直接 pymysql.connect(db_host, db_port)
8. 失败降级：SSH 隧道建立失败 → 抛 RuntimeError（不静默）

设计原则（对齐用户指示）：
- SSH 隧道 + JDBC 通用化，不绑 niushop
- 使用 stdlib subprocess 调 ssh 命令，不引入 paramiko 依赖
- JDBC 连接保持 pymysql（与 ec_source_adapter 一致）

约束：
- 不实际连接数据库/SSH（全部 mock）
- 不破坏现有 ec_source_adapter 测试
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import aos_api.jdbc_connector_runtime as jdbc_runtime
from aos_api.jdbc_connector_runtime import JdbcConnectorRuntime, SshTunnel, _cleanup_all_cached


@pytest.fixture(autouse=True)
def _isolate_runtime_cache():
    """缓存是进程级能力；每个单测必须从独立连接状态起跑。"""
    _cleanup_all_cached()
    yield
    _cleanup_all_cached()


# ═══════════════════════════════════════════════
# Section A: 配置解析与构造
# ═══════════════════════════════════════════════


def test_jdbc_runtime_parses_ssh_mysql_config() -> None:
    """G1 配置解析：sshHost + dbHost + database + username + secretRef 都能正确解析。"""
    config = {
        "sshHost": "ssh.example.com",
        "sshPort": 22,
        "sshUser": "tunnel_user",
        "sshKeyRef": "vault://secrets/ssh_key",
        "dbHost": "mysql.internal",
        "dbPort": 3306,
        "database": "niushop_b2c_v5",
        "username": "recommend_ro",
        "secretRef": "vault://secrets/db_creds",
    }
    rt = JdbcConnectorRuntime(config)
    assert rt.ssh_host == "ssh.example.com"
    assert rt.ssh_port == 22
    assert rt.ssh_user == "tunnel_user"
    assert rt.ssh_key_ref == "vault://secrets/ssh_key"
    assert rt.db_host == "mysql.internal"
    assert rt.db_port == 3306
    assert rt.database == "niushop_b2c_v5"
    assert rt.username == "recommend_ro"
    assert rt.secret_ref == "vault://secrets/db_creds"


def test_jdbc_runtime_defaults_optional_fields() -> None:
    """G1 可选字段缺省：sshPort=22, dbPort=3306。"""
    config = {
        "sshHost": "ssh.example.com",
        "sshUser": "user",
        "dbHost": "mysql.internal",
        "database": "db",
        "username": "u",
    }
    rt = JdbcConnectorRuntime(config)
    assert rt.ssh_port == 22
    assert rt.db_port == 3306


def test_jdbc_runtime_direct_mode_when_no_ssh_host() -> None:
    """G1 直连模式：无 sshHost → 不建立隧道，直接用 dbHost/dbPort 连接。"""
    config = {
        "dbHost": "mysql.prod.internal",
        "dbPort": 3306,
        "database": "db",
        "username": "u",
        "secretRef": "vault://secrets/db",
    }
    rt = JdbcConnectorRuntime(config)
    assert rt.ssh_host is None
    assert rt._ssh_tunnel is None
    assert rt.db_host == "mysql.prod.internal"


# ═══════════════════════════════════════════════
# Section B: SSH 隧道建立
# ═══════════════════════════════════════════════


@patch("aos_api.jdbc_connector_runtime._is_port_open", return_value=True)
@patch("aos_api.jdbc_connector_runtime.subprocess.Popen")
@patch("aos_api.jdbc_connector_runtime.time.sleep")
def test_ssh_tunnel_opens_with_correct_command(
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
    mock_port_open: MagicMock,
) -> None:
    """G2 SSH 隧道使用由 AOS 持有的 ``ssh -N`` 子进程。"""
    proc_mock = MagicMock()
    proc_mock.poll.return_value = None  # 进程存活
    proc_mock.pid = 12345
    mock_popen.return_value = proc_mock

    tunnel = SshTunnel(
        ssh_host="ssh.example.com",
        ssh_port=22,
        ssh_user="tunnel_user",
        ssh_key_path="/tmp/test_key",
        remote_host="mysql.internal",
        remote_port=3306,
    )
    local_port = tunnel.open()

    # 验证 ssh 命令构造
    mock_popen.assert_called_once()
    cmd_args = mock_popen.call_args[0][0]
    assert cmd_args[0] == "ssh"
    assert "-L" in cmd_args
    assert "-N" in cmd_args
    assert "-f" not in cmd_args
    assert "-fN" not in cmd_args
    assert "-p" in cmd_args
    # user 与 host 合并为 user@host 字符串
    assert any("tunnel_user@ssh.example.com" == a for a in cmd_args), \
        f"user@host missing in {cmd_args}"

    # 验证本地端口分配
    assert isinstance(local_port, int)
    assert 1024 <= local_port <= 65535


@patch("aos_api.jdbc_connector_runtime.subprocess.Popen")
@patch("aos_api.jdbc_connector_runtime.time.sleep")
def test_ssh_tunnel_raises_on_failure(
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
) -> None:
    """G2 SSH 隧道建立失败 → 抛 RuntimeError（不静默）。

    子进程立即退出（returncode=1） → RuntimeError。
    """
    proc_mock = MagicMock()
    proc_mock.poll.return_value = 1  # 进程立即退出
    proc_mock.stderr.read.return_value = b"Permission denied (publickey)"
    mock_popen.return_value = proc_mock

    tunnel = SshTunnel(
        ssh_host="ssh.example.com",
        ssh_port=22,
        ssh_user="tunnel_user",
        ssh_key_path="/tmp/test_key",
        remote_host="mysql.internal",
        remote_port=3306,
    )
    with pytest.raises(RuntimeError, match="SSH tunnel"):
        tunnel.open()
    proc_mock.terminate.assert_called_once()


@patch("aos_api.jdbc_connector_runtime._is_port_open", return_value=False)
@patch("aos_api.jdbc_connector_runtime.subprocess.Popen")
@patch("aos_api.jdbc_connector_runtime.time.sleep")
def test_ssh_tunnel_timeout_cleans_owned_process(
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
    mock_port_open: MagicMock,
) -> None:
    """G2 就绪超时后必须清理子进程，不留脱管隧道。"""
    proc_mock = MagicMock()
    proc_mock.poll.return_value = None
    mock_popen.return_value = proc_mock
    tunnel = SshTunnel(
        ssh_host="ssh.example.com",
        ssh_port=2222,
        ssh_user="tunnel_user",
        ssh_key_path="/tmp/test_key",
        remote_host="mysql.internal",
        remote_port=3306,
    )

    with pytest.raises(RuntimeError, match="failed to become ready"):
        tunnel.open()

    proc_mock.terminate.assert_called_once()
    proc_mock.wait.assert_called_once_with(timeout=5)


# ═══════════════════════════════════════════════
# Section C: JDBC 连接建立（SSH 隧道模式）
# ═══════════════════════════════════════════════


@patch("aos_api.jdbc_connector_runtime._is_port_open", return_value=True)
@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
@patch("aos_api.jdbc_connector_runtime.subprocess.Popen")
@patch("aos_api.jdbc_connector_runtime.time.sleep")
def test_jdbc_runtime_connects_via_tunnel(
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
    mock_pymysql_connect: MagicMock,
    mock_port_open: MagicMock,
) -> None:
    """G3 SSH 隧道模式：__enter__ → 建隧道 → pymysql.connect 用 127.0.0.1:local_port。"""
    proc_mock = MagicMock()
    proc_mock.poll.return_value = None
    proc_mock.pid = 12345
    mock_popen.return_value = proc_mock
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn

    config = {
        "sshHost": "ssh.example.com",
        "sshUser": "tunnel_user",
        "sshKeyRef": "vault://secrets/ssh_key",
        "dbHost": "mysql.internal",
        "dbPort": 3306,
        "database": "niushop_b2c_v5",
        "username": "recommend_ro",
        "secretRef": "vault://secrets/db_creds",
    }
    rt = JdbcConnectorRuntime(config)
    with rt:
        # pymysql.connect 应以 127.0.0.1 + 动态分配的 local_port 调用
        mock_pymysql_connect.assert_called_once()
        kwargs = mock_pymysql_connect.call_args.kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] != 3306  # 不是 dbPort
        assert kwargs["user"] == "recommend_ro"
        assert kwargs["database"] == "niushop_b2c_v5"

    # __exit__ 归还进程级缓存，不应提前关闭可复用连接。
    fake_conn.close.assert_not_called()


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_connects_direct_when_no_ssh(
    mock_pymysql_connect: MagicMock,
) -> None:
    """G3 直连模式：无 sshHost → 跳过隧道，直接用 dbHost/dbPort 连接。"""
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn

    config = {
        "dbHost": "mysql.prod.internal",
        "dbPort": 3306,
        "database": "db",
        "username": "u",
        "secretRef": "vault://secrets/db",
    }
    rt = JdbcConnectorRuntime(config)
    with rt:
        mock_pymysql_connect.assert_called_once()
        kwargs = mock_pymysql_connect.call_args.kwargs
        assert kwargs["host"] == "mysql.prod.internal"
        assert kwargs["port"] == 3306

    fake_conn.close.assert_not_called()


# ═══════════════════════════════════════════════
# Section D: Schema 发现
# ═══════════════════════════════════════════════


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_discover_schemas_returns_tree(
    mock_pymysql_connect: MagicMock,
) -> None:
    """G4 discover_schemas()：返回 schema/table/column 树（标准 information_schema 查询）。"""
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn

    # mock 三段查询结果：schemata → tables → columns
    cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = cursor

    # 1. schemata 查询
    # 2. tables 查询（返回 2 个 schema 的表）
    # 3. columns 查询（每个表返回字段）
    cursor.fetchall.side_effect = [
        # schemata
        [{"schema_name": "niushop_b2c_v5"}, {"schema_name": "information_schema"}],
        # tables for niushop_b2c_v5
        [{"table_name": "ns_order"}, {"table_name": "ns_member"}],
        # columns for ns_order
        [{"column_name": "order_id", "data_type": "bigint", "is_nullable": "NO", "column_key": "PRI"},
         {"column_name": "member_id", "data_type": "int", "is_nullable": "YES", "column_key": ""}],
        # columns for ns_member
        [{"column_name": "member_id", "data_type": "int", "is_nullable": "NO", "column_key": "PRI"}],
        # tables for information_schema (空，应被跳过)
        [],
    ]

    config = {
        "dbHost": "mysql.internal",
        "dbPort": 3306,
        "database": "niushop_b2c_v5",
        "username": "u",
        "secretRef": "vault://secrets/db",
    }
    with JdbcConnectorRuntime(config) as rt:
        tree = rt.discover_schemas()

    # information_schema 应被过滤掉
    schema_names = [s["name"] for s in tree]
    assert "niushop_b2c_v5" in schema_names
    assert "information_schema" not in schema_names

    # 验证表与字段结构
    ns_schema = next(s for s in tree if s["name"] == "niushop_b2c_v5")
    table_names = [t["name"] for t in ns_schema["tables"]]
    assert "ns_order" in table_names
    assert "ns_member" in table_names

    # 验证 ns_order 字段
    ns_order = next(t for t in ns_schema["tables"] if t["name"] == "ns_order")
    columns = ns_order["columns"]
    assert len(columns) == 2
    order_id_col = next(c for c in columns if c["name"] == "order_id")
    assert order_id_col["datatype"] == "bigint"
    assert order_id_col["primary_key"] is True
    assert order_id_col["nullable"] is False


# ═══════════════════════════════════════════════
# Section E: 行流读取
# ═══════════════════════════════════════════════


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_read_rows_without_cursor(
    mock_pymysql_connect: MagicMock,
) -> None:
    """G5 read_rows() 无游标 → SELECT * FROM table LIMIT %s。"""
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn
    cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [
        {"order_id": 1, "member_id": 100},
        {"order_id": 2, "member_id": 101},
    ]

    config = {"dbHost": "h", "dbPort": 3306, "database": "db", "username": "u", "secretRef": "s"}
    with JdbcConnectorRuntime(config) as rt:
        rows = rt.read_rows("ns_order", limit=2)

    assert len(rows) == 2
    assert rows[0]["order_id"] == 1
    assert cursor.execute.call_args_list[0].args[0] == "START TRANSACTION READ ONLY"
    # 验证 SQL 构造（无 WHERE 子句）
    sql_arg = cursor.execute.call_args[0][0]
    assert "SELECT * FROM `ns_order`" in sql_arg
    assert "LIMIT" in sql_arg


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_read_rows_with_cursor_incremental(
    mock_pymysql_connect: MagicMock,
) -> None:
    """G5 read_rows() 带游标 → WHERE pk > watermark ORDER BY pk LIMIT。"""
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn
    cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"order_id": 101}]

    config = {"dbHost": "h", "dbPort": 3306, "database": "db", "username": "u", "secretRef": "s"}
    with JdbcConnectorRuntime(config) as rt:
        rows = rt.read_rows("ns_order", cursor=(100, "order_id"), limit=50)

    assert len(rows) == 1
    assert rows[0]["order_id"] == 101
    sql_arg = cursor.execute.call_args[0][0]
    assert "WHERE `order_id` >" in sql_arg
    assert "ORDER BY `order_id`" in sql_arg
    assert "LIMIT" in sql_arg


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_composite_cursor_is_read_only_and_stable(
    mock_pymysql_connect: MagicMock,
) -> None:
    """增量源使用 (watermark, pk) 双游标，避免同秒数据遗漏。"""
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn
    cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"goods_id": 51, "modify_time": 1000}]
    config = {
        "dbHost": "h", "dbPort": 3306, "database": "db",
        "username": "u", "secretRef": "s",
    }
    with JdbcConnectorRuntime(config) as rt:
        rows = rt.read_rows(
            "ns_goods",
            composite_cursor=(1000, 50, "modify_time", "goods_id"),
            limit=100,
        )
    assert rows[0]["goods_id"] == 51
    assert cursor.execute.call_args_list[0].args[0] == "START TRANSACTION READ ONLY"
    sql, params = cursor.execute.call_args.args
    assert "modify_time" in sql and "goods_id" in sql
    assert params == (1000, 1000, 50, 100)


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_combines_parameterized_filters_with_composite_cursor(
    mock_pymysql_connect: MagicMock,
) -> None:
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn
    cursor = MagicMock()
    fake_conn.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchall.return_value = [{"goods_id": 51, "goods_state": 1}]
    config = {
        "dbHost": "h", "dbPort": 3306, "database": "db",
        "username": "u", "secretRef": "s",
    }
    with JdbcConnectorRuntime(config) as rt:
        rows = rt.read_rows(
            "ns_goods",
            composite_cursor=(1000, 50, "modify_time", "goods_id"),
            where_equals={"site_id": 1, "is_delete": 0, "goods_state": 1},
            limit=100,
        )
    assert rows[0]["goods_id"] == 51
    sql, params = cursor.execute.call_args.args
    assert "`site_id` = %s" in sql
    assert "`is_delete` = %s" in sql
    assert "`goods_state` = %s" in sql
    assert "`modify_time` > %s" in sql
    assert params == (1, 0, 1, 1000, 1000, 50, 100)


def test_jdbc_runtime_rejects_unsafe_identifier_before_query() -> None:
    rt = JdbcConnectorRuntime({
        "dbHost": "h", "database": "db", "username": "u", "password": "p",
    })
    rt._conn = MagicMock()
    with pytest.raises(ValueError, match="unsafe SQL identifier"):
        rt.read_rows("ns_goods; DROP TABLE ns_order")


# ═══════════════════════════════════════════════
# Section F: 清理（__exit__）
# ═══════════════════════════════════════════════


@patch("aos_api.jdbc_connector_runtime._is_port_open", return_value=True)
@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
@patch("aos_api.jdbc_connector_runtime.subprocess.Popen")
@patch("aos_api.jdbc_connector_runtime.time.sleep")
def test_jdbc_runtime_exit_closes_conn_and_tunnel(
    mock_sleep: MagicMock,
    mock_popen: MagicMock,
    mock_pymysql_connect: MagicMock,
    mock_port_open: MagicMock,
) -> None:
    """G6 __exit__：关闭 JDBC 连接 + 终止 SSH 隧道进程。"""
    proc_mock = MagicMock()
    proc_mock.poll.return_value = None
    proc_mock.pid = 12345
    mock_popen.return_value = proc_mock
    fake_conn = MagicMock()
    mock_pymysql_connect.return_value = fake_conn

    config = {
        "sshHost": "ssh.example.com",
        "sshUser": "u",
        "dbHost": "mysql.internal",
        "dbPort": 3306,
        "database": "db",
        "username": "u",
        "secretRef": "s",
        "sshKeyRef": "vault://secrets/ssh_key",
    }
    rt = JdbcConnectorRuntime(config)
    with rt:
        pass

    # __exit__ 仅归还缓存；进程级 cleanup 才关闭连接和隧道。
    fake_conn.close.assert_not_called()
    proc_mock.terminate.assert_not_called()


@patch("aos_api.jdbc_connector_runtime.pymysql.connect")
def test_jdbc_runtime_exit_handles_none_conn_gracefully(
    mock_pymysql_connect: MagicMock,
) -> None:
    """G6 __exit__ 容错：_conn 为 None 时不抛异常。"""
    mock_pymysql_connect.side_effect = RuntimeError("connect failed")
    config = {"dbHost": "h", "dbPort": 3306, "database": "db", "username": "u", "secretRef": "s"}
    rt = JdbcConnectorRuntime(config)
    # __enter__ 抛异常 → __exit__ 仍应被调用且不抛新异常
    with pytest.raises(RuntimeError):
        rt.__enter__()
    # __exit__ 不抛异常（_conn 为 None）
    rt.__exit__(None, None, None)


def _tunnel_failure_config() -> dict[str, object]:
    return {
        "sshHost": "ssh.example.com",
        "sshUser": "u",
        "dbHost": "mysql.internal",
        "dbPort": 3306,
        "database": "db",
        "username": "u",
        "secretRef": "s",
    }


@patch("aos_api.jdbc_connector_runtime._get_or_create_tunnel", return_value=43123)
@patch("aos_api.jdbc_connector_runtime._get_or_create_conn", side_effect=RuntimeError("connect failed"))
@patch("aos_api.jdbc_connector_runtime._is_tunnel_alive", return_value=False)
def test_db_connect_failure_evicts_only_the_dead_tunnel_used_by_the_call(
    mock_alive: MagicMock,
    mock_conn: MagicMock,
    mock_get_tunnel: MagicMock,
) -> None:
    config = _tunnel_failure_config()
    key = jdbc_runtime._tunnel_cache_key(config)
    owned = jdbc_runtime._CachedTunnel(tunnel=MagicMock(), local_port=43123)
    jdbc_runtime._TUNNEL_CACHE[key] = owned

    with pytest.raises(RuntimeError, match="connect failed"):
        JdbcConnectorRuntime(config).__enter__()

    assert key not in jdbc_runtime._TUNNEL_CACHE
    owned.tunnel.close.assert_called_once_with()
    mock_get_tunnel.assert_called_once_with(config)
    mock_conn.assert_called_once()
    mock_alive.assert_called_once_with(owned)


@patch("aos_api.jdbc_connector_runtime._get_or_create_tunnel", return_value=43123)
@patch("aos_api.jdbc_connector_runtime._get_or_create_conn", side_effect=RuntimeError("remote db unavailable"))
@patch("aos_api.jdbc_connector_runtime._is_tunnel_alive", return_value=True)
def test_db_connect_failure_keeps_a_healthy_tunnel_without_retry(
    mock_alive: MagicMock,
    mock_conn: MagicMock,
    mock_get_tunnel: MagicMock,
) -> None:
    config = _tunnel_failure_config()
    key = jdbc_runtime._tunnel_cache_key(config)
    owned = jdbc_runtime._CachedTunnel(tunnel=MagicMock(), local_port=43123)
    jdbc_runtime._TUNNEL_CACHE[key] = owned

    with pytest.raises(RuntimeError, match="remote db unavailable"):
        JdbcConnectorRuntime(config).__enter__()

    assert jdbc_runtime._TUNNEL_CACHE[key] is owned
    owned.tunnel.close.assert_not_called()
    mock_get_tunnel.assert_called_once_with(config)
    mock_conn.assert_called_once()
    mock_alive.assert_called_once_with(owned)


def test_dead_tunnel_eviction_does_not_close_a_concurrent_replacement() -> None:
    config = _tunnel_failure_config()
    key = jdbc_runtime._tunnel_cache_key(config)
    stale = jdbc_runtime._CachedTunnel(tunnel=MagicMock(), local_port=43123)
    replacement = jdbc_runtime._CachedTunnel(tunnel=MagicMock(), local_port=43124)
    jdbc_runtime._TUNNEL_CACHE[key] = replacement

    with patch("aos_api.jdbc_connector_runtime._is_tunnel_alive", return_value=False):
        assert jdbc_runtime._evict_cached_tunnel_if_dead(key, stale) is False

    assert jdbc_runtime._TUNNEL_CACHE[key] is replacement
    stale.tunnel.close.assert_not_called()
    replacement.tunnel.close.assert_not_called()
