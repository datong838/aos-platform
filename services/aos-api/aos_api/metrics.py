"""TX.2 — in-process RED metrics + path normalize (no OTel dep)."""
from __future__ import annotations

import re
import threading
from collections import defaultdict, deque
from typing import Any

_lock = threading.Lock()
_SAMPLE_CAP = 500

# (method, path, status) -> {count, sum_ms, errors}
_counters: dict[tuple[str, str, str], dict[str, float]] = defaultdict(
    lambda: {"count": 0.0, "sum_ms": 0.0, "errors": 0.0}
)
_samples: deque[float] = deque(maxlen=_SAMPLE_CAP)

_PATH_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^/v1/objects/[^/]+/[^/]+/neighbors$"), "/v1/objects/{object_type}/{object_id}/neighbors"),
    (re.compile(r"^/v1/objects/[^/]+/[^/]+$"), "/v1/objects/{object_type}/{object_id}"),
    (re.compile(r"^/v1/objects/[^/]+$"), "/v1/objects/{object_type}"),
    (re.compile(r"^/v1/wiki/[^/]+/[^/]+$"), "/v1/wiki/{object_type}/{object_id}"),
    (re.compile(r"^/v1/funnel/[^/]+/"), "/v1/funnel/{object_type}/…"),
    (re.compile(r"^/v1/aip/drafts/[^/]+"), "/v1/aip/drafts/{draft_id}"),
    (re.compile(r"^/v1/aip/lineage/[^/]+$"), "/v1/aip/lineage/{lineage_id}"),
    (re.compile(r"^/v1/aip/capabilities/jobs/[^/]+$"), "/v1/aip/capabilities/jobs/{job_id}"),
    (re.compile(r"^/v1/datasets/[^/]+/history$"), "/v1/datasets/{rid}/history"),
    (re.compile(r"^/v1/datasets/[^/]+$"), "/v1/datasets/{rid}"),
    (re.compile(r"^/v1/media-sets/[^/]+"), "/v1/media-sets/{rid}"),
    (re.compile(r"^/v1/modules/[^/]+"), "/v1/modules/{id}"),
    (re.compile(r"^/v1/ontology/link-types/[^/]+$"), "/v1/ontology/link-types/{id}"),
    (re.compile(r"^/v1/syncs/[^/]+$"), "/v1/syncs/{id}"),
    (re.compile(r"^/v1/dlq/[^/]+"), "/v1/dlq/{id}"),
]


def normalize_path(path: str) -> str:
    path = path.split("?", 1)[0]
    for pat, repl in _PATH_RULES:
        if pat.match(path):
            return repl
    return path


def parse_traceparent(header: str | None) -> str | None:
    """W3C traceparent → 32-hex trace-id (TX.2)."""
    if not header:
        return None
    parts = header.strip().split("-")
    if len(parts) >= 2 and len(parts[1]) == 32 and all(c in "0123456789abcdefABCDEF" for c in parts[1]):
        return parts[1].lower()
    return None


def record(*, method: str, path: str, status: int, duration_ms: float) -> None:
    key = (method.upper(), normalize_path(path), str(status))
    err = 1.0 if status >= 500 else 0.0
    with _lock:
        c = _counters[key]
        c["count"] += 1
        c["sum_ms"] += duration_ms
        c["errors"] += err
        _samples.append(duration_ms)


def reset_metrics() -> None:
    with _lock:
        _counters.clear()
        _samples.clear()


def _percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def snapshot() -> dict[str, Any]:
    with _lock:
        rows = [
            {
                "method": m,
                "path": p,
                "status": s,
                "count": int(v["count"]),
                "sumMs": round(v["sum_ms"], 3),
                "avgMs": round(v["sum_ms"] / v["count"], 3) if v["count"] else 0.0,
                "errors": int(v["errors"]),
            }
            for (m, p, s), v in sorted(_counters.items())
        ]
        samples = list(_samples)
    samples_sorted = sorted(samples)
    total = sum(r["count"] for r in rows)
    errors = sum(r["errors"] for r in rows)
    return {
        "service": "aos-api",
        "totals": {
            "count": total,
            "errors": errors,
            "p50Ms": _percentile(samples_sorted, 0.50),
            "p95Ms": _percentile(samples_sorted, 0.95),
            "sampleSize": len(samples),
        },
        "requests": rows,
    }


def prom_text() -> str:
    snap = snapshot()
    lines = [
        "# HELP aos_http_requests_total Total HTTP requests",
        "# TYPE aos_http_requests_total counter",
    ]
    for r in snap["requests"]:
        lines.append(
            f'aos_http_requests_total{{method="{r["method"]}",path="{r["path"]}",status="{r["status"]}"}} {r["count"]}'
        )
    lines += [
        "# HELP aos_http_request_duration_ms_sum Sum of request durations in milliseconds",
        "# TYPE aos_http_request_duration_ms_sum counter",
    ]
    for r in snap["requests"]:
        lines.append(
            f'aos_http_request_duration_ms_sum{{method="{r["method"]}",path="{r["path"]}",status="{r["status"]}"}} {r["sumMs"]}'
        )
    totals = snap["totals"]
    lines += [
        "# HELP aos_http_errors_total Total HTTP 5xx responses",
        "# TYPE aos_http_errors_total counter",
        f'aos_http_errors_total {totals["errors"]}',
    ]
    if totals["p50Ms"] is not None:
        lines += [
            "# HELP aos_http_duration_ms Approximate latency percentiles (rolling window)",
            "# TYPE aos_http_duration_ms gauge",
            f'aos_http_duration_ms{{quantile="0.5"}} {totals["p50Ms"]}',
            f'aos_http_duration_ms{{quantile="0.95"}} {totals["p95Ms"]}',
        ]
    lines.append("")
    return "\n".join(lines)
