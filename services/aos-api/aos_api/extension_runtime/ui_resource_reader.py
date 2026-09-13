"""Read only a published bundle's declared, hash-bound frontend entrypoint."""
from __future__ import annotations

import re
from typing import Any

from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.extension_runtime.ui_resources import FrontendUiManifest, _source_ref


_EXACT_RELEASE = f"SELECT * FROM ({_SNAPSHOT_QUERY}) AS releases WHERE publisher=%s AND bundle_id=%s AND version=%s LIMIT 2"
_HASH = re.compile(r"sha256:[0-9a-f]{64}")


class PublishedUiResourceReader:
    """Static code access confers no tenant, installation, or business authority."""

    def __init__(self, *, connect_factory: Any, release_policy: Any, loader: Any):
        self._connect = connect_factory
        self._policy = release_policy
        self._loader = loader

    def _release(self, identity: tuple[str, str, str]):
        with self._connect() as conn:
            clock = conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()
            rows = conn.execute(_EXACT_RELEASE, identity).fetchall()
        if clock is None or len(rows) != 1:
            raise LookupError("published frontend unavailable")
        record = _record_from_row(rows[0])
        proof = self._policy.snapshot().evaluate(record, checked_at=clock["checked_at"])
        return record, proof

    def read(self, *, publisher: str, bundle_id: str, version: str,
             entrypoint: str, package_hash: str, content_hash: str) -> bytes:
        identity = (publisher, bundle_id, version)
        if any(type(value) is not str or len(value) > 160 or
               re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", value) is None for value in identity):
            raise ValueError("invalid resource identity")
        if any(type(value) is not str or _HASH.fullmatch(value) is None
               for value in (package_hash, content_hash)):
            raise ValueError("invalid resource digest")
        if type(entrypoint) is not str or len(entrypoint) > 1024:
            raise ValueError("invalid frontend entrypoint")
        # Use the same path contract as the signed frontend manifest before any IO.
        FrontendUiManifest._entrypoint_is_bundle_local_html(entrypoint)
        record, proof = self._release(identity)
        if record.content_hash != package_hash:
            raise LookupError("published frontend unavailable")
        runtime = record.manifest.spec.runtime
        frontend = runtime.frontend if runtime else None
        source_ref = _source_ref(record)
        if frontend is None or source_ref is None:
            raise LookupError("published frontend unavailable")
        loaded = self._loader.load(source_ref)
        if (loaded.content_hash != package_hash or loaded.manifest != record.manifest
                or loaded.signature != record.signature):
            raise ValueError("published bundle changed")
        artifacts = {item.relative_path: item for item in loaded.artifacts}
        if len(artifacts) != len(loaded.artifacts):
            raise ValueError("ambiguous bundle artifacts")
        ui_artifact = artifacts.get(frontend.manifest)
        if ui_artifact is None or ui_artifact.digest != frontend.artifact_hash:
            raise ValueError("frontend manifest digest mismatch")
        ui = FrontendUiManifest.model_validate_json(self._loader.read_verified_artifact(
            source_ref, frontend.manifest, expected_digest=frontend.artifact_hash, limit=65_536))
        if ui.entrypoint != entrypoint:
            raise LookupError("declared frontend unavailable")
        artifact = artifacts.get(entrypoint)
        if artifact is None or artifact.digest != content_hash:
            raise LookupError("declared frontend unavailable")
        content = self._loader.read_verified_artifact(
            source_ref, entrypoint, expected_digest=content_hash, limit=1_048_576)
        content.decode("utf-8", errors="strict")
        current, current_proof = self._release(identity)
        if (current.content_hash != record.content_hash or current.manifest != record.manifest
                or current.signature != record.signature or current_proof != proof
                or _source_ref(current) != source_ref):
            raise ValueError("published release changed during read")
        return content
