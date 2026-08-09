"""O1-A/P12 Payment 权威批读契约。

上位规格：O1 §5.2.11。这些测试不连接真实源库，只冻结公共契约；
真实 `org-org/dev-project` 数据验证由 D5 证据步骤单独执行。
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from aos_api.ec_source_adapter import (
    BATCH_READ_SPECS,
    BatchReadSpec,
    batch_read_public,
)
from aos_api.jdbc_connector_runtime import (
    JdbcConnectorRuntime,
    _CachedConn,
    _CONN_CACHE,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _p12_graph() -> tuple[SimpleNamespace, list[SimpleNamespace]]:
    pipeline = SimpleNamespace(id="P12-payment-qyh", target_ot="Payment")
    nodes = [
        SimpleNamespace(
            id="source",
            node_type="source",
            config={"source_id": "niushop-qyh", "source_table": "ns_pay"},
        )
    ]
    return pipeline, nodes


def test_payment_batch_spec_is_immutable_and_frozen() -> None:
    spec = BATCH_READ_SPECS["payment_order_time"]
    assert spec == BatchReadSpec(
        table="ns_order",
        columns=("order_id", "create_time"),
        filter_column="order_id",
    )
    with pytest.raises(TypeError):
        BATCH_READ_SPECS["unsafe"] = spec  # type: ignore[index]


@patch("aos_api.ec_source_adapter.JdbcConnectorRuntime")
@patch("aos_api.ec_source_adapter._query_meta_source_props")
def test_batch_read_public_reuses_current_p12_source_and_deduplicates_values(
    query_props: MagicMock,
    runtime_cls: MagicMock,
) -> None:
    pipeline, nodes = _p12_graph()
    query_props.return_value = {"dbHost": "read-only", "database": "shop", "username": "ro"}
    runtime = runtime_cls.return_value.__enter__.return_value
    runtime.read_rows_by_values.return_value = [{"order_id": 7, "create_time": 100}]

    rows = batch_read_public(
        pipeline=pipeline,
        nodes=nodes,
        node_id=None,
        scope=SCOPE,
        spec_id="payment_order_time",
        filter_values=["7", "7", "8"],
    )

    assert rows == [{"order_id": 7, "create_time": 100}]
    query_props.assert_called_once_with("niushop-qyh", SCOPE)
    runtime.read_rows_by_values.assert_called_once_with(
        BATCH_READ_SPECS["payment_order_time"], ("7", "8")
    )


def test_batch_read_public_fails_closed_for_unknown_spec_or_missing_source() -> None:
    pipeline, nodes = _p12_graph()
    with pytest.raises(ValueError, match="unknown batch read spec"):
        batch_read_public(
            pipeline=pipeline,
            nodes=nodes,
            node_id=None,
            scope=SCOPE,
            spec_id="arbitrary_table",
            filter_values=["1"],
        )

    nodes[0].config = {"source_table": "ns_pay"}
    with pytest.raises(RuntimeError, match="has no source_id"):
        batch_read_public(
            pipeline=pipeline,
            nodes=nodes,
            node_id=None,
            scope=SCOPE,
            spec_id="payment_order_time",
            filter_values=["1"],
        )


def test_runtime_batch_read_is_parameterized_chunked_and_restores_transaction() -> None:
    spec = BatchReadSpec("ns_order", ("order_id", "create_time"), "order_id")
    fake_conn = MagicMock()
    fake_conn.get_autocommit.return_value = True
    cursor = fake_conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [
        [{"order_id": 1, "create_time": 10}],
        [{"order_id": 501, "create_time": 20}],
    ]
    runtime = JdbcConnectorRuntime(
        {"dbHost": "h", "database": "db", "username": "u", "password": "p"}
    )
    runtime._conn = fake_conn

    values = tuple(str(index) for index in range(1, 502))
    rows = runtime.read_rows_by_values(spec, values)

    assert rows == [
        {"order_id": 1, "create_time": 10},
        {"order_id": 501, "create_time": 20},
    ]
    sql_calls = [
        call
        for call in cursor.execute.call_args_list
        if "SELECT" in str(call.args[0]).upper()
    ]
    assert len(sql_calls) == 2
    assert sql_calls[0].args[1] == values[:500]
    assert sql_calls[1].args[1] == values[500:]
    assert all("%s" in call.args[0] for call in sql_calls)
    assert "ns_order" in sql_calls[0].args[0]
    assert "order_id" in sql_calls[0].args[0]
    fake_conn.rollback.assert_called_once()
    assert fake_conn.autocommit.call_args_list[0].args == (False,)
    assert fake_conn.autocommit.call_args_list[-1].args == (True,)


def test_runtime_batch_read_rejects_limit_before_query() -> None:
    spec = BatchReadSpec("ns_order", ("order_id", "create_time"), "order_id")
    runtime = JdbcConnectorRuntime(
        {"dbHost": "h", "database": "db", "username": "u", "password": "p"}
    )
    runtime._conn = MagicMock()
    with pytest.raises(ValueError, match="50000"):
        runtime.read_rows_by_values(spec, tuple(str(i) for i in range(50_001)))
    runtime._conn.cursor.assert_not_called()


def test_runtime_batch_read_sql_failure_evicts_bad_cached_connection() -> None:
    spec = BatchReadSpec("ns_order", ("order_id", "create_time"), "order_id")
    fake_conn = MagicMock()
    fake_conn.get_autocommit.return_value = True
    cursor = fake_conn.cursor.return_value.__enter__.return_value
    cursor.execute.side_effect = [None, RuntimeError("query failed")]
    cached = _CachedConn(conn=fake_conn)
    runtime = JdbcConnectorRuntime(
        {"dbHost": "h", "database": "db", "username": "u", "password": "p"}
    )
    runtime._conn = fake_conn
    runtime._cached_conn = cached
    runtime._conn_key = "p12-failure"
    _CONN_CACHE[runtime._conn_key] = cached

    with pytest.raises(RuntimeError, match="query failed"):
        runtime.read_rows_by_values(spec, ("1",))

    assert "p12-failure" not in _CONN_CACHE
    fake_conn.rollback.assert_called_once()
    fake_conn.close.assert_called_once()
    assert runtime._conn is None


def test_runtime_batch_read_serializes_same_cached_connection() -> None:
    spec = BatchReadSpec("ns_order", ("order_id", "create_time"), "order_id")
    fake_conn = MagicMock()
    fake_conn.get_autocommit.return_value = True
    cursor = fake_conn.cursor.return_value.__enter__.return_value
    active = 0
    max_active = 0
    guard = threading.Lock()

    def _execute(sql: str, params: object = None) -> None:
        nonlocal active, max_active
        if not sql.startswith("SELECT"):
            return
        with guard:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.02)
        with guard:
            active -= 1

    cursor.execute.side_effect = _execute
    cursor.fetchall.return_value = []
    cached = _CachedConn(conn=fake_conn)

    def _runtime() -> JdbcConnectorRuntime:
        runtime = JdbcConnectorRuntime(
            {"dbHost": "h", "database": "db", "username": "u", "password": "p"}
        )
        runtime._conn = fake_conn
        runtime._cached_conn = cached
        runtime._conn_key = "p12-shared"
        return runtime

    threads = [
        threading.Thread(target=_runtime().read_rows_by_values, args=(spec, (str(i),)))
        for i in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=1)

    assert all(not thread.is_alive() for thread in threads)
    assert max_active == 1


@patch("aos_api.ec_live_executor.batch_read_public")
def test_payment_enrichment_happens_on_raw_rows_before_normalize(
    batch_read: MagicMock,
) -> None:
    from aos_api.ec_live_executor import _enrich_payment_order_create_time

    pipeline, nodes = _p12_graph()
    rows = [
        {"id": 1, "relate_id": 7, "pay_time": 160},
        {"id": 2, "relate_id": 8, "pay_time": 0},
    ]
    batch_read.return_value = [
        {"order_id": 7, "create_time": 100},
        {"order_id": 8, "create_time": 80},
    ]

    _enrich_payment_order_create_time(
        pipeline=pipeline,
        nodes=nodes,
        node_id=None,
        scope=SCOPE,
        rows=rows,
    )

    assert rows[0]["_order_create_time"] == 100
    assert rows[1]["_order_create_time"] == 80
    batch_read.assert_called_once_with(
        pipeline=pipeline,
        nodes=nodes,
        node_id=None,
        scope=SCOPE,
        spec_id="payment_order_time",
        filter_values=("7", "8"),
    )
