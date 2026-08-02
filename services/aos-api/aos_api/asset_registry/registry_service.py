"""Pure service-layer policy for the canonical asset bundle registry."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    SHA256_PATTERN,
    BundleEvidence,
    BundleEvidenceStatus,
    BundleEvidenceType,
    BundleKind,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
    LoadedBundle,
)
from aos_api.asset_registry.errors import (
    BundleVersionImmutableError,
    DutySeparationRequiredError,
    ManifestInvalidError,
    SignatureInvalidError,
    VerificationFailedError,
    VersionInvalidError,
)
from aos_api.asset_registry.semver import SemVerError, parse_range, parse_version

CREATE_ROLES = frozenset({"admin", "asset-publisher", "developer"})
PUBLISH_ROLES = frozenset({"admin", "asset-publisher"})
REQUIRED_RELEASE_EVIDENCE = (
    BundleEvidenceType.MANIFEST_VALIDATION,
    BundleEvidenceType.CONTENT_HASH,
    BundleEvidenceType.SIGNATURE_VERIFICATION,
    BundleEvidenceType.SBOM,
    BundleEvidenceType.BUNDLE_EVALS,
)


class BundleLoader(Protocol):
    def load(self, source_ref: str) -> LoadedBundle: ...


class RegistryStore(Protocol):
    def list_bundles(self) -> list[dict[str, Any]]: ...

    def create_bundle(
        self,
        publisher: str,
        bundle_id: str,
        kind: BundleKind | str,
        display_name: str,
        created_by: str,
    ) -> dict[str, Any]: ...

    def get_bundle(
        self,
        bundle_id: str,
        publisher: str | None = None,
    ) -> dict[str, Any]: ...

    def create_version(
        self,
        loaded_bundle: LoadedBundle,
        created_by: str,
    ) -> dict[str, Any]: ...

    def get_version(
        self,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> dict[str, Any]: ...

    def transition_version(
        self,
        bundle_id: str,
        version: str,
        expected_statuses: Collection[BundleVersionStatus | str],
        target_status: BundleVersionStatus | str,
        actor: str,
        reason: str | None = None,
        *,
        publisher: str | None = None,
    ) -> dict[str, Any]: ...


class RegistryService:
    """Enforces registry roles, immutable snapshots, gates, and transitions."""

    def __init__(
        self,
        *,
        store: RegistryStore,
        loader: BundleLoader,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._loader = loader
        self._clock = clock or (lambda: datetime.now(UTC))

    def list_bundles(self) -> list[dict[str, Any]]:
        return self._store.list_bundles()

    def create_bundle(
        self,
        *,
        publisher: str,
        bundle_id: str,
        kind: BundleKind | str,
        display_name: str,
        actor: str,
        roles: Collection[str],
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        checked_publisher = _require_registry_id(publisher, label="publisher")
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_display_name = _require_exact_text(
            display_name,
            label="display name",
        )
        try:
            checked_kind = kind if isinstance(kind, BundleKind) else BundleKind(kind)
        except (TypeError, ValueError) as exc:
            raise ManifestInvalidError("bundle kind is invalid") from exc
        return self._store.create_bundle(
            publisher=checked_publisher,
            bundle_id=checked_bundle_id,
            kind=checked_kind,
            display_name=checked_display_name,
            created_by=actor,
        )

    def get_bundle(
        self,
        *,
        bundle_id: str,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_publisher = (
            _require_registry_id(publisher, label="publisher")
            if publisher is not None
            else None
        )
        return self._store.get_bundle(checked_bundle_id, checked_publisher)

    def create_version(
        self,
        *,
        bundle_id: str,
        source_ref: str,
        actor: str,
        roles: Collection[str],
        publisher: str | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_publisher = (
            _require_registry_id(publisher, label="publisher")
            if publisher is not None
            else None
        )
        target = self._store.get_bundle(checked_bundle_id, checked_publisher)
        loaded = self._loader.load(source_ref)
        _assert_loaded_bundle_matches_target(loaded, target)
        _validate_manifest_versions(loaded.manifest)
        return self._store.create_version(loaded, actor)

    def get_version(
        self,
        *,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_version = _require_version(version)
        checked_publisher = (
            _require_registry_id(publisher, label="publisher")
            if publisher is not None
            else None
        )
        return self._store.get_version(
            checked_bundle_id,
            checked_version,
            checked_publisher,
        )

    def validate(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        publisher: str | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        record = self._load_version_record(
            bundle_id=bundle_id,
            version=version,
            publisher=publisher,
        )
        _require_status(record.status, BundleVersionStatus.DRAFT, action="validate")
        _assert_release_gate(record, checked_at=_checked_now(self._clock))
        return self._store.transition_version(
            record.bundle_id,
            record.version,
            (BundleVersionStatus.DRAFT,),
            BundleVersionStatus.VALIDATED,
            actor,
            publisher=record.publisher,
        )

    def publish(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        publisher: str | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=PUBLISH_ROLES)
        record = self._load_version_record(
            bundle_id=bundle_id,
            version=version,
            publisher=publisher,
        )
        _require_status(record.status, BundleVersionStatus.VALIDATED, action="publish")
        _assert_release_gate(record, checked_at=_checked_now(self._clock))
        return self._store.transition_version(
            record.bundle_id,
            record.version,
            (BundleVersionStatus.VALIDATED,),
            BundleVersionStatus.PUBLISHED,
            actor,
            publisher=record.publisher,
        )

    def deprecate(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        reason: str | None = None,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        return self._terminal_transition(
            bundle_id=bundle_id,
            version=version,
            actor=actor,
            roles=roles,
            target=BundleVersionStatus.DEPRECATED,
            action="deprecate",
            reason=reason,
            publisher=publisher,
        )

    def revoke(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        reason: str | None = None,
        publisher: str | None = None,
    ) -> dict[str, Any]:
        return self._terminal_transition(
            bundle_id=bundle_id,
            version=version,
            actor=actor,
            roles=roles,
            target=BundleVersionStatus.REVOKED,
            action="revoke",
            reason=reason,
            publisher=publisher,
        )

    def _load_version_record(
        self,
        *,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> _VersionRecord:
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_version = _require_version(version)
        checked_publisher = (
            _require_registry_id(publisher, label="publisher")
            if publisher is not None
            else None
        )
        raw = self._store.get_version(
            checked_bundle_id,
            checked_version,
            checked_publisher,
        )
        return _VersionRecord.from_store(raw)

    def _terminal_transition(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        target: BundleVersionStatus,
        action: str,
        reason: str | None,
        publisher: str | None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=PUBLISH_ROLES)
        checked_reason = (
            _require_exact_text(reason, label="transition reason")
            if reason is not None
            else None
        )
        record = self._load_version_record(
            bundle_id=bundle_id,
            version=version,
            publisher=publisher,
        )
        _require_status(record.status, BundleVersionStatus.PUBLISHED, action=action)
        return self._store.transition_version(
            record.bundle_id,
            record.version,
            (BundleVersionStatus.PUBLISHED,),
            target,
            actor,
            checked_reason,
            publisher=record.publisher,
        )


class _VersionRecord:
    def __init__(
        self,
        *,
        bundle_id: str,
        publisher: str,
        kind: BundleKind,
        display_name: str,
        version: str,
        manifest: BundleManifest,
        content_hash: str,
        signature: BundleSignature | None,
        status: BundleVersionStatus,
        evidence: list[BundleEvidence],
    ) -> None:
        self.bundle_id = bundle_id
        self.publisher = publisher
        self.kind = kind
        self.display_name = display_name
        self.version = version
        self.manifest = manifest
        self.content_hash = content_hash
        self.signature = signature
        self.status = status
        self.evidence = evidence

    @classmethod
    def from_store(cls, raw: dict[str, Any]) -> _VersionRecord:
        try:
            bundle_id = _require_registry_id(raw["bundleId"], label="bundle id")
            publisher = _require_registry_id(raw["publisher"], label="publisher")
            display_name = _require_exact_text(
                raw["displayName"],
                label="display name",
            )
            kind = BundleKind(raw["kind"])
            version = _require_version(raw["version"])
            manifest = BundleManifest.model_validate(raw["manifest"])
            content_hash = raw["contentHash"]
            if not isinstance(content_hash, str) or re.fullmatch(
                SHA256_PATTERN,
                content_hash,
            ) is None:
                raise ValueError("content hash is invalid")
            status = BundleVersionStatus(raw["status"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ManifestInvalidError(
                "stored bundle version failed integrity validation"
            ) from exc

        try:
            signature = _parse_signature(raw["signature"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise SignatureInvalidError(
                "stored bundle signature failed integrity validation"
            ) from exc
        try:
            evidence = _parse_evidence(raw["evidence"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise VerificationFailedError(
                "stored bundle evidence failed integrity validation"
            ) from exc

        record = cls(
            bundle_id=bundle_id,
            publisher=publisher,
            kind=kind,
            display_name=display_name,
            version=version,
            manifest=manifest,
            content_hash=content_hash,
            signature=signature,
            status=status,
            evidence=evidence,
        )
        _assert_record_identity(record)
        _validate_manifest_versions(manifest)
        return record


def _parse_signature(raw: object) -> BundleSignature | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise TypeError("stored signature must be an object")
    return BundleSignature.model_validate_json(json.dumps(raw))


def _parse_evidence(raw: object) -> list[BundleEvidence]:
    if not isinstance(raw, list):
        raise TypeError("stored evidence must be an array")
    parsed: list[BundleEvidence] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("stored evidence entries must be objects")
        parsed.append(BundleEvidence.model_validate_json(json.dumps(item)))
    return parsed


def _assert_loaded_bundle_matches_target(
    loaded: LoadedBundle,
    target: dict[str, Any],
) -> None:
    try:
        target_bundle_id = target["bundleId"]
        target_publisher = target["publisher"]
        target_kind = BundleKind(target["kind"])
        target_display_name = target["displayName"]
    except (KeyError, TypeError, ValueError) as exc:
        raise ManifestInvalidError("target bundle failed integrity validation") from exc

    manifest = loaded.manifest
    if (
        manifest.metadata.id != target_bundle_id
        or manifest.metadata.publisher != target_publisher
        or manifest.kind != target_kind
        or manifest.metadata.display_name != target_display_name
    ):
        raise ManifestInvalidError(
            "manifest metadata does not match the target bundle"
        )


def _assert_record_identity(record: _VersionRecord) -> None:
    metadata = record.manifest.metadata
    if (
        metadata.id != record.bundle_id
        or metadata.publisher != record.publisher
        or metadata.version != record.version
        or metadata.display_name != record.display_name
        or record.manifest.kind != record.kind
    ):
        raise ManifestInvalidError(
            "stored manifest metadata does not match its bundle version"
        )


def _validate_manifest_versions(manifest: BundleManifest) -> None:
    fields = [("metadata.version", manifest.metadata.version)]
    ranges = [("spec.platformApi", manifest.spec.platform_api)]
    ranges.extend(
        (f"spec.dependencies[{index}].version", item.version)
        for index, item in enumerate(manifest.spec.dependencies)
    )
    ranges.extend(
        (f"spec.optionalDependencies[{index}].version", item.version)
        for index, item in enumerate(manifest.spec.optional_dependencies)
    )
    ranges.extend(
        (f"spec.conflicts[{index}].version", item.version)
        for index, item in enumerate(manifest.spec.conflicts)
        if item.version is not None
    )
    try:
        for field, value in fields:
            parse_version(value)
        for field, value in ranges:
            parse_range(value)
    except SemVerError as exc:
        raise VersionInvalidError(
            "bundle manifest contains an invalid semantic version",
            details={"field": field},
        ) from exc


def _assert_release_gate(record: _VersionRecord, *, checked_at: datetime) -> None:
    if record.signature is None:
        raise SignatureInvalidError("bundle signature is missing")

    by_type: dict[BundleEvidenceType, list[BundleEvidence]] = {}
    for evidence in record.evidence:
        by_type.setdefault(evidence.type, []).append(evidence)

    for evidence_type in REQUIRED_RELEASE_EVIDENCE:
        entries = by_type.get(evidence_type, [])
        is_valid = bool(entries) and all(
            _evidence_is_current(item, checked_at=checked_at) for item in entries
        )
        if evidence_type == BundleEvidenceType.CONTENT_HASH:
            is_valid = is_valid and all(
                item.artifact_hash == record.content_hash for item in entries
            )
        if not is_valid:
            _raise_evidence_gate_error(evidence_type)


def _evidence_is_current(
    evidence: BundleEvidence,
    *,
    checked_at: datetime,
) -> bool:
    return (
        evidence.status == BundleEvidenceStatus.VALID
        and evidence.observed_at <= checked_at
        and (evidence.expires_at is None or evidence.expires_at > checked_at)
        and evidence.revoked_at is None
    )


def _raise_evidence_gate_error(evidence_type: BundleEvidenceType) -> None:
    details = {"evidenceType": evidence_type.value}
    if evidence_type == BundleEvidenceType.SIGNATURE_VERIFICATION:
        raise SignatureInvalidError(
            "bundle signature evidence is not valid and current",
            details=details,
        )
    if evidence_type in {
        BundleEvidenceType.MANIFEST_VALIDATION,
        BundleEvidenceType.CONTENT_HASH,
    }:
        raise ManifestInvalidError(
            "bundle manifest or content hash evidence is not valid and current",
            details=details,
        )
    raise VerificationFailedError(
        "bundle release evidence is not valid and current",
        details=details,
    )


def _require_status(
    current: BundleVersionStatus,
    expected: BundleVersionStatus,
    *,
    action: str,
) -> None:
    if current != expected:
        raise BundleVersionImmutableError(
            f"bundle version cannot {action} from its current status",
            details={"currentStatus": current.value, "requiredStatus": expected.value},
        )


def _require_role(
    *,
    actor: str,
    roles: Collection[str],
    allowed: frozenset[str],
) -> None:
    if (
        not isinstance(actor, str)
        or not actor
        or actor != actor.strip()
        or "\x00" in actor
    ):
        raise DutySeparationRequiredError("registry actor must be normalized")
    if isinstance(roles, str) or not roles:
        raise DutySeparationRequiredError("an authorized registry role is required")
    if any(
        not isinstance(role, str) or not role or role != role.strip()
        for role in roles
    ):
        raise DutySeparationRequiredError("registry roles must be normalized")
    if not set(roles).intersection(allowed):
        raise DutySeparationRequiredError(
            "actor is not authorized for this registry transition",
            details={"actor": actor},
        )


def _require_registry_id(value: object, *, label: str) -> str:
    if not isinstance(value, str) or re.fullmatch(BUNDLE_ID_PATTERN, value) is None:
        raise ManifestInvalidError(f"{label} is invalid")
    return value


def _require_version(value: object) -> str:
    if not isinstance(value, str):
        raise VersionInvalidError("bundle version must be a string")
    try:
        parse_version(value)
    except SemVerError as exc:
        raise VersionInvalidError("bundle version is invalid") from exc
    return value


def _require_exact_text(value: object, *, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
    ):
        raise ManifestInvalidError(f"{label} is invalid")
    return value


def _checked_now(clock: Callable[[], datetime]) -> datetime:
    checked_at = clock()
    if not isinstance(checked_at, datetime) or checked_at.utcoffset() is None:
        raise VerificationFailedError("registry verification clock is invalid")
    return checked_at
