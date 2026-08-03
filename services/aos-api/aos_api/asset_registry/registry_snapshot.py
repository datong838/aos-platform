"""One-transaction PostgreSQL reader for deterministic Registry snapshots."""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from psycopg import Error as PsycopgError
from pydantic import ValidationError

from aos_api.asset_registry.composition_contracts import (
    MAX_SNAPSHOT_CANDIDATES,
    RegistrySnapshot,
    RegistrySnapshotCandidate,
)
from aos_api.asset_registry.contracts import (
    BundleEvidence,
    BundleKind,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
)
from aos_api.asset_registry.errors import (
    AssetRegistryError,
    ManifestInvalidError,
    ResolutionLimitExceededError,
    SignatureInvalidError,
    VerificationFailedError,
)
from aos_api.asset_registry.release_policy import (
    REQUIRED_RELEASE_EVIDENCE,
    ReleasePolicy,
)
from aos_api.db import connect

ConnectFactory = Callable[[], AbstractContextManager[Any]]
TransactionClock = Callable[[Any], datetime]


@dataclass(frozen=True)
class _SnapshotVersionRecord:
    publisher: str
    manifest: BundleManifest
    content_hash: str
    signature: BundleSignature | None
    status: BundleVersionStatus
    evidence: list[BundleEvidence]
    artifacts: list[dict[str, object]]


