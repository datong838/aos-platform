"""Domain-neutral contracts for versioned AOS asset bundles."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

BUNDLE_API_VERSION = "aos.dev/v1alpha1"
BUNDLE_ID_PATTERN = r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$"
CAPABILITY_PATTERN = r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$"
SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
MAX_BUNDLE_ID_LENGTH = 160
MAX_PUBLISHER_ID_LENGTH = 120
MAX_REFERENCE_LENGTH = 1024
MAX_ARTIFACT_SIZE = 8 * 1024 * 1024 * 1024
MAX_CONTRIBUTIONS_PER_MANIFEST = 10_000

_API_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"})
_API_PARAMETER = re.compile(r"^\{[A-Za-z][A-Za-z0-9_]*\}$")
_NAVIGATION_PARAMETER = re.compile(r"^:[A-Za-z][A-Za-z0-9_]*$")
_OPERATION_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


class StrictContract(BaseModel):
    """Base contract that rejects coercion and unknown manifest fields."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        populate_by_name=False,
        validate_assignment=True,
    )


class BundleKind(StrEnum):
    DOMAIN_PACK = "DomainPack"
    SOLUTION_PACK = "SolutionPack"
    VERTICAL_PACK = "VerticalPack"
    PLATFORM_ADAPTER_PACK = "PlatformAdapterPack"
    PLUGIN_PACK = "PluginPack"


class BundleVersionStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"
    REJECTED = "rejected"


class BundleEvidenceStatus(StrEnum):
    PENDING = "pending"
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"


class BundleEvidenceType(StrEnum):
    MANIFEST_VALIDATION = "manifest_validation"
    CONTENT_HASH = "content_hash"
    SIGNATURE_VERIFICATION = "signature_verification"
    SBOM = "sbom"
    DEPENDENCY_RESOLUTION = "dependency_resolution"
    PERMISSION_DIFF = "permission_diff"
    MIGRATION_PLAN = "migration_plan"
    PREFLIGHT = "preflight"
    BUNDLE_EVALS = "bundle_evals"
    INSTALLATION_APPLY = "installation_apply"
    INSTALLATION_VERIFY = "installation_verify"
    ROLLBACK = "rollback"
    SOURCE_CONNECTION = "source_connection"
    PIPELINE_RUN = "pipeline_run"
    DATASET_REVISION = "dataset_revision"
    DATA_QUALITY = "data_quality"
    ONTOLOGY_REVISION = "ontology_revision"
    LOGIC_PUBLICATION = "logic_publication"
    LOGIC_EVAL = "logic_eval"
    WORKSHOP_VALIDATION = "workshop_validation"
    ACTION_SAFETY = "action_safety"


class DowngradePolicy(StrEnum):
    RETAIN_CANONICAL = "retain-canonical"


