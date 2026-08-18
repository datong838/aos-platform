from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dog import decide_wake


def _hb(**updates) -> dict:
    payload = {
        "schema": "aos-cursor-session-dog/v1",
        "status": "working",
        "updated_at": "2026-08-18T17:10:00+08:00",
        "quiet_until": None,
        "next_gate": "R2_4S_PROVIDER_R4_HEALTH_THEN_V6",
    }
    payload.update(updates)
    return payload


def test_looping_fresh_heartbeat_does_not_wake() -> None:
    now = datetime(2026, 8, 18, 9, 10, 45, tzinfo=timezone.utc)
    decision = decide_wake(heartbeat=_hb(status="looping"), now=now)
    assert decision["wake"] is False
    assert decision["reason"] == "healthy"


def test_working_fresh_heartbeat_does_not_wake() -> None:
    now = datetime(2026, 8, 18, 9, 10, 59, tzinfo=timezone.utc)
    decision = decide_wake(heartbeat=_hb(), now=now)
    assert decision["wake"] is False
    assert decision["reason"] == "healthy"


def test_working_heartbeat_stale_at_60s() -> None:
    now = datetime(2026, 8, 18, 9, 11, tzinfo=timezone.utc)
    decision = decide_wake(heartbeat=_hb(), now=now)
    assert decision["wake"] is True
    assert decision["reason"] == "stale-heartbeat"


def test_failed_stopped_wakes_after_short_delay() -> None:
    now = datetime(2026, 8, 18, 9, 12, tzinfo=timezone.utc)
    decision = decide_wake(
        heartbeat=_hb(status="failed-stopped"),
        now=now,
    )
    assert decision["wake"] is True
    assert decision["reason"] == "failed-stopped"


def test_failed_stopped_does_not_wake_immediately() -> None:
    now = datetime(2026, 8, 18, 9, 10, 30, tzinfo=timezone.utc)
    decision = decide_wake(
        heartbeat=_hb(status="failed-stopped"),
        now=now,
    )
    assert decision["wake"] is False


def test_stale_working_heartbeat_is_interrupt_wake() -> None:
    now = datetime(2026, 8, 18, 9, 16, tzinfo=timezone.utc)
    decision = decide_wake(heartbeat=_hb(), now=now)
    assert decision["wake"] is True
    assert decision["reason"] == "stale-heartbeat"


def test_quiet_until_suppresses_wake_while_looping() -> None:
    now = datetime(2026, 8, 18, 9, 16, tzinfo=timezone.utc)
    decision = decide_wake(
        heartbeat=_hb(quiet_until="2026-08-18T17:30:00+08:00"),
        now=now,
    )
    assert decision["wake"] is False
    assert decision["reason"] == "quiet-until"


def test_completed_never_wakes() -> None:
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    decision = decide_wake(
        heartbeat=_hb(status="completed"),
        now=now,
    )
    assert decision["wake"] is False
    assert decision["reason"] == "completed"


def test_same_stall_is_not_woken_twice() -> None:
    now = datetime(2026, 8, 18, 9, 16, tzinfo=timezone.utc)
    first = decide_wake(heartbeat=_hb(), now=now)
    second = decide_wake(
        heartbeat=_hb(),
        now=now + timedelta(minutes=1),
        last_wake_fingerprint=first["fingerprint"],
    )
    assert first["wake"] is True
    assert second["wake"] is False
    assert second["reason"] == "already-woke-this-stall"


def test_missing_heartbeat_does_not_wake() -> None:
    now = datetime(2026, 8, 18, 9, 16, tzinfo=timezone.utc)
    decision = decide_wake(heartbeat=None, now=now)
    assert decision["wake"] is False
    assert decision["reason"] == "no-heartbeat"


def test_wake_prompt_does_not_noop_just_because_status_is_looping() -> None:
    from dog import WAKE_PROMPT

    assert "立即写 reentry-noop 并退出" not in WAKE_PROMPT
    assert "前台正在跑工具" in WAKE_PROMPT
    assert "不要只汇报下一门" in WAKE_PROMPT
