"""Strict public contracts for deterministic composition and installation."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    CAPABILITY_PATTERN,
    MAX_BUNDLE_ID_LENGTH,
    MAX_PUBLISHER_ID_LENGTH,
    MAX_REFERENCE_LENGTH,
    SHA256_PATTERN,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleKind,
    BundleManifest,
    ContributionClaim,
    DowngradePolicy,
    StrictContract,
    contribution_conflict_keys,
    contribution_sort_key,
)
from aos_api.asset_registry.semver import parse_range, parse_version

LOCK_SCHEMA_VERSION = "aos.dev/composition-lock/v1alpha1"
SNAPSHOT_SCHEMA_VERSION = "aos.dev/registry-snapshot/v1alpha1"
RESOLVER_VERSION = "aos-resolver/1.0.0"

MAX_REQUESTED_BUNDLES = 64
MAX_SNAPSHOT_CANDIDATES = 4_096
MAX_RESOLVED_NODES = 512
MAX_DEPENDENCY_EDGES = 4_096
MAX_DEPENDENCY_DEPTH = 64
MAX_BACKTRACKING_STATES = 10_000
MAX_CONTRIBUTION_CLAIMS = 10_000
MAX_CANONICAL_LOCK_PAYLOAD_BYTES = 4 * 1024 * 1024
MAX_SEMVER_REQUIREMENT_LENGTH = 256
MAX_PLATFORM_RELEASE_LENGTH = 160
MAX_OVERLAY_REVISION_LENGTH = 160
MAX_IDEMPOTENCY_KEY_LENGTH = 160
MAX_INSTALLATION_DISPLAY_NAME_LENGTH = 240
MAX_INSTALLATION_REASON_LENGTH = 2_000
MAX_INSTALLATION_LIST_LIMIT = 100
MAX_INSTALLATION_LIST_OFFSET = 10_000


def _normalized_text(value: str, *, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-blank and already normalized")
    if "\x00" in value:
        raise ValueError(f"{label} must not contain NUL")
    return value


def _canonical_uuid(value: str, *, label: str) -> str:
    value = _normalized_text(value, label=label)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{label} must use canonical lowercase UUID form")
    return value


def _aware_datetime(value: datetime, *, label: str) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return value


def _sorted_unique_text(values: list[str], *, label: str) -> list[str]:
    checked = [_normalized_text(value, label=label) for value in values]
    if len(checked) != len(set(checked)):
        raise ValueError(f"{label} values must be unique")
    return sorted(checked)


def _require_unique(values: list[object], *, keys: list[object], label: str) -> None:
    if len(values) != len(set(keys)):
        raise ValueError(f"{label} must be unique")


def _model_payload(model: StrictContract) -> dict[str, object]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=False)


class RequestedBundle(StrictContract):
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str = Field(min_length=1, max_length=MAX_SEMVER_REQUIREMENT_LENGTH)

    @field_validator("version")
    @classmethod
    def _valid_requirement(cls, value: str) -> str:
        value = _normalized_text(value, label="requested version")
        parse_range(value)
        return value


class CurrentInstallationRef(StrictContract):
    installation_id: str = Field(alias="installationId")
    revision: int = Field(ge=1)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    overlay_revision: str = Field(
        alias="overlayRevision",
        min_length=1,
        max_length=MAX_OVERLAY_REVISION_LENGTH,
    )

    @field_validator("installation_id")
    @classmethod
    def _valid_installation_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="installationId")

    @field_validator("overlay_revision")
    @classmethod
    def _normalized_overlay_revision(cls, value: str) -> str:
        return _normalized_text(value, label="overlayRevision")


class CanonicalCompositionRequest(StrictContract):
    requested: list[RequestedBundle] = Field(
        min_length=1,
        max_length=MAX_REQUESTED_BUNDLES,
    )
    platform_api_version: str = Field(
        alias="platformApiVersion",
        min_length=1,
        max_length=MAX_SEMVER_REQUIREMENT_LENGTH,
    )
    platform_release: str = Field(
        alias="platformRelease",
        min_length=1,
        max_length=MAX_PLATFORM_RELEASE_LENGTH,
    )
    environment: Literal["dev", "staging", "prod"]

    @field_validator("platform_api_version")
    @classmethod
    def _valid_platform_api_version(cls, value: str) -> str:
        value = _normalized_text(value, label="platformApiVersion")
        parse_version(value)
        return value

    @field_validator("platform_release")
    @classmethod
    def _normalized_platform_release(cls, value: str) -> str:
        return _normalized_text(value, label="platformRelease")

    @model_validator(mode="after")
    def _sort_and_deduplicate_requested(self) -> CanonicalCompositionRequest:
        keys = [(item.publisher, item.id) for item in self.requested]
        if len(keys) != len(set(keys)):
            raise ValueError("requested bundle coordinates must be unique")
        object.__setattr__(
            self,
            "requested",
            sorted(
                self.requested,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        return self


class CompositionRequest(CanonicalCompositionRequest):
    registry_snapshot_hash: str | None = Field(
        default=None,
        alias="registrySnapshotHash",
        pattern=SHA256_PATTERN,
    )
    current_installation_ref: CurrentInstallationRef | None = Field(
        default=None,
        alias="currentInstallationRef",
    )

    def lock_request(self) -> CanonicalCompositionRequest:
        """Return the exact request object embedded in a composition lock."""

        return CanonicalCompositionRequest.model_validate(
            {
                "requested": [
                    item.model_dump(mode="json", by_alias=True)
                    for item in self.requested
                ],
                "platformApiVersion": self.platform_api_version,
                "platformRelease": self.platform_release,
                "environment": self.environment,
            }
        )


class DependencyConstraint(StrictContract):
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str = Field(min_length=1, max_length=MAX_SEMVER_REQUIREMENT_LENGTH)

    @field_validator("version")
    @classmethod
    def _valid_range(cls, value: str) -> str:
        value = _normalized_text(value, label="dependency version")
        parse_range(value)
        return value


class ConflictConstraint(StrictContract):
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_SEMVER_REQUIREMENT_LENGTH,
    )

    @field_validator("version")
    @classmethod
    def _valid_optional_range(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = _normalized_text(value, label="conflict version")
        parse_range(value)
        return value


class CapabilitySet(StrictContract):
    provides: list[str] = Field(max_length=500)
    requires: list[str] = Field(max_length=500)

    @field_validator("provides", "requires")
    @classmethod
    def _normalized_capabilities(cls, values: list[str]) -> list[str]:
        for value in values:
            if not re.fullmatch(CAPABILITY_PATTERN, value):
                raise ValueError("capability id is invalid")
        return _sorted_unique_text(values, label="capability")

    @model_validator(mode="after")
    def _sets_are_disjoint(self) -> CapabilitySet:
        if set(self.provides).intersection(self.requires):
            raise ValueError("a capability cannot be both provided and required")
        return self


class PermissionSet(StrictContract):
    roles: list[str] = Field(max_length=500)
    markings: list[str] = Field(max_length=500)
    data_scopes: list[str] = Field(alias="dataScopes", max_length=500)
    action_types: list[str] = Field(alias="actionTypes", max_length=500)

    @field_validator("roles", "markings", "data_scopes", "action_types")
    @classmethod
    def _normalized_values(cls, values: list[str]) -> list[str]:
        return _sorted_unique_text(values, label="permission")


class MigrationDescriptor(StrictContract):
    plan_ref: str | None = Field(
        default=None,
        alias="planRef",
        max_length=MAX_REFERENCE_LENGTH,
    )
    downgrade_policy: DowngradePolicy = Field(
        alias="downgradePolicy",
        strict=False,
    )

    @field_validator("plan_ref")
    @classmethod
    def _normalized_plan_ref(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_text(value, label="planRef")


class ReleaseEvidenceSnapshot(StrictContract):
    type: BundleEvidenceType = Field(strict=False)
    artifact_hash: str = Field(alias="artifactHash", pattern=SHA256_PATTERN)
    status: BundleEvidenceStatus = Field(strict=False)
    observed_at: datetime = Field(alias="observedAt")
    expires_at: datetime | None = Field(default=None, alias="expiresAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")

    @field_validator("observed_at", "expires_at", "revoked_at")
    @classmethod
    def _timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            _aware_datetime(value, label="release evidence timestamp")
        return value


class RegistrySnapshotCandidate(StrictContract):
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str = Field(min_length=1, max_length=MAX_SEMVER_REQUIREMENT_LENGTH)
    kind: BundleKind = Field(strict=False)
    manifest: BundleManifest
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    signature_fingerprint: str = Field(
        alias="signatureFingerprint",
        pattern=SHA256_PATTERN,
    )
    release_evidence_revision: str = Field(
        alias="releaseEvidenceRevision",
        pattern=SHA256_PATTERN,
    )
    dependencies: list[DependencyConstraint] = Field(max_length=500)
    optional_dependencies: list[DependencyConstraint] = Field(
        alias="optionalDependencies",
        max_length=500,
    )
    conflicts: list[ConflictConstraint] = Field(max_length=500)
    capabilities: CapabilitySet
    permissions: PermissionSet
    migration: MigrationDescriptor
    contributions: list[ContributionClaim] = Field(max_length=MAX_CONTRIBUTION_CLAIMS)

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        value = _normalized_text(value, label="candidate version")
        parse_version(value)
        return value

    @model_validator(mode="after")
    def _coordinate_and_indexes_are_canonical(self) -> RegistrySnapshotCandidate:
        metadata = self.manifest.metadata
        if (
            metadata.publisher,
            metadata.id,
            metadata.version,
            self.manifest.kind,
        ) != (self.publisher, self.id, self.version, self.kind):
            raise ValueError("candidate coordinate must match manifest")

        object.__setattr__(
            self,
            "dependencies",
            sorted(
                self.dependencies,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        object.__setattr__(
            self,
            "optional_dependencies",
            sorted(
                self.optional_dependencies,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        object.__setattr__(
            self,
            "conflicts",
            sorted(
                self.conflicts,
                key=lambda item: (item.publisher, item.id, item.version or ""),
            ),
        )
        object.__setattr__(
            self,
            "contributions",
            sorted(self.contributions, key=contribution_sort_key),
        )
        _require_unique(
            self.dependencies,
            keys=[(item.publisher, item.id) for item in self.dependencies],
            label="candidate dependencies",
        )
        _require_unique(
            self.optional_dependencies,
            keys=[(item.publisher, item.id) for item in self.optional_dependencies],
            label="candidate optional dependencies",
        )
        _require_unique(
            self.conflicts,
            keys=[(item.publisher, item.id) for item in self.conflicts],
            label="candidate conflicts",
        )

        spec = self.manifest.spec
        expected_dependencies = sorted(
            [
                DependencyConstraint.model_validate(
                    {
                        "publisher": item.publisher or self.publisher,
                        "id": item.id,
                        "version": item.version,
                    }
                )
                for item in spec.dependencies
            ],
            key=lambda item: (item.publisher, item.id, item.version),
        )
        expected_optional_dependencies = sorted(
            [
                DependencyConstraint.model_validate(
                    {
                        "publisher": item.publisher or self.publisher,
                        "id": item.id,
                        "version": item.version,
                    }
                )
                for item in spec.optional_dependencies
            ],
            key=lambda item: (item.publisher, item.id, item.version),
        )
        expected_conflicts = sorted(
            [
                ConflictConstraint.model_validate(
                    {
                        "publisher": item.publisher or self.publisher,
                        "id": item.id,
                        "version": item.version,
                    }
                )
                for item in spec.conflicts
            ],
            key=lambda item: (item.publisher, item.id, item.version or ""),
        )
        expected_capabilities = CapabilitySet.model_validate(
            {
                "provides": spec.capabilities.provides,
                "requires": spec.capabilities.requires,
            }
        )
        expected_permissions = PermissionSet.model_validate(
            spec.permissions.model_dump(mode="json", by_alias=True)
        )
        expected_migration = MigrationDescriptor.model_validate(
            {
                "planRef": spec.migrations.plan,
                "downgradePolicy": spec.migrations.downgrade_policy,
            }
        )
        expected_contributions = sorted(
            spec.contributions,
            key=contribution_sort_key,
        )
        if (
            self.dependencies != expected_dependencies
            or self.optional_dependencies != expected_optional_dependencies
            or self.conflicts != expected_conflicts
            or self.capabilities != expected_capabilities
            or self.permissions != expected_permissions
            or self.migration != expected_migration
            or self.contributions != expected_contributions
        ):
            raise ValueError("candidate indexes must be derived from signed manifest")
        return self


def registry_candidate_sort_key(
    candidate: RegistrySnapshotCandidate,
) -> tuple[object, ...]:
    return (
        candidate.publisher,
        candidate.id,
        parse_version(candidate.version),
        candidate.version,
        candidate.content_hash,
    )


class RegistrySnapshot(StrictContract):
    schema_version: Literal[SNAPSHOT_SCHEMA_VERSION] = Field(
        default=SNAPSHOT_SCHEMA_VERSION,
        alias="schemaVersion",
    )
    candidates: list[RegistrySnapshotCandidate] = Field(
        max_length=MAX_SNAPSHOT_CANDIDATES
    )
    snapshot_hash: str = Field(alias="snapshotHash", pattern=SHA256_PATTERN)
    checked_at: datetime = Field(alias="checkedAt")

    @field_validator("checked_at")
    @classmethod
    def _checked_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="checkedAt")

    @model_validator(mode="after")
    def _candidates_and_hash_are_canonical(self) -> RegistrySnapshot:
        object.__setattr__(
            self,
            "candidates",
            sorted(self.candidates, key=registry_candidate_sort_key),
        )
        _require_unique(
            self.candidates,
            keys=[(item.publisher, item.id, item.version) for item in self.candidates],
            label="registry snapshot candidate coordinates",
        )
        if self.snapshot_hash != canonical_sha256(self.hash_payload_dump()):
            raise ValueError("snapshotHash does not match canonical snapshot payload")
        return self

    @classmethod
    def build(
        cls,
        *,
        candidates: list[RegistrySnapshotCandidate],
        checked_at: datetime,
    ) -> Self:
        """Build a snapshot with its hash derived from the sorted payload."""

        sorted_candidates = sorted(candidates, key=registry_candidate_sort_key)
        payload = {
            "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
            "candidates": [
                _model_payload(candidate) for candidate in sorted_candidates
            ],
        }
        return cls.model_validate(
            {
                "schemaVersion": SNAPSHOT_SCHEMA_VERSION,
                "candidates": sorted_candidates,
                "snapshotHash": canonical_sha256(payload),
                "checkedAt": checked_at,
            }
        )

    def hash_payload_dump(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version,
            "candidates": [_model_payload(candidate) for candidate in self.candidates],
        }


class ResolvedBundle(StrictContract):
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str = Field(min_length=1, max_length=MAX_SEMVER_REQUIREMENT_LENGTH)
    kind: BundleKind = Field(strict=False)
    content_hash: str = Field(alias="contentHash", pattern=SHA256_PATTERN)
    signature_fingerprint: str = Field(
        alias="signatureFingerprint",
        pattern=SHA256_PATTERN,
    )
    release_evidence_revision: str = Field(
        alias="releaseEvidenceRevision",
        pattern=SHA256_PATTERN,
    )
    dependencies: list[DependencyConstraint] = Field(max_length=500)
    optional_dependencies: list[DependencyConstraint] = Field(
        alias="optionalDependencies",
        max_length=500,
    )
    conflicts: list[ConflictConstraint] = Field(max_length=500)
    capabilities: CapabilitySet
    permissions: PermissionSet
    migration: MigrationDescriptor
    contributions: list[ContributionClaim] = Field(max_length=MAX_CONTRIBUTION_CLAIMS)
    selection_reason: Literal["requested", "dependency"] = Field(
        alias="selectionReason"
    )

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        value = _normalized_text(value, label="resolved version")
        parse_version(value)
        return value

    @model_validator(mode="after")
    def _indexes_are_sorted(self) -> ResolvedBundle:
        _require_unique(
            self.dependencies,
            keys=[(item.publisher, item.id) for item in self.dependencies],
            label="resolved dependencies",
        )
        _require_unique(
            self.optional_dependencies,
            keys=[(item.publisher, item.id) for item in self.optional_dependencies],
            label="resolved optional dependencies",
        )
        _require_unique(
            self.conflicts,
            keys=[(item.publisher, item.id) for item in self.conflicts],
            label="resolved conflicts",
        )
        contribution_keys = [
            key
            for claim in self.contributions
            for key in contribution_conflict_keys(claim)
        ]
        if len(contribution_keys) != len(set(contribution_keys)):
            raise ValueError("resolved contribution conflict keys must be unique")
        object.__setattr__(
            self,
            "dependencies",
            sorted(
                self.dependencies,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        object.__setattr__(
            self,
            "optional_dependencies",
            sorted(
                self.optional_dependencies,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        object.__setattr__(
            self,
            "conflicts",
            sorted(
                self.conflicts,
                key=lambda item: (item.publisher, item.id, item.version or ""),
            ),
        )
        object.__setattr__(
            self,
            "contributions",
            sorted(self.contributions, key=contribution_sort_key),
        )
        return self


class ResolvedEdge(StrictContract):
    from_publisher: str = Field(
        alias="fromPublisher",
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    from_id: str = Field(
        alias="fromId",
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    from_version: str = Field(alias="fromVersion", max_length=256)
    to_publisher: str = Field(
        alias="toPublisher",
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    to_id: str = Field(
        alias="toId",
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    to_version: str = Field(alias="toVersion", max_length=256)
    constraint: str = Field(min_length=1, max_length=MAX_SEMVER_REQUIREMENT_LENGTH)
    optional: bool

    @field_validator("from_version", "to_version")
    @classmethod
    def _strict_versions(cls, value: str) -> str:
        value = _normalized_text(value, label="resolved edge version")
        parse_version(value)
        return value

    @field_validator("constraint")
    @classmethod
    def _valid_constraint(cls, value: str) -> str:
        value = _normalized_text(value, label="edge constraint")
        parse_range(value)
        return value


def resolved_edge_sort_key(edge: ResolvedEdge) -> tuple[object, ...]:
    return (
        edge.from_publisher,
        edge.from_id,
        parse_version(edge.from_version),
        edge.to_publisher,
        edge.to_id,
        parse_version(edge.to_version),
        edge.constraint,
        edge.optional,
    )


class CapabilityProvider(StrictContract):
    capability: str = Field(min_length=1, max_length=160, pattern=CAPABILITY_PATTERN)
    publisher: str = Field(
        min_length=1,
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    id: str = Field(
        min_length=1,
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    version: str = Field(min_length=1, max_length=256)

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        value = _normalized_text(value, label="provider version")
        parse_version(value)
        return value


class ConstraintPathNode(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    version: str | None = Field(default=None, max_length=256)
    via: Literal["requested", "dependency", "optional"]

    @field_validator("version")
    @classmethod
    def _strict_optional_version(cls, value: str | None) -> str | None:
        if value is not None:
            parse_version(_normalized_text(value, label="path version"))
        return value


class ConstraintRecord(StrictContract):
    source_publisher: str = Field(
        alias="sourcePublisher",
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    source_id: str = Field(
        alias="sourceId",
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    source_version: str | None = Field(
        default=None,
        alias="sourceVersion",
        max_length=256,
    )
    target_publisher: str = Field(
        alias="targetPublisher",
        max_length=MAX_PUBLISHER_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    target_id: str = Field(
        alias="targetId",
        max_length=MAX_BUNDLE_ID_LENGTH,
        pattern=BUNDLE_ID_PATTERN,
    )
    requirement: str = Field(min_length=1, max_length=256)
    optional: bool

    @field_validator("source_version")
    @classmethod
    def _strict_optional_version(cls, value: str | None) -> str | None:
        if value is not None:
            parse_version(_normalized_text(value, label="constraint source version"))
        return value

    @field_validator("requirement")
    @classmethod
    def _valid_requirement(cls, value: str) -> str:
        value = _normalized_text(value, label="constraint requirement")
        parse_range(value)
        return value


class CandidateRejection(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(max_length=256)
    reason: Literal[
        "platform_api",
        "version_constraint",
        "prerelease",
        "conflict",
        "resource_limit",
    ]

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        parse_version(_normalized_text(value, label="rejected candidate version"))
        return value


class ConflictOwner(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(max_length=256)

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        parse_version(_normalized_text(value, label="conflict owner version"))
        return value


class ConflictResource(StrictContract):
    kind: str = Field(min_length=1, max_length=160)
    key: str = Field(min_length=1, max_length=2048)
    owners: list[ConflictOwner] = Field(min_length=1, max_length=MAX_RESOLVED_NODES)

    @field_validator("kind", "key")
    @classmethod
    def _normalized_resource_text(cls, value: str) -> str:
        return _normalized_text(value, label="conflict resource")

    @model_validator(mode="after")
    def _owners_are_sorted(self) -> ConflictResource:
        object.__setattr__(
            self,
            "owners",
            sorted(
                self.owners,
                key=lambda item: (item.publisher, item.id, item.version),
            ),
        )
        return self


class DependencyConflictDetails(StrictContract):
    subtype: Literal[
        "missing_dependency",
        "version_intersection_empty",
        "explicit_conflict",
        "capability_missing",
        "capability_multiple",
        "contribution_collision",
    ]
    path: list[ConstraintPathNode]
    constraints: list[ConstraintRecord]
    candidate_rejections: list[CandidateRejection] = Field(alias="candidateRejections")
    resource: ConflictResource | None

    @model_validator(mode="after")
    def _diagnostics_are_sorted(self) -> DependencyConflictDetails:
        object.__setattr__(
            self,
            "constraints",
            sorted(
                self.constraints,
                key=lambda item: (
                    item.target_publisher,
                    item.target_id,
                    item.source_publisher,
                    item.source_id,
                    item.source_version or "",
                    item.requirement,
                    item.optional,
                ),
            ),
        )
        object.__setattr__(
            self,
            "candidate_rejections",
            sorted(
                self.candidate_rejections,
                key=lambda item: (
                    item.publisher,
                    item.id,
                    item.version,
                    item.reason,
                ),
            ),
        )
        return self


class DependencyCycleDetails(StrictContract):
    cycle: list[ConstraintPathNode] = Field(
        min_length=1, max_length=MAX_DEPENDENCY_DEPTH
    )

    @model_validator(mode="after")
    def _rotate_to_smallest_node(self) -> DependencyCycleDetails:
        keys = [
            (item.publisher, item.id, item.version or "", item.via)
            for item in self.cycle
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("dependency cycle must not repeat a node")
        start = min(range(len(keys)), key=keys.__getitem__)
        object.__setattr__(self, "cycle", self.cycle[start:] + self.cycle[:start])
        return self


class ResolutionLimitDetails(StrictContract):
    resource: Literal[
        "requested",
        "snapshot_candidates",
        "resolved_nodes",
        "dependency_edges",
        "dependency_depth",
        "backtracking_states",
        "contribution_claims",
        "canonical_lock_payload_bytes",
    ]
    limit: int = Field(ge=1)
    observed: int = Field(ge=0)


class PermissionDiff(StrictContract):
    baseline: PermissionSet
    target: PermissionSet
    added: PermissionSet
    removed: PermissionSet
    unchanged: PermissionSet

    @model_validator(mode="after")
    def _sets_match_diff_semantics(self) -> PermissionDiff:
        for field_name in ("roles", "markings", "data_scopes", "action_types"):
            baseline = set(getattr(self.baseline, field_name))
            target = set(getattr(self.target, field_name))
            if set(getattr(self.added, field_name)) != target - baseline:
                raise ValueError("permission added set is inconsistent")
            if set(getattr(self.removed, field_name)) != baseline - target:
                raise ValueError("permission removed set is inconsistent")
            if set(getattr(self.unchanged, field_name)) != baseline & target:
                raise ValueError("permission unchanged set is inconsistent")
        return self


class MigrationStep(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(max_length=256)
    plan_ref: str = Field(
        alias="planRef", min_length=1, max_length=MAX_REFERENCE_LENGTH
    )
    downgrade_policy: DowngradePolicy = Field(alias="downgradePolicy", strict=False)

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        parse_version(_normalized_text(value, label="migration version"))
        return value

    @field_validator("plan_ref")
    @classmethod
    def _normalized_plan_ref(cls, value: str) -> str:
        return _normalized_text(value, label="migration planRef")


def migration_step_sort_key(step: MigrationStep) -> tuple[str, ...]:
    return (step.publisher, step.id, step.version, step.plan_ref)


def _migration_coordinate(step: MigrationStep) -> tuple[str, str]:
    return (step.publisher, step.id)


class MigrationChange(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    before: MigrationStep
    after: MigrationStep

    @model_validator(mode="after")
    def _coordinate_is_stable(self) -> MigrationChange:
        expected = (self.publisher, self.id)
        if (self.before.publisher, self.before.id) != expected or (
            self.after.publisher,
            self.after.id,
        ) != expected:
            raise ValueError("migration change coordinates must match")
        if self.before == self.after:
            raise ValueError("migration change before and after must differ")
        return self


class MigrationPlanDiff(StrictContract):
    baseline: list[MigrationStep]
    target: list[MigrationStep]
    added: list[MigrationStep]
    removed: list[MigrationStep]
    changed: list[MigrationChange]

    @model_validator(mode="after")
    def _diff_is_derived_and_sorted(self) -> MigrationPlanDiff:
        for field_name in ("baseline", "target", "added", "removed"):
            values = getattr(self, field_name)
            _require_unique(
                values,
                keys=[_migration_coordinate(item) for item in values],
                label=f"migration {field_name}",
            )
            object.__setattr__(
                self,
                field_name,
                sorted(values, key=migration_step_sort_key),
            )
        _require_unique(
            self.changed,
            keys=[(item.publisher, item.id) for item in self.changed],
            label="migration changes",
        )
        object.__setattr__(
            self,
            "changed",
            sorted(self.changed, key=lambda item: (item.publisher, item.id)),
        )

        baseline = {_migration_coordinate(item): item for item in self.baseline}
        target = {_migration_coordinate(item): item for item in self.target}
        expected_added = {
            coordinate: target[coordinate]
            for coordinate in target.keys() - baseline.keys()
        }
        expected_removed = {
            coordinate: baseline[coordinate]
            for coordinate in baseline.keys() - target.keys()
        }
        expected_changed = {
            coordinate: MigrationChange.model_validate(
                {
                    "publisher": coordinate[0],
                    "id": coordinate[1],
                    "before": baseline[coordinate],
                    "after": target[coordinate],
                }
            )
            for coordinate in baseline.keys() & target.keys()
            if baseline[coordinate] != target[coordinate]
        }
        actual_added = {_migration_coordinate(item): item for item in self.added}
        actual_removed = {_migration_coordinate(item): item for item in self.removed}
        actual_changed = {(item.publisher, item.id): item for item in self.changed}
        if actual_added != expected_added:
            raise ValueError("migration added set is inconsistent")
        if actual_removed != expected_removed:
            raise ValueError("migration removed set is inconsistent")
        if actual_changed != expected_changed:
            raise ValueError("migration changed set is inconsistent")
        return self


class ContributionBinding(StrictContract):
    publisher: str = Field(
        max_length=MAX_PUBLISHER_ID_LENGTH, pattern=BUNDLE_ID_PATTERN
    )
    id: str = Field(max_length=MAX_BUNDLE_ID_LENGTH, pattern=BUNDLE_ID_PATTERN)
    version: str = Field(max_length=256)
    claim: ContributionClaim

    @field_validator("version")
    @classmethod
    def _strict_version(cls, value: str) -> str:
        parse_version(_normalized_text(value, label="contribution version"))
        return value


def contribution_binding_sort_key(
    binding: ContributionBinding,
) -> tuple[object, ...]:
    primary_key = contribution_conflict_keys(binding.claim)[0]
    return (
        binding.claim.kind,
        primary_key,
        binding.publisher,
        binding.id,
        parse_version(binding.version),
        binding.version,
    )


def _contribution_binding_identity(binding: ContributionBinding) -> bytes:
    return canonical_json(_model_payload(binding))


class ContributionDiff(StrictContract):
    baseline: list[ContributionBinding]
    target: list[ContributionBinding]
    added: list[ContributionBinding]
    removed: list[ContributionBinding]
    unchanged: list[ContributionBinding]

    @model_validator(mode="after")
    def _diff_is_derived_and_sorted(self) -> ContributionDiff:
        for field_name in ("baseline", "target", "added", "removed", "unchanged"):
            values = getattr(self, field_name)
            keys = [_contribution_binding_identity(item) for item in values]
            _require_unique(
                values,
                keys=keys,
                label=f"contribution {field_name}",
            )
            object.__setattr__(
                self,
                field_name,
                sorted(values, key=contribution_binding_sort_key),
            )
        baseline = {
            _contribution_binding_identity(item): item for item in self.baseline
        }
        target = {_contribution_binding_identity(item): item for item in self.target}
        expected_added = target.keys() - baseline.keys()
        expected_removed = baseline.keys() - target.keys()
        expected_unchanged = baseline.keys() & target.keys()
        if {
            _contribution_binding_identity(item) for item in self.added
        } != expected_added:
            raise ValueError("contribution added set is inconsistent")
        if {
            _contribution_binding_identity(item) for item in self.removed
        } != expected_removed:
            raise ValueError("contribution removed set is inconsistent")
        if {
            _contribution_binding_identity(item) for item in self.unchanged
        } != expected_unchanged:
            raise ValueError("contribution unchanged set is inconsistent")
        return self


class CompositionLockPayload(StrictContract):
    lock_schema_version: Literal[LOCK_SCHEMA_VERSION] = Field(
        default=LOCK_SCHEMA_VERSION,
        alias="lockSchemaVersion",
    )
    resolver_version: Literal[RESOLVER_VERSION] = Field(
        default=RESOLVER_VERSION,
        alias="resolverVersion",
    )
    request: CanonicalCompositionRequest
    registry_snapshot_hash: str = Field(
        alias="registrySnapshotHash",
        pattern=SHA256_PATTERN,
    )
    resolved: list[ResolvedBundle] = Field(
        min_length=1,
        max_length=MAX_RESOLVED_NODES,
    )
    edges: list[ResolvedEdge] = Field(max_length=MAX_DEPENDENCY_EDGES)
    capability_providers: list[CapabilityProvider] = Field(
        alias="capabilityProviders",
    )
    permission_diff: PermissionDiff = Field(alias="permissionDiff")
    migration_plan: MigrationPlanDiff = Field(alias="migrationPlan")
    contribution_diff: ContributionDiff = Field(alias="contributionDiff")
    current_installation_ref: CurrentInstallationRef | None = Field(
        alias="currentInstallationRef"
    )

    @model_validator(mode="after")
    def _payload_is_canonical_and_bounded(self) -> CompositionLockPayload:
        _require_unique(
            self.resolved,
            keys=[(item.publisher, item.id) for item in self.resolved],
            label="resolved bundle coordinates",
        )
        _require_unique(
            self.edges,
            keys=[resolved_edge_sort_key(item) for item in self.edges],
            label="resolved edges",
        )
        _require_unique(
            self.capability_providers,
            keys=[item.capability for item in self.capability_providers],
            label="capability providers",
        )
        object.__setattr__(
            self,
            "resolved",
            sorted(
                self.resolved,
                key=lambda item: (
                    item.publisher,
                    item.id,
                    parse_version(item.version),
                    item.version,
                    item.content_hash,
                ),
            ),
        )
        object.__setattr__(
            self, "edges", sorted(self.edges, key=resolved_edge_sort_key)
        )
        object.__setattr__(
            self,
            "capability_providers",
            sorted(
                self.capability_providers,
                key=lambda item: (
                    item.capability,
                    item.publisher,
                    item.id,
                    item.version,
                ),
            ),
        )
        contribution_count = sum(len(item.contributions) for item in self.resolved)
        if contribution_count > MAX_CONTRIBUTION_CLAIMS:
            raise ValueError("resolved contribution claim limit exceeded")
        if (
            len(canonical_json(self.hash_payload_dump()))
            > MAX_CANONICAL_LOCK_PAYLOAD_BYTES
        ):
            raise ValueError("canonical lock payload size limit exceeded")
        return self

    def hash_payload_dump(self) -> dict[str, object]:
        return _model_payload(self)


class StoredCompositionLock(StrictContract):
    composition_id: str = Field(alias="compositionId")
    revision: int = Field(ge=1)
    payload: CompositionLockPayload
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    permission_diff_hash: str = Field(
        alias="permissionDiffHash",
        pattern=SHA256_PATTERN,
    )
    migration_plan_hash: str = Field(
        alias="migrationPlanHash",
        pattern=SHA256_PATTERN,
    )
    contribution_diff_hash: str = Field(
        alias="contributionDiffHash",
        pattern=SHA256_PATTERN,
    )
    created_at: datetime = Field(alias="createdAt")

    @field_validator("composition_id")
    @classmethod
    def _valid_composition_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="compositionId")

    @field_validator("created_at")
    @classmethod
    def _created_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="createdAt")

    @model_validator(mode="after")
    def _hashes_match_payload(self) -> StoredCompositionLock:
        expected = {
            "lockHash": canonical_sha256(self.payload.hash_payload_dump()),
            "permissionDiffHash": canonical_sha256(
                _model_payload(self.payload.permission_diff)
            ),
            "migrationPlanHash": canonical_sha256(
                _model_payload(self.payload.migration_plan)
            ),
            "contributionDiffHash": canonical_sha256(
                _model_payload(self.payload.contribution_diff)
            ),
        }
        actual = {
            "lockHash": self.lock_hash,
            "permissionDiffHash": self.permission_diff_hash,
            "migrationPlanHash": self.migration_plan_hash,
            "contributionDiffHash": self.contribution_diff_hash,
        }
        if actual != expected:
            raise ValueError("stored composition lock hashes do not match payload")
        return self


InstallationState = Literal[
    "draft",
    "submitted",
    "approved",
    "rejected",
    "applied",
    "active",
    "rolled_back",
    "uninstalled",
]
INSTALLATION_STATE_TRANSITIONS = frozenset(
    {
        ("draft", "submitted"),
        ("submitted", "approved"),
        ("submitted", "rejected"),
        ("approved", "applied"),
        ("applied", "active"),
        ("active", "rolled_back"),
        ("active", "uninstalled"),
    }
)


class CreateInstallationRequest(StrictContract):
    composition_id: str = Field(alias="compositionId")
    lock_revision: int = Field(alias="lockRevision", ge=1)
    overlay_revision: str = Field(
        alias="overlayRevision",
        min_length=1,
        max_length=MAX_OVERLAY_REVISION_LENGTH,
    )
    display_name: str = Field(
        alias="displayName",
        min_length=1,
        max_length=MAX_INSTALLATION_DISPLAY_NAME_LENGTH,
    )

    @field_validator("composition_id")
    @classmethod
    def _valid_composition_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="compositionId")

    @field_validator("overlay_revision", "display_name")
    @classmethod
    def _normalized_text_fields(cls, value: str) -> str:
        return _normalized_text(value, label="installation request value")


class EmptyInstallationActionRequest(StrictContract):
    pass


class ApproveInstallationRequest(StrictContract):
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    permission_diff_hash: str = Field(
        alias="permissionDiffHash",
        pattern=SHA256_PATTERN,
    )
    migration_plan_hash: str = Field(
        alias="migrationPlanHash",
        pattern=SHA256_PATTERN,
    )
    contribution_diff_hash: str = Field(
        alias="contributionDiffHash",
        pattern=SHA256_PATTERN,
    )


class RejectInstallationRequest(StrictContract):
    reason: str = Field(min_length=1, max_length=MAX_INSTALLATION_REASON_LENGTH)

    @field_validator("reason")
    @classmethod
    def _normalized_reason(cls, value: str) -> str:
        return _normalized_text(value, label="rejection reason")


class RollbackInstallationRequest(StrictContract):
    reason: str = Field(min_length=1, max_length=MAX_INSTALLATION_REASON_LENGTH)

    @field_validator("reason")
    @classmethod
    def _normalized_reason(cls, value: str) -> str:
        return _normalized_text(value, label="rollback reason")


class UninstallInstallationRequest(StrictContract):
    reason: str = Field(min_length=1, max_length=MAX_INSTALLATION_REASON_LENGTH)

    @field_validator("reason")
    @classmethod
    def _normalized_reason(cls, value: str) -> str:
        return _normalized_text(value, label="uninstall reason")


ApproveRequest = ApproveInstallationRequest
RejectRequest = RejectInstallationRequest
RollbackRequest = RollbackInstallationRequest
UninstallRequest = UninstallInstallationRequest
EmptyActionRequest = EmptyInstallationActionRequest


class InstallationRevision(StrictContract):
    installation_id: str = Field(alias="installationId")
    revision: int = Field(ge=1)
    parent_revision: int | None = Field(default=None, alias="parentRevision", ge=1)
    state: InstallationState
    composition_id: str = Field(alias="compositionId")
    lock_revision: int = Field(alias="lockRevision", ge=1)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    permission_diff_hash: str = Field(
        alias="permissionDiffHash",
        pattern=SHA256_PATTERN,
    )
    migration_plan_hash: str = Field(
        alias="migrationPlanHash",
        pattern=SHA256_PATTERN,
    )
    contribution_diff_hash: str = Field(
        alias="contributionDiffHash",
        pattern=SHA256_PATTERN,
    )
    overlay_revision: str = Field(
        alias="overlayRevision",
        min_length=1,
        max_length=MAX_OVERLAY_REVISION_LENGTH,
    )
    requested_by: str = Field(alias="requestedBy", min_length=1, max_length=240)
    decision_id: str | None = Field(default=None, alias="decisionId")
    created_at: datetime = Field(alias="createdAt")

    @field_validator("installation_id")
    @classmethod
    def _valid_installation_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="installationId")

    @field_validator("composition_id")
    @classmethod
    def _valid_composition_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="compositionId")

    @field_validator("decision_id")
    @classmethod
    def _valid_optional_decision_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _canonical_uuid(value, label="decisionId")

    @field_validator("overlay_revision", "requested_by")
    @classmethod
    def _normalized_text_fields(cls, value: str) -> str:
        return _normalized_text(value, label="installation revision value")

    @field_validator("created_at")
    @classmethod
    def _created_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="createdAt")

    @model_validator(mode="after")
    def _revision_lineage_is_consistent(self) -> InstallationRevision:
        expected_parent = None if self.revision == 1 else self.revision - 1
        if self.parent_revision != expected_parent:
            raise ValueError("parentRevision must identify the previous revision")
        requires_decision = self.state in {
            "approved",
            "rejected",
            "applied",
            "active",
            "rolled_back",
            "uninstalled",
        }
        if requires_decision != (self.decision_id is not None):
            raise ValueError("decisionId is inconsistent with installation state")
        return self


class InstallationDecision(StrictContract):
    decision_id: str = Field(alias="decisionId")
    installation_id: str = Field(alias="installationId")
    submitted_revision: int = Field(alias="submittedRevision", ge=1)
    decision: Literal["approved", "rejected"]
    actor: str = Field(min_length=1, max_length=240)
    lock_hash: str = Field(alias="lockHash", pattern=SHA256_PATTERN)
    permission_diff_hash: str = Field(
        alias="permissionDiffHash",
        pattern=SHA256_PATTERN,
    )
    migration_plan_hash: str = Field(
        alias="migrationPlanHash",
        pattern=SHA256_PATTERN,
    )
    contribution_diff_hash: str = Field(
        alias="contributionDiffHash",
        pattern=SHA256_PATTERN,
    )
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_INSTALLATION_REASON_LENGTH,
    )
    created_at: datetime = Field(alias="createdAt")

    @field_validator("decision_id", "installation_id")
    @classmethod
    def _valid_ids(cls, value: str, info) -> str:
        return _canonical_uuid(value, label=info.field_name)

    @field_validator("actor")
    @classmethod
    def _normalized_actor(cls, value: str) -> str:
        return _normalized_text(value, label="decision actor")

    @field_validator("reason")
    @classmethod
    def _normalized_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_text(value, label="decision reason")

    @field_validator("created_at")
    @classmethod
    def _created_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="createdAt")

    @model_validator(mode="after")
    def _reason_matches_decision(self) -> InstallationDecision:
        if self.decision == "rejected" and self.reason is None:
            raise ValueError("rejected decision requires a reason")
        return self


class InstallationEventEvidence(StrictContract):
    type: Literal["dry_apply", "verification", "rollback"]
    evidence_ref: str = Field(
        alias="evidenceRef",
        min_length=1,
        max_length=MAX_REFERENCE_LENGTH,
    )
    evidence_hash: str = Field(alias="evidenceHash", pattern=SHA256_PATTERN)
    status: Literal["valid", "invalid"]
    observed_at: datetime = Field(alias="observedAt")

    @field_validator("evidence_ref")
    @classmethod
    def _normalized_evidence_ref(cls, value: str) -> str:
        return _normalized_text(value, label="evidenceRef")

    @field_validator("observed_at")
    @classmethod
    def _observed_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="observedAt")


class InstallationEvent(StrictContract):
    sequence: int = Field(ge=1)
    from_revision: int | None = Field(default=None, alias="fromRevision", ge=1)
    to_revision: int = Field(alias="toRevision", ge=1)
    from_state: InstallationState | None = Field(default=None, alias="fromState")
    to_state: InstallationState = Field(alias="toState")
    actor: str = Field(min_length=1, max_length=240)
    reason: str | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_INSTALLATION_REASON_LENGTH,
    )
    evidence: InstallationEventEvidence | None
    created_at: datetime = Field(alias="createdAt")

    @field_validator("actor")
    @classmethod
    def _normalized_actor(cls, value: str) -> str:
        return _normalized_text(value, label="event actor")

    @field_validator("reason")
    @classmethod
    def _normalized_optional_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalized_text(value, label="event reason")

    @field_validator("created_at")
    @classmethod
    def _created_at_has_timezone(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="createdAt")

    @model_validator(mode="after")
    def _from_fields_are_consistent(self) -> InstallationEvent:
        if (self.from_revision is None) != (self.from_state is None):
            raise ValueError("fromRevision and fromState must have the same null state")
        return self


class InstallationListItem(StrictContract):
    installation_id: str = Field(alias="installationId")
    display_name: str = Field(alias="displayName", min_length=1, max_length=240)
    state: InstallationState
    current_revision: int = Field(alias="currentRevision", ge=1)
    active_revision: int | None = Field(default=None, alias="activeRevision", ge=1)
    previous_active_revision: int | None = Field(
        default=None,
        alias="previousActiveRevision",
        ge=1,
    )
    etag_version: int = Field(alias="etagVersion", ge=1)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    @field_validator("installation_id")
    @classmethod
    def _valid_installation_id(cls, value: str) -> str:
        return _canonical_uuid(value, label="installationId")

    @field_validator("display_name")
    @classmethod
    def _normalized_display_name(cls, value: str) -> str:
        return _normalized_text(value, label="displayName")

    @field_validator("created_at", "updated_at")
    @classmethod
    def _timestamps_are_aware(cls, value: datetime) -> datetime:
        return _aware_datetime(value, label="installation timestamp")

    @model_validator(mode="after")
    def _pointers_and_timestamps_are_consistent(self) -> InstallationListItem:
        if self.updated_at < self.created_at:
            raise ValueError("updatedAt must not precede createdAt")
        if self.etag_version != self.current_revision:
            raise ValueError("etagVersion must equal currentRevision")
        for pointer_name in ("active_revision", "previous_active_revision"):
            pointer = getattr(self, pointer_name)
            if pointer is not None and pointer > self.current_revision:
                raise ValueError(
                    "installation revision pointer exceeds currentRevision"
                )
        pre_active_states = {
            "draft",
            "submitted",
            "approved",
            "rejected",
            "applied",
        }
        if self.state in pre_active_states and (
            self.active_revision is not None
            or self.previous_active_revision is not None
        ):
            raise ValueError("pre-active installation cannot expose active pointers")
        if self.state == "active" and self.active_revision != self.current_revision:
            raise ValueError("active installation must point at currentRevision")
        if (
            self.state == "active"
            and self.previous_active_revision is not None
            and self.previous_active_revision >= self.current_revision
        ):
            raise ValueError("active previousRevision must precede currentRevision")
        if self.state in ("rolled_back", "uninstalled"):
            if self.active_revision == self.current_revision:
                raise ValueError("rolled-back installation cannot keep current active")
            if self.active_revision != self.previous_active_revision:
                raise ValueError("rollback must restore previousActiveRevision")
        return self


class InstallationRecord(InstallationListItem):
    current: InstallationRevision
    decision: InstallationDecision | None
    events: list[InstallationEvent]

    @model_validator(mode="after")
    def _record_is_consistent(self) -> InstallationRecord:
        if self.current.installation_id != self.installation_id:
            raise ValueError("current revision belongs to another installation")
        if self.current.revision != self.current_revision:
            raise ValueError("current revision pointer is inconsistent")
        if self.current.state != self.state:
            raise ValueError("record state must be derived from current revision")
        if self.current.decision_id is None:
            if self.decision is not None:
                raise ValueError(
                    "record decision is not referenced by current revision"
                )
        elif (
            self.decision is None
            or self.decision.decision_id != self.current.decision_id
        ):
            raise ValueError("record decision must match current decisionId")

        if self.decision is not None:
            decision = self.decision
            if decision.installation_id != self.installation_id:
                raise ValueError("record decision belongs to another installation")
            if decision.submitted_revision >= self.current_revision:
                raise ValueError(
                    "decision must reference an earlier submitted revision"
                )
            current_hashes = (
                self.current.lock_hash,
                self.current.permission_diff_hash,
                self.current.migration_plan_hash,
                self.current.contribution_diff_hash,
            )
            decision_hashes = (
                decision.lock_hash,
                decision.permission_diff_hash,
                decision.migration_plan_hash,
                decision.contribution_diff_hash,
            )
            if decision_hashes != current_hashes:
                raise ValueError("record decision hashes must match current revision")
            if decision.actor == self.current.requested_by:
                raise ValueError("record decision violates duty separation")
            expected_decision = (
                "rejected" if self.current.state == "rejected" else "approved"
            )
            if decision.decision != expected_decision:
                raise ValueError("record decision is inconsistent with current state")

        object.__setattr__(
            self, "events", sorted(self.events, key=lambda item: item.sequence)
        )
        sequences = [item.sequence for item in self.events]
        if sequences != list(range(1, len(self.events) + 1)):
            raise ValueError(
                "installation event sequences must start at 1 and be continuous"
            )
        if not self.events:
            raise ValueError("installation record requires complete events")
        if len(self.events) != self.current_revision:
            raise ValueError("complete event count must equal currentRevision")
        first = self.events[0]
        if (
            first.from_revision is not None
            or first.from_state is not None
            or first.to_revision != 1
            or first.to_state != "draft"
        ):
            raise ValueError(
                "installation event history must begin with draft revision 1"
            )
        for previous, current in zip(self.events, self.events[1:]):
            if (
                current.from_revision != previous.to_revision
                or current.from_state != previous.to_state
                or current.to_revision != previous.to_revision + 1
            ):
                raise ValueError("installation event history is not continuous")
            if (
                previous.to_state,
                current.to_state,
            ) not in INSTALLATION_STATE_TRANSITIONS:
                raise ValueError(
                    "installation event contains an invalid state transition"
                )
        tail = self.events[-1]
        if (
            tail.to_revision != self.current_revision
            or tail.to_state != self.current.state
        ):
            raise ValueError("installation event tail must match current revision")
        if self.decision is not None:
            submitted_events = [
                item
                for item in self.events
                if item.to_revision == self.decision.submitted_revision
                and item.to_state == "submitted"
            ]
            if len(submitted_events) != 1:
                raise ValueError("decision must reference the submitted event")
        return self


class InstallationResponse(InstallationRecord):
    """Full detail/action response; HTTP ETag must match ``etagVersion``."""


class InstallationListResponse(StrictContract):
    items: list[InstallationListItem]
    total: int = Field(ge=0)
    limit: int = Field(default=50, ge=1, le=MAX_INSTALLATION_LIST_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_INSTALLATION_LIST_OFFSET)

    @model_validator(mode="after")
    def _items_are_sorted(self) -> InstallationListResponse:
        object.__setattr__(
            self,
            "items",
            sorted(
                self.items,
                key=lambda item: (-item.created_at.timestamp(), item.installation_id),
            ),
        )
        if len(self.items) > self.limit:
            raise ValueError("installation list contains more items than limit")
        return self


class InstallationListQuery(StrictContract):
    state: InstallationState | None = None
    limit: int = Field(default=50, ge=1, le=MAX_INSTALLATION_LIST_LIMIT)
    offset: int = Field(default=0, ge=0, le=MAX_INSTALLATION_LIST_OFFSET)
