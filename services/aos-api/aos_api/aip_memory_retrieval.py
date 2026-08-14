"""Authoritative AIP-5 knowledge retrieval and rebuildable reference index."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aos_api.aip_agent_registry_contracts import (
    AgentInstanceStatus,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.aip_contracts import ArtifactRef, ResourceRef, TenantContext
from aos_api.aip_memory_contracts import (
    KnowledgeCitation,
    KnowledgeContextChunk,
    KnowledgeQuery,
    KnowledgeQueryResult,
    KnowledgeScope,
    KnowledgeSourceRef,
)
from aos_api.aip_memory_projection_contracts import (
    MemoryExposure,
    MemoryProjectionExactRef,
    MemoryRevisionExactRef,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

PayloadResolver = Callable[[TenantScope, ArtifactRef], "ResolvedKnowledgePayload"]


class AgentMemoryContextRequest(BaseModel):
    """Trusted assembler input; identity and tenant are never inferred from role names."""

    model_config = ConfigDict(extra="forbid")

    agent_instance_ref: VersionedAssetRef
    skill_ref: VersionedAssetRef
    logic_ref: VersionedAssetRef
    purposes: list[str] = Field(min_length=1, max_length=64)
    authorized_markings: list[str] = Field(min_length=1, max_length=32)
    time_cutoff: datetime
    max_tokens: int = Field(default=4096, ge=1, le=131072)

    @model_validator(mode="after")
    def _exact_instance_and_allowlists(self) -> AgentMemoryContextRequest:
        if self.agent_instance_ref.asset_type != "AgentInstance":
            raise ValueError("agent_instance_ref must reference AgentInstance")
        if self.skill_ref.asset_type != "SkillTemplate":
            raise ValueError("skill_ref must reference SkillTemplate")
        if self.logic_ref.asset_type != "LogicRevision":
            raise ValueError("logic_ref must reference LogicRevision")
        for name, values in (
            ("purposes", self.purposes),
            ("authorized_markings", self.authorized_markings),
        ):
            cleaned = [value.strip() for value in values]
            if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
                raise ValueError(f"{name} must contain unique non-blank values")
            setattr(self, name, cleaned)
        return self


class AgentMemoryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: TenantContext
    agent_instance_ref: VersionedAssetRef
    skill_ref: VersionedAssetRef
    logic_ref: VersionedAssetRef
    purposes: list[str] = Field(min_length=1, max_length=64)
    authorized_markings: list[str] = Field(min_length=1, max_length=32)
    projection_refs: list[MemoryProjectionExactRef] = Field(default_factory=list)
    memory_refs: list[MemoryRevisionExactRef] = Field(default_factory=list)
    citations: list[KnowledgeCitation] = Field(default_factory=list)
    chunks: list[KnowledgeContextChunk] = Field(default_factory=list)
    status: str = Field(pattern=r"^(complete|degraded|blocked)$")
    blocked_reasons: list[str] = Field(default_factory=list)
    assembled_tokens: int = Field(default=0, ge=0)
    time_cutoff: datetime

    @model_validator(mode="after")
    def _one_to_one_context(self) -> AgentMemoryContext:
        for name, values in (
            ("purposes", self.purposes),
            ("authorized_markings", self.authorized_markings),
        ):
            cleaned = [value.strip() for value in values]
            if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
                raise ValueError(f"{name} must contain unique non-blank values")
            setattr(self, name, cleaned)
        sizes = {
            len(self.projection_refs),
            len(self.memory_refs),
            len(self.citations),
            len(self.chunks),
        }
        if len(sizes) != 1:
            raise ValueError(
                "projection, memory, citation and chunk must align one-to-one"
            )
        if self.status == "blocked" and (
            self.projection_refs or self.assembled_tokens or not self.blocked_reasons
        ):
            raise ValueError("blocked context requires no content and stable reasons")
        if self.status == "complete" and (
            not self.projection_refs or self.blocked_reasons
        ):
            raise ValueError("complete context requires content without blockers")
        if self.status == "degraded" and (
            not self.projection_refs or not self.blocked_reasons
        ):
            raise ValueError("degraded context requires content and blockers")
        return self


class MemoryRevocationImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant: TenantContext
    projection_ref: MemoryProjectionExactRef
    projection_status: str
    recipient_count: int = Field(ge=0)
    exposure_count: int = Field(ge=0)
    affected_agent_run_count: int = Field(ge=0)
    affected_agent_run_refs: list[ResourceRef] = Field(default_factory=list)
    re_evaluation_status: str = Field(pattern=r"^(not_required|required|blocked)$")
    blocker_codes: list[str] = Field(default_factory=list)


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
            self.citation is not None
            or self.content is not None
            or not self.blocked_reasons
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

    def candidate_ids(
        self, scope: TenantScope, subject: ResourceRef
    ) -> set[str] | None:
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
                (
                    *scope.key,
                    _stable_json(subject.model_dump(mode="json", by_alias=True)),
                ),
            ).fetchall()

    def _resolve(
        self, scope: TenantScope, artifact: ArtifactRef
    ) -> ResolvedKnowledgePayload | None:
        try:
            return self._payload_resolver(scope, artifact)
        except Exception:
            return None

    def query_exact_memory(
        self,
        scope: TenantScope,
        memory_ref: MemoryRevisionExactRef,
        *,
        time_cutoff: datetime,
        authorized_markings: list[str],
        required_applicability: list[str],
        max_tokens: int,
    ) -> KnowledgeQueryResult:
        """Resolve one exact current Memory revision without subject/scope fallback."""
        if not scope.org_id.strip() or not scope.project_id.strip():
            return _blocked("tenant_scope_invalid")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT i.memory_item_id,i.scope,i.status,i.subject_ref,
                          i.current_revision,r.revision,r.payload_ref,r.content_hash,
                          r.confidence,r.applicability,r.markings,r.effective_at,
                          r.expires_at,s.source_kind,s.source_uri,s.source_ref,
                          s.observed_at,s.freshness_expires_at,s.license_id,
                          s.usage_policy,s.content_hash AS source_content_hash,
                          s.provider,s.provider_version,
                          s.applicability AS source_applicability
                   FROM aip_memory_item i
                   JOIN aip_memory_item_revision r ON r.org_id=i.org_id
                    AND r.project_id=i.project_id AND r.memory_item_id=i.memory_item_id
                   JOIN aip_memory_source_revision s ON s.org_id=r.org_id
                    AND s.project_id=r.project_id AND s.source_id=r.source_id
                    AND s.revision=r.source_revision
                   WHERE i.org_id=%s AND i.project_id=%s AND i.memory_item_id=%s
                     AND r.revision=%s""",
                (*scope.key, memory_ref.memory_item_id, memory_ref.revision),
            ).fetchone()
        if row is None:
            return _blocked("exact_memory_not_found")
        reasons: list[str] = []
        if row["content_hash"] != memory_ref.content_hash:
            reasons.append("memory_hash_drifted")
        if int(row["current_revision"]) != memory_ref.revision:
            reasons.append("memory_revision_not_current")
        if row["status"] != "active":
            reasons.append(f"memory_{row['status']}")
        if row["effective_at"] > time_cutoff:
            reasons.append("time_cutoff_excluded")
        if row["expires_at"] is not None and row["expires_at"] <= time_cutoff:
            reasons.append("memory_expired")
        if row["freshness_expires_at"] <= time_cutoff:
            reasons.append("source_stale")
        if not set(row["markings"]).issubset(set(authorized_markings)):
            reasons.append("marking_forbidden")
        wanted = {value.strip() for value in required_applicability if value.strip()}
        if not wanted or not wanted.issubset(set(row["applicability"])):
            reasons.append("applicability_mismatch")
        if reasons:
            return _blocked(*_unique(reasons))
        artifact = ArtifactRef.model_validate(row["payload_ref"])
        resolved = self._resolve(scope, artifact)
        if resolved is None or resolved.artifact != artifact:
            return _blocked("payload_authority_drift")
        if resolved.token_count > max_tokens:
            return _blocked("token_budget_exceeded")
        citation = _citation_from_row(row, artifact)
        return KnowledgeQueryResult(
            citations=[citation],
            chunks=[
                KnowledgeContextChunk(
                    citation=citation,
                    content=resolved.content,
                    token_count=resolved.token_count,
                )
            ],
            status="complete",
            blocked_reasons=[],
            assembled_tokens=resolved.token_count,
        )


