"""Assist service boundary.

P8-4A intentionally provides no in-memory fallback. P8-4B supplies the
PostgreSQL authority implementation behind this interface.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from aos_api.aip_assist_contracts import (
    AssistStreamEvent,
    AssistThreadSnapshot,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


class AipAssistAuthorityUnavailable(RuntimeError):
    code = "ASSIST_AUTHORITY_UNAVAILABLE"


class AipAssistService(Protocol):
    def create_thread(
        self,
        scope: TenantScope,
        principal: Principal,
        request: CreateAssistThreadRequest,
        *,
        idempotency_key: str,
    ) -> AssistThreadSnapshot: ...

    def get_thread(self, scope: TenantScope, thread_id: str) -> AssistThreadSnapshot: ...

    def stream_turn(
        self,
        scope: TenantScope,
        principal: Principal,
        thread_id: str,
        request: CreateAssistTurnRequest,
        *,
        idempotency_key: str,
    ) -> Iterable[AssistStreamEvent]: ...


class UnavailableAipAssistService:
    """Fail closed until the PostgreSQL authority is installed."""

    @staticmethod
    def _unavailable() -> None:
        raise AipAssistAuthorityUnavailable("Assist authority is not installed")

    def create_thread(self, *args, **kwargs) -> AssistThreadSnapshot:
        self._unavailable()

    def get_thread(self, *args, **kwargs) -> AssistThreadSnapshot:
        self._unavailable()

    def stream_turn(self, *args, **kwargs) -> Iterable[AssistStreamEvent]:
        self._unavailable()


__all__ = [
    "AipAssistAuthorityUnavailable",
    "AipAssistService",
    "UnavailableAipAssistService",
]
