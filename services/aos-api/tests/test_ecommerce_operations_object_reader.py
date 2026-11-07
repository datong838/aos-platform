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
