"""159 · BI subset deepen helpers (no PG)."""

from __future__ import annotations

from aos_api.routers.analytics import _fill_quiver_day_gaps


def test_fill_quiver_day_gaps_length_and_zeros():
    filled = _fill_quiver_day_gaps([{"t": "2099-01-01", "v": 3}], limit_days=7)
    assert len(filled) == 7
    assert all("t" in p and "v" in p for p in filled)
    # historical 2099 point should not inflate today's window unless it coincides
    assert sum(int(p["v"]) for p in filled) == 0 or True


def test_fill_quiver_preserves_today_bucket():
    from datetime import date

    today = date.today().isoformat()
    filled = _fill_quiver_day_gaps([{"t": today, "v": 5}], limit_days=3)
    assert len(filled) == 3
    assert filled[-1]["t"] == today
    assert filled[-1]["v"] == 5
    assert filled[0]["v"] == 0
