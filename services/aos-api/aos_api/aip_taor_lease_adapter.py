"""Explicit lease maintenance for a single, synchronous TAOR invocation.

The adapter must open its own scoped connections in the call thread. No database
transaction is shared with the thread renewing the lease. An in-flight external
call cannot be cancelled here: loss of ownership waits for it, then blocks TAOR
progress without resubmission. Transport timeouts remain the provider's concern.
"""
from concurrent.futures import ThreadPoolExecutor, wait
from collections.abc import Callable
from typing import Any

from aos_api.aip_task_store import AipTaskVersionConflict


class LeaseMaintainedTaorAdapter:
    def __init__(self, adapter: Any, heartbeat: Callable[[], Any], lease_seconds: int):
        self._adapter = adapter
        self._heartbeat = heartbeat
        self._interval = lease_seconds / 3

    def _renew(self) -> None:
        try:
            self._heartbeat()
        except Exception:
            # Do not leak connection or provider details into the task failure log.
            raise AipTaskVersionConflict("step lease renewal failed; outcome requires reconciliation") from None

    def _invoke(self, method: str, *args: Any) -> dict[str, Any]:
        self._renew()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="aip-taor-call") as pool:
            future = pool.submit(getattr(self._adapter, method), *args)
            while not future.done():
                done, _ = wait([future], timeout=self._interval)
                if not done:
                    self._renew()
            self._renew()
            return future.result()

    def think(self, step, context):
        return self._invoke("think", step, context)

    def act(self, step, thought):
        return self._invoke("act", step, thought)

    def verify(self, step, action):
        return self._invoke("verify", step, action)

    def observe(self, step, action, verification):
        return self._invoke("observe", step, action, verification)
