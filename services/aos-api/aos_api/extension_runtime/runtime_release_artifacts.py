"""Current published Registry release and allowlisted runtime artifact reader."""
from __future__ import annotations

import hashlib

from aos_api.asset_registry.composition_contracts import ResolvedBundle
from aos_api.asset_registry.errors import RegistryIntegrityCorruptError, RegistrySnapshotStaleError
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.tenant_scope import TenantScope

from .consumer_connection import consumer_connection


class CurrentRuntimeReleaseArtifacts:
    def __init__(self, *, connect, scope: TenantScope, loader: ManifestLoader) -> None:
        if not callable(connect) or type(scope) is not TenantScope or type(loader) is not ManifestLoader:
            raise TypeError("exact runtime release artifact dependencies required")
        self.connect = connect
        self.scope = scope
        self.loader = loader

    @property
    def _tenant(self):
        return {"org_id": self.scope.org_id, "project_id": self.scope.project_id}

    def _load_rows(self, selected: ResolvedBundle):
        with consumer_connection(self.connect, self._tenant) as conn:
            return tuple(conn.execute(
                """SELECT v.version_pk,b.publisher,b.bundle_id,b.kind,v.version,
                          v.manifest_json,v.content_hash,v.signature,v.status,
                          COALESCE(artifacts.items,'[]'::jsonb) AS artifacts,
                          COALESCE(evidence.items,'[]'::jsonb) AS evidence
                     FROM asset_bundle_version v
                     JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
                     LEFT JOIN LATERAL (
                       SELECT jsonb_agg(jsonb_build_object(
                         'relativePath',a.relative_path,'digest',a.digest,
                         'size',a.size,'mediaType',a.media_type)
                         ORDER BY a.relative_path) AS items
                         FROM asset_bundle_artifact a WHERE a.version_pk=v.version_pk
                     ) artifacts ON TRUE
                     LEFT JOIN LATERAL (
                       SELECT jsonb_agg(jsonb_build_object(
                         'type',e.evidence_type,'artifactRef',e.artifact_ref,
                         'artifactHash',e.artifact_hash,'status',e.status,
                         'observedAt',e.observed_at,'expiresAt',e.expires_at,
                         'revokedAt',e.revoked_at,'metadata',e.metadata)
                         ORDER BY e.evidence_type,e.artifact_hash,e.observed_at,
                                  e.expires_at NULLS FIRST,e.artifact_ref) AS items
                         FROM asset_bundle_evidence e WHERE e.version_pk=v.version_pk
                     ) evidence ON TRUE
                    WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s
                      AND v.content_hash=%s AND v.status='published'""",
                (selected.publisher, selected.id, selected.version, selected.content_hash),
            ).fetchall())

    def load_record(self, selected: ResolvedBundle):
        if type(selected) is not ResolvedBundle:
            raise TypeError("exact resolved runtime release required")
        rows = self._load_rows(selected)
        if len(rows) != 1:
            raise RegistrySnapshotStaleError("selected runtime release is not uniquely published")
        record = _record_from_row(rows[0])
        metadata = record.manifest.metadata
        if (record.publisher, metadata.id, metadata.version, record.content_hash) != (
            selected.publisher, selected.id, selected.version, selected.content_hash
        ):
            raise RegistryIntegrityCorruptError()
        return record

    def _load_artifacts(self, selected: ResolvedBundle):
        with consumer_connection(self.connect, self._tenant) as conn:
            return tuple(conn.execute(
                """SELECT a.relative_path,a.artifact_ref,a.digest,a.size
                     FROM asset_bundle_artifact a
                     JOIN asset_bundle_version v ON v.version_pk=a.version_pk
                     JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
                    WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s
                      AND v.content_hash=%s AND v.status='published'
                    ORDER BY a.relative_path""",
                (selected.publisher, selected.id, selected.version, selected.content_hash),
            ).fetchall())

    def read_artifact(self, selected: ResolvedBundle, path: str, limit: int) -> bytes:
        if type(selected) is not ResolvedBundle:
            raise TypeError("exact resolved runtime release required")
        if (type(path) is not str or not path or path != path.strip()
                or path.startswith(("/", "~")) or "\\" in path or "://" in path
                or any(part in ("", ".", "..") for part in path.split("/"))
                or type(limit) is not int or isinstance(limit, bool)
                or not 1 <= limit <= ManifestLoader.MAX_FILE_BYTES):
            raise ValueError("bounded runtime artifact request required")
        rows = self._load_artifacts(selected)
        if not rows:
            raise RegistrySnapshotStaleError("selected runtime artifacts are unavailable")
        indexed = {}
        sources = set()
        for row in rows:
            relative = row["relative_path"] if isinstance(row, dict) else row[0]
            artifact_ref = row["artifact_ref"] if isinstance(row, dict) else row[1]
            digest = row["digest"] if isinstance(row, dict) else row[2]
            size = row["size"] if isinstance(row, dict) else row[3]
            if (type(relative) is not str or type(artifact_ref) is not str
                    or type(digest) is not str or type(size) is not int):
                raise RegistryIntegrityCorruptError()
            suffix = "/" + relative
            if relative in indexed or not artifact_ref.endswith(suffix):
                raise RegistryIntegrityCorruptError()
            indexed[relative] = (digest, size)
            sources.add(artifact_ref[:-len(suffix)])
        if len(sources) != 1 or path not in indexed:
            raise RegistryIntegrityCorruptError()
        digest, size = indexed[path]
        if size < 0 or size > limit:
            raise ValueError("runtime artifact exceeds bounded request")
        raw = self.loader.read_verified_artifact(
            next(iter(sources)), path, expected_digest=digest, limit=limit
        )
        if (type(raw) is not bytes or len(raw) != size
                or "sha256:" + hashlib.sha256(raw).hexdigest() != digest):
            raise RegistryIntegrityCorruptError()
        return raw