class AipAgentMemoryRetrieval:
    """E7 exact-instance projection adapter and append-only exposure authority."""

    def __init__(
        self,
        *,
        payload_resolver: PayloadResolver,
        connect_factory=None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._knowledge = AipMemoryRetrieval(
            payload_resolver=payload_resolver,
            connect_factory=self._connect_factory,
        )

    def query_context(
        self, scope: TenantScope, request: AgentMemoryContextRequest
    ) -> AgentMemoryContext:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if not scope.org_id.strip() or not scope.project_id.strip():
            return self._blocked_context(tenant, request, "tenant_scope_invalid")
        with self._connect_factory(scope) as conn:
            instance = self._exact_active_instance(
                conn, scope, request.agent_instance_ref
            )
            if instance is None:
                return self._blocked_context(
                    tenant, request, "agent_instance_not_exact_and_active"
                )
            rows = conn.execute(
                """SELECT DISTINCT p.*
                   FROM aip_memory_agent_projection p
                   LEFT JOIN aip_memory_agent_projection_recipient r
                     ON r.org_id=p.org_id AND r.project_id=p.project_id
                    AND r.projection_id=p.projection_id
                   WHERE p.org_id=%s AND p.project_id=%s AND p.status='active'
                     AND p.effective_at<=%s AND p.expires_at>%s
                     AND ((p.kind='personal' AND p.owner_instance_id=%s
                           AND p.owner_instance_version=%s
                           AND p.owner_instance_hash=%s)
                       OR (p.kind='shared' AND r.recipient_instance_id=%s
                           AND r.recipient_instance_version=%s
                           AND r.recipient_instance_hash=%s))
                   ORDER BY p.projection_id""",
                (
                    *scope.key,
                    request.time_cutoff,
                    request.time_cutoff,
                    request.agent_instance_ref.asset_id,
                    request.agent_instance_ref.revision,
                    request.agent_instance_ref.content_hash,
                    request.agent_instance_ref.asset_id,
                    request.agent_instance_ref.revision,
                    request.agent_instance_ref.content_hash,
                ),
            ).fetchall()
        if not rows:
            return self._blocked_context(tenant, request, "projection_not_found")

        projection_refs: list[MemoryProjectionExactRef] = []
        memory_refs: list[MemoryRevisionExactRef] = []
        citations: list[KnowledgeCitation] = []
        chunks: list[KnowledgeContextChunk] = []
        reasons: list[str] = []
        used_tokens = 0
        for row in rows:
            with self._connect_factory(scope) as conn:
                owner_ref = VersionedAssetRef.model_validate(row["owner_instance_ref"])
                if self._exact_active_instance(conn, scope, owner_ref) is None:
                    reasons.append(
                        f"{row['projection_id']}:owner_instance_inactive_or_drifted"
                    )
                    continue
            if not set(request.purposes).issubset(set(row["allowed_purposes"])):
                reasons.append(f"{row['projection_id']}:purpose_forbidden")
                continue
            if not set(row["allowed_markings"]).issubset(
                set(request.authorized_markings)
            ):
                reasons.append(f"{row['projection_id']}:marking_forbidden")
                continue
            projection_ref = MemoryProjectionExactRef(
                projection_id=row["projection_id"],
                version=int(row["version"]),
                content_hash=row["content_hash"],
            )
            memory_ref = MemoryRevisionExactRef.model_validate(row["memory_ref"])
            result = self._knowledge.query_exact_memory(
                scope,
                memory_ref,
                time_cutoff=request.time_cutoff,
                authorized_markings=request.authorized_markings,
                required_applicability=request.purposes,
                max_tokens=request.max_tokens - used_tokens,
            )
            if result.status == "blocked":
                reasons.extend(
                    f"{row['projection_id']}:{reason}"
                    for reason in result.blocked_reasons
                )
                continue
            projection_refs.append(projection_ref)
            memory_refs.append(memory_ref)
            citations.extend(result.citations)
            chunks.extend(result.chunks)
            used_tokens += result.assembled_tokens
        if not projection_refs:
            return self._blocked_context(
                tenant, request, *(_unique(reasons) or ["projection_not_found"])
            )
        return AgentMemoryContext(
            tenant=tenant,
            agent_instance_ref=request.agent_instance_ref,
            skill_ref=request.skill_ref,
            logic_ref=request.logic_ref,
            purposes=request.purposes,
            authorized_markings=request.authorized_markings,
            projection_refs=projection_refs,
            memory_refs=memory_refs,
            citations=citations,
            chunks=chunks,
            status="degraded" if reasons else "complete",
            blocked_reasons=_unique(reasons),
            assembled_tokens=used_tokens,
            time_cutoff=request.time_cutoff,
        )

    def accept_context(
        self,
        scope: TenantScope,
        context: AgentMemoryContext,
        *,
        agent_run_ref: ResourceRef,
        task_run_ref: ResourceRef,
        eval_contract_ref: VersionedAssetRef,
        accepted_at: datetime,
    ) -> list[MemoryExposure]:
        if context.status == "blocked" or not context.projection_refs:
            raise ValueError("blocked or empty context cannot be accepted")
        if context.tenant != TenantContext(
            org_id=scope.org_id, project_id=scope.project_id
        ):
            raise ValueError("context tenant does not match authority scope")
        if context.time_cutoff > accepted_at:
            raise ValueError("context time cutoff cannot be after acceptance")
        with self._connect_factory(scope) as conn:
            if (
                self._exact_active_instance(conn, scope, context.agent_instance_ref)
                is None
            ):
                raise ValueError("context AgentInstance is no longer exact and active")
            run = self._require_exact_running_run(
                conn,
                scope,
                agent_run_ref,
                task_run_ref,
                context.agent_instance_ref,
            )
            if (
                VersionedAssetRef.model_validate(run["skill_ref"]) != context.skill_ref
                or VersionedAssetRef.model_validate(run["logic_ref"])
                != context.logic_ref
            ):
                raise ValueError("AgentRun Skill/Logic does not match accepted context")
            self._require_frozen_eval_contract(conn, scope, eval_contract_ref)
            exposures: list[MemoryExposure] = []
            for projection_ref, memory_ref in zip(
                context.projection_refs, context.memory_refs, strict=True
            ):
                self._require_current_projection(
                    conn,
                    scope,
                    context,
                    projection_ref,
                    memory_ref,
                    accepted_at,
                )
                exposure = self._build_exposure(
                    scope,
                    run,
                    agent_run_ref,
                    task_run_ref,
                    context,
                    projection_ref,
                    memory_ref,
                    eval_contract_ref,
                    accepted_at,
                )
                existing = conn.execute(
                    """SELECT * FROM aip_memory_exposure
                       WHERE org_id=%s AND project_id=%s AND agent_run_id=%s
                         AND projection_id=%s AND memory_item_id=%s
                         AND memory_revision=%s""",
                    (
                        *scope.key,
                        agent_run_ref.resource_id,
                        projection_ref.projection_id,
                        memory_ref.memory_item_id,
                        memory_ref.revision,
                    ),
                ).fetchone()
                if existing is not None:
                    if existing["exposure_hash"] != exposure.exposure_hash:
                        raise ValueError("exposure exact tuple drifted")
                    exposures.append(exposure)
                    continue
                conn.execute(
                    """INSERT INTO aip_memory_exposure (
                       org_id,project_id,exposure_id,agent_run_id,task_run_id,
                       instance_id,instance_version,instance_hash,skill_ref,logic_ref,
                       projection_id,projection_version,projection_hash,
                       memory_item_id,memory_revision,memory_hash,eval_contract_ref,
                       time_cutoff,accepted_at,exposure_hash)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s,
                         %s,%s,%s,%s::jsonb,%s,%s,%s)""",
                    (
                        *scope.key,
                        exposure.exposure_id,
                        exposure.agent_run_ref.resource_id,
                        exposure.task_run_ref.resource_id,
                        exposure.agent_instance_ref.asset_id,
                        exposure.agent_instance_ref.revision,
                        exposure.agent_instance_ref.content_hash,
                        _stable_json(
                            exposure.skill_ref.model_dump(mode="json", by_alias=True)
                        ),
                        _stable_json(
                            exposure.logic_ref.model_dump(mode="json", by_alias=True)
                        ),
                        exposure.projection_ref.projection_id,
                        exposure.projection_ref.version,
                        exposure.projection_ref.content_hash,
                        exposure.memory_ref.memory_item_id,
                        exposure.memory_ref.revision,
                        exposure.memory_ref.content_hash,
                        _stable_json(
                            exposure.eval_contract_ref.model_dump(
                                mode="json", by_alias=True
                            )
                        ),
                        exposure.time_cutoff,
                        exposure.accepted_at,
                        exposure.exposure_hash,
                    ),
                )
                exposures.append(exposure)
            conn.commit()
            return exposures

    def revocation_impact(
        self, scope: TenantScope, projection_id: str, *, observed_at: datetime
    ) -> MemoryRevocationImpact:
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """SELECT p.*,
                     (SELECT COUNT(*) FROM aip_memory_agent_projection_recipient r
                       WHERE r.org_id=p.org_id AND r.project_id=p.project_id
                         AND r.projection_id=p.projection_id) AS recipient_count,
                     (SELECT COUNT(*) FROM aip_memory_exposure e
                       WHERE e.org_id=p.org_id AND e.project_id=p.project_id
                         AND e.projection_id=p.projection_id) AS exposure_count,
                     (SELECT COUNT(DISTINCT e.agent_run_id) FROM aip_memory_exposure e
                       WHERE e.org_id=p.org_id AND e.project_id=p.project_id
                         AND e.projection_id=p.projection_id) AS run_count
                   FROM aip_memory_agent_projection p
                   WHERE p.org_id=%s AND p.project_id=%s AND p.projection_id=%s""",
                (*scope.key, projection_id),
            ).fetchone()
            if row is None:
                raise ValueError("projection not found")
            run_rows = conn.execute(
                """SELECT DISTINCT e.agent_run_id,r.version
                   FROM aip_memory_exposure e
                   JOIN aip_agent_run r ON r.org_id=e.org_id AND r.project_id=e.project_id
                    AND r.agent_run_id=e.agent_run_id
                   WHERE e.org_id=%s AND e.project_id=%s AND e.projection_id=%s
                   ORDER BY e.agent_run_id LIMIT 100""",
                (*scope.key, projection_id),
            ).fetchall()
            dependency = self._projection_dependency_blockers(
                conn, scope, row, observed_at
            )
        blockers = _unique(dependency)
        return MemoryRevocationImpact(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            projection_ref=MemoryProjectionExactRef(
                projection_id=row["projection_id"],
                version=int(row["version"]),
                content_hash=row["content_hash"],
            ),
            projection_status=row["status"],
            recipient_count=int(row["recipient_count"]),
            exposure_count=int(row["exposure_count"]),
            affected_agent_run_count=int(row["run_count"]),
            affected_agent_run_refs=[
                ResourceRef(
                    resource_type="AgentRun",
                    resource_id=value["agent_run_id"],
                    revision=str(value["version"]),
                    authority="postgresql",
                )
                for value in run_rows
            ],
            re_evaluation_status="required" if blockers else "not_required",
            blocker_codes=blockers,
        )

    @staticmethod
    def _blocked_context(tenant, request, *reasons) -> AgentMemoryContext:
        return AgentMemoryContext(
            tenant=tenant,
            agent_instance_ref=request.agent_instance_ref,
            skill_ref=request.skill_ref,
            logic_ref=request.logic_ref,
            purposes=request.purposes,
            authorized_markings=request.authorized_markings,
            status="blocked",
            blocked_reasons=_unique(list(reasons)),
            time_cutoff=request.time_cutoff,
        )

    @staticmethod
    def _exact_active_instance(conn, scope, ref):
        row = conn.execute(
            """SELECT i.*,t.content_hash FROM aip_agent_instance i
               JOIN aip_agent_template_revision t ON t.template_id=i.template_id
                AND t.revision=i.template_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.instance_id=%s""",
            (*scope.key, ref.asset_id),
        ).fetchone()
        if row is None:
            return None
        instance = AipAgentRegistryStore._instance_from_row(scope, row)
        if (
            instance.instance_ref != ref
            or instance.status is not AgentInstanceStatus.ACTIVE
        ):
            return None
        return instance

    @classmethod
    def _require_exact_running_run(
        cls, conn, scope, agent_run_ref, task_run_ref, instance_ref
    ):
        if (
            agent_run_ref.resource_type != "AgentRun"
            or not agent_run_ref.revision
            or agent_run_ref.authority != "postgresql"
        ):
            raise ValueError("exact AgentRun revision required")
        if (
            task_run_ref.resource_type != "TaskRun"
            or not task_run_ref.revision
            or task_run_ref.authority != "postgresql"
        ):
            raise ValueError("exact TaskRun revision required")
        row = conn.execute(
            """SELECT a.*,t.version AS task_run_version,t.status AS task_run_status
               FROM aip_agent_run a JOIN aip_task_run t
                 ON t.org_id=a.org_id AND t.project_id=a.project_id
                AND t.run_id=a.task_run_id
               WHERE a.org_id=%s AND a.project_id=%s AND a.agent_run_id=%s""",
            (*scope.key, agent_run_ref.resource_id),
        ).fetchone()
        if row is None or row["task_run_id"] != task_run_ref.resource_id:
            raise ValueError("exact AgentRun/TaskRun authority not found")
        if (
            str(row["version"]) != agent_run_ref.revision
            or str(row["task_run_version"]) != task_run_ref.revision
        ):
            raise ValueError("AgentRun or TaskRun exact revision drifted")
        if row["status"] != "running" or row["task_run_status"] != "running":
            raise ValueError("context can only be accepted by a running AgentRun")
        if VersionedAssetRef.model_validate(row["instance_ref"]) != instance_ref:
            raise ValueError("AgentRun instance does not match context")
        return row

    @staticmethod
    def _require_frozen_eval_contract(conn, scope, ref):
        if ref.asset_type != "EvalContract":
            raise ValueError("eval_contract_ref must reference EvalContract")
        row = conn.execute(
            """SELECT content_hash,lifecycle FROM aip_eval_contract_revision
               WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s""",
            (*scope.key, ref.asset_id, ref.revision),
        ).fetchone()
        if (
            row is None
            or row["content_hash"] != ref.content_hash
            or row["lifecycle"] != "frozen"
        ):
            raise ValueError("exact frozen EvalContract not found")

    @classmethod
    def _require_current_projection(
        cls, conn, scope, context, projection_ref, memory_ref, accepted_at
    ):
        row = conn.execute(
            """SELECT p.* FROM aip_memory_agent_projection p
               LEFT JOIN aip_memory_agent_projection_recipient r
                 ON r.org_id=p.org_id AND r.project_id=p.project_id
                AND r.projection_id=p.projection_id
               WHERE p.org_id=%s AND p.project_id=%s AND p.projection_id=%s
                 AND ((p.kind='personal' AND p.owner_instance_id=%s
                       AND p.owner_instance_version=%s AND p.owner_instance_hash=%s)
                   OR (p.kind='shared' AND r.recipient_instance_id=%s
                       AND r.recipient_instance_version=%s AND r.recipient_instance_hash=%s))
               LIMIT 1""",
            (
                *scope.key,
                projection_ref.projection_id,
                context.agent_instance_ref.asset_id,
                context.agent_instance_ref.revision,
                context.agent_instance_ref.content_hash,
                context.agent_instance_ref.asset_id,
                context.agent_instance_ref.revision,
                context.agent_instance_ref.content_hash,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("projection is not authorized for exact AgentInstance")
        exact = MemoryProjectionExactRef(
            projection_id=row["projection_id"],
            version=int(row["version"]),
            content_hash=row["content_hash"],
        )
        if (
            exact != projection_ref
            or MemoryRevisionExactRef.model_validate(row["memory_ref"]) != memory_ref
        ):
            raise ValueError("projection or memory exact reference drifted")
        if not set(context.purposes).issubset(set(row["allowed_purposes"])):
            raise ValueError("projection purpose no longer authorizes context")
        if not set(row["allowed_markings"]).issubset(set(context.authorized_markings)):
            raise ValueError("projection markings no longer authorize context")
        blockers = cls._projection_dependency_blockers(conn, scope, row, accepted_at)
        if blockers:
            raise ValueError(",".join(blockers))
        return row

    @classmethod
    def _projection_dependency_blockers(cls, conn, scope, row, observed_at):
        blockers: list[str] = []
        if row["status"] != "active":
            blockers.append(f"projection_{row['status']}")
        if observed_at < row["effective_at"] or observed_at >= row["expires_at"]:
            blockers.append("projection_outside_effective_interval")
        owner = VersionedAssetRef.model_validate(row["owner_instance_ref"])
        if cls._exact_active_instance(conn, scope, owner) is None:
            blockers.append("owner_instance_inactive_or_drifted")
        recipients = conn.execute(
            """SELECT recipient_instance_ref
               FROM aip_memory_agent_projection_recipient
               WHERE org_id=%s AND project_id=%s AND projection_id=%s""",
            (*scope.key, row["projection_id"]),
        ).fetchall()
        if any(
            cls._exact_active_instance(
                conn,
                scope,
                VersionedAssetRef.model_validate(value["recipient_instance_ref"]),
            )
            is None
            for value in recipients
        ):
            blockers.append("recipient_instance_inactive_or_drifted")
        memory = conn.execute(
            """SELECT i.status,i.current_revision,r.content_hash,r.expires_at,
                      r.markings,r.applicability,
                      s.freshness_expires_at
               FROM aip_memory_item i JOIN aip_memory_item_revision r
                 ON r.org_id=i.org_id AND r.project_id=i.project_id
                AND r.memory_item_id=i.memory_item_id
               JOIN aip_memory_source_revision s ON s.org_id=r.org_id
                AND s.project_id=r.project_id AND s.source_id=r.source_id
                AND s.revision=r.source_revision
               WHERE i.org_id=%s AND i.project_id=%s AND i.memory_item_id=%s
                 AND r.revision=%s""",
            (*scope.key, row["memory_item_id"], row["memory_revision"]),
        ).fetchone()
        if memory is None:
            blockers.append("exact_memory_not_found")
        else:
            if memory["status"] != "active":
                blockers.append(f"memory_{memory['status']}")
            if int(memory["current_revision"]) != int(row["memory_revision"]):
                blockers.append("memory_revision_not_current")
            if memory["content_hash"] != row["memory_hash"]:
                blockers.append("memory_hash_drifted")
            if not set(memory["markings"]).issubset(set(row["allowed_markings"])):
                blockers.append("memory_marking_outside_projection")
            if not set(row["allowed_purposes"]).issubset(set(memory["applicability"])):
                blockers.append("memory_applicability_outside_projection")
            if memory["expires_at"] is not None and memory["expires_at"] <= observed_at:
                blockers.append("memory_expired")
            if memory["freshness_expires_at"] <= observed_at:
                blockers.append("source_stale")
        return _unique(blockers)

    @staticmethod
    def _build_exposure(
        scope,
        run,
        agent_run_ref,
        task_run_ref,
        context,
        projection_ref,
        memory_ref,
        eval_ref,
        accepted_at,
    ):
        skill_ref = VersionedAssetRef.model_validate(run["skill_ref"])
        logic_ref = VersionedAssetRef.model_validate(run["logic_ref"])
        seed = {
            "agentRunRef": agent_run_ref.model_dump(mode="json", by_alias=True),
            "projectionRef": projection_ref.model_dump(mode="json", by_alias=True),
            "memoryRef": memory_ref.model_dump(mode="json", by_alias=True),
        }
        exposure_id = (
            f"aip5e7x-{hashlib.sha256(_stable_json(seed).encode()).hexdigest()[:32]}"
        )
        unsigned = {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "exposureId": exposure_id,
            "agentRunRef": agent_run_ref.model_dump(mode="json", by_alias=True),
            "taskRunRef": task_run_ref.model_dump(mode="json", by_alias=True),
            "agentInstanceRef": context.agent_instance_ref.model_dump(
                mode="json", by_alias=True
            ),
            "skillRef": skill_ref.model_dump(mode="json", by_alias=True),
            "logicRef": logic_ref.model_dump(mode="json", by_alias=True),
            "projectionRef": projection_ref.model_dump(mode="json", by_alias=True),
            "memoryRef": memory_ref.model_dump(mode="json", by_alias=True),
            "evalContractRef": eval_ref.model_dump(mode="json", by_alias=True),
            "timeCutoff": context.time_cutoff.isoformat(),
            "acceptedAt": accepted_at.isoformat(),
        }
        return MemoryExposure(
            **unsigned,
            exposureHash=hashlib.sha256(_stable_json(unsigned).encode()).hexdigest(),
        )


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
            return O1WikiReadResult(
                status="blocked", blocked_reasons=["wiki_not_found"]
            )
        body = row["body"] if isinstance(row["body"], dict) else {}
        envelope = body.get("governance")
        if not isinstance(envelope, dict):
            return O1WikiReadResult(
                status="blocked",
                blocked_reasons=["wiki_governance_envelope_missing"],
            )
        required = {
            "revision",
            "contentHash",
            "source",
            "confidence",
            "applicability",
            "markings",
            "payload",
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
                return O1WikiReadResult(
                    status="blocked", blocked_reasons=["source_stale"]
                )
            if not set(envelope["markings"]).issubset(set(authorized_markings)):
                return O1WikiReadResult(
                    status="blocked", blocked_reasons=["marking_forbidden"]
                )
            wanted = {
                value.strip() for value in required_applicability if value.strip()
            }
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


def _citation_from_row(row: Any, artifact: ArtifactRef) -> KnowledgeCitation:
    return KnowledgeCitation(
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
    "AgentMemoryContext",
    "AgentMemoryContextRequest",
    "AipAgentMemoryRetrieval",
    "AipMemoryRetrieval",
    "AipMemoryRetrievalIndex",
    "MemoryRevocationImpact",
    "O1WikiKnowledgeAdapter",
    "O1WikiReadResult",
    "PayloadResolver",
    "ResolvedKnowledgePayload",
]
