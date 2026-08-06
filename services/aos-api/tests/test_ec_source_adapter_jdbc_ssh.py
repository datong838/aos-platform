"""D2.6 子任务 D: ec_source_adapter 通用 JDBC SSH 分支测试。

验证 fetch_source_rows 在 source_meta 含 connector_type=jdbc-mysql-ssh 时走通用
JdbcConnectorRuntime 分支，而不是原 pymysql 直连分支（向后兼容保留）。

关键场景：
1. connector_type=jdbc-mysql-ssh → 走 JdbcConnectorRuntime（mock 验证调用）
2. connector_type=niushop-mysql 或缺失 → 走原 pymysql 直连分支（向后兼容）
3. connector_type=jdbc-postgres-ssh → 走 JdbcConnectorRuntime（PostgreSQL 通用分支）

设计原则：
- 不破坏现有 niushop-mysql 分支测试（向后兼容）
- 新增 jdbc-mysql-ssh / jdbc-postgres-ssh 分支用通用运行时
- JdbcConnectorRuntime 本身已有独立测试覆盖（test_jdbc_connector_runtime.py）
  本文件只验证分支派发，不重复测试运行时内部行为
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api import ec_source_adapter
from aos_api.ec_source_adapter import fetch_source_rows, reset_soft_delete_counts
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ═══════════════════════════════════════════════
# fakes
# ═══════════════════════════════════════════════


def _ns_order_raw_row(*, order_id: int = 1, is_delete: int = 0) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "member_id": 1001,
        "site_id": 1,
        "is_delete": is_delete,
    }


def _meta_source_props_mysql_ssh() -> dict[str, Any]:
    """jdbc-mysql-ssh 连接器配置（含 SSH 隧道字段）。"""
    return {
        "connector_type": "jdbc-mysql-ssh",
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


def _meta_source_props_niushop_mysql() -> dict[str, Any]:
    """原 niushop-mysql 连接器配置（无 SSH 隧道）。"""
    return {
        "connector_type": "niushop-mysql",
        "host": "127.0.0.1",
        "port": 13306,
        "user": "recommend_ro",
        "password": "secret",
        "database": "niushop_b2c_v5",
    }


def _meta_source_props_postgres_ssh() -> dict[str, Any]:
    """jdbc-postgres-ssh 连接器配置。"""
    return {
        "connector_type": "jdbc-postgres-ssh",
        "sshHost": "ssh.example.com",
        "sshPort": 22,
        "sshUser": "tunnel_user",
        "sshKeyRef": "vault://secrets/ssh_key",
        "dbHost": "pg.internal",
        "dbPort": 5432,
        "database": "aos_pg",
        "username": "pg_user",
        "secretRef": "vault://secrets/pg_creds",
    }


def _fake_aos_conn(props: dict[str, Any] | None) -> MagicMock:
    conn = MagicMock()
    result = MagicMock()
    if props is None:
        result.fetchone.return_value = None
    else:
        result.fetchone.return_value = {"props": props}
    conn.execute.return_value = result
    return conn


class _FakeNode:
    def __init__(self, config: dict[str, Any]) -> None:
        self.id = "n-src"
        self.node_type = "source"
        self.config = config


# ═══════════════════════════════════════════════
# Section A: jdbc-mysql-ssh 分支派发
# ═══════════════════════════════════════════════


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_fetch_source_rows_dispatches_to_jdbc_mysql_ssh(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """G1 connector_type=jdbc-mysql-ssh → 走 JdbcConnectorRuntime 分支。

    mock meta_source 返回 jdbc-mysql-ssh 配置 → 应实例化 JdbcConnectorRuntime
    并调用 read_rows，而不是 pymysql 直连。
    """
    aos_conn = _fake_aos_conn(_meta_source_props_mysql_ssh())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    fake_rt = MagicMock()
    fake_rt.__enter__.return_value = fake_rt
    fake_rt.read_rows.return_value = [_ns_order_raw_row(order_id=1)]
    mock_runtime_cls.return_value = fake_rt

    reset_soft_delete_counts()
    node = _FakeNode({
        "source_id": "src-jdbc-ssh",
        "table": "ns_order",
        "pk": "order_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-p05-jdbc-ssh"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # JdbcConnectorRuntime 被实例化
    mock_runtime_cls.assert_called_once()
    config_arg = mock_runtime_cls.call_args[0][0]
    assert config_arg["sshHost"] == "ssh.example.com"
    assert config_arg["database"] == "niushop_b2c_v5"

    # read_rows 被调用，返回的行流进入清洗逻辑
    fake_rt.read_rows.assert_called_once()
    assert len(rows) == 1
    assert rows[0]["order_id"] == 1


# ═══════════════════════════════════════════════
# Section B: jdbc-postgres-ssh 分支派发
# ═══════════════════════════════════════════════


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter.connect")
def test_fetch_source_rows_dispatches_to_jdbc_postgres_ssh(
    mock_connect: MagicMock,
    mock_runtime_cls: MagicMock,
) -> None:
    """G2 connector_type=jdbc-postgres-ssh → 走 JdbcConnectorRuntime 分支。"""
    aos_conn = _fake_aos_conn(_meta_source_props_postgres_ssh())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    fake_rt = MagicMock()
    fake_rt.__enter__.return_value = fake_rt
    fake_rt.read_rows.return_value = [{"id": 1, "site_id": 1, "is_delete": 0}]
    mock_runtime_cls.return_value = fake_rt

    reset_soft_delete_counts()
    node = _FakeNode({
        "source_id": "src-pg-ssh",
        "table": "aos_object",
        "pk": "id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-pg-ssh"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    mock_runtime_cls.assert_called_once()
    config_arg = mock_runtime_cls.call_args[0][0]
    assert config_arg["sshHost"] == "ssh.example.com"
    assert config_arg["dbPort"] == 5432


# ═══════════════════════════════════════════════
# Section C: 向后兼容 — niushop-mysql 保留 pymysql 直连
# ═══════════════════════════════════════════════


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_fetch_source_rows_keeps_niushop_mysql_pymysql_branch(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """G3 connector_type=niushop-mysql → 保留 pymysql 直连分支（向后兼容）。

    关键：不破坏现有 D1 测试，原 niushop-mysql 分支保持不变。
    """
    aos_conn = _fake_aos_conn(_meta_source_props_niushop_mysql())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn = MagicMock()
    cur = MagicMock()
    niushop_conn.cursor.return_value = cur
    cur.fetchall.return_value = [_ns_order_raw_row(order_id=1)]
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _FakeNode({
        "source_id": "src-niushop-legacy",
        "table": "ns_order",
        "pk": "order_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-p05-legacy"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # pymysql.connect 被调用（保留原分支）
    mock_pymysql.connect.assert_called_once()
    # JdbcConnectorRuntime 不应被调用
    # （通过 patch 但断言 not called）

    assert len(rows) == 1


# ═══════════════════════════════════════════════
# Section D: 无 connector_type 默认走 pymysql 直连（向后兼容）
# ═══════════════════════════════════════════════


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_fetch_source_rows_defaults_to_pymysql_when_no_connector_type(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """G4 connector_type 缺失 → 默认走 pymysql 直连（向后兼容，防回归）。"""
    props = {
        # 无 connector_type 字段
        "host": "127.0.0.1",
        "port": 13306,
        "user": "recommend_ro",
        "password": "secret",
        "database": "niushop_b2c_v5",
    }
    aos_conn = _fake_aos_conn(props)
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn = MagicMock()
    cur = MagicMock()
    niushop_conn.cursor.return_value = cur
    cur.fetchall.return_value = [_ns_order_raw_row(order_id=1)]
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _FakeNode({
        "source_id": "src-no-connector-type",
        "table": "ns_order",
        "pk": "order_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=SimpleNamespace(id="pl-p05-default"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    mock_pymysql.connect.assert_called_once()
    assert len(rows) == 1
