"""D2.6 子任务 C: phase6_schemas Niushop 真实 Schema 发现测试。

覆盖 phase6_schemas.py 的 fallback 分支：
- 当 source 不在 phase6 store（demo 模式触发条件）+ connector_type=jdbc-mysql-ssh 时
  → 调用 JdbcConnectorRuntime.discover_schemas() 返回真实 schema tree
- 当 source 不在 phase6 store + connector_type=niushop-mysql 时
  → 返回 Niushop 专属 demo schema（8 张 ns_xxx 表）

设计原则：
- 不破坏现有 demo schema 行为（默认 orders/customers/events）
- 新增 jdbc-mysql-ssh / jdbc-postgres-ssh / niushop-mysql 三个分支
- JdbcConnectorRuntime 本身已有独立测试覆盖，本文件只验证路由调用
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from aos_api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_principal():
    """mock require_principal 依赖，避免真实认证。"""
    from aos_api.auth import require_principal
    fake_principal = MagicMock()
    with app.dependency_overrides as overrides:
        overrides[require_principal] = lambda: fake_principal
        yield fake_principal
    app.dependency_overrides.clear()


# ═══════════════════════════════════════════════
# Section A: niushop-mysql source 返回 Niushop 专属 demo schema
# ═══════════════════════════════════════════════


@patch("aos_api.routers.phase6_schemas._resolve_connector_type")
def test_niushop_mysql_source_returns_niushop_demo_schemas(
    mock_resolve: MagicMock,
    client: TestClient,
    mock_principal,
) -> None:
    """G1 connector_type=niushop-mysql → 返回 8 张 ns_xxx 表的 demo schema。

    source 不在 phase6 store → 走 fallback → 命中 niushop-mysql 分支
    → 返回 niushop_b2c_v5 schema + 8 张 ns_xxx 表
    """
    mock_resolve.return_value = "niushop-mysql"
    resp = client.get("/api/datasource/sources/src-niushop-demo/schemas")

    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is True
    items = data["items"]
    schema_names = [s["name"] for s in items]
    assert "niushop_b2c_v5" in schema_names


@patch("aos_api.routers.phase6_schemas._resolve_connector_type")
def test_niushop_mysql_source_returns_niushop_demo_tables(
    mock_resolve: MagicMock,
    client: TestClient,
    mock_principal,
) -> None:
    """G2 niushop-mysql schema=niushop_b2c_v5 → 返回 8 张 ns_xxx 表。"""
    mock_resolve.return_value = "niushop-mysql"
    resp = client.get(
        "/api/datasource/sources/src-niushop-demo/schemas/niushop_b2c_v5/tables"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is True
    items = data["items"]
    table_names = [t["name"] for t in items]
    assert "ns_site" in table_names
    assert "ns_goods" in table_names
    assert "ns_order" in table_names
    assert "ns_member" in table_names
    assert len(items) == 8


@patch("aos_api.routers.phase6_schemas._resolve_connector_type")
def test_niushop_mysql_source_returns_niushop_demo_columns(
    mock_resolve: MagicMock,
    client: TestClient,
    mock_principal,
) -> None:
    """G3 niushop-mysql table=ns_order → 返回 order_id PK + member_id + create_time。"""
    mock_resolve.return_value = "niushop-mysql"
    resp = client.get(
        "/api/datasource/sources/src-niushop-demo/schemas/niushop_b2c_v5/tables/ns_order/columns"
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is True
    items = data["items"]
    col_names = [c["name"] for c in items]
    assert "order_id" in col_names
    assert "member_id" in col_names
    assert "create_time" in col_names
    pk_col = next(c for c in items if c["name"] == "order_id")
    assert pk_col["primary_key"] is True


# ═══════════════════════════════════════════════
# Section B: jdbc-mysql-ssh source 调用 JdbcConnectorRuntime
# ═══════════════════════════════════════════════


@patch("aos_api.routers.phase6_schemas.JdbcConnectorRuntime")
@patch("aos_api.routers.phase6_schemas._resolve_connector_type")
def test_jdbc_mysql_ssh_source_calls_runtime_for_schemas(
    mock_resolve: MagicMock,
    mock_runtime_cls: MagicMock,
    client: TestClient,
    mock_principal,
) -> None:
    """G4 connector_type=jdbc-mysql-ssh → 调用 JdbcConnectorRuntime.discover_schemas。

    source 不在 phase6 store → 走 fallback → 命中 jdbc-mysql-ssh 分支
    → 实例化 JdbcConnectorRuntime + discover_schemas
    """
    mock_resolve.return_value = "jdbc-mysql-ssh"
    fake_rt = MagicMock()
    fake_rt.__enter__.return_value = fake_rt
    fake_rt.discover_schemas.return_value = [
        {
            "name": "niushop_b2c_v5",
            "tables": [
                {"name": "ns_order", "columns": [
                    {"name": "order_id", "datatype": "BIGINT", "nullable": False, "primary_key": True}
                ]},
            ],
        }
    ]
    mock_runtime_cls.return_value = fake_rt

    resp = client.get("/api/datasource/sources/src-jdbc-ssh/schemas")

    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is False
    assert data["count"] >= 1
    mock_runtime_cls.assert_called_once()
    fake_rt.discover_schemas.assert_called_once()


# ═══════════════════════════════════════════════
# Section C: 无 connector_type 默认走原 demo schema（向后兼容）
# ═══════════════════════════════════════════════


@patch("aos_api.routers.phase6_schemas._resolve_connector_type")
def test_no_connector_type_returns_default_demo_schemas(
    mock_resolve: MagicMock,
    client: TestClient,
    mock_principal,
) -> None:
    """G5 connector_type 缺失 → 默认走原 demo schema（orders/customers，向后兼容）。

    关键：不破坏现有行为。
    """
    mock_resolve.return_value = None
    resp = client.get("/api/datasource/sources/src-default/schemas")

    assert resp.status_code == 200
    data = resp.json()
    assert data["demo"] is True
    items = data["items"]
    schema_names = [s["name"] for s in items]
    assert "public" in schema_names  # 默认 schema


# ═══════════════════════════════════════════════
# Section D: _resolve_connector_type 工具函数
# ═══════════════════════════════════════════════


def test_resolve_connector_type_returns_meta_source_value() -> None:
    """G6 _resolve_connector_type 从 meta_source.connector_type 读取。"""
    from aos_api.routers.phase6_schemas import _resolve_connector_type
    with patch("aos_api.routers.phase6_schemas._query_meta_source", return_value={"connector_type": "jdbc-mysql-ssh"}):
        result = _resolve_connector_type("src-1", scope=None)
    assert result == "jdbc-mysql-ssh"


def test_resolve_connector_type_returns_none_when_no_meta_source() -> None:
    """G6 _resolve_connector_type 无 meta_source → 返回 None（向后兼容）。"""
    from aos_api.routers.phase6_schemas import _resolve_connector_type
    with patch("aos_api.routers.phase6_schemas._query_meta_source", return_value=None):
        result = _resolve_connector_type("src-missing", scope=None)
    assert result is None
