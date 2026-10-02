"""Read current installation release evidence without granting startup authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal
from uuid import UUID

from aos_api.asset_registry.composition_store import load_stored_lock
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope

from .release_revalidation import RuntimeReleaseRevalidator
from .ui_resources import _source_ref


class CurrentReleaseEvidenceBlocked(ValueError):
    """An exact current release view could not be proved."""


@dataclass(frozen=True, slots=True)
class SelectedReleaseEvidence:
    publisher: str
    bundle_id: str
    version: str
    content_hash: str
    signature_fingerprint: str
    release_evidence_revision: str


@dataclass(frozen=True, slots=True)
class CurrentInstallationReleaseEvidence:
    scope: tuple[str, str]
    installation_id: str
    current_revision: int
    active_revision: int | None
    etag_version: int
    lock_hash: str
    releases: tuple[SelectedReleaseEvidence, ...]
    runtime_members: tuple[str, ...]
    checked_at: datetime
    authorization: Literal["EVIDENCE_ONLY_NO_START"] = field(
        default="EVIDENCE_ONLY_NO_START", init=False,
    )


def read_current_installation_release_evidence(
    *,
    connect_factory: Callable,
    scope: TenantScope,
    installation_id: str,
    release_policy: ReleasePolicy,
    loader: ManifestLoader,
) -> CurrentInstallationReleaseEvidence:
    if (not callable(connect_factory) or type(scope) is not TenantScope
            or not isinstance(release_policy, ReleasePolicy)
            or not isinstance(loader, ManifestLoader)):
        raise CurrentReleaseEvidenceBlocked("READER_DEPENDENCY_INVALID")
    try:
        exact_installation = UUID(str(installation_id))
    except (TypeError, ValueError, AttributeError):
        raise CurrentReleaseEvidenceBlocked("INSTALLATION_ID_INVALID") from None
    try:
        with connect_factory() as conn:
            conn.read_only = True
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                apply_asset_transaction_scope(
                    conn, org_id=scope.org_id, project_id=scope.project_id,
                )
                rows = conn.execute(
                    """SELECT i.installation_id,i.current_revision,i.active_revision,
                              i.etag_version,r.state,r.composition_pk,r.lock_revision,
                              r.lock_hash,c.composition_id
                         FROM bundle_installation i
                         JOIN bundle_installation_revision r
                           ON r.org_id=i.org_id AND r.project_id=i.project_id
                          AND r.installation_pk=i.installation_pk
                          AND r.revision=i.current_revision
                         JOIN bundle_composition c
                           ON c.org_id=r.org_id AND c.project_id=r.project_id
                          AND c.composition_pk=r.composition_pk
                        WHERE i.org_id=%s AND i.project_id=%s
                          AND i.installation_id=%s
                        LIMIT 2""",
                    (*scope.key, exact_installation),
                ).fetchall()
                if len(rows) != 1:
                    raise CurrentReleaseEvidenceBlocked("INSTALLATION_MISSING")
                row = rows[0]
                if (row["state"] not in {"approved", "applied", "active"}
                        or type(row["current_revision"]) is not int
                        or row["current_revision"] < 1
                        or type(row["etag_version"]) is not int
                        or row["etag_version"] < 1
                        or (row["active_revision"] is not None
                            and (type(row["active_revision"]) is not int
                                 or not 1 <= row["active_revision"] <= row["current_revision"]))):
                    raise CurrentReleaseEvidenceBlocked("INSTALLATION_STATE_INVALID")
                composition_pk, lock = load_stored_lock(
                    conn, org_id=scope.org_id, project_id=scope.project_id,
                    composition_id=str(row["composition_id"]),
                    revision=row["lock_revision"],
                )
                if (composition_pk != row["composition_pk"]
                        or lock.lock_hash != row["lock_hash"]):
                    raise CurrentReleaseEvidenceBlocked("INSTALLATION_LOCK_DRIFT")
                checked = RuntimeReleaseRevalidator(
                    release_policy=release_policy,
                ).revalidate_in_transaction(conn, lock=lock)
                indexed = {}
                for release_row in conn.execute(_SNAPSHOT_QUERY).fetchall():
                    key = (str(release_row["publisher"]),
                           str(release_row["bundle_id"]),
                           str(release_row["version"]))
                    if key in indexed:
                        raise CurrentReleaseEvidenceBlocked("REGISTRY_RELEASE_AMBIGUOUS")
                    indexed[key] = release_row
                releases = []
                for selected in lock.payload.resolved:
                    release_row = indexed.get(
                        (selected.publisher, selected.id, selected.version)
                    )
                    if release_row is None:
                        raise CurrentReleaseEvidenceBlocked("REGISTRY_RELEASE_MISSING")
                    record = _record_from_row(release_row)
                    source_ref = _source_ref(record)
                    if source_ref is None:
                        raise CurrentReleaseEvidenceBlocked("RELEASE_SOURCE_MISSING")
                    loaded = loader.load(source_ref)
                    if (record.content_hash != selected.content_hash
                            or loaded.content_hash != selected.content_hash
                            or loaded.manifest != record.manifest
                            or loaded.signature != record.signature):
                        raise CurrentReleaseEvidenceBlocked("RELEASE_BYTES_DRIFT")
                    releases.append(SelectedReleaseEvidence(
                        publisher=selected.publisher,
                        bundle_id=selected.id,
                        version=selected.version,
                        content_hash=selected.content_hash,
                        signature_fingerprint=selected.signature_fingerprint,
                        release_evidence_revision=selected.release_evidence_revision,
                    ))
                return CurrentInstallationReleaseEvidence(
                    scope=scope.key,
                    installation_id=str(exact_installation),
                    current_revision=row["current_revision"],
                    active_revision=row["active_revision"],
                    etag_version=row["etag_version"],
                    lock_hash=lock.lock_hash,
                    releases=tuple(releases),
                    runtime_members=checked.runtime_members,
                    checked_at=checked.checked_at,
                )
    except CurrentReleaseEvidenceBlocked:
        raise
    except Exception:
        raise CurrentReleaseEvidenceBlocked("RELEASE_EVIDENCE_INVALID") from None
