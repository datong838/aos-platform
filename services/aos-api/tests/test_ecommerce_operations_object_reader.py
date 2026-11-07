from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_operations_object_reader import (
    EcommerceOperationsObjectReader,
    OperationsObjectReadError,
)


class Cursor:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return Cursor(self.rows)


def test_reader_is_tenant_scoped_read_only_and_excludes_payload() -> None:
    now = datetime(2026, 8, 24, tzinfo=UTC)
    connection = Connection(
        [{"object_type": "Order", "external_id": "order-1", "source_updated_at": now, "payload_hash": "a" * 64}]
    )

    @contextmanager
    def connect():
        yield connection

    items = EcommerceOperationsObjectReader(connect_factory=connect).read(
        org_id="org-org", project_id="dev-project", object_type="Order", cutoff=now
    )
    assert items[0].object_id == "order-1"
    sql = "\n".join(call[0] for call in connection.calls)
    assert "SET TRANSACTION" not in sql
    assert "properties" not in sql
    assert connection.calls[-1][1][:3] == ("org-org", "dev-project", "Order")


def test_reader_rejects_unbounded_or_naive_reads_before_connecting() -> None:
    def connect():
        raise AssertionError("invalid reads must not connect")

    reader = EcommerceOperationsObjectReader(connect_factory=connect)
    with pytest.raises(ValueError, match="timezone"):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            object_type="Order",
            cutoff=datetime(2026, 8, 24),
        )
    with pytest.raises(ValueError, match="between 1 and 50"):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            object_type="Order",
            cutoff=datetime(2026, 8, 24, tzinfo=UTC),
            limit=51,
        )
    with pytest.raises(ValueError, match="unsupported"):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            object_type="Customer",  # type: ignore[arg-type]
            cutoff=datetime(2026, 8, 24, tzinfo=UTC),
        )


def test_reader_fails_closed_on_malformed_canonical_row() -> None:
    now = datetime(2026, 8, 24, tzinfo=UTC)
    connection = Connection(
        [
            {
                "object_type": "Order",
                "external_id": "order-1",
                "source_updated_at": now,
                "payload_hash": "not-sha256",
            }
        ]
    )

    @contextmanager
    def connect():
        yield connection

    with pytest.raises(OperationsObjectReadError, match="failed closed"):
        EcommerceOperationsObjectReader(connect_factory=connect).read(
            org_id="org-org",
            project_id="dev-project",
            object_type="Order",
            cutoff=now,
        )


def test_reader_page_reports_population_separately_from_bounded_items():
    now = datetime(2026, 8, 24, tzinfo=UTC)
    connection = Connection([{"total_count": 167, "object_type": "Order", "external_id": "sample-order-1",
                              "source_updated_at": now, "payload_hash": "a" * 64}])
    @contextmanager
    def connect():
        yield connection
    page = EcommerceOperationsObjectReader(connect_factory=connect).read_page(
        org_id="org-org", project_id="dev-project", object_type="Order", cutoff=now)
    assert page.total_count == 167 and len(page.items) == 1
    query, params = connection.calls[-1]
    assert "COUNT(*)" in query.upper() and params[-2:] == (50, 0)
    assert "properties" not in query and params[:3] == ("org-org", "dev-project", "Order")


def test_reader_page_empty_population_is_explicit_zero():
    connection = Connection([{"total_count": 0, "object_type": None, "external_id": None,
                              "source_updated_at": None, "payload_hash": None}])
    @contextmanager
    def connect():
        yield connection
    page = EcommerceOperationsObjectReader(connect_factory=connect).read_page(
        org_id="org-org", project_id="dev-project", object_type="Order", cutoff=datetime.now(UTC))
    assert page.total_count == 0 and page.items == []


def test_page_search_escapes_literal_wildcards_and_pages_beyond_window():
    now = datetime(2026, 8, 24, tzinfo=UTC)
    connection = Connection([{"total_count": 167, "object_type": "Order", "external_id": "sample-order-100",
                              "source_updated_at": now, "payload_hash": "a" * 64}])
    @contextmanager
    def connect():
        yield connection
    page = EcommerceOperationsObjectReader(connect_factory=connect).read_page(
        org_id="org-org", project_id="dev-project", object_type="Order", cutoff=now,
        query=r"  10%_\  ", offset=100, limit=20)
    assert page.total_count == 167 and page.items[0].object_id == "sample-order-100"
    sql, params = connection.calls[-1]
    assert "ILIKE" in sql and "OFFSET %s" in sql
    assert params[-3:] == (r"%10\%\_\\%", 20, 100)
    assert "properties" not in sql and "shop_or_marketplace_id" in sql


def test_page_beyond_population_preserves_total_and_returns_empty():
    connection = Connection([{"total_count": 2, "object_type": None}])
    @contextmanager
    def connect():
        yield connection
    page = EcommerceOperationsObjectReader(connect_factory=connect).read_page(
        org_id="org-org", project_id="dev-project", object_type="Order", cutoff=datetime.now(UTC), offset=50)
    assert page.total_count == 2 and page.items == []


@pytest.mark.parametrize("changes", [{"offset": -1}, {"offset": 100001}, {"offset": True},
                                    {"query": "x" * 121}, {"query": "bad\x00id"}, {"limit": True}])
def test_invalid_search_never_connects(changes):
    def connect():
        raise AssertionError("must validate before connecting")
    with pytest.raises(ValueError):
        EcommerceOperationsObjectReader(connect_factory=connect).read_page(
            org_id="org-org", project_id="dev-project", object_type="Order", cutoff=datetime.now(UTC), **changes)
