from contextlib import contextmanager
from datetime import UTC, datetime

import pytest

from aos_api.ecommerce_workshop_customer_contracts import CustomerReadinessAxis, CustomerViewId
from aos_api.ecommerce_workshop_customer_reader import CustomerReadError
from aos_api.ecommerce_workshop_customer_source_reader import EcommerceWorkshopCustomerSourceReader
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 8, 29, 2, tzinfo=UTC)


class Cursor:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class Connection:
    def __init__(self, run, rows):
        self.run = run
        self.rows = rows
        self.calls = []

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if "FROM meta_schedule_run" in normalized:
            return Cursor(one=self.run)
        if "FROM ecom_object" in normalized:
            return Cursor(many=self.rows)
        return Cursor()


def _connect(run, rows):
    connection = Connection(run, rows)

    @contextmanager
    def connect():
        yield connection

    return connection, connect


def test_reader_preserves_real_count_and_suppresses_customer_identities() -> None:
    run = {"id": "scr-p08-natural", "scheduled_for": datetime(2026, 8, 29, 1, tzinfo=UTC), "started_at": datetime(2026, 8, 29, 1, tzinfo=UTC), "finished_at": datetime(2026, 8, 29, 1, 1, tzinfo=UTC), "rows_written": 54}
    connection, connect = _connect(run, [{"payload_hash": f"{index:064x}"} for index in range(54)])
    value = EcommerceWorkshopCustomerSourceReader(connect_factory=connect).read_view(TenantScope("org-org", "dev-project"), view_id=CustomerViewId.CUSTOMER, cutoff=NOW, limit=100)
    assert value.input_count == value.suppressed_count == 54
    assert value.items == ()
    assert value.readiness_axes[0].axis is CustomerReadinessAxis.CUSTOMER_LITE
    assert value.readiness_axes[0].status == "ready"
    assert all(item.status == "blocked" for item in value.readiness_axes[1:])
    sql = "\n".join(call[0] for call in connection.calls)
    assert "SET TRANSACTION" not in sql
    assert "properties" not in sql and "external_id" not in str(value)
    object_query = next(call for call in connection.calls if "FROM ecom_object" in call[0])
    assert object_query[1][:2] == ("org-org", "dev-project")


def test_reader_fails_closed_without_natural_success_or_on_count_drift() -> None:
    _, missing = _connect(None, [])
    with pytest.raises(CustomerReadError, match="natural run"):
        EcommerceWorkshopCustomerSourceReader(connect_factory=missing).read_view(TenantScope("org-org", "dev-project"), view_id=CustomerViewId.CUSTOMER, cutoff=NOW, limit=100)
    run = {"id": "scr-p08-natural", "scheduled_for": datetime(2026, 8, 29, 1, tzinfo=UTC), "started_at": datetime(2026, 8, 29, 1, tzinfo=UTC), "finished_at": datetime(2026, 8, 29, 1, 1, tzinfo=UTC), "rows_written": 54}
    _, drift = _connect(run, [{"payload_hash": "a" * 64}])
    with pytest.raises(CustomerReadError, match="count drift"):
        EcommerceWorkshopCustomerSourceReader(connect_factory=drift).read_view(TenantScope("org-org", "dev-project"), view_id=CustomerViewId.CUSTOMER, cutoff=NOW, limit=100)
