"""Atomic PostgreSQL persistence for the canonical asset bundle registry."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable, Collection
from contextlib import AbstractContextManager
from copy import deepcopy
from datetime import datetime
from typing import Any, ClassVar, Protocol

from psycopg import errors
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.contracts import (
    BUNDLE_ID_PATTERN,
    MAX_BUNDLE_ID_LENGTH,
    BundleEvidence,
    BundleKind,
    BundleVersionStatus,
    LoadedBundle,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    BundleVersionImmutableError,
    ManifestInvalidError,
    RevisionConflictError,
    VersionInvalidError,
)
from aos_api.db import connect

JsonRecord = dict[str, Any]
ConnectFactory = Callable[[], AbstractContextManager[Any]]
TransitionPrecondition = Callable[[JsonRecord], None]
LEGACY_EVIDENCE_REVISION = "sha256:" + "0" * 64


class RegistryStore(Protocol):
    """Transport-neutral persistence boundary used by the Registry service."""

    def list_bundles(self) -> list[JsonRecord]: ...

    def create_bundle(
        self,
        publisher: str,
        bundle_id: str,
        kind: BundleKind | str,
        display_name: str,
        created_by: str,
    ) -> JsonRecord: ...

    def get_bundle(
        self, bundle_id: str, publisher: str | None = None
    ) -> JsonRecord: ...

    def create_version(
        self, loaded_bundle: LoadedBundle, created_by: str
    ) -> JsonRecord: ...

    def get_version(
        self,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> JsonRecord: ...

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
        precondition: TransitionPrecondition | None = None,
    ) -> JsonRecord: ...


class PostgresRegistryStore:
    """Registry store whose multi-table writes commit or roll back together."""

    _ALLOWED_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        BundleVersionStatus.DRAFT.value: frozenset(
            {
                BundleVersionStatus.VALIDATED.value,
                BundleVersionStatus.REJECTED.value,
            }
        ),
        BundleVersionStatus.VALIDATED.value: frozenset(
            {
                BundleVersionStatus.PUBLISHED.value,
                BundleVersionStatus.REJECTED.value,
            }
        ),
        BundleVersionStatus.PUBLISHED.value: frozenset(
            {
                BundleVersionStatus.DEPRECATED.value,
                BundleVersionStatus.REVOKED.value,
            }
        ),
    }

    def __init__(self, connect_factory: ConnectFactory = connect) -> None:
        self._connect_factory = connect_factory

    def list_bundles(self) -> list[JsonRecord]:
        with self._connect_factory() as conn:
            rows = conn.execute(
                """
                SELECT publisher, bundle_id, kind, display_name, created_at
                  FROM asset_bundle
                 ORDER BY publisher ASC, bundle_id ASC
                """
            ).fetchall()
        return [self._bundle_record(row) for row in rows]

    def create_bundle(
        self,
        publisher: str,
        bundle_id: str,
        kind: BundleKind | str,
        display_name: str,
        created_by: str,
    ) -> JsonRecord:
        publisher = self._require_text(publisher, "publisher")
        bundle_id = self._require_text(bundle_id, "bundle_id")
        display_name = self._require_text(display_name, "display_name")
        self._require_text(created_by, "created_by")
        self._require_bundle_id(publisher, "publisher", max_length=120)
        self._require_bundle_id(bundle_id, "bundle_id", max_length=MAX_BUNDLE_ID_LENGTH)
        if len(display_name) > 240:
            raise ManifestInvalidError("display_name exceeds the contract limit")
        try:
            kind_value = BundleKind(self._enum_value(kind)).value
        except ValueError as exc:
            raise ManifestInvalidError("asset bundle kind is invalid") from exc
        try:
            with self._connect_factory() as conn:
                row = conn.execute(
                    """
                    INSERT INTO asset_bundle (
                      bundle_pk, publisher, bundle_id, kind, display_name
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING publisher, bundle_id, kind, display_name, created_at
                    """,
                    (uuid.uuid4(), publisher, bundle_id, kind_value, display_name),
                ).fetchone()
                conn.commit()
        except errors.UniqueViolation as exc:
            raise RevisionConflictError(
                "asset bundle already exists",
                details={"publisher": publisher, "bundleId": bundle_id},
            ) from exc
        except errors.CheckViolation as exc:
            raise ManifestInvalidError(
                "asset bundle identity violates registry constraints"
            ) from exc
        assert row is not None
        return self._bundle_record(row)

    def get_bundle(self, bundle_id: str, publisher: str | None = None) -> JsonRecord:
        bundle_id = self._require_text(bundle_id, "bundle_id")
        publisher = self._optional_text(publisher, "publisher")
        with self._connect_factory() as conn:
            bundle = self._resolve_bundle(conn, bundle_id, publisher)
            versions = conn.execute(
                """
                SELECT version, content_hash, signature, status, created_by,
                       created_at, updated_at
                  FROM asset_bundle_version
                 WHERE bundle_pk = %s
                 ORDER BY created_at DESC, version DESC
                """,
                (bundle["bundle_pk"],),
            ).fetchall()
        record = self._bundle_record(bundle)
        record["versions"] = [self._version_summary(row) for row in versions]
        return record

    def create_version(
        self, loaded_bundle: LoadedBundle, created_by: str
    ) -> JsonRecord:
        loaded = LoadedBundle.model_validate(loaded_bundle)
        created_by = self._require_text(created_by, "created_by")
        metadata = loaded.manifest.metadata
        version_pk = uuid.uuid4()
        try:
            with self._connect_factory() as conn:
                # Child projection statements take the same transaction lock
                # before acquiring tuple locks.  This keeps direct SQL writers
                # and publish on one lock order and prevents deadlocks/phantoms.
                conn.execute("SELECT pg_advisory_xact_lock(228, 1)")
                bundle = self._resolve_bundle(
                    conn, metadata.id, metadata.publisher, for_update=True
                )
                if (
                    str(bundle["kind"]) != loaded.manifest.kind.value
                    or str(bundle["display_name"]) != metadata.display_name
                ):
                    raise ManifestInvalidError(
                        "loaded bundle metadata does not match its registry identity",
                        details={
                            "publisher": metadata.publisher,
                            "bundleId": metadata.id,
                        },
                    )

                conn.execute(
                    """
                    INSERT INTO asset_bundle_version (
                      version_pk, bundle_pk, version, manifest_json, content_hash,
                      signature, status, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s)
                    """,
                    (
                        version_pk,
                        bundle["bundle_pk"],
                        metadata.version,
                        Jsonb(loaded.manifest.model_dump(mode="json", by_alias=True)),
                        loaded.content_hash,
                        (
                            Jsonb(
                                loaded.signature.model_dump(mode="json", by_alias=True)
                            )
                            if loaded.signature is not None
                            else None
                        ),
                        created_by,
                    ),
                )
                self._insert_dependencies(conn, version_pk, loaded)
                self._insert_artifacts(conn, version_pk, loaded)
                self._insert_evidence(conn, version_pk, loaded, created_by)
                record = self._load_version(conn, bundle, metadata.version)
                conn.commit()
                return record
        except (AssetNotFoundError, ManifestInvalidError):
            raise
        except errors.UniqueViolation as exc:
            raise RevisionConflictError(
                "asset bundle version already exists",
                details={
                    "publisher": metadata.publisher,
                    "bundleId": metadata.id,
                    "version": metadata.version,
                },
            ) from exc
        except errors.CheckViolation as exc:
            raise VersionInvalidError(
                "asset bundle version violates registry constraints"
            ) from exc

    def get_version(
        self,
        bundle_id: str,
        version: str,
        publisher: str | None = None,
    ) -> JsonRecord:
        bundle_id = self._require_text(bundle_id, "bundle_id")
        version = self._require_text(version, "version")
        publisher = self._optional_text(publisher, "publisher")
        with self._connect_factory() as conn:
            bundle = self._resolve_bundle(conn, bundle_id, publisher)
            return self._load_version(conn, bundle, version)

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
        precondition: TransitionPrecondition | None = None,
    ) -> JsonRecord:
        bundle_id = self._require_text(bundle_id, "bundle_id")
        version = self._require_text(version, "version")
        actor = self._require_text(actor, "actor")
        self._optional_text(reason, "reason")
        publisher = self._optional_text(publisher, "publisher")
        expected = self._status_values(expected_statuses)
        target = self._status_value(target_status)

        try:
            with self._connect_factory() as conn:
                conn.execute("SELECT pg_advisory_xact_lock(228, 1)")
                bundle = self._resolve_bundle(
                    conn, bundle_id, publisher, for_update=True
                )
                current = conn.execute(
                    """
                    SELECT version_pk, status
                      FROM asset_bundle_version
                     WHERE bundle_pk = %s AND version = %s
                     FOR UPDATE
                    """,
                    (bundle["bundle_pk"], version),
                ).fetchone()
                if current is None:
                    raise AssetNotFoundError("asset bundle version not found")
                current_status = str(current["status"])
                if current_status not in expected:
                    raise RevisionConflictError(
                        "asset bundle version status changed",
                        details={
                            "expectedStatuses": sorted(expected),
                            "currentStatus": current_status,
                        },
                    )
                if target not in self._ALLOWED_TRANSITIONS.get(current_status, ()):
                    raise VersionInvalidError(
                        "asset bundle version status transition is not allowed",
                        details={
                            "currentStatus": current_status,
                            "targetStatus": target,
                        },
                    )
                version_pk = current["version_pk"]
                # Lock every release-gate projection before evaluating the
                # precondition.  The callback and state update therefore see
                # one indivisible database snapshot.
                for table in (
                    "asset_bundle_dependency",
                    "asset_bundle_artifact",
                    "asset_bundle_evidence",
                ):
                    conn.execute(
                        f"SELECT 1 FROM {table} WHERE version_pk = %s FOR UPDATE",
                        (version_pk,),
                    ).fetchall()
                locked_record = self._load_version(conn, bundle, version)
                if precondition is not None:
                    precondition(deepcopy(locked_record))
                evidence_snapshot = self._load_evidence_snapshot(conn, version_pk)
                evidence_revision = canonical_sha256(evidence_snapshot)
                updated = conn.execute(
                    """
                    UPDATE asset_bundle_version
                       SET status = %s, updated_at = NOW()
                     WHERE bundle_pk = %s AND version = %s
                       AND status = ANY(%s)
                    RETURNING version_pk
                    """,
                    (target, bundle["bundle_pk"], version, list(expected)),
                ).fetchone()
                if updated is None:
                    raise RevisionConflictError(
                        "asset bundle version status changed",
                        details={"expectedStatuses": sorted(expected)},
                    )
                sequence_row = conn.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence
                      FROM asset_bundle_version_event
                     WHERE version_pk = %s
                    """,
                    (version_pk,),
                ).fetchone()
                assert sequence_row is not None
                conn.execute(
                    """
                    INSERT INTO asset_bundle_version_event (
                      event_pk, version_pk, sequence, from_status, to_status,
                      actor, reason, evidence_revision, evidence_snapshot
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid.uuid4(),
                        version_pk,
                        int(sequence_row["next_sequence"]),
                        current_status,
                        target,
                        actor,
                        reason,
                        evidence_revision,
                        Jsonb(evidence_snapshot),
                    ),
                )
                record = self._load_version(conn, bundle, version)
                conn.commit()
                return record
        except (
            AssetNotFoundError,
            RevisionConflictError,
            VersionInvalidError,
        ):
            raise
        except (errors.DeadlockDetected, errors.SerializationFailure) as exc:
            raise RevisionConflictError(
                "asset bundle transition conflicted with a concurrent writer",
                details={"retryable": True},
            ) from exc
        except errors.CheckViolation as exc:
            message = str(exc.diag.message_primary or "")
            if "immutable" in message or "cannot be" in message:
                raise BundleVersionImmutableError(
                    "published asset bundle version is immutable"
                ) from exc
            raise VersionInvalidError(
                "asset bundle version status transition violates registry constraints"
            ) from exc

    @classmethod
    def _insert_dependencies(
        cls, conn: Any, version_pk: uuid.UUID, loaded: LoadedBundle
    ) -> None:
        groups = (
            (False, loaded.manifest.spec.dependencies),
            (True, loaded.manifest.spec.optional_dependencies),
        )
        for optional, dependencies in groups:
            for ordinal, dependency in enumerate(dependencies):
                conn.execute(
                    """
                    INSERT INTO asset_bundle_dependency (
                      version_pk, dependency_publisher, dependency_id,
                      version_range, optional, ordinal
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        version_pk,
                        dependency.publisher,
                        dependency.id,
                        dependency.version,
                        optional,
                        ordinal,
                    ),
                )

    @classmethod
    def _insert_artifacts(
        cls, conn: Any, version_pk: uuid.UUID, loaded: LoadedBundle
    ) -> None:
        for artifact in loaded.artifacts:
            conn.execute(
                """
                INSERT INTO asset_bundle_artifact (
                  version_pk, relative_path, artifact_ref, digest, size, media_type
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    version_pk,
                    artifact.relative_path,
                    artifact.artifact_ref,
                    artifact.digest,
                    artifact.size,
                    artifact.media_type,
                ),
            )

    @classmethod
    def _insert_evidence(
        cls,
        conn: Any,
        version_pk: uuid.UUID,
        loaded: LoadedBundle,
        created_by: str,
    ) -> None:
        for evidence in loaded.evidence:
            conn.execute(
                """
                INSERT INTO asset_bundle_evidence (
                  version_pk, evidence_type, artifact_ref, artifact_hash, status,
                  observed_at, expires_at, revoked_at, metadata, updated_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    version_pk,
                    evidence.type.value,
                    evidence.artifact_ref,
                    evidence.artifact_hash,
                    evidence.status.value,
                    evidence.observed_at,
                    evidence.expires_at,
                    evidence.revoked_at,
                    Jsonb(evidence.metadata),
                    created_by,
                ),
            )

    def _load_version(self, conn: Any, bundle: Any, version: str) -> JsonRecord:
        row = conn.execute(
            """
            SELECT version_pk, version, manifest_json, content_hash, signature,
                   status, created_by, created_at, updated_at
              FROM asset_bundle_version
             WHERE bundle_pk = %s AND version = %s
            """,
            (bundle["bundle_pk"], version),
        ).fetchone()
        if row is None:
            raise AssetNotFoundError("asset bundle version not found")
        version_pk = row["version_pk"]
        dependencies = conn.execute(
            """
            SELECT dependency_publisher, dependency_id, version_range,
                   optional, ordinal
              FROM asset_bundle_dependency
             WHERE version_pk = %s
             ORDER BY optional ASC, ordinal ASC
            """,
            (version_pk,),
        ).fetchall()
        artifacts = conn.execute(
            """
            SELECT relative_path, artifact_ref, digest, size, media_type
              FROM asset_bundle_artifact
             WHERE version_pk = %s
             ORDER BY relative_path ASC
            """,
            (version_pk,),
        ).fetchall()
        evidence = conn.execute(
            """
            SELECT evidence_type, artifact_ref, artifact_hash, status,
                   observed_at, expires_at, revoked_at, metadata
              FROM asset_bundle_evidence
             WHERE version_pk = %s
             ORDER BY evidence_type ASC, artifact_ref ASC
            """,
            (version_pk,),
        ).fetchall()
        events = conn.execute(
            """
            SELECT sequence, from_status, to_status, actor, reason,
                   evidence_revision, evidence_snapshot, created_at
              FROM asset_bundle_version_event
             WHERE version_pk = %s
             ORDER BY sequence ASC
            """,
            (version_pk,),
        ).fetchall()
        return {
            "publisher": str(bundle["publisher"]),
            "bundleId": str(bundle["bundle_id"]),
            "kind": str(bundle["kind"]),
            "displayName": str(bundle["display_name"]),
            "version": str(row["version"]),
            "manifest": dict(row["manifest_json"]),
            "contentHash": str(row["content_hash"]),
            "signature": dict(row["signature"]) if row["signature"] else None,
            "status": str(row["status"]),
            "createdBy": str(row["created_by"]),
            "createdAt": self._timestamp(row["created_at"]),
            "updatedAt": self._timestamp(row["updated_at"]),
            "dependencies": [
                {
                    "publisher": item["dependency_publisher"],
                    "id": str(item["dependency_id"]),
                    "versionRange": str(item["version_range"]),
                    "optional": bool(item["optional"]),
                    "ordinal": int(item["ordinal"]),
                }
                for item in dependencies
            ],
            "artifacts": [
                {
                    "relativePath": str(item["relative_path"]),
                    "artifactRef": str(item["artifact_ref"]),
                    "digest": str(item["digest"]),
                    "size": int(item["size"]),
                    "mediaType": str(item["media_type"]),
                }
                for item in artifacts
            ],
            "evidence": [
                {
                    "type": str(item["evidence_type"]),
                    "artifactRef": str(item["artifact_ref"]),
                    "artifactHash": str(item["artifact_hash"]),
                    "status": str(item["status"]),
                    "observedAt": self._evidence_timestamp(item["observed_at"]),
                    "expiresAt": self._optional_evidence_timestamp(item["expires_at"]),
                    "revokedAt": self._optional_evidence_timestamp(item["revoked_at"]),
                    "metadata": dict(item["metadata"] or {}),
                }
                for item in evidence
            ],
            "lifecycleEvents": [self._event_record(item) for item in events],
        }

    @classmethod
    def _event_record(cls, row: Any) -> JsonRecord:
        actor = str(row["actor"])
        evidence_revision = str(row["evidence_revision"])
        raw_snapshot = row["evidence_snapshot"]
        snapshot = list(raw_snapshot) if raw_snapshot is not None else None
        if snapshot is not None:
            try:
                normalized = [
                    BundleEvidence.model_validate_json(json.dumps(item)).model_dump(
                        mode="json", by_alias=True, exclude_none=False
                    )
                    for item in snapshot
                ]
            except (TypeError, ValueError) as exc:
                raise ManifestInvalidError(
                    "asset lifecycle evidence snapshot is invalid"
                ) from exc
            identity = [(item["type"], item["artifactRef"]) for item in normalized]
            if (
                identity != sorted(identity)
                or len(identity) != len(set(identity))
                or canonical_sha256(snapshot) != evidence_revision
            ):
                raise ManifestInvalidError(
                    "asset lifecycle evidence snapshot failed integrity validation"
                )
        return {
            "sequence": int(row["sequence"]),
            "fromStatus": str(row["from_status"]),
            "toStatus": str(row["to_status"]),
            "actor": actor,
            "reason": row["reason"],
            "evidenceRevision": evidence_revision,
            "evidenceSnapshot": snapshot,
            "createdAt": cls._timestamp(row["created_at"]),
        }

    @staticmethod
    def _load_evidence_snapshot(conn: Any, version_pk: uuid.UUID) -> list[JsonRecord]:
        row = conn.execute(
            """
            SELECT COALESCE(
                     jsonb_agg(
                       jsonb_build_object(
                         'type', evidence_type,
                         'artifactRef', artifact_ref,
                         'artifactHash', artifact_hash,
                         'status', status,
                         'observedAt', observed_at,
                         'expiresAt', expires_at,
                         'revokedAt', revoked_at,
                         'metadata', metadata
                       )
                       ORDER BY evidence_type, artifact_ref
                     ),
                     '[]'::JSONB
                   ) AS evidence_snapshot
              FROM asset_bundle_evidence
             WHERE version_pk = %s
            """,
            (version_pk,),
        ).fetchone()
        assert row is not None
        return list(row["evidence_snapshot"])

    @staticmethod
    def _resolve_bundle(
        conn: Any,
        bundle_id: str,
        publisher: str | None,
        *,
        for_update: bool = False,
    ) -> Any:
        lock_clause = " FOR UPDATE" if for_update else ""
        if publisher is None:
            rows = conn.execute(
                """
                SELECT bundle_pk, publisher, bundle_id, kind, display_name, created_at
                  FROM asset_bundle
                 WHERE bundle_id = %s
                 ORDER BY publisher ASC
                 LIMIT 2
                """
                + lock_clause,
                (bundle_id,),
            ).fetchall()
            if len(rows) > 1:
                raise RevisionConflictError(
                    "bundle id is ambiguous without publisher",
                    details={"bundleId": bundle_id},
                )
        else:
            rows = conn.execute(
                """
                SELECT bundle_pk, publisher, bundle_id, kind, display_name, created_at
                  FROM asset_bundle
                 WHERE bundle_id = %s AND publisher = %s
                 LIMIT 1
                """
                + lock_clause,
                (bundle_id, publisher),
            ).fetchall()
        if not rows:
            raise AssetNotFoundError("asset bundle not found")
        return rows[0]

    @classmethod
    def _status_values(
        cls, statuses: Collection[BundleVersionStatus | str]
    ) -> frozenset[str]:
        if isinstance(statuses, (str, bytes)) or not statuses:
            raise ValueError("expected_statuses must be a non-empty collection")
        return frozenset(cls._status_value(status) for status in statuses)

    @staticmethod
    def _status_value(status: BundleVersionStatus | str) -> str:
        raw = PostgresRegistryStore._enum_value(status)
        try:
            return BundleVersionStatus(raw).value
        except ValueError as exc:
            raise VersionInvalidError("asset bundle version status is invalid") from exc

    @staticmethod
    def _enum_value(value: Any) -> str:
        raw = value.value if hasattr(value, "value") else value
        if not isinstance(raw, str):
            raise TypeError("enum value must be a string")
        return raw

    @staticmethod
    def _require_text(value: str, label: str) -> str:
        if not isinstance(value, str) or not value or value != value.strip():
            raise ValueError(f"{label} must be non-blank and normalized")
        return value

    @staticmethod
    def _require_bundle_id(value: str, label: str, *, max_length: int) -> None:
        if len(value) > max_length or re.fullmatch(BUNDLE_ID_PATTERN, value) is None:
            raise ManifestInvalidError(f"{label} violates the bundle identity contract")

    @classmethod
    def _optional_text(cls, value: str | None, label: str) -> str | None:
        if value is None:
            return None
        return cls._require_text(value, label)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.isoformat()

    @classmethod
    def _optional_timestamp(cls, value: datetime | None) -> str | None:
        return cls._timestamp(value) if value is not None else None

    @staticmethod
    def _evidence_timestamp(value: datetime) -> str:
        """Match PostgreSQL JSON timestamptz fractional-second rendering."""
        if value.microsecond == 0:
            return value.isoformat(timespec="seconds")
        fraction = f"{value.microsecond:06d}"
        marker = f".{fraction}"
        prefix, suffix = value.isoformat(timespec="microseconds").split(marker, 1)
        return f"{prefix}.{fraction.rstrip('0')}{suffix}"

    @classmethod
    def _optional_evidence_timestamp(cls, value: datetime | None) -> str | None:
        return cls._evidence_timestamp(value) if value is not None else None

    @classmethod
    def _bundle_record(cls, row: Any) -> JsonRecord:
        return {
            "publisher": str(row["publisher"]),
            "bundleId": str(row["bundle_id"]),
            "kind": str(row["kind"]),
            "displayName": str(row["display_name"]),
            "createdAt": cls._timestamp(row["created_at"]),
        }

    @classmethod
    def _version_summary(cls, row: Any) -> JsonRecord:
        return {
            "version": str(row["version"]),
            "contentHash": str(row["content_hash"]),
            "signature": dict(row["signature"]) if row["signature"] else None,
            "status": str(row["status"]),
            "createdBy": str(row["created_by"]),
            "createdAt": cls._timestamp(row["created_at"]),
            "updatedAt": cls._timestamp(row["updated_at"]),
        }