def _require_exact_text(value: str, *, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-blank and already normalized")
    if "\x00" in value:
        raise ValueError(f"{label} must not contain NUL")
    return value


def _require_relative_bundle_path(value: str, *, label: str) -> str:
    value = _require_exact_text(value, label=label)
    if (
        "\\" in value
        or "://" in value
        or _WINDOWS_DRIVE.match(value)
        or value.startswith(("/", "~"))
    ):
        raise ValueError(f"{label} must be a relative path inside the bundle")
    raw_path = value.removesuffix("/")
    raw_parts = raw_path.split("/")
    path = PurePosixPath(raw_path)
    if (
        not raw_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise ValueError(f"{label} must not traverse outside the bundle")
    return value


def _require_bundle_source_ref(value: str) -> str:
    value = _require_exact_text(value, label="bundle source reference")
    if not value.startswith("bundle://"):
        raise ValueError("bundle source reference must use bundle://")
    relative = value.removeprefix("bundle://")
    if not relative or "?" in relative or "#" in relative:
        raise ValueError("bundle source reference must identify an allowlisted path")
    _require_relative_bundle_path(relative, label="bundle source reference")
    return value


class BundleMetadata(StrictContract):
    id: str = Field(
        min_length=1, max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    version: str = Field(min_length=1, max_length=120)
    display_name: str = Field(alias="displayName", min_length=1, max_length=240)
    publisher: str = Field(min_length=1, max_length=120, pattern=BUNDLE_ID_PATTERN)
    license: str = Field(min_length=1, max_length=120)

    @field_validator("version", "display_name", "license")
    @classmethod
    def _normalized_text(cls, value: str) -> str:
        return _require_exact_text(value, label="metadata value")


class BundleDependency(StrictContract):
    id: str = Field(
        min_length=1, max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    version: str = Field(min_length=1, max_length=240)
    publisher: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=BUNDLE_ID_PATTERN
    )

    @field_validator("version")
    @classmethod
    def _normalized_range(cls, value: str) -> str:
        return _require_exact_text(value, label="dependency version range")


class BundleConflict(StrictContract):
    id: str = Field(
        min_length=1, max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    version: str | None = Field(default=None, min_length=1, max_length=240)
    publisher: str | None = Field(
        default=None, min_length=1, max_length=120, pattern=BUNDLE_ID_PATTERN
    )

    @field_validator("version")
    @classmethod
    def _normalized_optional_range(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_exact_text(value, label="conflict version range")


class BundleExports(StrictContract):
    """Known, versioned contribution groups; each value is a bundle-local path."""

    ontology: list[str] = Field(default_factory=list, max_length=500)
    links: list[str] = Field(default_factory=list, max_length=500)
    metrics: list[str] = Field(default_factory=list, max_length=500)
    agents: list[str] = Field(default_factory=list, max_length=500)
    logic: list[str] = Field(default_factory=list, max_length=500)
    workshops: list[str] = Field(default_factory=list, max_length=500)
    evals: list[str] = Field(default_factory=list, max_length=500)
    knowledge: list[str] = Field(default_factory=list, max_length=500)
    policies: list[str] = Field(default_factory=list, max_length=500)
    connectors: list[str] = Field(default_factory=list, max_length=500)
    schemas: list[str] = Field(default_factory=list, max_length=500)
    mappings: list[str] = Field(default_factory=list, max_length=500)
    backend: list[str] = Field(default_factory=list, max_length=500)
    ui: list[str] = Field(default_factory=list, max_length=500)

    @field_validator("*")
    @classmethod
    def _safe_unique_paths(cls, values: list[str]) -> list[str]:
        checked = [
            _require_relative_bundle_path(value, label="export path")
            for value in values
        ]
        if len(checked) != len(set(checked)):
            raise ValueError("export paths must be unique")
        return checked


def _normalized_route_segments(value: str, *, label: str) -> list[str]:
    value = _require_exact_text(value, label=label)
    if not value.startswith("/"):
        raise ValueError(f"{label} must start with /")
    if "\\" in value or "%" in value or "?" in value or "#" in value or "//" in value:
        raise ValueError(f"{label} contains a forbidden route form")
    if value == "/":
        return []
    segments = value.removesuffix("/").removeprefix("/").split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise ValueError(f"{label} contains an invalid path segment")
    return segments


def normalize_api_path(value: str) -> str:
    """Return the frozen API contribution collision path."""

    segments = _normalized_route_segments(value, label="API contribution path")
    normalized: list[str] = []
    for segment in segments:
        if "{" in segment or "}" in segment:
            if not _API_PARAMETER.fullmatch(segment):
                raise ValueError("API path contains an invalid template parameter")
            normalized.append("{}")
        else:
            normalized.append(segment)
    return "/" + "/".join(normalized) if normalized else "/"


def normalize_navigation_route(value: str) -> str:
    """Return the frozen navigation contribution collision route."""

    segments = _normalized_route_segments(value, label="navigation route")
    normalized: list[str] = []
    for segment in segments:
        if segment.startswith(":"):
            if not _NAVIGATION_PARAMETER.fullmatch(segment):
                raise ValueError(
                    "navigation route contains an invalid parameter segment"
                )
            normalized.append(":")
        else:
            normalized.append(segment.lower())
    return "/" + "/".join(normalized) if normalized else "/"


class ApiContributionClaim(StrictContract):
    kind: Literal["api"]
    method: str = Field(min_length=1, max_length=16)
    path: str = Field(min_length=1, max_length=1024)
    operation_id: str = Field(alias="operationId", min_length=1, max_length=160)
    mode: Literal["exclusive"]

    @field_validator("method")
    @classmethod
    def _supported_method(cls, value: str) -> str:
        value = _require_exact_text(value, label="API method").upper()
        if value not in _API_METHODS:
            raise ValueError("API method is not supported")
        return value

    @field_validator("path")
    @classmethod
    def _valid_path(cls, value: str) -> str:
        normalize_api_path(value)
        return value.removesuffix("/") or "/"

    @field_validator("operation_id")
    @classmethod
    def _valid_operation_id(cls, value: str) -> str:
        value = _require_exact_text(value, label="operationId")
        if not _OPERATION_ID.fullmatch(value):
            raise ValueError("operationId is invalid")
        return value


class NavigationContributionClaim(StrictContract):
    kind: Literal["navigation"]
    route: str = Field(min_length=1, max_length=1024)
    mode: Literal["exclusive", "shared"]

    @field_validator("route")
    @classmethod
    def _valid_route(cls, value: str) -> str:
        normalize_navigation_route(value)
        return value.removesuffix("/") or "/"


class UiContributionClaim(StrictContract):
    kind: Literal["ui"]
    slot: str = Field(
        min_length=1,
        max_length=160,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=160,
        pattern=BUNDLE_ID_PATTERN,
    )
    mode: Literal["exclusive", "shared"]


ContributionClaim: TypeAlias = Annotated[
    ApiContributionClaim | NavigationContributionClaim | UiContributionClaim,
    Field(discriminator="kind"),
]
ContributionConflictKey: TypeAlias = tuple[str, ...]


def contribution_conflict_keys(
    claim: ApiContributionClaim | NavigationContributionClaim | UiContributionClaim,
) -> tuple[ContributionConflictKey, ...]:
    """Return every collision key claimed by one signed contribution."""

    if isinstance(claim, ApiContributionClaim):
        return (
            ("api", claim.method, normalize_api_path(claim.path)),
            ("api-operation", claim.operation_id),
        )
    if isinstance(claim, NavigationContributionClaim):
        return (("navigation", normalize_navigation_route(claim.route)),)
    return (("ui", claim.slot, claim.id),)


def contribution_conflict_key(
    claim: ApiContributionClaim | NavigationContributionClaim | UiContributionClaim,
) -> ContributionConflictKey:
    """Return the primary path/route/slot collision key for one claim."""

    return contribution_conflict_keys(claim)[0]


def contribution_sort_key(
    claim: ApiContributionClaim | NavigationContributionClaim | UiContributionClaim,
) -> tuple[str, ...]:
    """Return the deterministic ordering key for normalized contributions."""

    keys = contribution_conflict_keys(claim)
    return (claim.kind, *keys[0], *(keys[1] if len(keys) > 1 else ()))


class BundleCapabilities(StrictContract):
    provides: list[str] = Field(max_length=500)
    requires: list[str] = Field(max_length=500)

    @field_validator("provides", "requires")
    @classmethod
    def _unique_capabilities(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(CAPABILITY_PATTERN, value):
                raise ValueError("capability id is invalid")
        if len(values) != len(set(values)):
            raise ValueError("capability ids must be unique")
        return values

    @model_validator(mode="after")
    def _not_both_provided_and_required(self) -> BundleCapabilities:
        overlap = set(self.provides).intersection(self.requires)
        if overlap:
            raise ValueError("a capability cannot be both provided and required")
        return self


class BundlePermissions(StrictContract):
    roles: list[str] = Field(max_length=500)
    markings: list[str] = Field(max_length=500)
    data_scopes: list[str] = Field(alias="dataScopes", max_length=500)
    action_types: list[str] = Field(alias="actionTypes", max_length=500)

    @field_validator("roles", "markings", "data_scopes", "action_types")
    @classmethod
    def _unique_permission_values(cls, values: list[str]) -> list[str]:
        for value in values:
            _require_exact_text(value, label="permission value")
        if len(values) != len(set(values)):
            raise ValueError("permission values must be unique")
        return values


class BundleMigrations(StrictContract):
    plan: str | None = Field(max_length=MAX_REFERENCE_LENGTH)
    downgrade_policy: DowngradePolicy = Field(alias="downgradePolicy", strict=False)

    @field_validator("plan")
    @classmethod
    def _safe_plan_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_relative_bundle_path(value, label="migration plan path")


class BundleSpec(StrictContract):
    platform_api: str = Field(alias="platformApi", min_length=1, max_length=240)
    dependencies: list[BundleDependency] = Field(max_length=500)
    optional_dependencies: list[BundleDependency] = Field(
        alias="optionalDependencies", max_length=500
    )
    conflicts: list[BundleConflict] = Field(max_length=500)
    exports: BundleExports
    capabilities: BundleCapabilities
    permissions: BundlePermissions
    migrations: BundleMigrations
    preflight: str | None = Field(max_length=MAX_REFERENCE_LENGTH)
    regression: str | None = Field(max_length=MAX_REFERENCE_LENGTH)
    rollback: str | None = Field(max_length=MAX_REFERENCE_LENGTH)
    contributions: list[ContributionClaim] = Field(
        default_factory=list,
        max_length=MAX_CONTRIBUTIONS_PER_MANIFEST,
        exclude_if=lambda value: not value,
    )

    @field_validator("platform_api")
    @classmethod
    def _normalized_platform_range(cls, value: str) -> str:
        return _require_exact_text(value, label="platform API version range")

    @field_validator("preflight", "regression", "rollback")
    @classmethod
    def _safe_optional_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_relative_bundle_path(value, label="manifest reference")

    @model_validator(mode="after")
    def _dependencies_are_unambiguous(self) -> BundleSpec:
        required = [(item.publisher, item.id) for item in self.dependencies]
        optional = [(item.publisher, item.id) for item in self.optional_dependencies]
        if len(required) != len(set(required)):
            raise ValueError("required dependencies must be unique")
        if len(optional) != len(set(optional)):
            raise ValueError("optional dependencies must be unique")
        if set(required).intersection(optional):
            raise ValueError("a dependency cannot be both required and optional")
        conflicts = [(item.publisher, item.id) for item in self.conflicts]
        if len(conflicts) != len(set(conflicts)):
            raise ValueError("conflicts must be unique")

        contribution_keys = [
            key
            for claim in self.contributions
            for key in contribution_conflict_keys(claim)
        ]
        if len(contribution_keys) != len(set(contribution_keys)):
            raise ValueError("contribution conflict keys must be unique")

        if self.exports.backend and not any(
            claim.kind == "api" for claim in self.contributions
        ):
            raise ValueError("backend exports require an API contribution claim")
        if self.exports.ui and not any(
            claim.kind in {"navigation", "ui"} for claim in self.contributions
        ):
            raise ValueError("UI exports require a navigation or UI contribution claim")
        return self


class BundleManifest(StrictContract):
    api_version: Literal["aos.dev/v1alpha1"] = Field(alias="apiVersion")
    kind: BundleKind = Field(strict=False)
    metadata: BundleMetadata
    spec: BundleSpec

    @model_validator(mode="after")
    def _cannot_depend_on_or_conflict_with_itself(self) -> BundleManifest:
        if self.spec.exports.knowledge and self.kind is not BundleKind.VERTICAL_PACK:
            raise ValueError("knowledge exports are restricted to VerticalPack bundles")
        own_key = (self.metadata.publisher, self.metadata.id)

        def dependency_key(item: BundleDependency | BundleConflict) -> tuple[str, str]:
            return (item.publisher or self.metadata.publisher, item.id)

        if any(
            dependency_key(item) == own_key
            for item in [
                *self.spec.dependencies,
                *self.spec.optional_dependencies,
                *self.spec.conflicts,
            ]
        ):
            raise ValueError("bundle cannot depend on or conflict with itself")

        required = [dependency_key(item) for item in self.spec.dependencies]
        optional = [dependency_key(item) for item in self.spec.optional_dependencies]
        conflicts = [dependency_key(item) for item in self.spec.conflicts]
        if len(required) != len(set(required)):
            raise ValueError(
                "required dependencies must be unique after publisher inheritance"
            )
        if len(optional) != len(set(optional)):
            raise ValueError(
                "optional dependencies must be unique after publisher inheritance"
            )
        if set(required).intersection(optional):
            raise ValueError(
                "a dependency cannot be both required and optional after publisher inheritance"
            )
        if len(conflicts) != len(set(conflicts)):
            raise ValueError("conflicts must be unique after publisher inheritance")
        return self


class BundleArtifact(StrictContract):
    relative_path: str = Field(alias="relativePath", min_length=1, max_length=1024)
    artifact_ref: str = Field(alias="artifactRef", min_length=1, max_length=1024)
    digest: str = Field(pattern=SHA256_PATTERN)
    size: int = Field(ge=0, le=MAX_ARTIFACT_SIZE)
    media_type: str = Field(alias="mediaType", min_length=1, max_length=255)

    @field_validator("relative_path")
    @classmethod
    def _safe_relative_path(cls, value: str) -> str:
        return _require_relative_bundle_path(value, label="artifact path")

    @field_validator("artifact_ref")
    @classmethod
    def _safe_artifact_ref(cls, value: str) -> str:
        return _require_bundle_source_ref(value)

    @field_validator("media_type")
    @classmethod
    def _normalized_media_type(cls, value: str) -> str:
        value = _require_exact_text(value, label="media type")
        if "/" not in value:
            raise ValueError("media type must be a type/subtype value")
        return value


class BundleEvidence(StrictContract):
    type: BundleEvidenceType = Field(strict=False)
    artifact_ref: str = Field(alias="artifactRef", min_length=1, max_length=1024)
    artifact_hash: str = Field(alias="artifactHash", pattern=SHA256_PATTERN)
    status: BundleEvidenceStatus = Field(strict=False)
    observed_at: datetime = Field(alias="observedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    metadata: dict[str, JsonValue] = Field(default_factory=dict, max_length=100)

    @field_validator("artifact_ref")
    @classmethod
    def _safe_evidence_ref(cls, value: str) -> str:
        return _require_bundle_source_ref(value)

    @field_validator("observed_at", "expires_at", "revoked_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("evidence timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def _lifecycle_is_consistent(self) -> BundleEvidence:
        if self.expires_at is not None and self.expires_at <= self.observed_at:
            raise ValueError("expiresAt must be after observedAt")
        if self.status == BundleEvidenceStatus.REVOKED:
            if self.revoked_at is None:
                raise ValueError("revoked evidence requires revokedAt")
        elif self.revoked_at is not None:
            raise ValueError("revokedAt is only valid for revoked evidence")
        return self


class BundleSignature(StrictContract):
    algorithm: Literal["Ed25519"]
    key_id: str = Field(alias="keyId", min_length=1, max_length=240)
    signature: str = Field(min_length=1, max_length=2048)
    signed_at: datetime = Field(alias="signedAt")

    @field_validator("key_id", "signature")
    @classmethod
    def _normalized_signature_text(cls, value: str) -> str:
        return _require_exact_text(value, label="signature value")

    @field_validator("signed_at")
    @classmethod
    def _signed_at_has_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("signedAt must include a timezone")
        return value


class LoadedBundle(StrictContract):
    """Server-derived result of loading an allowlisted bundle source."""

    source_ref: str = Field(alias="sourceRef", min_length=1, max_length=1024)
    manifest: BundleManifest
    artifacts: list[BundleArtifact] = Field(max_length=20_000)
    evidence: list[BundleEvidence] = Field(max_length=500)
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    signature: BundleSignature | None
    loaded_at: datetime = Field(alias="loadedAt")

    @field_validator("source_ref")
    @classmethod
    def _safe_source_ref(cls, value: str) -> str:
        return _require_bundle_source_ref(value)

    @field_validator("loaded_at")
    @classmethod
    def _loaded_at_has_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("loadedAt must include a timezone")
        return value

    @model_validator(mode="after")
    def _indexes_are_unique(self) -> LoadedBundle:
        paths = [artifact.relative_path for artifact in self.artifacts]
        if len(paths) != len(set(paths)):
            raise ValueError("artifact paths must be unique")
        evidence_keys = [
            (item.type, item.artifact_ref, item.artifact_hash) for item in self.evidence
        ]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("evidence entries must be unique")
        return self
