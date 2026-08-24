from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

import pytest

from aos_api.ecommerce_aftersale_event_reader import (
    EcommerceAftersaleEventReader,
    EcommerceAftersaleEventReaderError,
)


CUTOFF = datetime(2026, 8, 24, 5, tzinfo=UTC)


def _row() -> dict[str, Any]:
    return {
        "org_id": "org-org",
        "project_id": "dev-project",
        "event_id": "aftersale-1",
        "source_revision": 2,
        "source_hash": "a" * 64,
        "event_type": "refund_requested",
        "status": "open",
        "occurred_at": CUTOFF,
        "order_resource_id": "order-1",
        "order_revision": 3,
        "order_content_hash": "b" * 64,
        "order_line_resource_id": None,
        "order_line_revision": None,
        "order_line_content_hash": None,
    }


class Connection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...] | None]] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def fetchall(self):
        return self.rows


def test_reader_is_bounded_tenant_read_only_and_payload_free() -> None:
    connection = Connection([_row()])

    @contextmanager
    def connect():
        yield connection

    items = EcommerceAftersaleEventReader(connect_factory=connect).read(
        org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=10
    )

    assert items[0].event_id == "aftersale-1"
    assert items[0].order_ref.resource_id == "order-1"
    assert items[0].order_line_ref is None
    sql = "\n".join(call[0] for call in connection.calls)
    assert "REPEATABLE READ READ ONLY" in sql
    assert "FROM ecommerce_aftersale_event" in sql
    assert "ORDER BY occurred_at DESC,event_id DESC,source_revision DESC" in sql
    assert "payload" not in sql.lower()
    assert connection.calls[-1][1] == (
        "org-org",
        "dev-project",
        CUTOFF,
        10,
    )


def test_reader_rejects_invalid_bounds_before_connecting() -> None:
    def connect():
        raise AssertionError("invalid reads must not connect")

    reader = EcommerceAftersaleEventReader(connect_factory=connect)
    with pytest.raises(ValueError, match="timezone"):
        reader.read(
            org_id="org-org",
            project_id="dev-project",
            cutoff=datetime(2026, 8, 24),
            limit=10,
        )
    with pytest.raises(ValueError, match="between 1 and 50"):
        reader.read(
            org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=51
        )


@pytest.mark.parametrize(
    "change",
    [
        {"source_hash": "bad"},
        {"order_revision": 0},
        {"order_line_resource_id": "line-1"},
        {"occurred_at": datetime(2026, 8, 24)},
        {"org_id": "dev-org"},
    ],
)
def test_reader_fails_closed_on_malformed_canonical_row(change: dict[str, Any]) -> None:
    row = _row()
    row.update(change)
    connection = Connection([row])

    @contextmanager
    def connect():
        yield connection

    with pytest.raises(EcommerceAftersaleEventReaderError, match="failed closed"):
        EcommerceAftersaleEventReader(connect_factory=connect).read(
            org_id="org-org", project_id="dev-project", cutoff=CUTOFF, limit=10
        )
