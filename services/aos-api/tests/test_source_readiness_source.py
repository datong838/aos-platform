"""XU1: atomic/read-only and no-payload PostgreSQL reader gates."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime

from aos_api.source_readiness import PostgresSourceReadinessFactSource
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


class Connection:
    def __init__(self, *, failed_pipeline_id: str | None = None) -> None:
        self.calls: list[tuple[str, object]] = []
        self.rolled_back = False
        self.failed_pipeline_id = failed_pipeline_id

    def rollback(self):
        self.rolled_back = True
        self.calls.append(("ROLLBACK", None))

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, params))
        if "current_setting('aos.org_id'" in normalized:
            return Result([{"org_id": "org-org", "project_id": "dev-project"}])
        if "FROM meta_pipeline p" in normalized:
            return Result(
                [
                    {
                        "pipeline_id": item.pipeline_id,
                        "object_type_hint": item.object_type,
                        "source_id": "niushop-qyh",
                        "target": {"objectType": item.object_type},
                    }
                    for item in CANONICAL_QYH_SOURCES
                ]
            )
        if "FROM meta_schedule s" in normalized:
            return Result(
                [
                    {
                        "pipeline_id": item.pipeline_id,
                        "schedule_id": f"sch-{item.pipeline_id}",
                        "cron": f"0 {index + 2} * * *",
                        "schedule_enabled": True,
                        "ingest_kind": "pipeline-live-v1",
                        "ingest_pipeline_id": item.pipeline_id,
                        "ingest_source_id": "niushop-qyh",
                        "id": f"run-{item.pipeline_id}",
                        "status": (
                            "failed"
                            if item.pipeline_id == self.failed_pipeline_id
                            else "succeeded"
                        ),
                        "scheduled_for": NOW,
                        "started_at": NOW,
                        "finished_at": NOW,
                        "rows_written": 1,
                        "error_code": (
                            "SSH_CONNECT_TIMEOUT"
                            if item.pipeline_id == self.failed_pipeline_id
                            else None
                        ),
                    }
                    for index, item in enumerate(CANONICAL_QYH_SOURCES)
                ]
            )
        if "FROM ecom_object" in normalized:
            return Result(
                [
                    {
                        "object_type": item.object_type,
                        "source_total": 1,
                        "source_active": 1,
                        "source_deleted": 0,
                        "source_event_at": NOW,
                    }
                    for item in CANONICAL_QYH_SOURCES
                ]
            )
        if "FROM obj_instance" in normalized:
            return Result(
                [
                    {"object_type": item.object_type, "projection_total": 1}
                    for item in CANONICAL_QYH_SOURCES
                ]
            )
        if "FROM aip_capability_binding" in normalized:
            return Result(
                [
                    {
                        "binding_id": "ecommerce.data_advisor.strategy.plan.r2",
                        "capability_id": "strategy.plan",
                        "version": 63,
                        "status": "active",
                        "dependency_snapshot_hash": "a" * 64,
                    }
                ]
            )
        return Result([])


def test_reader_is_one_repeatable_read_transaction_and_never_reads_props() -> None:
    conn = Connection()

    @contextmanager
    def connect_factory():
        yield conn

    snapshot = PostgresSourceReadinessFactSource(
        connect_factory=connect_factory,
        clock=lambda: NOW,
    ).read_atomic(org_id="org-org", project_id="dev-project")

    assert len(snapshot.sources) == 12
    assert conn.calls[0] == ("ROLLBACK", None)
    assert conn.calls[1][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    sql = " ".join(call[0] for call in conn.calls if call[0] != "ROLLBACK")
    assert " props" not in sql.lower()
    assert "properties" not in sql.lower()
    assert "secret" not in sql.lower()


def test_reader_projects_sanitized_latest_run_error_code() -> None:
    failed_pipeline_id = CANONICAL_QYH_SOURCES[0].pipeline_id
    conn = Connection(failed_pipeline_id=failed_pipeline_id)

    @contextmanager
    def connect_factory():
        yield conn

    snapshot = PostgresSourceReadinessFactSource(
        connect_factory=connect_factory,
        clock=lambda: NOW,
    ).read_atomic(org_id="org-org", project_id="dev-project")

    source = next(item for item in snapshot.sources if item.pipeline_id == failed_pipeline_id)
    assert source.latest_run is not None
    assert source.latest_run.status == "failed"
    assert source.latest_run.error_code == "SSH_CONNECT_TIMEOUT"
