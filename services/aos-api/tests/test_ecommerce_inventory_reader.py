"""D0-B tenant-safe bounded ProductSku Inventory reader tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from aos_api.ecommerce_inventory_reader import (
    EcommerceInventoryReader,
    EcommerceInventoryReaderError,
)


CUTOFF = datetime(2026, 8, 24, 4, 40, tzinfo=UTC)


def _row(*, object_id: str = "sku-1") -> dict[str, Any]:
    return {
        "external_id": object_id,
        "properties": {
            "stock": "100",
            "stockAlarm": "10",
            "stock_health": "ok",
        },
        "source_updated_at": CUTOFF,
        "payload_hash": "a" * 64,
    }


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self) -> list[dict[str, Any]]:
        return self.rows


class ConnectionQueue:
    def __init__(self, *row_sets: list[dict[str, Any]]) -> None:
        self.row_sets = list(row_sets)
        self.connections: list[FakeConnection] = []

    @contextmanager
    def connect(self):
        connection = FakeConnection(self.row_sets.pop(0))
        self.connections.append(connection)
        yield connection


def test_inventory_reader_is_tenant_bound_read_only_and_exact() -> None:
    queue = ConnectionQueue([_row(), _row(object_id="sku-0")])
    reader = EcommerceInventoryReader(connect_factory=queue.connect)

    result = reader.read(
        org_id="org-org",
        project_id="dev-project",
        cutoff=CUTOFF,
        limit=1,
    )

    assert result.tenant.org_id == "org-org"
    assert result.page.count == 1
    assert result.page.has_more is True
    assert result.items[0].stock == 100
    assert result.items[0].stock_alarm == 10
    assert result.page.unknown_count == 0
    assert result.items[0].revision.content_hash == "sha256:" + "a" * 64

    connection = queue.connections[0]
    sql = " ".join(call[0] for call in connection.calls).upper()
    assert "SET TRANSACTION" not in sql
    assert "SET LOCAL ROLE AOS_RUNTIME" in sql
    assert "FROM ECOM_OBJECT" in sql
    assert "ORDER BY SOURCE_UPDATED_AT DESC, EXTERNAL_ID DESC" in sql
    assert not any(token in sql for token in ("INSERT ", "UPDATE ", "DELETE "))
    query_params = connection.calls[-1][1]
    assert query_params == (
        "org-org",
        "dev-project",
        "ProductSku",
        CUTOFF,
        2,
    )


def test_inventory_reader_keeps_positive_and_canary_scopes_independent() -> None:
    queue = ConnectionQueue([_row()], [])
    reader = EcommerceInventoryReader(connect_factory=queue.connect)

    positive = reader.read(
        org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=10
    )
    canary = reader.read(
        org_id="dev-org", project_id="dev-project", cutoff=CUTOFF, limit=10
    )

    assert positive.page.count == 1
    assert canary.page.count == 0
    assert queue.connections[0].calls[-1][1][:2] == ("org-org", "dev-project")
    assert queue.connections[1].calls[-1][1][:2] == ("dev-org", "dev-project")


@pytest.mark.parametrize("properties", [
    {"stock": "100", "stockAlarm": "10", "stock_health": "unknown"},
    {"stock": "not-an-int", "stockAlarm": "10", "stock_health": "ok"},
    {"stock": "1.5", "stockAlarm": "10", "stock_health": "ok"},
    {"stock": "-1", "stockAlarm": "10", "stock_health": "ok"},
])
def test_inventory_reader_fails_closed_on_semantic_drift(
    properties: dict[str, object],
) -> None:
    row = _row()
    row["properties"] = properties
    reader = EcommerceInventoryReader(
        connect_factory=ConnectionQueue([row]).connect
    )

    with pytest.raises(EcommerceInventoryReaderError):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            cutoff=CUTOFF,
            limit=10,
        )


def test_inventory_reader_keeps_optional_missing_values_as_unknown() -> None:
    missing_stock = _row(object_id="sku-missing-stock")
    missing_stock["properties"] = {"stockAlarm": "10", "stock_health": "ok"}
    missing_alarm = _row(object_id="sku-missing-alarm")
    missing_alarm["properties"] = {"stock": "100", "stock_health": "ok"}
    missing_health = _row(object_id="sku-missing-health")
    missing_health["properties"] = {"stock": "100", "stockAlarm": "10"}
    reader = EcommerceInventoryReader(
        connect_factory=ConnectionQueue([missing_stock, missing_alarm, missing_health]).connect
    )

    result = reader.read(
        org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=10
    )

    assert result.page.count == 3
    assert result.page.unknown_count == 3
    assert result.items[0].stock is None
    assert result.items[1].stock_alarm is None
    assert result.items[2].stock_health is None


def test_inventory_reader_accepts_integral_decimal_strings_without_truncation() -> None:
    row = _row()
    row["properties"] = {
        "stock": "497.000",
        "stockAlarm": "10.0",
        "stock_health": "ok",
    }
    reader = EcommerceInventoryReader(connect_factory=ConnectionQueue([row]).connect)

    result = reader.read(
        org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=10
    )

    assert result.items[0].stock == 497
    assert result.items[0].stock_alarm == 10
    assert result.page.unknown_count == 0


def test_inventory_reader_rejects_naive_cutoff_and_invalid_limit() -> None:
    reader = EcommerceInventoryReader(connect_factory=ConnectionQueue([]).connect)
    with pytest.raises(ValueError):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            cutoff=datetime(2026, 8, 24, 4, 40),
            limit=10,
        )
    with pytest.raises(ValueError):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            cutoff=CUTOFF,
            limit=101,
        )
