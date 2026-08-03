"""Exact selected-release revalidation for M2 installation transitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from aos_api.asset_registry.composition_contracts import StoredCompositionLock
from aos_api.asset_registry.contracts import (
    BundleEvidence,
    BundleManifest,
    BundleSignature,
    BundleVersionStatus,
)
from aos_api.asset_registry.errors import (
    AssetRegistryError,
    RegistryIntegrityCorruptError,
    RegistrySnapshotStaleError,
    TrustRootUnavailableError,
)
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.release_policy import ReleasePolicy


@dataclass(frozen=True, slots=True)
class RevalidationResult:
    checked_at: datetime


@dataclass(frozen=True, slots=True)
class _ReleaseRecord:
    publisher: str
    manifest: BundleManifest
    content_hash: str
    signature: BundleSignature | None
    status: BundleVersionStatus
    evidence: list[BundleEvidence]
    artifacts: list[dict[str, object]]


class InstallationRevalidator:
    def __init__(self, *, release_policy: ReleasePolicy) -> None:
        self._release_policy = release_policy

    def revalidate_in_transaction(
        self,
        conn: Any,
        *,
        lock: StoredCompositionLock,
    ) -> RevalidationResult:
        lock = StoredCompositionLock.model_validate(lock)
        conn.execute("SELECT pg_advisory_xact_lock(228, 1)")
        policy = self._release_policy.snapshot()
        clock = conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()
        if clock is None or not isinstance(clock["checked_at"], datetime):
            raise RegistryIntegrityCorruptError()
        checked_at = clock["checked_at"]
        rows = conn.execute(_SNAPSHOT_QUERY).fetchall()
        indexed: dict[tuple[str, str, str], Any] = {}
        for row in rows:
            key = (str(row["publisher"]), str(row["bundle_id"]), str(row["version"]))
            if key in indexed:
                raise RegistryIntegrityCorruptError()
            indexed[key] = row

        for selected in lock.payload.resolved:
            key = (selected.publisher, selected.id, selected.version)
            row = indexed.get(key)
            if row is None:
                raise RegistrySnapshotStaleError(
                    "selected Registry release is no longer available"
                )
            try:
                record = _record_from_row(row)
                if record.content_hash != selected.content_hash:
                    raise RegistryIntegrityCorruptError()
                policy.evaluate(
                    record,
                    checked_at=checked_at,
                    expected_signature_fingerprint=selected.signature_fingerprint,
                    expected_evidence_revision=selected.release_evidence_revision,
                )
            except TrustRootUnavailableError:
                raise
            except RegistryIntegrityCorruptError:
                raise
            except AssetRegistryError as exc:
                raise RegistrySnapshotStaleError(
                    "selected Registry release is stale"
                ) from exc
            except (KeyError, TypeError, ValueError, ValidationError) as exc:
                raise RegistryIntegrityCorruptError() from exc
        return RevalidationResult(checked_at=checked_at)


def _record_from_row(row: Any) -> _ReleaseRecord:
    manifest = BundleManifest.model_validate(row["manifest_json"])
    signature = (
        BundleSignature.model_validate_json(json.dumps(row["signature"]))
        if row["signature"] is not None
        else None
    )
    evidence = [
        BundleEvidence.model_validate_json(json.dumps(item)) for item in row["evidence"]
    ]
    artifacts = [
        {
            "relativePath": item["relativePath"],
            "digest": item["digest"],
            "size": item["size"],
            "mediaType": item["mediaType"],
        }
        for item in row["artifacts"]
    ]
    return _ReleaseRecord(
        publisher=str(row["publisher"]),
        manifest=manifest,
        content_hash=str(row["content_hash"]),
        signature=signature,
        status=BundleVersionStatus(row["status"]),
        evidence=evidence,
        artifacts=artifacts,
    )
