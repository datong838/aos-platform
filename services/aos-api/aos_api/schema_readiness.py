"""Read-only relation readiness checks for legacy self-initialising stores."""
from __future__ import annotations

from threading import Lock

from aos_api.db import connect, get_dsn


_ready_relations: set[tuple[str, str]] = set()
_ready_lock = Lock()


def relation_exists(name: str) -> bool:
    """Return whether a public relation exists in the exact configured database."""
    key = (get_dsn(), name)
    with _ready_lock:
        if key in _ready_relations:
            return True
    with connect() as conn:
        row = conn.execute(
            "SELECT to_regclass(%s) AS relation",
            (f"public.{name}",),
        ).fetchone()
    ready = bool(row and row.get("relation"))
    if ready:
        with _ready_lock:
            _ready_relations.add(key)
    return ready


def mark_relation_ready(name: str) -> None:
    """Record a relation created by the current database bootstrap."""
    with _ready_lock:
        _ready_relations.add((get_dsn(), name))
