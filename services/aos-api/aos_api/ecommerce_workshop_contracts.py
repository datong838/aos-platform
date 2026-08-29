"""Strict public contracts for the ecommerce Workshop catalog and readiness."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    SHA256_PATTERN,
    BundlePermissions,
    StrictContract,
)
from aos_api.asset_registry.semver import SemVerError, parse_version

ECOMMERCE_WORKSHOP_SCHEMA_VERSION = "aos.ecommerce-workshop/v1"
_MODULE_ID_PATTERN = r"^ecommerce[.][a-z0-9]+(?:[.-][a-z0-9]+)*$"
_REASON_CODE_PATTERN = r"^[A-Z][A-Z0-9_]{1,119}$"


class WorkshopReadiness(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class WorkshopDependencyState(StrEnum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class WorkshopDependencyType(StrEnum):
    OBJECT = "object"
    CAPABILITY = "capability"
    AIP_FEATURE = "aip_feature"
    DATA_SCOPE = "data_scope"
    PERMISSION = "permission"
    REGISTRY = "registry"
    INSTALLATION = "installation"


class WorkshopTenant(StrictContract):
    org_id: str = Field(alias="orgId", min_length=1, max_length=160)
    project_id: str = Field(alias="projectId", min_length=1, max_length=160)


class WorkshopInstallationRef(StrictContract):
    installation_id: str = Field(alias="installationId")
    revision: int = Field(ge=1)
    composition_id: str = Field(alias="compositionId")
    lock_revision: int = Field(alias="lockRevision", ge=1)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    overlay_revision: str = Field(alias="overlayRevision", min_length=1, max_length=160)

    @field_validator("installation_id", "composition_id")
    @classmethod
    def _canonical_uuid(cls, value: str) -> str:
        from uuid import UUID

        try:
            parsed = UUID(value)
        except ValueError as exc:
            raise ValueError("Workshop installation reference must use UUIDs") from exc
        if str(parsed) != value:
            raise ValueError("Workshop installation reference must use canonical UUIDs")
        return value


class WorkshopModuleRef(StrictContract):
    publisher: str = Field(pattern=BUNDLE_ID_PATTERN, min_length=1, max_length=120)
    bundle_id: str = Field(alias="bundleId", pattern=BUNDLE_ID_PATTERN)
    version: str = Field(min_length=1, max_length=120)
    bundle_content_hash: str = Field(
        alias="bundleContentHash", pattern=SHA256_PATTERN
    )
    module_artifact_ref: str = Field(
        alias="moduleArtifactRef", min_length=1, max_length=1024
    )
    module_artifact_hash: str = Field(
        alias="moduleArtifactHash", pattern=SHA256_PATTERN
    )

    @field_validator("module_artifact_ref")
    @classmethod
    def _safe_artifact_ref(cls, value: str) -> str:
        if (
            value != value.strip()
            or not value.startswith("bundle://")
            or any(marker in value for marker in ("\\", "..", "?", "#", "\x00"))
        ):
            raise ValueError("moduleArtifactRef is invalid")
        return value

    @field_validator("version")
    @classmethod
    def _strict_semver(cls, value: str) -> str:
        try:
            parsed = parse_version(value)
        except SemVerError as exc:
            raise ValueError("Workshop bundle version must use strict SemVer") from exc
        if str(parsed) != value:
            raise ValueError("Workshop bundle version must be canonical SemVer")
        return value


class WorkshopDependencyRef(StrictContract):
    resource_type: str = Field(alias="resourceType", min_length=1, max_length=120)
    resource_id: str = Field(alias="resourceId", min_length=1, max_length=240)
    revision: str | None = Field(default=None, max_length=240)
    content_hash: str | None = Field(
        default=None, alias="contentHash", pattern=SHA256_PATTERN
    )
    authority: str = Field(min_length=1, max_length=240)


class WorkshopReadinessBlocker(StrictContract):
    dependency_type: WorkshopDependencyType = Field(alias="dependencyType", strict=False)
    dependency_id: str = Field(alias="dependencyId", min_length=1, max_length=240)
    state: WorkshopDependencyState = Field(strict=False)
    reason_code: str = Field(
        alias="reasonCode", pattern=_REASON_CODE_PATTERN, min_length=2, max_length=120
    )
    recoverable: bool
    required_action: str = Field(alias="requiredAction", min_length=1, max_length=500)
    ref: WorkshopDependencyRef | None = None


class EcommerceWorkshopModuleProjection(StrictContract):
    module_id: str = Field(alias="moduleId", pattern=_MODULE_ID_PATTERN)
    display_name: str = Field(alias="displayName", min_length=1, max_length=240)
    menu_label: str = Field(alias="menuLabel", min_length=1, max_length=120)
    route: str = Field(min_length=1, max_length=1024)
    slot: Literal["workshop.primary.ecommerce"]
    order: int = Field(ge=0, le=100_000)
    installation_ref: WorkshopInstallationRef = Field(alias="installationRef")
    module_ref: WorkshopModuleRef = Field(alias="moduleRef")
    readiness: WorkshopReadiness = Field(strict=False)
    blockers: list[WorkshopReadinessBlocker] = Field(max_length=2_000)
    dependency_refs: list[WorkshopDependencyRef] = Field(
        default_factory=list, alias="dependencyRefs", max_length=2_000
    )
    permissions: BundlePermissions
    required_objects: list[str] = Field(alias="requiredObjects", max_length=500)
    required_capabilities: list[str] = Field(
        alias="requiredCapabilities", max_length=500
    )
    required_aip_features: list[str] = Field(
        alias="requiredAipFeatures", max_length=500
    )
    view_refs: list[str] = Field(alias="viewRefs", max_length=500)
    eval_pack_refs: list[str] = Field(alias="evalPackRefs", max_length=500)
    production_contract_refs: list[str] = Field(
        alias="productionContractRefs", max_length=500
    )
    responsibility_template_refs: list[str] = Field(
        alias="responsibilityTemplateRefs", max_length=500
    )
    impact_calculator_refs: list[str] = Field(
        alias="impactCalculatorRefs", max_length=500
    )
    legacy_asset_refs: list[str] = Field(alias="legacyAssetRefs", max_length=500)
    legacy_routes: list[str] = Field(alias="legacyRoutes", max_length=500)
    minimum_runtime_version: str = Field(
        alias="minimumRuntimeVersion", min_length=1, max_length=120
    )
    last_receipt_ref: WorkshopDependencyRef | None = Field(
        default=None, alias="lastReceiptRef"
    )

    @field_validator("route")
    @classmethod
    def _canonical_route(cls, value: str) -> str:
        if not value.startswith("/workshop/") or value.endswith("/"):
            raise ValueError("Workshop route must be canonical")
        return value

    @field_validator("minimum_runtime_version")
    @classmethod
    def _strict_runtime_semver(cls, value: str) -> str:
        try:
            parsed = parse_version(value)
        except SemVerError as exc:
            raise ValueError("minimumRuntimeVersion must use strict SemVer") from exc
        if str(parsed) != value:
            raise ValueError("minimumRuntimeVersion must be canonical SemVer")
        return value

    @field_validator(
        "required_objects",
        "required_capabilities",
        "required_aip_features",
        "view_refs",
        "eval_pack_refs",
        "production_contract_refs",
        "responsibility_template_refs",
        "impact_calculator_refs",
        "legacy_asset_refs",
        "legacy_routes",
    )
    @classmethod
    def _sorted_unique(cls, values: list[str]) -> list[str]:
        if any(not value or value != value.strip() or "\x00" in value for value in values):
            raise ValueError("Workshop projection list values must be normalized")
        if len(values) != len(set(values)):
            raise ValueError("Workshop projection list values must be unique")
        return sorted(values)

    @model_validator(mode="after")
    def _readiness_matches_blockers(self) -> EcommerceWorkshopModuleProjection:
        if self.readiness is WorkshopReadiness.AVAILABLE and self.blockers:
            raise ValueError("available Workshop modules cannot expose blockers")
        if self.readiness is not WorkshopReadiness.AVAILABLE and not self.blockers:
            raise ValueError("non-available Workshop modules require blockers")
        identities = [
            (item.dependency_type.value, item.dependency_id) for item in self.blockers
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Workshop blockers must be unique")
        object.__setattr__(
            self,
            "blockers",
            sorted(
                self.blockers,
                key=lambda item: (item.dependency_type.value, item.dependency_id),
            ),
        )
        ref_identities = [
            (item.resource_type, item.resource_id) for item in self.dependency_refs
        ]
        if len(ref_identities) != len(set(ref_identities)):
            raise ValueError("Workshop dependency refs must be unique")
        object.__setattr__(
            self,
            "dependency_refs",
            sorted(
                self.dependency_refs,
                key=lambda item: (item.resource_type, item.resource_id),
            ),
        )
        return self


class EcommerceWorkshopModuleListResponse(StrictContract):
    schema_version: Literal[ECOMMERCE_WORKSHOP_SCHEMA_VERSION] = Field(
        default=ECOMMERCE_WORKSHOP_SCHEMA_VERSION, alias="schemaVersion"
    )
    tenant: WorkshopTenant
    evaluated_at: datetime = Field(alias="evaluatedAt")
    data_cutoff: datetime | None = Field(default=None, alias="dataCutoff")
    items: list[EcommerceWorkshopModuleProjection] = Field(max_length=500)
    count: int = Field(ge=0, le=500)

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Workshop timestamps require a timezone")
        return value

    @model_validator(mode="after")
    def _items_are_canonical(self) -> EcommerceWorkshopModuleListResponse:
        if self.count != len(self.items):
            raise ValueError("Workshop count must equal item count")
        identities = [(item.module_id, item.route, item.order) for item in self.items]
        if len(identities) != len({item[0] for item in identities}):
            raise ValueError("Workshop module ids must be unique")
        if len(identities) != len({item[1] for item in identities}):
            raise ValueError("Workshop routes must be unique")
        if len(identities) != len({item[2] for item in identities}):
            raise ValueError("Workshop order values must be unique")
        object.__setattr__(self, "items", sorted(self.items, key=lambda item: item.order))
        return self


class WorkshopFeatureActivationCommandRequest(StrictContract):
    expected_revision: int = Field(alias="expectedRevision", ge=0)
    content_hash: str | None = Field(default=None, alias="contentHash", pattern=SHA256_PATTERN)
    expires_at: datetime | None = Field(default=None, alias="expiresAt")

    @field_validator("expires_at")
    @classmethod
    def _aware_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("FeatureActivation expiry requires a timezone")
        return value


class WorkshopFeatureActivationCommandReceipt(StrictContract):
    schema_version: Literal[
        "aos.ecommerce-workshop.feature-activation-command-receipt/v1"
    ] = Field(alias="schemaVersion")
    receipt_id: str = Field(alias="receiptId", min_length=1, max_length=120)
    feature_id: str = Field(alias="featureId", pattern=r"^aip[.][a-z0-9]+(?:[.-][a-z0-9]+)*$")
    operation: Literal["activate", "revoke"]
    revision: int = Field(ge=1)
    status: Literal["active", "revoked"]
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    created_at: datetime = Field(alias="createdAt")

    @field_validator("created_at")
    @classmethod
    def _aware_created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("FeatureActivation receipt time requires a timezone")
        return value


class WorkshopFeatureActivationCommandResponse(StrictContract):
    tenant: WorkshopTenant
    receipt: WorkshopFeatureActivationCommandReceipt
    replayed: bool


class WorkshopFeatureActivationProjection(StrictContract):
    feature_id: str = Field(alias="featureId", pattern=r"^aip[.][a-z0-9]+(?:[.-][a-z0-9]+)*$")
    revision: int = Field(ge=1)
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    status: Literal["active", "superseded", "revoked"]
    activated_at: datetime = Field(alias="activatedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")

    @field_validator("activated_at", "expires_at")
    @classmethod
    def _aware_activation_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("FeatureActivation projection time requires a timezone")
        return value


class WorkshopFeatureActivationListResponse(StrictContract):
    schema_version: Literal["aos.ecommerce-workshop.feature-activation-list/v1"] = Field(
        default="aos.ecommerce-workshop.feature-activation-list/v1", alias="schemaVersion"
    )
    tenant: WorkshopTenant
    evaluated_at: datetime = Field(alias="evaluatedAt")
    items: list[WorkshopFeatureActivationProjection]

    @field_validator("evaluated_at")
    @classmethod
    def _aware_evaluated_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("FeatureActivation evaluatedAt requires a timezone")
        return value


class EcommerceWorkshopModuleReadinessResponse(StrictContract):
    schema_version: Literal[ECOMMERCE_WORKSHOP_SCHEMA_VERSION] = Field(
        default=ECOMMERCE_WORKSHOP_SCHEMA_VERSION, alias="schemaVersion"
    )
    tenant: WorkshopTenant
    evaluated_at: datetime = Field(alias="evaluatedAt")
    data_cutoff: datetime | None = Field(default=None, alias="dataCutoff")
    item: EcommerceWorkshopModuleProjection

    @field_validator("evaluated_at", "data_cutoff")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("Workshop timestamps require a timezone")
        return value
