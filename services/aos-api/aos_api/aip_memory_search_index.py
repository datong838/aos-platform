"""Tenant-scoped rebuildable search references and capability projections."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import ResourceRef
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]

_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
_CN_MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_CN_ID = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
_URL = re.compile(r"(?:https?://|www\.)", re.I)


class SearchLane(StrEnum):
    FULLTEXT = "fulltext"
    VECTOR = "vector"
    RERANK = "rerank"


class SearchCapabilityStatus(StrEnum):
    UNBUILT = "unbuilt"
    READY = "ready"
    DEGRADED = "degraded"
    BLOCKED = "blocked"


class SearchReferenceDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    subject: ResourceRef
    source_id: str = Field(min_length=1, max_length=200)
    source_revision: int = Field(ge=1)
    terms: list[str] = Field(min_length=1, max_length=64)
    markings: list[str] = Field(min_length=1, max_length=32)
    applicability: list[str] = Field(min_length=1, max_length=64)
    freshness_expires_at: datetime

    @field_validator("memory_item_id", "source_id")
    @classmethod
    def _trim_identifier(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("search reference identifiers must not be blank")
        return cleaned

    @field_validator("terms")
    @classmethod
    def _safe_terms(cls, values: list[str]) -> list[str]:
        terms = [" ".join(value.split()) for value in values]
        if any(not value or len(value) > 120 for value in terms):
            raise ValueError("search terms must be non-blank and at most 120 characters")
        if len(terms) != len(set(terms)):
            raise ValueError("search terms must be unique")
        text = " ".join(terms)
        if len(text) > 4096:
            raise ValueError("search terms exceed projection limit")
        if any(pattern.search(text) for pattern in (_EMAIL, _CN_MOBILE, _CN_ID, _URL)):
            raise ValueError("search terms must not contain PII or URLs")
        return terms

    @field_validator("markings", "applicability")
    @classmethod
    def _unique_non_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("projection labels must be unique and non-blank")
        return cleaned


class SearchCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lane: SearchLane
    status: SearchCapabilityStatus
    provider: str | None = Field(default=None, max_length=200)
    provider_revision: str | None = Field(default=None, max_length=120)
    reason_code: str | None = Field(default=None, max_length=200)
    version: int = Field(ge=1)
    observed_at: datetime

    @model_validator(mode="after")
    def _consistent_state(self) -> SearchCapability:
        provider = self.provider.strip() if self.provider else None
        revision = self.provider_revision.strip() if self.provider_revision else None
        reason = self.reason_code.strip() if self.reason_code else None
        if self.status is SearchCapabilityStatus.READY:
            if not provider or not revision or reason is not None:
                raise ValueError("ready capability requires provider/revision and no reason")
        elif not reason:
            raise ValueError("non-ready capability requires a reason")
        self.provider = provider
        self.provider_revision = revision
        self.reason_code = reason
        return self


class SearchReferenceHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_item_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    score: float = Field(ge=0.0)


class AipMemorySearchIndexError(RuntimeError):
    pass


class AipMemorySearchIndexConflict(AipMemorySearchIndexError):
    pass


class AipMemorySearchIndex:
    """Manages projections only; canonical authorization stays in AIP Memory."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def replace_references(
        self,
        scope: TenantScope,
        drafts: Iterable[SearchReferenceDraft],
        *,
        indexed_at: datetime,
    ) -> int:
        items = list(drafts)
        keys = {(item.memory_item_id, item.revision) for item in items}
        if len(keys) != len(items):
            raise ValueError("search reference revisions must be unique")
        with self._connect_factory(scope) as conn:
            for item in items:
                row = conn.execute(
                    """SELECT i.subject_ref,r.content_hash,r.source_id,r.source_revision,
                              r.markings,r.applicability,s.freshness_expires_at
                       FROM aip_memory_item i
                       JOIN aip_memory_item_revision r
                         ON r.org_id=i.org_id AND r.project_id=i.project_id
                        AND r.memory_item_id=i.memory_item_id
                        AND r.revision=i.current_revision
                       JOIN aip_memory_source_revision s
                         ON s.org_id=r.org_id AND s.project_id=r.project_id
                        AND s.source_id=r.source_id AND s.revision=r.source_revision
                       WHERE i.org_id=%s AND i.project_id=%s
                         AND i.memory_item_id=%s AND r.revision=%s""",
                    (*scope.key, item.memory_item_id, item.revision),
                ).fetchone()
                if row is None or not self._matches_authority(item, row):
                    raise AipMemorySearchIndexConflict(
                        "search reference does not match canonical memory revision"
                    )
            conn.execute(
                "DELETE FROM aip_memory_search_reference WHERE org_id=%s AND project_id=%s",
                scope.key,
            )
            for item in items:
                source_ref = ResourceRef(
                    resource_type="aip.memory_source_revision",
                    resource_id=item.source_id,
                    revision=str(item.source_revision),
                    authority="postgresql",
                )
                conn.execute(
                    """INSERT INTO aip_memory_search_reference (
                       org_id,project_id,memory_item_id,revision,content_hash,
                       subject_ref,source_id,source_revision,source_ref,search_terms,
                       search_text,markings,applicability,freshness_expires_at,indexed_at)
                       VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,
                         %s,%s::jsonb,%s::jsonb,%s,%s)""",
                    (
                        *scope.key,
                        item.memory_item_id,
                        item.revision,
                        item.content_hash,
                        self._json(item.subject.model_dump(mode="json", by_alias=True)),
                        item.source_id,
                        item.source_revision,
                        self._json(source_ref.model_dump(mode="json", by_alias=True)),
                        self._json(item.terms),
                        " ".join(item.terms),
                        self._json(item.markings),
                        self._json(item.applicability),
                        item.freshness_expires_at,
                        indexed_at,
                    ),
                )
            conn.commit()
        return len(items)

    def upsert_reference(
        self,
        scope: TenantScope,
        draft: SearchReferenceDraft,
        *,
        indexed_at: datetime,
    ) -> bool:
        """Insert one exact projection without rebuilding unrelated references.

        Returns ``True`` when a row is created and ``False`` for an exact
        idempotent replay.  A conflicting projection never overwrites the
        existing row.
        """

        with self._connect_factory(scope) as conn:
            authority = conn.execute(
                """SELECT i.subject_ref,r.content_hash,r.source_id,r.source_revision,
                          r.markings,r.applicability,s.freshness_expires_at
                   FROM aip_memory_item i
                   JOIN aip_memory_item_revision r
                     ON r.org_id=i.org_id AND r.project_id=i.project_id
                    AND r.memory_item_id=i.memory_item_id
                    AND r.revision=i.current_revision
                   JOIN aip_memory_source_revision s
                     ON s.org_id=r.org_id AND s.project_id=r.project_id
                    AND s.source_id=r.source_id AND s.revision=r.source_revision
                   WHERE i.org_id=%s AND i.project_id=%s
                     AND i.memory_item_id=%s AND r.revision=%s""",
                (*scope.key, draft.memory_item_id, draft.revision),
            ).fetchone()
            if authority is None or not self._matches_authority(draft, authority):
                raise AipMemorySearchIndexConflict(
                    "search reference does not match canonical memory revision"
                )
            source_ref = ResourceRef(
                resource_type="aip.memory_source_revision",
                resource_id=draft.source_id,
                revision=str(draft.source_revision),
                authority="postgresql",
            )
            row = conn.execute(
                """INSERT INTO aip_memory_search_reference (
                   org_id,project_id,memory_item_id,revision,content_hash,
                   subject_ref,source_id,source_revision,source_ref,search_terms,
                   search_text,markings,applicability,freshness_expires_at,indexed_at)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s::jsonb,
                     %s,%s::jsonb,%s::jsonb,%s,%s)
                   ON CONFLICT (org_id,project_id,memory_item_id,revision)
                   DO NOTHING RETURNING *""",
                (
                    *scope.key,
                    draft.memory_item_id,
                    draft.revision,
                    draft.content_hash,
                    self._json(draft.subject.model_dump(mode="json", by_alias=True)),
                    draft.source_id,
                    draft.source_revision,
                    self._json(source_ref.model_dump(mode="json", by_alias=True)),
                    self._json(draft.terms),
                    " ".join(draft.terms),
                    self._json(draft.markings),
                    self._json(draft.applicability),
                    draft.freshness_expires_at,
                    indexed_at,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    """SELECT * FROM aip_memory_search_reference
                       WHERE org_id=%s AND project_id=%s
                         AND memory_item_id=%s AND revision=%s""",
                    (*scope.key, draft.memory_item_id, draft.revision),
                ).fetchone()
                if row is None or not self._matches_projection(draft, row):
                    raise AipMemorySearchIndexConflict(
                        "search reference idempotency conflict"
                    )
                conn.commit()
                return False
            conn.commit()
            return True

    def clear_references(self, scope: TenantScope) -> int:
        with self._connect_factory(scope) as conn:
            result = conn.execute(
                "DELETE FROM aip_memory_search_reference WHERE org_id=%s AND project_id=%s",
                scope.key,
            )
            conn.commit()
            return int(result.rowcount or 0)

    def set_capability(
        self,
        scope: TenantScope,
        capability: SearchCapability,
        *,
        expected_version: int,
    ) -> SearchCapability:
        if expected_version < 0:
            raise ValueError("expected_version must be non-negative")
        with self._connect_factory(scope) as conn:
            if (
                capability.lane is SearchLane.VECTOR
                and capability.status is SearchCapabilityStatus.READY
            ):
                available = conn.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') AS ready"
                ).fetchone()["ready"]
                if not available:
                    raise AipMemorySearchIndexConflict(
                        "vector capability cannot be ready without pgvector"
                    )
            if expected_version == 0:
                row = conn.execute(
                    """INSERT INTO aip_memory_search_capability (
                       org_id,project_id,lane,status,provider,provider_revision,
                       reason_code,version,observed_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,1,%s)
                       ON CONFLICT (org_id,project_id,lane) DO NOTHING RETURNING *""",
                    (
                        *scope.key,
                        capability.lane.value,
                        capability.status.value,
                        capability.provider,
                        capability.provider_revision,
                        capability.reason_code,
                        capability.observed_at,
                    ),
                ).fetchone()
            else:
                row = conn.execute(
                    """UPDATE aip_memory_search_capability
                       SET status=%s,provider=%s,provider_revision=%s,reason_code=%s,
                           version=version+1,observed_at=%s
                       WHERE org_id=%s AND project_id=%s AND lane=%s AND version=%s
                       RETURNING *""",
                    (
                        capability.status.value,
                        capability.provider,
                        capability.provider_revision,
                        capability.reason_code,
                        capability.observed_at,
                        *scope.key,
                        capability.lane.value,
                        expected_version,
                    ),
                ).fetchone()
            if row is None:
                raise AipMemorySearchIndexConflict("capability CAS conflict")
            conn.commit()
            return self._capability(row)

    def list_capabilities(self, scope: TenantScope) -> list[SearchCapability]:
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT * FROM aip_memory_search_capability
                   WHERE org_id=%s AND project_id=%s ORDER BY lane""",
                scope.key,
            ).fetchall()
        return [self._capability(row) for row in rows]

    def search_references(
        self,
        scope: TenantScope,
        query: str,
        *,
        authorized_markings: list[str],
        required_applicability: list[str],
        time_cutoff: datetime,
        limit: int,
    ) -> list[SearchReferenceHit]:
        cleaned = " ".join(query.split())
        if not cleaned or not authorized_markings or not required_applicability:
            return []
        if limit < 1 or limit > 50:
            raise ValueError("search reference limit must be 1..50")
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """SELECT memory_item_id,revision,content_hash,
                          ts_rank_cd(to_tsvector('simple',search_text),
                                     plainto_tsquery('simple',%s)) AS score
                   FROM aip_memory_search_reference
                   WHERE org_id=%s AND project_id=%s
                     AND to_tsvector('simple',search_text)
                         @@ plainto_tsquery('simple',%s)
                     AND markings <@ %s::jsonb
                     AND applicability @> %s::jsonb
                     AND freshness_expires_at > %s
                   ORDER BY score DESC,memory_item_id,revision
                   LIMIT %s""",
                (
                    cleaned,
                    *scope.key,
                    cleaned,
                    self._json(authorized_markings),
                    self._json(required_applicability),
                    time_cutoff,
                    limit,
                ),
            ).fetchall()
        return [
            SearchReferenceHit(
                memory_item_id=row["memory_item_id"],
                revision=int(row["revision"]),
                content_hash=row["content_hash"],
                score=float(row["score"]),
            )
            for row in rows
        ]

    @staticmethod
    def _matches_authority(item: SearchReferenceDraft, row: Any) -> bool:
        subject = ResourceRef.model_validate(row["subject_ref"])
        return (
            subject == item.subject
            and row["content_hash"] == item.content_hash
            and row["source_id"] == item.source_id
            and int(row["source_revision"]) == item.source_revision
            and list(row["markings"]) == item.markings
            and list(row["applicability"]) == item.applicability
            and row["freshness_expires_at"] == item.freshness_expires_at
        )

    @staticmethod
    def _matches_projection(item: SearchReferenceDraft, row: Any) -> bool:
        return (
            AipMemorySearchIndex._matches_authority(item, row)
            and list(row["search_terms"]) == item.terms
            and row["search_text"] == " ".join(item.terms)
        )

    @staticmethod
    def _capability(row: Any) -> SearchCapability:
        return SearchCapability(
            lane=row["lane"],
            status=row["status"],
            provider=row["provider"],
            provider_revision=row["provider_revision"],
            reason_code=row["reason_code"],
            version=int(row["version"]),
            observed_at=row["observed_at"],
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


__all__ = [
    "AipMemorySearchIndex",
    "AipMemorySearchIndexConflict",
    "AipMemorySearchIndexError",
    "SearchCapability",
    "SearchCapabilityStatus",
    "SearchLane",
    "SearchReferenceDraft",
    "SearchReferenceHit",
]
