"""Assist service boundary.

P8-4A intentionally provides no in-memory fallback. P8-4B supplies the
PostgreSQL authority implementation behind this interface.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Protocol

from aos_api.aip_assist_contracts import (
    AssistBlocker,
    AssistEventType,
    AssistStreamEvent,
    AssistThreadSnapshot,
    AssistThreadHistory,
    AssistSubjectOptionList,
    CreateAssistThreadRequest,
    CreateAssistTurnRequest,
)
from aos_api.aip_assist_context_assembler import (
    AipAssistContextAssembler,
    PostgresAssistAuthorityReader,
)
from aos_api.aip_assist_runtime import AssistRuntimeExecutor, ExactAipAssistRuntime
from aos_api.aip_assist_store import AipAssistStore
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


class AipAssistAuthorityUnavailable(RuntimeError):
    code = "ASSIST_AUTHORITY_UNAVAILABLE"


class AipAssistService(Protocol):
    def list_subjects(self, scope: TenantScope, *, limit: int = 50) -> AssistSubjectOptionList: ...

    def create_thread(
        self,
        scope: TenantScope,
        principal: Principal,
        request: CreateAssistThreadRequest,
        *,
        idempotency_key: str,
    ) -> AssistThreadSnapshot: ...

    def get_thread(self, scope: TenantScope, thread_id: str) -> AssistThreadSnapshot: ...

    def get_history(self, scope: TenantScope, thread_id: str) -> AssistThreadHistory: ...

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

    def list_subjects(self, *args, **kwargs) -> AssistSubjectOptionList:
        self._unavailable()

    def get_thread(self, *args, **kwargs) -> AssistThreadSnapshot:
        self._unavailable()

    def get_history(self, *args, **kwargs) -> AssistThreadHistory:
        self._unavailable()

    def stream_turn(self, *args, **kwargs) -> Iterable[AssistStreamEvent]:
        self._unavailable()


class PostgresAipAssistService:
    def __init__(
        self,
        store: AipAssistStore | None = None,
        runtime: AssistRuntimeExecutor | None = None,
    ) -> None:
        self.store = store or AipAssistStore()
        self.runtime = runtime or ExactAipAssistRuntime(
            AipAssistContextAssembler(PostgresAssistAuthorityReader())
        )

    def create_thread(
        self,
        scope: TenantScope,
        principal: Principal,
        request: CreateAssistThreadRequest,
        *,
        idempotency_key: str,
    ) -> AssistThreadSnapshot:
        return self.store.create_thread(
            scope,
            request,
            idempotency_key=idempotency_key,
            actor=principal.subject,
        )

    def list_subjects(self, scope: TenantScope, *, limit: int = 50) -> AssistSubjectOptionList:
        return self.store.list_subjects(scope, limit=limit)

    def get_thread(self, scope: TenantScope, thread_id: str) -> AssistThreadSnapshot:
        return self.store.get_thread(scope, thread_id)

    def get_history(self, scope: TenantScope, thread_id: str) -> AssistThreadHistory:
        return self.store.get_history(scope, thread_id)

    def stream_turn(
        self,
        scope: TenantScope,
        principal: Principal,
        thread_id: str,
        request: CreateAssistTurnRequest,
        *,
        idempotency_key: str,
    ) -> Iterable[AssistStreamEvent]:
        prepared = self.store.prepare_turn(
            scope,
            thread_id,
            request,
            idempotency_key=idempotency_key,
            actor=principal.subject,
        )
        if prepared.replay is not None:
            return prepared.replay.events
        first_sequence = len(prepared.events) + 1
        if prepared.resumed:
            suffix = [
                AssistStreamEvent(
                    event_type=AssistEventType.BLOCKED,
                    thread_id=thread_id,
                    turn_id=prepared.turn_id,
                    sequence=first_sequence,
                    occurred_at=datetime.now(UTC),
                    blocker=AssistBlocker(
                        code="ASSIST_TURN_RECOVERY_REQUIRED",
                        message="An interrupted Assist turn requires an explicit new turn",
                        retryable=True,
                    ),
                )
            ]
        else:
            try:
                suffix = self.runtime.execute(
                    scope,
                    prepared.thread.subject,
                    request.message,
                    principal_markings=principal.markings,
                    thread_id=thread_id,
                    turn_id=prepared.turn_id,
                    first_sequence=first_sequence,
                )
            except Exception:
                suffix = [
                    AssistStreamEvent(
                        event_type=AssistEventType.ERROR,
                        thread_id=thread_id,
                        turn_id=prepared.turn_id,
                        sequence=first_sequence,
                        occurred_at=datetime.now(UTC),
                        blocker=AssistBlocker(
                            code="ASSIST_RUNTIME_FAILED",
                            message="Assist runtime failed before a safe answer was produced",
                            retryable=True,
                        ),
                    )
                ]
        return self.store.finalize_turn(
            scope,
            prepared,
            suffix,
            idempotency_key=idempotency_key,
            actor=principal.subject,
        ).events


__all__ = [
    "AipAssistAuthorityUnavailable",
    "AipAssistService",
    "PostgresAipAssistService",
    "UnavailableAipAssistService",
]
