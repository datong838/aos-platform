"""W1-11 · Pipeline 重试策略 + 死信队列（DLQ）。

RetryPolicy：指数退避计算（1s/2s/4s）。
DeadLetterQueue：超过最大重试次数的 Job 进入 DLQ。

详见 docs/palantier/20_tech/220tech_pipeline-retry.md。
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aos_api.jobs.build_engine import Job


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return "dlq-" + uuid.uuid4().hex[:12]


# --------------------------------------------------------------------------- #
# 重试策略
# --------------------------------------------------------------------------- #
class RetryPolicy:
    """指数退避策略：base_delay * 2^attempt。

    attempt=0 → 1s, attempt=1 → 2s, attempt=2 → 4s。
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay

    def should_retry(self, attempt: int) -> bool:
        return attempt < self.max_retries

    def compute_backoff(self, attempt: int) -> float:
        return self.base_delay * (2 ** attempt)


# --------------------------------------------------------------------------- #
# 死信队列
# --------------------------------------------------------------------------- #
class DeadLetterEntry(BaseModel):
    id: str
    job_id: str
    spec_name: str
    error: str
    retry_count: int
    pushed_at: str = Field(default_factory=_now)


class DeadLetterQueue:
    def __init__(self) -> None:
        self._entries: list[DeadLetterEntry] = []
        self._lock = threading.Lock()

    def push(self, job: "Job") -> DeadLetterEntry:
        entry = DeadLetterEntry(
            id=_new_id(),
            job_id=job.id,
            spec_name=job.spec.name,
            error=job.error or "unknown",
            retry_count=job.retry_count,
        )
        with self._lock:
            self._entries.append(entry)
        return entry

    def list(self) -> list[DeadLetterEntry]:
        with self._lock:
            return list(self._entries)

    def count(self) -> int:
        with self._lock:
            return len(self._entries)

    def get(self, entry_id: str) -> DeadLetterEntry | None:
        with self._lock:
            for e in self._entries:
                if e.id == entry_id:
                    return e
        return None

    def remove(self, entry_id: str) -> bool:
        with self._lock:
            for i, e in enumerate(self._entries):
                if e.id == entry_id:
                    self._entries.pop(i)
                    return True
        return False

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
            return n
