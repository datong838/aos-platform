from contextlib import contextmanager
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import aos_api.phase5_pipeline_engine as pipeline_engine_module
import aos_api.qyh_cron_scheduler as scheduler_module
from aos_api.qyh_cron_scheduler import (
    QYH_DAILY_CRON_BY_PIPELINE,
    QYH_PIPELINE_ORDER,
    _validate_cron_slot,
    cron_matches,
    next_run_at,
)
from aos_api.tenant_scope import TenantScope


class _PersistConnection:
    def __init__(self) -> None:
        self.calls = []
        self.committed = False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        return self

    def commit(self):
        self.committed = True


def test_qyh_has_exactly_twelve_real_pipeline_targets() -> None:
    ids = [pipeline_id for pipeline_id, _ in QYH_PIPELINE_ORDER]
    assert len(ids) == 12
    assert len(set(ids)) == 12
    assert "P05-order-qyh" in ids
    assert "P12-payment-qyh" in ids


def test_qyh_daily_schedules_are_staggered_one_run_per_ot() -> None:
    assert set(QYH_DAILY_CRON_BY_PIPELINE) == set(ids for ids, _ in QYH_PIPELINE_ORDER)
    assert list(QYH_DAILY_CRON_BY_PIPELINE.values()) == [
        f"0 {hour} * * *" for hour in range(2, 14)
    ]
    tz = ZoneInfo("Asia/Shanghai")
    assert cron_matches("0 6 * * *", datetime(2026, 8, 10, 6, 0, tzinfo=tz))
    assert not cron_matches("0 6 * * *", datetime(2026, 8, 10, 7, 0, tzinfo=tz))


def test_hourly_cron_matches_only_at_hour_boundary_shanghai() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    assert cron_matches("0 * * * *", datetime(2026, 8, 10, 9, 0, tzinfo=tz))
    assert not cron_matches("0 * * * *", datetime(2026, 8, 10, 9, 1, tzinfo=tz))


def test_next_hourly_run_uses_shanghai_timezone() -> None:
    tz = ZoneInfo("Asia/Shanghai")
    result = next_run_at("0 * * * *", datetime(2026, 8, 10, 9, 43, tzinfo=tz))
    assert result == datetime(2026, 8, 10, 10, 0, tzinfo=tz)


def test_invalid_cron_fails_closed() -> None:
    assert not cron_matches("not a cron", datetime.now(ZoneInfo("Asia/Shanghai")))
    assert next_run_at("not a cron") is None


def test_cron_slot_accepts_only_the_server_current_minute() -> None:
    now = datetime(2026, 8, 28, 4, 0, 17, tzinfo=timezone.utc)
    scheduled = datetime(2026, 8, 28, 12, 0, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert _validate_cron_slot(scheduled, now=now) == datetime(
        2026, 8, 28, 4, 0, tzinfo=timezone.utc
    )


def test_cron_slot_rejects_future_or_historical_minutes() -> None:
    now = datetime(2026, 8, 28, 4, 0, 17, tzinfo=timezone.utc)
    for scheduled in (
        datetime(2026, 8, 28, 4, 1, tzinfo=timezone.utc),
        datetime(2026, 8, 28, 3, 59, tzinfo=timezone.utc),
    ):
        try:
            _validate_cron_slot(scheduled, now=now)
        except ValueError as exc:
            assert str(exc) == "CRON_SLOT_OUTSIDE_CURRENT_MINUTE"
        else:  # pragma: no cover - explicit fail-closed assertion
            raise AssertionError("out-of-minute cron slot must be rejected")


def test_cron_slot_requires_an_explicit_timezone() -> None:
    try:
        _validate_cron_slot(
            datetime(2026, 8, 28, 4, 0),
            now=datetime(2026, 8, 28, 4, 0, tzinfo=timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "CRON_SLOT_TIMEZONE_REQUIRED"
    else:  # pragma: no cover - explicit fail-closed assertion
        raise AssertionError("naive cron slot must be rejected")


def test_execute_schedule_persists_sanitized_transport_code(monkeypatch) -> None:
    scope = TenantScope("org-org", "dev-project")
    conn = _PersistConnection()

    @contextmanager
    def fake_connect(_scope):
        yield conn

    class Engine:
        @staticmethod
        def execute_pipeline_once(_scope, _pipeline_id):
            return {
                "ok": False,
                "rows_written": 0,
                "duration_ms": 17,
                "error_code": "SSH_CONNECT_TIMEOUT",
                "error_message": "pipeline executor failed",
            }

    monkeypatch.setattr(
        scheduler_module,
        "_get_schedule",
        lambda _scope, _schedule_id: {
            "id": "sch-P10-system-config-qyh",
            "enabled": True,
            "pipelineId": "P10-system-config-qyh",
            "ingest": {
                "kind": "pipeline-live-v1",
                "pipelineId": "P10-system-config-qyh",
            },
        },
    )
    monkeypatch.setattr(scheduler_module, "_claim_run", lambda *_args: "run-1")
    monkeypatch.setattr(scheduler_module, "connect", fake_connect)
    monkeypatch.setattr(pipeline_engine_module, "get_engine", lambda: Engine())

    outcome = scheduler_module.execute_schedule(
        scope,
        "sch-P10-system-config-qyh",
        trigger="test",
        scheduled_for=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )

    persisted = next(params for sql, params in conn.calls if sql.startswith("UPDATE meta_schedule_run"))
    assert outcome["status"] == "failed"
    assert persisted[3] == "SSH_CONNECT_TIMEOUT"
    assert persisted[4] == "pipeline executor failed"
    assert conn.committed is True


def test_execute_schedule_masks_unexpected_scheduler_exception(monkeypatch) -> None:
    scope = TenantScope("org-org", "dev-project")
    conn = _PersistConnection()

    @contextmanager
    def fake_connect(_scope):
        yield conn

    class Engine:
        @staticmethod
        def execute_pipeline_once(_scope, _pipeline_id):
            raise RuntimeError("password=secret user@example.com")

    monkeypatch.setattr(
        scheduler_module,
        "_get_schedule",
        lambda _scope, _schedule_id: {
            "id": "sch-P10-system-config-qyh",
            "enabled": True,
            "pipelineId": "P10-system-config-qyh",
            "ingest": {
                "kind": "pipeline-live-v1",
                "pipelineId": "P10-system-config-qyh",
            },
        },
    )
    monkeypatch.setattr(scheduler_module, "_claim_run", lambda *_args: "run-2")
    monkeypatch.setattr(scheduler_module, "connect", fake_connect)
    monkeypatch.setattr(pipeline_engine_module, "get_engine", lambda: Engine())

    scheduler_module.execute_schedule(
        scope,
        "sch-P10-system-config-qyh",
        trigger="test",
        scheduled_for=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc),
    )

    persisted = next(params for sql, params in conn.calls if sql.startswith("UPDATE meta_schedule_run"))
    assert persisted[3] == "SCHEDULE_EXECUTOR_EXCEPTION"
    assert persisted[4] == "schedule executor failed"
    assert "secret" not in str(persisted)
