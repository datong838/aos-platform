"""Canonical Assist context assembly boundary for AIP-8 P8-4A."""
from __future__ import annotations

import hashlib
import json
from typing import Protocol

from aos_api.aip_assist_contracts import (
    AssistAuthorityContext,
    AssistContextSnapshot,
    AssistSubjectRefs,
)
from aos_api.tenant_scope import TenantScope


class AssistContextBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class AssistAuthorityReader(Protocol):
    def resolve(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
    ) -> AssistAuthorityContext: ...


class AipAssistContextAssembler:
    def __init__(self, reader: AssistAuthorityReader) -> None:
        self._reader = reader

    def assemble(
        self,
        scope: TenantScope,
        subject: AssistSubjectRefs,
        *,
        principal_markings: list[str],
    ) -> AssistContextSnapshot:
        authority = self._reader.resolve(scope, subject)
        if (authority.tenant.org_id, authority.tenant.project_id) != scope.key:
            raise AssistContextBlocked("ASSIST_CONTEXT_TENANT_DRIFT")
        if (
            authority.task_ref != subject.task_ref
            or authority.task_run_ref != subject.task_run_ref
            or authority.agent_run_ref != subject.agent_run_ref
            or authority.selection_refs != subject.selection_refs
            or authority.cutoff_at != subject.cutoff_at
        ):
            raise AssistContextBlocked("ASSIST_CONTEXT_EXACT_REF_DRIFT")
        if not set(authority.markings).issubset(set(principal_markings)):
            raise AssistContextBlocked("ASSIST_CONTEXT_MARKING_DENIED")
        if authority.readiness_blockers:
            raise AssistContextBlocked(authority.readiness_blockers[0].code)

        payload = authority.model_dump(mode="json", by_alias=True)
        context_hash = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return AssistContextSnapshot(**authority.model_dump(), context_hash=context_hash)


__all__ = [
    "AipAssistContextAssembler",
    "AssistAuthorityReader",
    "AssistContextBlocked",
]
