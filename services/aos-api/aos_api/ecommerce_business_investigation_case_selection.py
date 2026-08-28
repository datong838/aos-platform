"""BI-W10 fail-closed exact selection for Business Investigation Case creation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_profile_catalog import (
    EcommerceInvestigationProfileCatalog,
)
from aos_api.source_readiness import SourceReadinessService, build_source_readiness_service
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_PIPELINE_IDS,
    SourceReadinessStatus,
)
from aos_api.tenant_scope import TenantScope


class BusinessInvestigationCaseSelectionBlocked(RuntimeError):
    def __init__(self, blockers: list[str]) -> None:
        self.blockers = sorted(set(blockers))
        super().__init__(",".join(self.blockers))


class BusinessInvestigationCaseSelectionConflict(RuntimeError):
    pass


class BusinessInvestigationCaseSelection(AipContractModel):
    schema_version: str = "aos.ecommerce.business-investigation-case-selection/v1"
    tenant: TenantContext
    analysis_type: str
    source_readiness_status: SourceReadinessStatus
    source_readiness_checked_at: str | None = None
    source_readiness_cutoff_at: str | None = None
    channel_ref: InvestigationExactRef | None = None
    business_entity_ref: InvestigationExactRef | None = None
    entity_channel_binding_ref: InvestigationExactRef | None = None
    investigation_profile_ref: InvestigationExactRef | None = None
    scope_ref: InvestigationExactRef | None = None
    case_creatable: bool = False
    run_creatable: bool = False
    blockers: list[str] = Field(default_factory=list)
    run_blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _creatable_requires_complete_exact_selection(self) -> "BusinessInvestigationCaseSelection":
        refs = (
            self.channel_ref,
            self.business_entity_ref,
            self.entity_channel_binding_ref,
            self.investigation_profile_ref,
            self.scope_ref,
        )
        if self.case_creatable and (self.blockers or any(item is None for item in refs)):
            raise ValueError("caseCreatable requires five exact refs and no blockers")
        if self.run_creatable and not self.case_creatable:
            raise ValueError("runCreatable requires caseCreatable")
        if self.run_creatable and self.run_blockers:
            raise ValueError("runCreatable requires no runBlockers")
        return self


@dataclass(frozen=True, slots=True)
class CanonicalShopSelection:
    channel_ref: InvestigationExactRef
    business_entity_ref: InvestigationExactRef
    entity_channel_binding_ref: InvestigationExactRef


@dataclass(frozen=True, slots=True)
class CanonicalProfileSelection:
    investigation_profile_ref: InvestigationExactRef
    scope_ref: InvestigationExactRef
    run_creatable: bool
    case_blockers: tuple[str, ...] = ()
    run_blockers: tuple[str, ...] = ()


class ShopSelectionSource(Protocol):
    def read(self, scope: TenantScope) -> CanonicalShopSelection | None: ...


class ProfileSelectionSource(Protocol):
    def read(
        self, scope: TenantScope, analysis_type: str
    ) -> CanonicalProfileSelection | None: ...


def _hash(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class PostgresCanonicalShopSelectionSource:
    """Derive an exact tenant-bound selection from the single active Shop head."""

    def __init__(self, connect_factory: Callable[[TenantScope], Any] = db_connect) -> None:
        self._connect = connect_factory

    def read(self, scope: TenantScope) -> CanonicalShopSelection | None:
        with self._connect(scope) as conn:
            rows = conn.execute(
                """SELECT platform,shop_or_marketplace_id,external_id,schema_version,
                          payload_hash,source_updated_at
                   FROM ecom_object
                   WHERE org_id=%s AND workspace_id=%s AND object_type='Shop'
                     AND deleted_at IS NULL AND canonical_status='active'
                   ORDER BY platform,shop_or_marketplace_id,external_id LIMIT 2""",
                scope.key,
            ).fetchall()
        if len(rows) != 1:
            return None
        row = rows[0]
        revision = int(row["schema_version"])
        platform = str(row["platform"])
        marketplace = str(row["shop_or_marketplace_id"])
        external_id = str(row["external_id"])
        payload_hash = str(row["payload_hash"])
        source_updated_at = row["source_updated_at"].isoformat()
        channel_id = f"{platform}:{marketplace}"
        entity_id = external_id
        base = {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "platform": platform,
            "shopOrMarketplaceId": marketplace,
            "schemaVersion": revision,
            "payloadHash": payload_hash,
            "sourceUpdatedAt": source_updated_at,
        }
        channel_ref = InvestigationExactRef(
            resourceType="ChannelRevision",
            resourceId=channel_id,
            revision=revision,
            contentHash=_hash({**base, "resourceType": "ChannelRevision"}),
        )
        business_entity_ref = InvestigationExactRef(
            resourceType="BusinessEntityRevision",
            resourceId=entity_id,
            revision=revision,
            contentHash=_hash(
                {**base, "resourceType": "BusinessEntityRevision", "externalId": external_id}
            ),
        )
        binding_ref = InvestigationExactRef(
            resourceType="BusinessEntityChannelBindingRevision",
            resourceId=f"{channel_id}:{external_id}",
            revision=revision,
            contentHash=_hash(
                {
                    **base,
                    "resourceType": "BusinessEntityChannelBindingRevision",
                    "channelRef": channel_ref.model_dump(by_alias=True, mode="json"),
                    "businessEntityRef": business_entity_ref.model_dump(
                        by_alias=True, mode="json"
                    ),
                }
            ),
        )
        return CanonicalShopSelection(channel_ref, business_entity_ref, binding_ref)


class CatalogCanonicalProfileSelectionSource:
    """Resolve stable L1 refs while keeping AIP runtime composition separate."""

    def __init__(self, catalog: EcommerceInvestigationProfileCatalog | None = None) -> None:
        self._catalog = catalog or EcommerceInvestigationProfileCatalog()

    def read(
        self, scope: TenantScope, analysis_type: str
    ) -> CanonicalProfileSelection | None:
        del scope
        resolved = self._catalog.read(analysis_type)
        if resolved is None:
            return None
        profile, investigation_scope = resolved
        return CanonicalProfileSelection(
            profile.exact_ref,
            investigation_scope.exact_ref,
            run_creatable=False,
            run_blockers=("AIP_PRODUCTION_COMPOSITION_NOT_RESOLVED",),
        )


class BusinessInvestigationCaseSelectionResolver:
    def __init__(
        self,
        readiness_service: SourceReadinessService | None = None,
        shop_source: ShopSelectionSource | None = None,
        profile_source: ProfileSelectionSource | None = None,
    ) -> None:
        self._readiness = readiness_service or build_source_readiness_service()
        self._shops = shop_source or PostgresCanonicalShopSelectionSource()
        self._profiles = profile_source or CatalogCanonicalProfileSelectionSource()

    def read(self, scope: TenantScope, analysis_type: str) -> BusinessInvestigationCaseSelection:
        readiness = self._readiness.read(org_id=scope.org_id, project_id=scope.project_id)
        blockers: list[str] = []
        run_blockers: list[str] = []
        if readiness.status is not SourceReadinessStatus.READY or tuple(
            item.pipeline_id for item in readiness.sources
        ) != CANONICAL_QYH_PIPELINE_IDS:
            blockers.append("SOURCE_READINESS_NOT_READY")
        shop = self._shops.read(scope)
        if shop is None:
            blockers.append("CANONICAL_SHOP_SELECTION_UNAVAILABLE")
        profile = self._profiles.read(scope, analysis_type)
        if profile is None:
            blockers.extend(
                ["INVESTIGATION_PROFILE_AUTHORITY_MISSING", "INVESTIGATION_SCOPE_AUTHORITY_MISSING"]
            )
        else:
            blockers.extend(profile.case_blockers)
            run_blockers.extend(profile.run_blockers)
        case_creatable = not blockers and shop is not None and profile is not None
        if not case_creatable:
            run_blockers.append("CASE_SELECTION_NOT_CREATABLE")
        return BusinessInvestigationCaseSelection(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            analysisType=analysis_type,
            sourceReadinessStatus=readiness.status,
            sourceReadinessCheckedAt=readiness.checked_at.isoformat(),
            sourceReadinessCutoffAt=readiness.cutoff_at.isoformat(),
            channelRef=shop.channel_ref if shop else None,
            businessEntityRef=shop.business_entity_ref if shop else None,
            entityChannelBindingRef=shop.entity_channel_binding_ref if shop else None,
            investigationProfileRef=profile.investigation_profile_ref if profile else None,
            scopeRef=profile.scope_ref if profile else None,
            caseCreatable=case_creatable,
            runCreatable=bool(case_creatable and profile and profile.run_creatable),
            blockers=sorted(set(blockers)),
            runBlockers=sorted(set(run_blockers)),
        )

    def verify_case_refs(
        self,
        scope: TenantScope,
        analysis_type: str,
        refs: tuple[InvestigationExactRef, ...],
    ) -> BusinessInvestigationCaseSelection:
        selection = self.read(scope, analysis_type)
        if not selection.case_creatable:
            raise BusinessInvestigationCaseSelectionBlocked(selection.blockers)
        expected = (
            selection.channel_ref,
            selection.business_entity_ref,
            selection.entity_channel_binding_ref,
            selection.investigation_profile_ref,
            selection.scope_ref,
        )
        if refs != expected:
            raise BusinessInvestigationCaseSelectionConflict(
                "submitted refs do not match the current canonical Case selection"
            )
        return selection
