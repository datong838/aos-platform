"""D1-W1: Niushop SourceAdapter 只读专项测试 (FR-D1-4).

覆盖：
- 向后兼容（sample_input 透传）
- 从 node.config 取 source_id 查 meta_source 拿连接配置
- 只读事务（SET SESSION TRANSACTION READ ONLY）
- 软删行（is_delete=1）过滤 + DLQ 计数
- 0 时间转 null（Unix 秒 → UTC）
- LIMIT 100 采样上限（初装不受限，增量受游标控制）
- 增量游标 (watermark, primary_key) 二元组
- 隧道断开 fail-closed

用 mock/fake 测试，不需要真实 MySQL 连接。
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pymysql as _real_pymysql
import pytest

from aos_api.ec_source_adapter import fetch_source_rows, get_soft_delete_count, reset_soft_delete_counts
from aos_api.tenant_scope import TenantScope

TEST_SCOPE = TenantScope("dev-org", "dev-project")


# ═══════════════════════════════════════════════
# 公共 fake 构造
# ═══════════════════════════════════════════════

def _make_node(
    node_id: str = "n-src",
    node_type: str = "source",
    config: dict[str, Any] | None = None,
) -> Any:
    """构造一个 PipelineNode-like 对象。"""
    return SimpleNamespace(id=node_id, node_type=node_type, config=config or {})


def _make_pipeline(pid: str = "pl-1") -> Any:
    return SimpleNamespace(id=pid)


def _meta_source_props() -> dict[str, Any]:
    """meta_source.props 中的连接配置。"""
    return {
        "host": "127.0.0.1",
        "port": 13306,
        "user": "recommend_ro",
        "password": "secret",
        "database": "niushop_b2c_v5",
    }


def _fake_aos_conn(props: dict[str, Any] | None = None) -> MagicMock:
    """fake AOS postgres connection (用于查 meta_source)。

    data_os_store 用法: with connect(scope) as conn: row = conn.execute(sql, params).fetchone()
    """
    conn = MagicMock()
    result = MagicMock()
    if props is None:
        result.fetchone.return_value = None
    else:
        result.fetchone.return_value = {"props": props}
    conn.execute.return_value = result
    return conn


class _FakePymysqlCursor:
    """fake pymysql DictCursor。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, Any]] = []

    def execute(self, sql: str, params: Any = None) -> None:
        self.executed.append((sql, params))

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows

    def close(self) -> None:
        pass


def _fake_pymysql_conn(rows: list[dict[str, Any]]) -> tuple[MagicMock, _FakePymysqlCursor]:
    """fake pymysql connection (用于查 Niushop)。

    返回 (conn, cursor) 以便测试断言 cursor.executed。
    """
    cur = _FakePymysqlCursor(rows)
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn, cur


def _patch_niushop(
    meta_props: dict[str, Any] | None = None,
    niushop_rows: list[dict[str, Any]] | None = None,
):
    """patch AOS db.connect + pymysql.connect，返回 (aos_conn, niushop_conn, niushop_cur)。"""
    aos_conn = _fake_aos_conn(meta_props if meta_props is not None else _meta_source_props())
    niushop_conn, niushop_cur = _fake_pymysql_conn(niushop_rows or [])

    db_patch = patch("aos_api.ec_source_adapter.connect", return_value=MagicMock(
        __enter__=MagicMock(return_value=aos_conn),
        __exit__=MagicMock(return_value=None),
    ))
    pymysql_patch = patch("aos_api.ec_source_adapter.pymysql")

    return db_patch, pymysql_patch, aos_conn, niushop_conn, niushop_cur


# ═══════════════════════════════════════════════
# 1. 向后兼容分支（骨架 sample_input 透传）
# ═══════════════════════════════════════════════

def test_fallback_to_sample_input_dict() -> None:
    """骨架行为：sample_input 是 dict 时返回 [sample_input]。"""
    sample = {"a": 1}
    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input=sample,
        scope=TEST_SCOPE,
    )
    assert rows == [sample]


def test_fallback_to_sample_input_list() -> None:
    """骨架行为：sample_input 是 list 时过滤非 dict。"""
    sample = [{"a": 1}, "x", {"b": 2}]
    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input=sample,
        scope=TEST_SCOPE,
    )
    assert rows == [{"a": 1}, {"b": 2}]


def test_fallback_to_sample_input_none() -> None:
    """骨架行为：sample_input 是 None 时返回 []。"""
    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[],
        node_id=None,
        sample_input=None,
        scope=TEST_SCOPE,
    )
    assert rows == []


