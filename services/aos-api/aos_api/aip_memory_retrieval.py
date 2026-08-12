"""Authoritative AIP-5 knowledge retrieval and rebuildable reference index."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    KnowledgeCitation,
    KnowledgeContextChunk,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeScope,
    KnowledgeSourceRef,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

PayloadResolver = Callable[[TenantScope, ArtifactRef], "ResolvedKnowledgePayload"]


class ResolvedKnowledgePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: ArtifactRef
    content: str = Field(min_length=1)
    token_count: int = Field(ge=1)


class O1WikiReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern=r"^(complete|blocked)$")
    citation: KnowledgeCitation | None = None
    content: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _result_shape_is_consistent(self) -> O1WikiReadResult:
        if self.status == "complete" and (
            self.citation is None or self.content is None or self.blocked_reasons
        ):
            raise ValueError("complete Wiki read requires citation and content")
        if self.status == "blocked" and (
            self.citation is not None or self.content is not None or not self.blocked_reasons
        ):
            raise ValueError("blocked Wiki read requires reasons and no content")
        return self


@dataclass(frozen=True)
class _IndexRef:
    memory_item_id: str
    revision: int
    content_hash: str
    subject_key: str


class AipMemoryRetrievalIndex:
    """Ephemeral reference-only index; PostgreSQL remains authoritative."""

    def __init__(self, connect_factory=None) -> None:
        self._connect_factory = connect_factory or db_connect
        self._refs: dict[tuple[str, str], list[_IndexRef]] = {}
        self._state: dict[tuple[str, str], str] = {}

    def state(self, scope: TenantScope) -> str:
        return self._state.get(scope.key, "unbuilt")

    def clear(self, scope: TenantScope) -> None:
        self._refs.pop(scope.key, None)
        self._state[scope.key] = "unavailable"

    def rebuild(self, scope: TenantScope) -> int:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT i.memory_item_id,i.current_revision,r.content_hash,
                          i.subject_ref
                   FROM aip_memory_item i
                   JOIN aip_memory_item_revision r
                     ON r.org_id=i.org_id AND r.project_id=i.project_id
                    AND r.memory_item_id=i.memory_item_id
                    AND r.revision=i.current_revision
                   WHERE i.org_id=%s AND i.project_id=%s""",
                scope.key,
            ).fetchall()
        self._refs[scope.key] = [
            _IndexRef(
                memory_item_id=row["memory_item_id"],
                revision=int(row["current_revision"]),
                content_hash=row["content_hash"],
                subject_key=_stable_json(row["subject_ref"]),
            )
            for row in rows
        ]
        self._state[scope.key] = "ready"
        return len(rows)

    def candidate_ids(self, scope: TenantScope, subject: ResourceRef) -> set[str] | None:
        if self.state(scope) == "unbuilt":
            self.rebuild(scope)
        if self.state(scope) != "ready":
            return None
        key = _stable_json(subject.model_dump(mode="json", by_alias=True))
        return {
            ref.memory_item_id
            for ref in self._refs.get(scope.key, [])
            if ref.subject_key == key
        }


