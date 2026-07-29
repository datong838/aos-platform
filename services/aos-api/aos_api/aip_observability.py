"""AIP Observability — assemble summary/traces from in-process metrics samples."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from aos_api.metrics import snapshot


def _fmt_count(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n)) if n == int(n) else f"{n:.1f}"


def build_summary(range_key: str = "1h") -> dict[str, Any]:
    """Build Overview KPIs + trend spark from metrics.snapshot()."""
    snap = snapshot()
    totals = snap.get("totals") or {}
    count = float(totals.get("count") or 0)
    errors = float(totals.get("errors") or 0)
    p95 = totals.get("p95Ms")
    p50 = totals.get("p50Ms")
    sample_size = int(totals.get("sampleSize") or 0)

    err_rate = (errors / count) if count > 0 else 0.0
    p95_val = float(p95) if p95 is not None else 0.0
    p50_val = float(p50) if p50 is not None else 0.0

    # Token not tracked in HTTP metrics — derive a soft sample from request volume.
    tokens_est = count * 230.0

    kpis = [
        {
            "key": "requests",
            "label": "请求量",
            "value": _fmt_count(count),
            "deltaPct": 0.0,
            "unit": "req",
        },
        {
            "key": "latency",
            "label": "P95 延迟",
            "value": f"{int(round(p95_val))}ms" if p95 is not None else "—",
            "deltaPct": 0.0,
            "unit": "ms",
        },
        {
            "key": "errors",
            "label": "错误率",
            "value": f"{err_rate * 100:.2f}%",
            "deltaPct": 0.0,
            "unit": "%",
        },
        {
            "key": "tokens",
            "label": "Token 消耗",
            "value": _fmt_count(tokens_est) if count > 0 else "0",
            "deltaPct": 0.0,
            "unit": "tok",
        },
    ]

    # Synthetic trend from rolling sample size / latency (not a time series store).
    n_points = {"1h": 12, "6h": 24, "24h": 48, "7d": 56}.get(range_key, 12)
    base_req = max(count / max(n_points, 1), 1.0) if count else 0.0
    trend: list[dict[str, Any]] = []
    for i in range(n_points):
        wave = 1.0 + 0.15 * ((i % 5) - 2) / 2.0
        trend.append(
            {
                "t": f"{i * 5}m" if range_key == "1h" else f"p{i}",
                "requests": int(round(base_req * wave)),
                "latencyMs": int(round(p50_val + (p95_val - p50_val) * (i % 3) / 2.0))
                if sample_size
                else 0,
                "errors": int(errors > 0 and i % 4 == 0),
            }
        )

    return {
        "source": "sampled",
        "range": range_key,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "kpis": kpis,
        "trend": trend,
        "totals": {
            "count": int(count),
            "errors": int(errors),
            "p50Ms": p50,
            "p95Ms": p95,
            "sampleSize": sample_size,
        },
    }


def build_traces(limit: int = 20) -> dict[str, Any]:
    """Sample 'traces' from per-route HTTP counters (path ≈ root span)."""
    snap = snapshot()
    rows = snap.get("requests") or []
    # Aggregate by method+path (sum across status codes).
    agg: dict[tuple[str, str], dict[str, float]] = {}
    for r in rows:
        key = (str(r.get("method") or "GET"), str(r.get("path") or "/"))
        bucket = agg.setdefault(key, {"count": 0.0, "sum_ms": 0.0, "errors": 0.0})
        bucket["count"] += float(r.get("count") or 0)
        bucket["sum_ms"] += float(r.get("sumMs") or 0)
        bucket["errors"] += float(r.get("errors") or 0)

    ranked = sorted(agg.items(), key=lambda x: x[1]["count"], reverse=True)
    items: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)
    for idx, ((method, path), b) in enumerate(ranked[: max(1, min(limit, 100))]):
        avg = (b["sum_ms"] / b["count"]) if b["count"] else 0.0
        status = "error" if b["errors"] > 0 else "ok"
        digest = hashlib.md5(f"{method}:{path}".encode(), usedforsecurity=False).hexdigest()[:10]
        items.append(
            {
                "traceId": f"samp_{idx:03d}_{digest}",
                "rootSpan": f"{method} {path}",
                "service": "aos-api",
                "durationMs": int(round(avg)),
                "status": status,
                "spans": max(1, int(min(b["count"], 20))),
                "startedAt": now.strftime("%H:%M:%S"),
            }
        )

    return {
        "source": "sampled",
        "generatedAt": now.isoformat(),
        "items": items,
    }
