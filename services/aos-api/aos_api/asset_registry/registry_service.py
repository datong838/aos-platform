"""Pure service-layer policy for the canonical asset bundle registry."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
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
    TrustRootUnavailableError,
    VerificationFailedError,
    VersionInvalidError,
)
from aos_api.asset_registry.semver import SemVerError, parse_range, parse_version
from aos_api.asset_registry.signature import (
    TrustRoot,
    TrustRootProvider,
    verify_ed25519,
)

CREATE_ROLES = frozenset(
    {"admin", "asset-publisher", "asset-registry-admin", "developer"}
)
PUBLISH_ROLES = frozenset({"admin", "asset-publisher", "asset-registry-admin"})
REQUIRED_RELEASE_EVIDENCE = (
    BundleEvidenceType.MANIFEST_VALIDATION,
    BundleEvidenceType.CONTENT_HASH,
    BundleEvidenceType.SIGNATURE_VERIFICATION,
    BundleEvidenceType.SBOM,
    BundleEvidenceType.BUNDLE_EVALS,
)
LEGACY_EVIDENCE_REVISION = "sha256:" + "0" * 64


class BundleLoader(Protocol):
    @property
    def trust_roots(self) -> TrustRootProvider | None: ...

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
        precondition: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]: ...


class RegistryService:
    """Enforces registry roles, immutable snapshots, gates, and transitions."""

    def __init__(
        self,
        *,
        store: RegistryStore,
        loader: BundleLoader,
        clock: Callable[[], datetime] | None = None,
        trust_roots: TrustRootProvider | None = None,
    ) -> None:
        self._store = store
        self._loader = loader
        self._clock = clock or (lambda: datetime.now(UTC))
        self._trust_roots = trust_roots or getattr(loader, "trust_roots", None)

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
        publisher_scopes: Collection[str] | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        checked_publisher = _require_registry_id(publisher, label="publisher")
        _require_publisher_access(
            actor=actor,
            roles=roles,
            publisher_scopes=publisher_scopes,
            publisher=checked_publisher,
            allowed_roles=CREATE_ROLES,
        )
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
        publisher_scopes: Collection[str] | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_publisher = _require_write_publisher(publisher)
        _require_publisher_access(
            actor=actor,
            roles=roles,
            publisher_scopes=publisher_scopes,
            publisher=checked_publisher,
            allowed_roles=CREATE_ROLES,
        )
        target = self._store.get_bundle(checked_bundle_id, checked_publisher)
        loaded = self._loader.load(source_ref)
        _raise_for_trust_root_provider_outage(loaded)
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
        return _public_version_projection(
            self._store.get_version(
                checked_bundle_id,
                checked_version,
                checked_publisher,
            )
        )

    def validate(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        publisher: str | None = None,
        publisher_scopes: Collection[str] | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=CREATE_ROLES)
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_version = _require_version(version)
        checked_publisher = _require_write_publisher(publisher)
        _require_publisher_access(
            actor=actor,
            roles=roles,
            publisher_scopes=publisher_scopes,
            publisher=checked_publisher,
            allowed_roles=CREATE_ROLES,
        )
        return self._store.transition_version(
            checked_bundle_id,
            checked_version,
            (BundleVersionStatus.DRAFT,),
            BundleVersionStatus.VALIDATED,
            actor,
            publisher=checked_publisher,
            precondition=self._release_precondition(
                expected=BundleVersionStatus.DRAFT,
                action="validate",
                actor=actor,
                require_separation=False,
            ),
        )

    def publish(
        self,
        *,
        bundle_id: str,
        version: str,
        actor: str,
        roles: Collection[str],
        publisher: str | None = None,
        publisher_scopes: Collection[str] | None = None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=PUBLISH_ROLES)
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_version = _require_version(version)
        checked_publisher = _require_write_publisher(publisher)
        _require_publisher_access(
            actor=actor,
            roles=roles,
            publisher_scopes=publisher_scopes,
            publisher=checked_publisher,
            allowed_roles=PUBLISH_ROLES,
        )
        return self._store.transition_version(
            checked_bundle_id,
            checked_version,
            (BundleVersionStatus.VALIDATED,),
            BundleVersionStatus.PUBLISHED,
            actor,
            publisher=checked_publisher,
            precondition=self._release_precondition(
                expected=BundleVersionStatus.VALIDATED,
                action="publish",
                actor=actor,
                require_separation=True,
            ),
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
        publisher_scopes: Collection[str] | None = None,
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
            publisher_scopes=publisher_scopes,
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
        publisher_scopes: Collection[str] | None = None,
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
            publisher_scopes=publisher_scopes,
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
        publisher_scopes: Collection[str] | None,
    ) -> dict[str, Any]:
        _require_role(actor=actor, roles=roles, allowed=PUBLISH_ROLES)
        checked_reason = _require_exact_text(reason, label="transition reason")
        checked_bundle_id = _require_registry_id(bundle_id, label="bundle id")
        checked_version = _require_version(version)
        checked_publisher = _require_write_publisher(publisher)
        _require_publisher_access(
            actor=actor,
            roles=roles,
            publisher_scopes=publisher_scopes,
            publisher=checked_publisher,
            allowed_roles=PUBLISH_ROLES,
        )
        return self._store.transition_version(
            checked_bundle_id,
            checked_version,
            (BundleVersionStatus.PUBLISHED,),
            target,
            actor,
            checked_reason,
            publisher=checked_publisher,
            precondition=lambda raw: _require_status(
                _VersionRecord.from_store(raw).status,
                BundleVersionStatus.PUBLISHED,
                action=action,
            ),
        )

    def _release_precondition(
        self,
        *,
        expected: BundleVersionStatus,
        action: str,
        actor: str,
        require_separation: bool,
    ) -> Callable[[dict[str, Any]], None]:
        def check(raw: dict[str, Any]) -> None:
            record = _VersionRecord.from_store(raw)
            _require_status(record.status, expected, action=action)
            checked_at = _checked_now(self._clock)
            _probe_trust_root_provider(
                record,
                trust_roots=self._trust_roots,
            )
            _assert_release_gate(record, checked_at=checked_at)
            _assert_current_signature(
                record,
                checked_at=checked_at,
                trust_roots=self._trust_roots,
            )
            if require_separation:
                _assert_publish_duty_separation(record, actor=actor)

        return check


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
        artifacts: list[dict[str, Any]],
        created_by: str,
        lifecycle_events: list[dict[str, Any]],
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
        self.artifacts = artifacts
        self.created_by = created_by
        self.lifecycle_events = lifecycle_events

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
            if (
                not isinstance(content_hash, str)
                or re.fullmatch(
                    SHA256_PATTERN,
                    content_hash,
                )
                is None
            ):
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

        artifacts = _parse_artifacts(raw.get("artifacts"))
        lifecycle_events = _parse_lifecycle_events(raw.get("lifecycleEvents"))
        created_by = _require_exact_text(raw.get("createdBy"), label="created by")

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
            artifacts=artifacts,
            created_by=created_by,
            lifecycle_events=lifecycle_events,
        )
        _assert_record_identity(record)
        _validate_manifest_versions(manifest)
        return record


def _public_version_projection(raw: dict[str, Any]) -> dict[str, Any]:
    """Return globally readable Registry metadata without internal audit details."""

    projected = deepcopy(raw)
    evidence_rows = raw.get("evidence", [])
    projected["evidence"] = [
        {
            key: item[key]
            for key in (
                "type",
                "artifactHash",
                "status",
                "observedAt",
                "expiresAt",
                "revokedAt",
            )
            if key in item
        }
        for item in evidence_rows
        if isinstance(item, dict)
    ]
    event_rows = raw.get("lifecycleEvents", [])
    projected["lifecycleEvents"] = [
        {
            key: item[key]
            for key in (
                "sequence",
                "fromStatus",
                "toStatus",
                "evidenceRevision",
                "createdAt",
            )
            if key in item
        }
        for item in event_rows
        if isinstance(item, dict)
    ]
    return projected


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


def _parse_artifacts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ManifestInvalidError("stored bundle artifacts must be an array")
    parsed: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ManifestInvalidError("stored bundle artifact must be an object")
        try:
            relative_path = _require_exact_text(
                item["relativePath"], label="artifact relative path"
            )
            digest = item["digest"]
            size = item["size"]
            media_type = _require_exact_text(
                item["mediaType"], label="artifact media type"
            )
        except KeyError as exc:
            raise ManifestInvalidError("stored bundle artifact is incomplete") from exc
        if not isinstance(digest, str) or re.fullmatch(SHA256_PATTERN, digest) is None:
            raise ManifestInvalidError("stored bundle artifact digest is invalid")
        if type(size) is not int or size < 0:
            raise ManifestInvalidError("stored bundle artifact size is invalid")
        parsed.append(
            {
                "relativePath": relative_path,
                "digest": digest,
                "size": size,
                "mediaType": media_type,
            }
        )
    parsed.sort(key=lambda item: item["relativePath"])
    return parsed


def _parse_lifecycle_events(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ManifestInvalidError("stored lifecycle events must be an array")
    parsed: list[dict[str, Any]] = []
    previous = 0
    for item in raw:
        if not isinstance(item, dict):
            raise ManifestInvalidError("stored lifecycle event must be an object")
        try:
            sequence = item["sequence"]
            from_status = BundleVersionStatus(item["fromStatus"])
            to_status = BundleVersionStatus(item["toStatus"])
            actor = _require_exact_text(item["actor"], label="lifecycle actor")
            evidence_revision = item["evidenceRevision"]
            evidence_snapshot = item["evidenceSnapshot"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestInvalidError("stored lifecycle event is invalid") from exc
        if type(sequence) is not int or sequence != previous + 1:
            raise ManifestInvalidError("stored lifecycle event sequence is invalid")
        if (
            not isinstance(evidence_revision, str)
            or re.fullmatch(SHA256_PATTERN, evidence_revision) is None
            or (
                evidence_snapshot is not None
                and not isinstance(evidence_snapshot, list)
            )
        ):
            raise ManifestInvalidError("stored lifecycle evidence snapshot is invalid")
        if evidence_snapshot is not None:
            try:
                _parse_evidence(evidence_snapshot)
                snapshot_revision = canonical_sha256(evidence_snapshot)
            except (TypeError, ValueError, ValidationError) as exc:
                raise ManifestInvalidError(
                    "stored lifecycle evidence snapshot is invalid"
                ) from exc
            if snapshot_revision != evidence_revision:
                raise ManifestInvalidError(
                    "stored lifecycle evidence snapshot revision is invalid"
                )
        previous = sequence
        parsed.append(
            {
                "sequence": sequence,
                "fromStatus": from_status,
                "toStatus": to_status,
                "actor": actor,
                "evidenceRevision": evidence_revision,
                "evidenceSnapshot": deepcopy(evidence_snapshot),
            }
        )
    return parsed


def _raise_for_trust_root_provider_outage(loaded: LoadedBundle) -> None:
    for evidence in loaded.evidence:
        if (
            evidence.type == BundleEvidenceType.SIGNATURE_VERIFICATION
            and evidence.metadata.get("reason") == "trust_root_provider_unavailable"
        ):
            raise TrustRootUnavailableError(
                "publisher trust-root service is unavailable",
                details={"retryable": True},
            )


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
        raise ManifestInvalidError("manifest metadata does not match the target bundle")


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


class _SingleTrustRootProvider:
    def __init__(self, trust_root: TrustRoot) -> None:
        self._trust_root = trust_root

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        if (
            self._trust_root.publisher == publisher
            and self._trust_root.key_id == key_id
        ):
            return self._trust_root
        return None


def _probe_trust_root_provider(
    record: _VersionRecord,
    *,
    trust_roots: TrustRootProvider | None,
) -> None:
    if record.signature is None or trust_roots is None:
        return
    try:
        trust_roots.get_trust_root(
            publisher=record.publisher,
            key_id=record.signature.key_id,
        )
    except Exception as exc:
        raise TrustRootUnavailableError(
            "publisher trust-root service is unavailable",
            details={"retryable": True},
        ) from exc


def _assert_current_signature(
    record: _VersionRecord,
    *,
    checked_at: datetime,
    trust_roots: TrustRootProvider | None,
) -> None:
    if record.signature is None or trust_roots is None:
        raise SignatureInvalidError("publisher trust roots are unavailable")
    try:
        trust_root = trust_roots.get_trust_root(
            publisher=record.publisher,
            key_id=record.signature.key_id,
        )
    except Exception as exc:
        raise TrustRootUnavailableError(
            "publisher trust-root service is unavailable",
            details={"retryable": True},
        ) from exc
    if trust_root is None:
        raise SignatureInvalidError("publisher trust root is unavailable")
    trust_root_revision = getattr(trust_root, "revision", None)
    if (
        not isinstance(trust_root_revision, str)
        or not trust_root_revision
        or trust_root_revision != trust_root_revision.strip()
    ):
        raise SignatureInvalidError("publisher trust root revision is invalid")

    descriptor = {
        "manifest": record.manifest.model_dump(
            mode="json", by_alias=True, exclude_none=False
        ),
        "artifacts": record.artifacts,
    }
    if canonical_sha256(descriptor) != record.content_hash:
        raise ManifestInvalidError("stored bundle content descriptor changed")
    verified = verify_ed25519(
        payload=canonical_json(descriptor),
        signature_b64=record.signature.signature,
        publisher=record.publisher,
        key_id=record.signature.key_id,
        trust_roots=_SingleTrustRootProvider(trust_root),
        algorithm=record.signature.algorithm,
        verified_at=checked_at,
    )
    if not verified:
        raise SignatureInvalidError("bundle signature is not valid under current trust")

    signature_evidence = [
        item
        for item in record.evidence
        if item.type == BundleEvidenceType.SIGNATURE_VERIFICATION
    ]
    if len(signature_evidence) != 1:
        raise SignatureInvalidError("bundle signature evidence must be unique")
    evidence = signature_evidence[0]
    signature_envelope_hash = canonical_sha256(
        record.signature.model_dump(mode="json", by_alias=True, exclude_none=False)
    )
    if evidence.artifact_hash != signature_envelope_hash:
        raise SignatureInvalidError("bundle signature evidence does not match envelope")
    if evidence.metadata.get("trustRootRevision") != trust_root_revision:
        raise SignatureInvalidError("bundle signature evidence trust root is stale")
    if evidence.expires_at != trust_root.not_after:
        raise SignatureInvalidError("bundle signature evidence expiry is inconsistent")


def _assert_publish_duty_separation(
    record: _VersionRecord,
    *,
    actor: str,
) -> None:
    validated_actors = [
        event["actor"]
        for event in record.lifecycle_events
        if event["toStatus"] == BundleVersionStatus.VALIDATED
    ]
    if len(validated_actors) != 1:
        raise DutySeparationRequiredError(
            "published bundle requires one persisted validation event"
        )
    if actor in {record.created_by, validated_actors[0]}:
        raise DutySeparationRequiredError(
            "bundle publisher must differ from creator and validator",
            details={"actor": actor},
        )


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
        not isinstance(role, str) or not role or role != role.strip() for role in roles
    ):
        raise DutySeparationRequiredError("registry roles must be normalized")
    if not set(roles).intersection(allowed):
        raise DutySeparationRequiredError(
            "actor is not authorized for this registry transition",
            details={"actor": actor},
        )


def _require_publisher_access(
    *,
    actor: str,
    roles: Collection[str],
    publisher_scopes: Collection[str] | None,
    publisher: str,
    allowed_roles: frozenset[str],
) -> None:
    _require_role(actor=actor, roles=roles, allowed=allowed_roles)
    if (
        publisher_scopes is None
        or isinstance(publisher_scopes, (str, bytes))
        or not publisher_scopes
    ):
        raise DutySeparationRequiredError(
            "an authorized publisher scope is required",
            details={"actor": actor, "publisher": publisher},
        )
    normalized: set[str] = set()
    for scope in publisher_scopes:
        if scope == "*":
            normalized.add(scope)
            continue
        normalized.add(_require_registry_id(scope, label="publisher scope"))
    role_set = set(roles)
    if publisher in normalized:
        return
    if "asset-registry-admin" in role_set and "*" in normalized:
        return
    raise DutySeparationRequiredError(
        "actor is not authorized for the target publisher",
        details={"actor": actor, "publisher": publisher},
    )


def _require_write_publisher(publisher: object) -> str:
    if publisher is None:
        raise ManifestInvalidError("publisher is required for registry writes")
    return _require_registry_id(publisher, label="publisher")


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