class AipMemoryRetrieval:
    def __init__(
        self,
        *,
        payload_resolver: PayloadResolver,
        index: AipMemoryRetrievalIndex | None = None,
        connect_factory=None,
    ) -> None:
        self._payload_resolver = payload_resolver
        self._index = index
        self._connect_factory = connect_factory or db_connect

    def query(
        self,
        scope: TenantScope,
        request: KnowledgeQuery,
        *,
        authorized_markings: list[str],
        required_applicability: list[str],
    ) -> KnowledgeQueryResult:
        if not scope.org_id.strip() or not scope.project_id.strip():
            return _blocked("tenant_scope_invalid")
        reasons: list[str] = []
        allowed_markings = set(authorized_markings)
        if not set(request.markings).issubset(allowed_markings):
            return _blocked("requested_marking_forbidden")
        wanted_applicability = {
            value.strip() for value in required_applicability if value.strip()
        }
        subjects = [request.subject]
        seen = {_stable_json(request.subject.model_dump(mode="json", by_alias=True))}
        for subject in request.object_refs:
            key = _stable_json(subject.model_dump(mode="json", by_alias=True))
            if key not in seen:
                subjects.append(subject)
                seen.add(key)
        selected: list[Any] = []
        index_degraded = False
        for subject in subjects:
            row, subject_reasons, degraded = self._select_subject(
                scope,
                subject,
                time_cutoff=request.time_cutoff,
                allowed_markings=allowed_markings,
                wanted_applicability=wanted_applicability,
            )
            reasons.extend(subject_reasons)
            index_degraded = index_degraded or degraded
            if row is not None:
                selected.append(row)
        if not selected:
            return _blocked(*_unique(reasons or ["knowledge_not_found"]))

        citations: list[KnowledgeCitation] = []
        chunks: list[KnowledgeContextChunk] = []
        used_tokens = 0
        for row in selected:
            artifact = ArtifactRef.model_validate(row["payload_ref"])
            resolved = self._resolve(scope, artifact)
            if resolved is None or resolved.artifact != artifact:
                reasons.append("payload_authority_drift")
                continue
            if used_tokens + resolved.token_count > request.max_tokens:
                reasons.append("token_budget_exceeded")
                continue
            citation = KnowledgeCitation(
                memory_item_id=row["memory_item_id"],
                revision=row["revision"],
                scope=row["scope"],
                subject=row["subject_ref"],
                payload=artifact,
                content_hash=row["content_hash"],
                source=KnowledgeSourceRef(
                    source_kind=row["source_kind"],
                    source_uri=row["source_uri"],
                    source_ref=row["source_ref"],
                    observed_at=row["observed_at"],
                    freshness_expires_at=row["freshness_expires_at"],
                    license_id=row["license_id"],
                    usage_policy=row["usage_policy"],
                    content_hash=row["source_content_hash"],
                    provider=row["provider"],
                    provider_version=row["provider_version"],
                    applicability=row["source_applicability"],
                ),
                freshness="active",
                confidence=row["confidence"],
                applicability=row["applicability"],
                markings=row["markings"],
            )
            citations.append(citation)
            chunks.append(
                KnowledgeContextChunk(
                    citation=citation,
                    content=resolved.content,
                    token_count=resolved.token_count,
                )
            )
            used_tokens += resolved.token_count
        if not citations:
            return _blocked(*_unique(reasons or ["knowledge_not_found"]))
        if index_degraded:
            reasons.append("index_unavailable_authority_scan")
        return KnowledgeQueryResult(
            citations=citations,
            chunks=chunks,
            status="degraded" if reasons else "complete",
            blocked_reasons=_unique(reasons),
            assembled_tokens=used_tokens,
        )

    def _select_subject(
        self,
        scope: TenantScope,
        subject: ResourceRef,
        *,
        time_cutoff: datetime,
        allowed_markings: set[str],
        wanted_applicability: set[str],
    ) -> tuple[Any | None, list[str], bool]:
        index_ids: set[str] | None = None
        index_degraded = False
        if self._index is not None:
            index_ids = self._index.candidate_ids(scope, subject)
            index_degraded = index_ids is None
        rows = self._authority_rows(scope, subject)
        if index_ids is not None:
            rows = [row for row in rows if row["memory_item_id"] in index_ids]
        if not rows:
            return None, ["knowledge_not_found"], index_degraded
        reasons: list[str] = []
        eligible: list[Any] = []
        for row in rows:
            if row["status"] != "active":
                reasons.append(f"memory_{row['status']}")
            elif row["effective_at"] > time_cutoff:
                reasons.append("time_cutoff_excluded")
            elif row["expires_at"] is not None and row["expires_at"] <= time_cutoff:
                reasons.append("memory_expired")
            elif row["freshness_expires_at"] <= time_cutoff:
                reasons.append("source_stale")
            elif not set(row["markings"]).issubset(allowed_markings):
                reasons.append("marking_forbidden")
            elif not wanted_applicability or not wanted_applicability.issubset(
                set(row["applicability"])
            ):
                reasons.append("applicability_mismatch")
            else:
                eligible.append(row)
        if not eligible:
            return None, _unique(reasons or ["knowledge_not_found"]), index_degraded
        priority = {"workspace": 0, "organization": 1, "public_package": 2}
        eligible.sort(
            key=lambda row: (
                priority[row["scope"]],
                -float(row["confidence"]),
                row["memory_item_id"],
            )
        )
        top_scope = eligible[0]["scope"]
        top = [row for row in eligible if row["scope"] == top_scope]
        if len({row["content_hash"] for row in top}) > 1:
            return None, ["memory_conflict"], index_degraded
        return top[0], [], index_degraded

    def _authority_rows(self, scope: TenantScope, subject: ResourceRef) -> list[Any]:
        with self._connect_factory(scope) as conn:
            return conn.execute(
                """SELECT i.memory_item_id,i.scope,i.status,i.subject_ref,
                          r.revision,r.payload_ref,r.content_hash,r.confidence,
                          r.applicability,r.markings,r.effective_at,r.expires_at,
                          s.source_kind,s.source_uri,s.source_ref,s.observed_at,
                          s.freshness_expires_at,s.license_id,s.usage_policy,
                          s.content_hash AS source_content_hash,s.provider,
                          s.provider_version,s.applicability AS source_applicability
                   FROM aip_memory_item i
                   JOIN aip_memory_item_revision r
                     ON r.org_id=i.org_id AND r.project_id=i.project_id
                    AND r.memory_item_id=i.memory_item_id
                    AND r.revision=i.current_revision
                   JOIN aip_memory_source_revision s
                     ON s.org_id=r.org_id AND s.project_id=r.project_id
                    AND s.source_id=r.source_id AND s.revision=r.source_revision
                   WHERE i.org_id=%s AND i.project_id=%s
                     AND i.subject_ref=%s::jsonb""",
                (*scope.key, _stable_json(subject.model_dump(mode="json", by_alias=True))),
            ).fetchall()

    def _resolve(
        self, scope: TenantScope, artifact: ArtifactRef
    ) -> ResolvedKnowledgePayload | None:
        try:
            return self._payload_resolver(scope, artifact)
        except Exception:
            return None