class RegistrySnapshotReader:
    """Build a complete snapshot from one repeatable-read, read-only transaction."""

    def __init__(
        self,
        *,
        release_policy: ReleasePolicy,
        connect_factory: ConnectFactory = connect,
        clock: TransactionClock | None = None,
    ) -> None:
        self._release_policy = release_policy
        self._connect_factory = connect_factory
        self._clock = clock or _transaction_timestamp

    def read(self) -> RegistrySnapshot:
        """Return all currently eligible published candidates or fail atomically."""

        try:
            with self._connect_factory() as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                checked_at = self._clock(conn)
                if (
                    not isinstance(checked_at, datetime)
                    or checked_at.utcoffset() is None
                ):
                    raise VerificationFailedError(
                        "registry snapshot transaction clock is invalid"
                    )
                rows = conn.execute(
                    _SNAPSHOT_QUERY,
                    (
                        [item.value for item in REQUIRED_RELEASE_EVIDENCE],
                        MAX_SNAPSHOT_CANDIDATES + 1,
                    ),
                ).fetchall()
                if len(rows) > MAX_SNAPSHOT_CANDIDATES:
                    raise ResolutionLimitExceededError(
                        "registry snapshot candidate limit exceeded",
                        details={
                            "resource": "snapshot_candidates",
                            "limit": MAX_SNAPSHOT_CANDIDATES,
                            "observed": len(rows),
                        },
                    )
                candidates = [
                    self._candidate_from_row(row, checked_at=checked_at) for row in rows
                ]
                try:
                    return RegistrySnapshot.build(
                        candidates=candidates,
                        checked_at=checked_at,
                    )
                except (TypeError, ValueError, ValidationError) as exc:
                    raise ManifestInvalidError(
                        "Registry snapshot failed integrity validation"
                    ) from exc
        except AssetRegistryError:
            raise
        except PsycopgError as exc:
            raise VerificationFailedError(
                "registry snapshot could not be read"
            ) from exc

    def _candidate_from_row(
        self,
        row: Any,
        *,
        checked_at: datetime,
    ) -> RegistrySnapshotCandidate:
        try:
            manifest = BundleManifest.model_validate(row["manifest_json"])
            artifacts = _parse_artifacts(row["artifacts"])
            status = BundleVersionStatus(row["status"])
            kind = BundleKind(row["kind"])
            publisher = str(row["publisher"])
            bundle_id = str(row["bundle_id"])
            version = str(row["version"])
            content_hash = str(row["content_hash"])
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise ManifestInvalidError(
                "stored Registry snapshot candidate failed integrity validation"
            ) from exc
        try:
            signature = (
                BundleSignature.model_validate_json(json.dumps(row["signature"]))
                if row["signature"] is not None
                else None
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise SignatureInvalidError(
                "stored Registry snapshot signature failed integrity validation"
            ) from exc
        try:
            evidence = [
                BundleEvidence.model_validate_json(json.dumps(item))
                for item in row["evidence"]
            ]
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise VerificationFailedError(
                "stored Registry snapshot evidence failed integrity validation"
            ) from exc

        record = _SnapshotVersionRecord(
            publisher=publisher,
            manifest=manifest,
            content_hash=content_hash,
            signature=signature,
            status=status,
            evidence=evidence,
            artifacts=artifacts,
        )
        release = self._release_policy.evaluate(
            record,
            checked_at=checked_at,
            require_published=True,
        )
        spec = manifest.spec
        try:
            return RegistrySnapshotCandidate.model_validate(
                {
                    "publisher": publisher,
                    "id": bundle_id,
                    "version": version,
                    "kind": kind,
                    "manifest": manifest,
                    "contentHash": content_hash,
                    "signatureFingerprint": release.signature_fingerprint,
                    "releaseEvidenceRevision": release.release_evidence_revision,
                    "dependencies": [
                        {
                            "publisher": item.publisher or publisher,
                            "id": item.id,
                            "version": item.version,
                        }
                        for item in spec.dependencies
                    ],
                    "optionalDependencies": [
                        {
                            "publisher": item.publisher or publisher,
                            "id": item.id,
                            "version": item.version,
                        }
                        for item in spec.optional_dependencies
                    ],
                    "conflicts": [
                        {
                            "publisher": item.publisher or publisher,
                            "id": item.id,
                            "version": item.version,
                        }
                        for item in spec.conflicts
                    ],
                    "capabilities": spec.capabilities.model_dump(
                        mode="json", by_alias=True
                    ),
                    "permissions": spec.permissions.model_dump(
                        mode="json", by_alias=True
                    ),
                    "migration": {
                        "planRef": spec.migrations.plan,
                        "downgradePolicy": spec.migrations.downgrade_policy,
                    },
                    "contributions": spec.contributions,
                }
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise ManifestInvalidError(
                "stored Registry snapshot candidate indexes are inconsistent"
            ) from exc


def _transaction_timestamp(conn: Any) -> datetime:
    row = conn.execute("SELECT transaction_timestamp() AS checked_at").fetchone()
    if row is None:
        raise VerificationFailedError("registry snapshot transaction clock is missing")
    return row["checked_at"]


def _parse_artifacts(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise TypeError("stored Registry artifacts must be an array")
    artifacts: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("stored Registry artifact must be an object")
        artifacts.append(
            {
                "relativePath": item["relativePath"],
                "digest": item["digest"],
                "size": item["size"],
                "mediaType": item["mediaType"],
            }
        )
    return artifacts


_SNAPSHOT_QUERY = """
SELECT v.version_pk,
       b.publisher,
       b.bundle_id,
       b.kind,
       v.version,
       v.manifest_json,
       v.content_hash,
       v.signature,
       v.status,
       COALESCE(artifacts.items, '[]'::JSONB) AS artifacts,
       COALESCE(evidence.items, '[]'::JSONB) AS evidence
  FROM asset_bundle_version AS v
  JOIN asset_bundle AS b ON b.bundle_pk = v.bundle_pk
  LEFT JOIN LATERAL (
    SELECT jsonb_agg(
             jsonb_build_object(
               'relativePath', a.relative_path,
               'digest', a.digest,
               'size', a.size,
               'mediaType', a.media_type
             )
             ORDER BY a.relative_path
           ) AS items
      FROM asset_bundle_artifact AS a
     WHERE a.version_pk = v.version_pk
  ) AS artifacts ON TRUE
  LEFT JOIN LATERAL (
    SELECT jsonb_agg(
             jsonb_build_object(
               'type', e.evidence_type,
               'artifactRef', e.artifact_ref,
               'artifactHash', e.artifact_hash,
               'status', e.status,
               'observedAt', e.observed_at,
               'expiresAt', e.expires_at,
               'revokedAt', e.revoked_at,
               'metadata', e.metadata
             )
             ORDER BY e.evidence_type, e.artifact_hash, e.observed_at,
                      e.expires_at NULLS FIRST, e.artifact_ref
           ) AS items
      FROM asset_bundle_evidence AS e
     WHERE e.version_pk = v.version_pk
 ) AS evidence ON TRUE
 WHERE v.status = 'published'
   AND NOT EXISTS (
     SELECT 1
       FROM unnest(%s::TEXT[]) AS required(evidence_type)
      WHERE NOT EXISTS (
              SELECT 1
                FROM asset_bundle_evidence AS present
               WHERE present.version_pk = v.version_pk
                 AND present.evidence_type = required.evidence_type
            )
         OR EXISTS (
              SELECT 1
                FROM asset_bundle_evidence AS non_current
               WHERE non_current.version_pk = v.version_pk
                 AND non_current.evidence_type = required.evidence_type
                 AND (
                   non_current.status <> 'valid'
                   OR non_current.observed_at > transaction_timestamp()
                   OR (
                     non_current.expires_at IS NOT NULL
                     AND non_current.expires_at <= transaction_timestamp()
                   )
                   OR non_current.revoked_at IS NOT NULL
                 )
            )
   )
 ORDER BY b.publisher, b.bundle_id, v.version, v.content_hash
 LIMIT %s
"""
