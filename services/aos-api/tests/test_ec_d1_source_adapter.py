"""D1 SourceAdapter 真实源、只读运行时与失败关闭契约。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aos_api.ec_source_adapter import (
    fetch_source_rows,
    get_soft_delete_count,
    reset_soft_delete_counts,
)
from aos_api.tenant_scope import TenantScope


TEST_SCOPE = TenantScope("org-org", "dev-project")


def _node(config: dict[str, Any] | None = None, node_id: str = "n-src") -> Any:
    return SimpleNamespace(id=node_id, node_type="source", config=config or {})


def _pipeline(pid: str = "pl-1") -> Any:
    return SimpleNamespace(id=pid)


def _props() -> dict[str, Any]:
    return {
        "host": "127.0.0.1", "port": 13306, "user": "recommend_ro",
        "password": "secret", "database": "niushop_b2c_v5",
    }


def _aos_context(props: dict[str, Any] | None) -> tuple[MagicMock, MagicMock]:
    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = (
        {"props": props} if props is not None else None
    )
    context = MagicMock()
    context.__enter__.return_value = conn
    context.__exit__.return_value = None
    return context, conn


class _Runtime:
    def __init__(self, rows: list[dict[str, Any]] | None = None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def __enter__(self) -> "_Runtime":
        if self.error:
            raise self.error
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def read_rows(self, table: str, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append({"table": table, **kwargs})
        return list(self.rows)


def _run(
    runtime: _Runtime,
    *,
    config: dict[str, Any],
    pipeline_id: str = "pl-1",
) -> tuple[list[dict[str, Any]], MagicMock]:
    context, conn = _aos_context(_props())
    with patch("aos_api.ec_source_adapter.connect", return_value=context), patch(
        "aos_api.ec_source_adapter.JdbcConnectorRuntime", return_value=runtime
    ) as runtime_cls:
        rows = fetch_source_rows(
            pipeline=_pipeline(pipeline_id), nodes=[_node(config)], node_id="n-src",
            sample_input=None, scope=TEST_SCOPE,
        )
    runtime_cls.assert_called_once_with(_props())
    return rows, conn


@pytest.mark.parametrize("sample_input", [{"a": 1}, [{"a": 1}], None])
def test_missing_source_id_fails_closed(sample_input: Any) -> None:
    with pytest.raises(RuntimeError, match="has no source_id"):
        fetch_source_rows(
            pipeline=_pipeline(), nodes=[], node_id=None,
            sample_input=sample_input, scope=TEST_SCOPE,
        )


def test_unknown_node_id_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="has no source_id"):
        fetch_source_rows(
            pipeline=_pipeline(), nodes=[_node({"source_id": "src-1"}, "other")],
            node_id="n-src", sample_input=None, scope=TEST_SCOPE,
        )


def test_queries_scoped_source_and_reads_initial_without_limit() -> None:
    runtime = _Runtime([{"goods_id": 1, "is_delete": 0}])
    rows, conn = _run(
        runtime,
        config={"source_id": "src-1", "table": "ns_goods", "pk": "goods_id", "initial": True},
    )
    sql, params = conn.execute.call_args.args
    assert "meta_source" in sql
    assert params == ("src-1", "org-org", "dev-project")
    assert runtime.calls == [
        {"table": "ns_goods", "composite_cursor": None, "limit": None, "where_equals": {}}
    ]
    assert rows == [{"goods_id": 1, "is_delete": 0}]


def test_incremental_uses_composite_cursor_and_limit_100() -> None:
    runtime = _Runtime([{"goods_id": 51, "is_delete": 0}])
    rows, _conn = _run(
        runtime,
        config={
            "source_id": "src-1", "table": "ns_goods", "pk": "goods_id",
            "watermark_col": "modify_time",
            "cursor": {"watermark": 1000, "primary_key": 50},
        },
    )
    assert runtime.calls == [{
        "table": "ns_goods",
        "composite_cursor": (1000, 50, "modify_time", "goods_id"),
        "limit": 100,
        "where_equals": {},
    }]
    assert rows[0]["goods_id"] == 51


def test_soft_delete_zero_time_and_pii_cleaning() -> None:
    reset_soft_delete_counts()
    runtime = _Runtime([
        {"member_id": 1, "is_delete": 1, "create_time": 10},
        {
            "member_id": 2, "is_delete": 0, "create_time": 0,
            "mobile": "13800000000", "nickname": "secret", "keep": "ok",
        },
    ])
    rows, _conn = _run(
        runtime,
        pipeline_id="pl-clean",
        config={"source_id": "src-1", "table": "ns_member", "pk": "member_id"},
    )
    assert rows == [{"member_id": 2, "is_delete": 0, "create_time": None, "keep": "ok"}]
    assert get_soft_delete_count("pl-clean", "n-src") == 1


def test_runtime_connection_failure_is_not_swallowed() -> None:
    context, _conn = _aos_context(_props())
    runtime = _Runtime(error=ConnectionError("tunnel broken"))
    with patch("aos_api.ec_source_adapter.connect", return_value=context), patch(
        "aos_api.ec_source_adapter.JdbcConnectorRuntime", return_value=runtime
    ):
        with pytest.raises(ConnectionError, match="tunnel broken"):
            fetch_source_rows(
                pipeline=_pipeline(),
                nodes=[_node({"source_id": "src-1", "table": "ns_goods"})],
                node_id="n-src", sample_input=None, scope=TEST_SCOPE,
            )


def test_jdbc_source_applies_parameterized_pipeline_filter() -> None:
    runtime = _Runtime([{"goods_id": 1, "site_id": 1, "goods_state": 1, "is_delete": 0}])
    rows, _conn = _run(
        runtime,
        config={
            "source_id": "src-1",
            "table": "ns_goods",
            "initial": True,
            "site_filter": "site_id=1 AND is_delete=0 AND goods_state=1",
        },
    )
    assert rows[0]["goods_id"] == 1
    assert runtime.calls == [{
        "table": "ns_goods",
        "composite_cursor": None,
        "limit": None,
        "where_equals": {"site_id": 1, "is_delete": 0, "goods_state": 1},
    }]


def test_jdbc_source_rejects_unsafe_pipeline_filter_before_query() -> None:
    runtime = _Runtime()
    with pytest.raises(ValueError, match="unsafe site_filter"):
        _run(
            runtime,
            config={
                "source_id": "src-1",
                "table": "ns_goods",
                "site_filter": "site_id=1 OR 1=1",
            },
        )
    assert runtime.calls == []


def test_meta_source_not_found_fails_closed() -> None:
    context, _conn = _aos_context(None)
    with patch("aos_api.ec_source_adapter.connect", return_value=context):
        with pytest.raises(ValueError, match="meta_source"):
            fetch_source_rows(
                pipeline=_pipeline(),
                nodes=[_node({"source_id": "missing", "table": "ns_goods"})],
                node_id="n-src", sample_input=None, scope=TEST_SCOPE,
            )