class O1WikiKnowledgeAdapter:
    """Read-only adapter; legacy Wiki pages without governance stay blocked."""

    def __init__(self, connect_factory=None) -> None:
        self._connect_factory = connect_factory or db_connect

    def read(
        self,
        scope: TenantScope,
        object_type: str,
        object_id: str,
        *,
        time_cutoff: datetime,
        authorized_markings: list[str],
        required_applicability: list[str],
    ) -> O1WikiReadResult:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT body FROM wiki_page
                   WHERE org_id=%s AND project_id=%s
                     AND object_type=%s AND object_id=%s""",
                (*scope.key, object_type, object_id),
            ).fetchone()
        if row is None:
            return O1WikiReadResult(status="blocked", blocked_reasons=["wiki_not_found"])
        body = row["body"] if isinstance(row["body"], dict) else {}
        envelope = body.get("governance")
        if not isinstance(envelope, dict):
            return O1WikiReadResult(
                status="blocked",
                blocked_reasons=["wiki_governance_envelope_missing"],
            )
        required = {
            "revision", "contentHash", "source", "confidence",
            "applicability", "markings", "payload",
        }
        if not required.issubset(envelope):
            return O1WikiReadResult(
                status="blocked",
                blocked_reasons=["wiki_governance_envelope_invalid"],
            )
        try:
            content = str(body["content"])
            if hashlib.sha256(content.encode()).hexdigest() != envelope["contentHash"]:
                raise ValueError("wiki content hash drift")
            source = KnowledgeSourceRef.model_validate(envelope["source"])
            if source.freshness_expires_at <= time_cutoff:
                return O1WikiReadResult(status="blocked", blocked_reasons=["source_stale"])
            if not set(envelope["markings"]).issubset(set(authorized_markings)):
                return O1WikiReadResult(
                    status="blocked", blocked_reasons=["marking_forbidden"]
                )
            wanted = {value.strip() for value in required_applicability if value.strip()}
            if not wanted or not wanted.issubset(set(envelope["applicability"])):
                return O1WikiReadResult(
                    status="blocked", blocked_reasons=["applicability_mismatch"]
                )
            artifact = ArtifactRef.model_validate(envelope["payload"])
            if artifact.content_hash != envelope["contentHash"]:
                raise ValueError("Wiki payload hash does not match governed content")
            citation = KnowledgeCitation(
                memory_item_id=f"wiki:{object_type}:{object_id}",
                revision=int(envelope["revision"]),
                scope=KnowledgeScope.WORKSPACE,
                subject=ResourceRef(
                    resource_type="ontology.object",
                    resource_id=f"{object_type}/{object_id}",
                    revision=str(envelope["revision"]),
                    authority="wiki_page",
                ),
                payload=artifact,
                content_hash=envelope["contentHash"],
                source=source,
                freshness="active",
                confidence=float(envelope["confidence"]),
                applicability=list(envelope["applicability"]),
                markings=list(envelope["markings"]),
            )
        except Exception:
            return O1WikiReadResult(
                status="blocked",
                blocked_reasons=["wiki_governance_envelope_invalid"],
            )
        return O1WikiReadResult(status="complete", citation=citation, content=content)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _blocked(*reasons: str) -> KnowledgeQueryResult:
    return KnowledgeQueryResult(
        citations=[],
        chunks=[],
        status="blocked",
        blocked_reasons=_unique(list(reasons)),
        assembled_tokens=0,
    )


__all__ = [
    "AipMemoryRetrieval",
    "AipMemoryRetrievalIndex",
    "O1WikiKnowledgeAdapter",
    "O1WikiReadResult",
    "PayloadResolver",
    "ResolvedKnowledgePayload",
]
