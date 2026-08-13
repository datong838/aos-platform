"""Tenant-scoped, read-only readiness view for governed knowledge retrieval."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_memory_search_index import (
    AipMemorySearchIndex,
    SearchCapability,
    SearchCapabilityStatus,
    SearchLane,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class KnowledgeAuthorityAvailability(AipContractModel):
    status: str = Field(pattern=r"^(available|authority_unavailable)$")
    count: int | None = Field(default=None, ge=0)
    blocker: str | None = None

    @model_validator(mode="after")
    def _consistent_authority_state(self) -> KnowledgeAuthorityAvailability:
        blocker = self.blocker.strip() if self.blocker else None
        if self.status == "available":
            if self.count is None or blocker is not None:
                raise ValueError("available authority requires count and no blocker")
        elif self.count is not None or blocker is None:
            raise ValueError("unavailable authority requires blocker and no count")
        self.blocker = blocker
        return self


class KnowledgeSourceSummary(AipContractModel):
    provider: str
    provider_version: str
    license_id: str
    usage_policy: str
    revision_count: int = Field(ge=1)
    stale_count: int = Field(ge=0)


class KnowledgeSearchCapability(AipContractModel):
    lane: SearchLane
    status: SearchCapabilityStatus
    provider: str | None = None
    provider_revision: str | None = None
    reason_code: str | None = None
    version: int = Field(ge=1)
    observed_at: datetime

    @classmethod
    def from_projection(cls, item: SearchCapability) -> KnowledgeSearchCapability:
        return cls.model_validate(item.model_dump())


class KnowledgeSearchReadiness(AipContractModel):
    reference_count: int = Field(ge=0)
    provider_configured: bool
    capabilities: list[KnowledgeSearchCapability] = Field(min_length=3, max_length=3)
    blockers: list[str]

    @model_validator(mode="after")
    def _complete_search_lanes(self) -> KnowledgeSearchReadiness:
        lanes = [item.lane for item in self.capabilities]
        if len(set(lanes)) != len(lanes) or set(lanes) != set(SearchLane):
            raise ValueError("search readiness requires each search lane exactly once")
        if len(self.blockers) != len(set(self.blockers)):
            raise ValueError("search readiness blockers must be unique")
        return self


class KnowledgeReadiness(AipContractModel):
    tenant: TenantContext
    package: KnowledgeAuthorityAvailability
    sources: list[KnowledgeSourceSummary]
    source_blockers: list[str]
    search: KnowledgeSearchReadiness
    eval: KnowledgeAuthorityAvailability
    observed_at: datetime


class AipMemoryReadinessError(RuntimeError):
    code = "AIP_MEMORY_READINESS_UNAVAILABLE"


class AipMemoryReadinessService:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        search_index: AipMemorySearchIndex | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._search_index = search_index or AipMemorySearchIndex(connect_factory)

    def read(
        self,
        scope: TenantScope,
        *,
        search_provider_configured: bool,
        observed_at: datetime | None = None,
    ) -> KnowledgeReadiness:
        now = observed_at or datetime.now(UTC)
        try:
            with self._connect_factory(scope) as conn:
                reference_count = int(
                    conn.execute(
                        """SELECT COUNT(*) AS count FROM aip_memory_search_reference
                           WHERE org_id=%s AND project_id=%s""",
                        scope.key,
                    ).fetchone()["count"]
                )
                source_rows = conn.execute(
                    """SELECT provider,provider_version,license_id,usage_policy,
                              COUNT(*) AS revision_count,
                              COUNT(*) FILTER (WHERE freshness_expires_at <= %s) AS stale_count
                       FROM aip_memory_source_revision
                       WHERE org_id=%s AND project_id=%s
                       GROUP BY provider,provider_version,license_id,usage_policy
                       ORDER BY provider,provider_version,license_id,usage_policy""",
                    (now, *scope.key),
                ).fetchall()
            capabilities = {
                item.lane: item for item in self._search_index.list_capabilities(scope)
            }
        except Exception as exc:
            raise AipMemoryReadinessError(
                "knowledge readiness storage is unavailable"
            ) from exc
        lane_items = [
            capabilities.get(lane)
            or SearchCapability(
                lane=lane,
                status=SearchCapabilityStatus.UNBUILT,
                reason_code="capability_not_registered",
                version=1,
                observed_at=now,
            )
            for lane in SearchLane
        ]
        search_blockers: list[str] = []
        if not search_provider_configured:
            search_blockers.append("trusted_search_provider_unavailable")
        if reference_count == 0:
            search_blockers.append("search_reference_missing")
        search_blockers.extend(
            item.reason_code
            for item in lane_items
            if item.status is not SearchCapabilityStatus.READY and item.reason_code
        )
        sources = [
            KnowledgeSourceSummary(
                provider=row["provider"],
                provider_version=row["provider_version"],
                license_id=row["license_id"],
                usage_policy=row["usage_policy"],
                revision_count=int(row["revision_count"]),
                stale_count=int(row["stale_count"]),
            )
            for row in source_rows
        ]
        return KnowledgeReadiness(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            package=KnowledgeAuthorityAvailability(
                status="authority_unavailable",
                blocker="knowledge_package_installation_authority_unavailable",
            ),
            sources=sources,
            source_blockers=[] if sources else ["knowledge_source_missing"],
            search=KnowledgeSearchReadiness(
                reference_count=reference_count,
                provider_configured=search_provider_configured,
                capabilities=[
                    KnowledgeSearchCapability.from_projection(item) for item in lane_items
                ],
                blockers=list(dict.fromkeys(search_blockers)),
            ),
            eval=KnowledgeAuthorityAvailability(
                status="authority_unavailable",
                blocker="gold_set_registry_authority_unavailable",
            ),
            observed_at=now,
        )


__all__ = [
    "AipMemoryReadinessError",
    "AipMemoryReadinessService",
    "KnowledgeAuthorityAvailability",
    "KnowledgeReadiness",
    "KnowledgeSearchCapability",
    "KnowledgeSearchReadiness",
    "KnowledgeSourceSummary",
]