def test_fallback_when_no_source_id_in_config() -> None:
    """node.config 无 source_id 时回退到 sample_input 透传（向后兼容）。"""
    node = _make_node(config={"table": "ns_goods"})  # 缺 source_id
    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input={"fallback": True},
        scope=TEST_SCOPE,
    )
    assert rows == [{"fallback": True}]


def test_fallback_when_node_id_not_in_nodes() -> None:
    """node_id 在 nodes 中找不到时回退到 sample_input 透传。"""
    node = _make_node(node_id="other", config={"source_id": "src-1"})
    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input={"fallback": True},
        scope=TEST_SCOPE,
    )
    assert rows == [{"fallback": True}]


# ═══════════════════════════════════════════════
# 2. Niushop 只读源分支
# ═══════════════════════════════════════════════

@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_reads_source_id_from_node_config_and_queries_meta_source(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """从 node.config 取 source_id 并查 meta_source 拿连接配置。"""
    # fake AOS db.connect 返回 meta_source.props
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    # fake pymysql.connect 返回行
    niushop_conn, niushop_cur = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
    })

    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 验证查了 meta_source（用 source_id + scope）
    aos_conn.execute.assert_called_once()
    call_args = aos_conn.execute.call_args
    sql = call_args.args[0]
    params = call_args.args[1]
    assert "meta_source" in sql
    assert "props" in sql
    assert params == ("src-1", "dev-org", "dev-project")

    # 验证 pymysql.connect 用了 props 中的连接配置
    mock_pymysql.connect.assert_called_once()
    kwargs = mock_pymysql.connect.call_args.kwargs
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 13306
    assert kwargs["user"] == "recommend_ro"
    assert kwargs["password"] == "secret"
    assert kwargs["database"] == "niushop_b2c_v5"

    # 验证返回了行
    assert rows == [{"goods_id": 1, "is_delete": 0}]


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_sets_read_only_transaction(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """只读事务被设置：第一个 execute 是 SET SESSION TRANSACTION READ ONLY。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn, niushop_cur = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
    })

    fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 第一个 execute 必须是 READ ONLY
    assert len(niushop_cur.executed) >= 1
    first_sql = niushop_cur.executed[0][0]
    assert "SET SESSION TRANSACTION READ ONLY" in first_sql


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_filters_soft_deleted_rows(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """软删行（is_delete=1）被过滤，不进入返回的行流。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_rows = [
        {"goods_id": 1, "is_delete": 0, "modify_time": 100},
        {"goods_id": 2, "is_delete": 1, "modify_time": 200},  # 软删
        {"goods_id": 3, "is_delete": 0, "modify_time": 300},
    ]
    niushop_conn, _ = _fake_pymysql_conn(niushop_rows)
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=_make_pipeline("pl-soft"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 返回的行不含 is_delete=1
    assert len(rows) == 2
    assert all(r["is_delete"] == 0 for r in rows)
    assert {r["goods_id"] for r in rows} == {1, 3}

    # 软删计数被记录
    assert get_soft_delete_count("pl-soft", "n-src") == 1


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_converts_zero_time_to_null(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """0 时间转 null（Unix 秒 → UTC）：*_time 字段值为 0 时变 None。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_rows = [{
        "goods_id": 1,
        "is_delete": 0,
        "create_time": 0,           # 0 → None
        "modify_time": 100,         # 非 0 保留
        "refund_action_time": 0,    # 0 → None
        "goods_name": "x",          # 非 time 字段不动
    }]
    niushop_conn, _ = _fake_pymysql_conn(niushop_rows)
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["create_time"] is None       # 0 → None
    assert row["refund_action_time"] is None  # 0 → None
    assert row["modify_time"] == 100         # 非 0 保留
    assert row["goods_name"] == "x"          # 非 time 字段不动


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_respects_limit_100_in_incremental_mode(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """增量模式（有 cursor）受 LIMIT 100 采样上限控制。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn, niushop_cur = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "cursor": {"watermark": 1000, "primary_key": 50},
    })

    fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 找到数据查询（非 READ ONLY）的 SQL，验证含 LIMIT
    data_sqls = [
        (sql, params) for sql, params in niushop_cur.executed
        if "READ ONLY" not in sql
    ]
    assert len(data_sqls) == 1
    sql, params = data_sqls[0]
    assert "LIMIT" in sql.upper()
    # LIMIT 值是 100
    assert 100 in (params if isinstance(params, (list, tuple)) else [])


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_no_limit_in_initial_mode(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """初装模式（initial=True）不受 LIMIT 100 限制。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn, niushop_cur = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "initial": True,
    })

    fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    data_sqls = [
        sql for sql, _ in niushop_cur.executed
        if "READ ONLY" not in sql
    ]
    assert len(data_sqls) == 1
    sql = data_sqls[0]
    assert "LIMIT" not in sql.upper()


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_incremental_cursor_filter(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """增量游标 (watermark, primary_key) 二元组生成正确的 WHERE 子句和参数。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn, niushop_cur = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "watermark_col": "modify_time",
        "cursor": {"watermark": 1000, "primary_key": 50},
    })

    fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    data_sqls = [
        (sql, params) for sql, params in niushop_cur.executed
        if "READ ONLY" not in sql
    ]
    assert len(data_sqls) == 1
    sql, params = data_sqls[0]
    # 复合游标 WHERE 子句
    assert "modify_time" in sql
    assert "goods_id" in sql
    assert ">" in sql
    # 参数含 watermark=1000, primary_key=50, site_filter, limit
    flat_params = list(params) if isinstance(params, (list, tuple)) else [params]
    assert 1000 in flat_params
    assert 50 in flat_params


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_fail_closed_on_tunnel_error(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """隧道断开（pymysql.OperationalError）时 fail-closed：异常向上抛出。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    # pymysql.connect 抛 OperationalError（模拟隧道断开）
    mock_pymysql.OperationalError = _real_pymysql.OperationalError
    mock_pymysql.connect.side_effect = _real_pymysql.OperationalError("tunnel broken")
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
    })

    # fail-closed：异常向上抛出，不吞错
    with pytest.raises(_real_pymysql.OperationalError):
        fetch_source_rows(
            pipeline=_make_pipeline(),
            nodes=[node],
            node_id="n-src",
            sample_input=None,
            scope=TEST_SCOPE,
        )


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_query_timeout_30s(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """单查询超时 30s：pymysql.connect 的 connect_timeout 和 read_timeout 都是 30。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_conn, _ = _fake_pymysql_conn([{"goods_id": 1, "is_delete": 0}])
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
    })

    fetch_source_rows(
        pipeline=_make_pipeline(),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    kwargs = mock_pymysql.connect.call_args.kwargs
    assert kwargs["connect_timeout"] == 30
    assert kwargs["read_timeout"] == 30


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_soft_delete_count_recorded_for_dlq(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """软删行计数记录到 module-level dict，供 G6 DLQ 取用。"""
    aos_conn = _fake_aos_conn(_meta_source_props())
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    niushop_rows = [
        {"goods_id": 1, "is_delete": 0},
        {"goods_id": 2, "is_delete": 1},  # 软删
        {"goods_id": 3, "is_delete": 1},  # 软删
        {"goods_id": 4, "is_delete": 0},
    ]
    niushop_conn, _ = _fake_pymysql_conn(niushop_rows)
    mock_pymysql.connect.return_value = niushop_conn
    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "src-1",
        "table": "ns_goods",
        "pk": "goods_id",
        "initial": True,
    })

    rows = fetch_source_rows(
        pipeline=_make_pipeline("pl-dlq"),
        nodes=[node],
        node_id="n-src",
        sample_input=None,
        scope=TEST_SCOPE,
    )

    # 有效行 2 条
    assert len(rows) == 2
    # 软删计数 2 条
    assert get_soft_delete_count("pl-dlq", "n-src") == 2


@patch("aos_api.ec_source_adapter.pymysql")
@patch("aos_api.ec_source_adapter.connect")
def test_meta_source_not_found_raises(
    mock_connect: MagicMock,
    mock_pymysql: MagicMock,
) -> None:
    """meta_source 查不到对应 source_id 时抛错（fail-closed，不回退 sample_input）。"""
    aos_conn = _fake_aos_conn(None)  # fetchone 返回 None
    mock_connect.return_value.__enter__.return_value = aos_conn
    mock_connect.return_value.__exit__.return_value = None

    mock_pymysql.cursors.DictCursor = MagicMock()

    reset_soft_delete_counts()
    node = _make_node(config={
        "source_id": "missing-src",
        "table": "ns_goods",
        "pk": "goods_id",
    })

    with pytest.raises(ValueError, match="meta_source"):
        fetch_source_rows(
            pipeline=_make_pipeline(),
            nodes=[node],
            node_id="n-src",
            sample_input=None,
            scope=TEST_SCOPE,
        )
