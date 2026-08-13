"""Authority-first natural-language search over governed AIP knowledge."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_memory_contracts import (
    KnowledgeCitation,
    KnowledgeContextChunk,
    KnowledgeSearch,
    KnowledgeSearchLane,
    KnowledgeSearchMatch,
    KnowledgeSearchResult,
    KnowledgeSourceRef,
)
from aos_api.aip_memory_retrieval import PayloadResolver
from aos_api.aip_memory_search_index import AipMemorySearchIndex, SearchCapability
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


class AipMemoryKnowledgeSearch:
    def __init__(
        self,
        *,
        payload_resolver: PayloadResolver,
        index: AipMemorySearchIndex | None = None,
        connect_factory=None,
    ) -> None:
        self._payload_resolver = payload_resolver
        self._index = index or AipMemorySearchIndex(connect_factory)
        self._connect_factory = connect_factory or db_connect

    def search(
        self,
        scope: TenantScope,
        request: KnowledgeSearch,
        *,
        authorized_markings: list[str],
        required_applicability: list[str],
    ) -> KnowledgeSearchResult:
        if not set(request.markings).issubset(set(authorized_markings)):
            return self._blocked("requested_marking_forbidden")
        wanted = [value.strip() for value in required_applicability if value.strip()]
        if not wanted:
            return self._blocked("applicability_required")
        lanes = self._lanes(scope)
        fulltext = lanes[0]
        lane_reasons = [lane.reason_code for lane in lanes if lane.reason_code]
        if fulltext.status != "ready":
            return self._blocked(*(lane_reasons or ["search_capability_unavailable"]), lanes=lanes)
        hits = self._index.search_references(
            scope,
            request.query,
            authorized_markings=authorized_markings,
            required_applicability=wanted,
            time_cutoff=request.time_cutoff,
            limit=request.limit,
        )
        rows = self._authority_rows(scope, [hit.memory_item_id for hit in hits])
        by_id = {row["memory_item_id"]: row for row in rows}
        matches: list[KnowledgeSearchMatch] = []
        reasons = list(lane_reasons)
        used_tokens = 0
        for hit in hits:
            row = by_id.get(hit.memory_item_id)
            reason = self._ineligible(
                row,
                hit.revision,
                hit.content_hash,
                time_cutoff=request.time_cutoff,
                authorized_markings=set(authorized_markings),
                required_applicability=set(wanted),
            )
            if reason:
                reasons.append(reason)
                continue
            artifact = ArtifactRef.model_validate(row["payload_ref"])
            try:
                resolved = self._payload_resolver(scope, artifact)
            except Exception:
                reasons.append("payload_authority_unavailable")
                continue
            if resolved.artifact != artifact or artifact.content_hash != row["content_hash"]:
                reasons.append("payload_authority_drift")
                continue
            if used_tokens + resolved.token_count > request.max_tokens:
                reasons.append("token_budget_exceeded")
                continue
            citation = self._citation(row, artifact)
            chunk = KnowledgeContextChunk(
                citation=citation,
                content=resolved.content,
                token_count=resolved.token_count,
            )
            matches.append(
                KnowledgeSearchMatch(citation=citation, chunk=chunk, score=hit.score)
            )
            used_tokens += resolved.token_count
        if not matches:
            return self._blocked(*self._unique(reasons or ["knowledge_not_found"]), lanes=lanes)
        return KnowledgeSearchResult(
            matches=matches,
            lanes=lanes,
            status="degraded" if reasons else "complete",
            blocked_reasons=self._unique(reasons),
            assembled_tokens=used_tokens,
        )

    def _lanes(self, scope: TenantScope) -> list[KnowledgeSearchLane]:
        values = {capability.lane.value: capability for capability in self._index.list_capabilities(scope)}
        defaults = {
            "fulltext": ("unbuilt", "fulltext_index_unbuilt"),
            "vector": ("degraded", "degraded_vector_unavailable"),
            "rerank": ("unbuilt", "rerank_unconfigured"),
        }
        return [
            self._lane(values.get(name), name, defaults[name])
            for name in ("fulltext", "vector", "rerank")
        ]

    @staticmethod
    def _lane(
        capability: SearchCapability | None,
        name: str,
        default: tuple[str, str],
    ) -> KnowledgeSearchLane:
        if capability is None:
            return KnowledgeSearchLane(lane=name, status=default[0], reason_code=default[1])
        return KnowledgeSearchLane(
            lane=name,
            status=capability.status.value,
            reason_code=capability.reason_code,
            provider=capability.provider,
            provider_revision=capability.provider_revision,
        )

    def _authority_rows(self, scope: TenantScope, item_ids: list[str]) -> list[Any]:
        if not item_ids:
            return []
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
                     AND i.memory_item_id=ANY(%s)""",
                (*scope.key, item_ids),
            ).fetchall()

    @staticmethod
    def _ineligible(
        row: Any | None,
        revision: int,
        content_hash: str,
        *,
        time_cutoff: datetime,
        authorized_markings: set[str],
        required_applicability: set[str],
    ) -> str | None:
        if row is None or int(row["revision"]) != revision or row["content_hash"] != content_hash:
            return "reference_authority_drift"
        if row["status"] != "active":
            return f"memory_{row['status']}"
        if row["effective_at"] > time_cutoff:
            return "time_cutoff_excluded"
        if row["expires_at"] is not None and row["expires_at"] <= time_cutoff:
            return "memory_expired"
        if row["freshness_expires_at"] <= time_cutoff:
            return "source_stale"
        if not set(row["markings"]).issubset(authorized_markings):
            return "marking_forbidden"
        if not required_applicability.issubset(set(row["applicability"])):
            return "applicability_mismatch"
        return None

    @staticmethod
    def _citation(row: Any, artifact: ArtifactRef) -> KnowledgeCitation:
        return KnowledgeCitation(
            memory_item_id=row["memory_item_id"],
            revision=int(row["revision"]),
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
            confidence=float(row["confidence"]),
            applicability=row["applicability"],
            markings=row["markings"],
        )

    def _blocked(
        self,
        *reasons: str,
        lanes: list[KnowledgeSearchLane] | None = None,
    ) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            matches=[],
            lanes=lanes or self._default_lanes(),
            status="blocked",
            blocked_reasons=self._unique(list(reasons)),
            assembled_tokens=0,
        )

    @staticmethod
    def _default_lanes() -> list[KnowledgeSearchLane]:
        return [
            KnowledgeSearchLane(lane="fulltext", status="unbuilt", reason_code="fulltext_index_unbuilt"),
            KnowledgeSearchLane(lane="vector", status="degraded", reason_code="degraded_vector_unavailable"),
            KnowledgeSearchLane(lane="rerank", status="unbuilt", reason_code="rerank_unconfigured"),
        ]

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))


__all__ = ["AipMemoryKnowledgeSearch"]
