"""Exact Assist runtime; no local answer or implicit Provider fallback."""
from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Protocol

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_assist_context_assembler import (
    AipAssistContextAssembler,
    AssistContextBlocked,
)
from aos_api.aip_assist_contracts import (
    AssistBlocker,
    AssistEventType,
    AssistStreamEvent,
    AssistSubjectRefs,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_llm_adapter import LLMAdapter, LLMRuntimeBlocked
from aos_api.tenant_scope import TenantScope


class AssistRuntimeExecutor(Protocol):
    def execute(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
        message: str,
        *,
        principal_markings: list[str],
        thread_id: str,
        turn_id: str,
        first_sequence: int,
    ) -> list[AssistStreamEvent]: ...


def _blocked(
    *,
    thread_id: str,
    turn_id: str,
    sequence: int,
    code: str,
) -> AssistStreamEvent:
    normalized_code = re.sub(r"[^A-Z0-9_]+", "_", code.upper()).strip("_")
    return AssistStreamEvent(
        event_type=AssistEventType.BLOCKED,
        thread_id=thread_id,
        turn_id=turn_id,
        sequence=sequence,
        occurred_at=datetime.now(UTC),
        blocker=AssistBlocker(
            code=(normalized_code or "ASSIST_RUNTIME_BLOCKED")[:160],
            message="Assist runtime dependency is not ready",
            retryable=False,
        ),
    )


def _resource_ref(value: object) -> ResourceRef:
    ref = VersionedAssetRef.model_validate(value)
    return ResourceRef(
        resource_type=ref.asset_type,
        resource_id=ref.asset_id,
        revision=str(ref.revision),
        authority=f"aip-model-runtime:{ref.content_hash}",
    )


class ExactAipAssistRuntime:
    def __init__(
        self,
        assembler: AipAssistContextAssembler,
        llm: LLMAdapter | None = None,
    ) -> None:
        self._assembler = assembler
        self._llm = llm or LLMAdapter()

    def execute(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
        message: str,
        *,
        principal_markings: list[str],
        thread_id: str,
        turn_id: str,
        first_sequence: int,
    ) -> list[AssistStreamEvent]:
        try:
            context = self._assembler.assemble(
                scope,
                subject,
                principal_markings=principal_markings,
            )
        except AssistContextBlocked as exc:
            return [
                _blocked(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    sequence=first_sequence,
                    code=exc.code,
                )
            ]

        context_event = AssistStreamEvent(
            event_type=AssistEventType.CONTEXT,
            thread_id=thread_id,
            turn_id=turn_id,
            sequence=first_sequence,
            occurred_at=datetime.now(UTC),
            context=context,
        )
        try:
            response = self._llm.chat_exact(
                scope,
                context.model_route_ref.resource_id,
                message,
                lineage_id=turn_id,
                system_prompt=(
                    "你是 AOS Assist。只能依据给定的权威上下文回答；"
                    "不得补造数据、权限、来源或执行结果。"
                ),
            )
        except LLMRuntimeBlocked as exc:
            return [
                context_event,
                _blocked(
                    thread_id=thread_id,
                    turn_id=turn_id,
                    sequence=first_sequence + 1,
                    code=str(exc),
                ),
            ]

        usage_refs = [
            ResourceRef(
                resource_type="ProviderUsageReceipt",
                resource_id=str(receipt_id),
                revision="1",
                authority="aip-provider-usage",
            )
            for receipt_id in response["usageReceiptIds"]
        ]
        lineage_refs = [
            _resource_ref(response[name])
            for name in (
                "routeRef",
                "policyRef",
                "modelRef",
                "providerRef",
                "priceSnapshotRef",
            )
        ]
        delta = AssistStreamEvent(
            event_type=AssistEventType.DELTA,
            thread_id=thread_id,
            turn_id=turn_id,
            sequence=first_sequence + 1,
            occurred_at=datetime.now(UTC),
            content=response["answer"],
        )
        done = AssistStreamEvent(
            event_type=AssistEventType.DONE,
            thread_id=thread_id,
            turn_id=turn_id,
            sequence=first_sequence + 2,
            occurred_at=datetime.now(UTC),
            usage_refs=usage_refs,
            lineage_refs=lineage_refs,
        )
        return [context_event, delta, done]


__all__ = ["AssistRuntimeExecutor", "ExactAipAssistRuntime"]
