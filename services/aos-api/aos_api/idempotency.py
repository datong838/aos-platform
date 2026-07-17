"""Idempotency-Key middleware placeholder — T0.3 / T-API write path."""
from __future__ import annotations

import json
import threading
from typing import Any

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.idempotency")


class IdempotencyStore:
    """Process-local store (Wave-0). Keyed by org+project+key."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}

    def _compose(self, org_id: str, project_id: str, key: str) -> str:
        return f"{org_id}|{project_id}|{key}"

    def get(self, org_id: str, project_id: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            hit = self._items.get(self._compose(org_id, project_id, key))
            if hit:
                log.info("idempotent_replay key=%s", key[:32])
            return hit

    def put(
        self,
        org_id: str,
        project_id: str,
        key: str,
        *,
        status_code: int,
        body: Any,
    ) -> None:
        payload = {
            "status_code": status_code,
            "body": body,
            "body_json": json.dumps(body, sort_keys=True, default=str),
        }
        with self._lock:
            self._items[self._compose(org_id, project_id, key)] = payload
        log.debug("idempotent_store key=%s status=%s", key[:32], status_code)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


idempotency_store = IdempotencyStore()
