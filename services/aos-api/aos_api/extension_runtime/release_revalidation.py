"""Fresh Registry checks for the isolated lifecycle's final transaction only."""
from datetime import datetime
from dataclasses import dataclass

from aos_api.asset_registry.composition_contracts import StoredCompositionLock
from aos_api.asset_registry.installation_revalidation import _record_from_row
from aos_api.asset_registry.registry_snapshot import _SNAPSHOT_QUERY
from aos_api.asset_registry.errors import RegistryIntegrityCorruptError, RegistrySnapshotStaleError
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values


@dataclass(frozen=True)
class RuntimeReleaseCheck:
    checked_at: datetime
    runtime_members: tuple[str, ...]


class RuntimeReleaseRevalidator:
    def __init__(self, *, release_policy):
        self._release_policy=release_policy

    def revalidate_in_transaction(self, conn, *, lock):
        _require_transaction(conn)
        lock=StoredCompositionLock.model_validate(lock)
        conn.execute("SELECT pg_advisory_xact_lock(228, 1)")
        policy=self._release_policy.snapshot()
        row=conn.execute("SELECT clock_timestamp() AS checked_at").fetchone()
        if row is None:
            raise RegistryIntegrityCorruptError()
        checked_at=_values(row,("checked_at",))[0]
        if not isinstance(checked_at,datetime) or checked_at.utcoffset() is None:
            raise RegistryIntegrityCorruptError()
        indexed={}
        for row in conn.execute(_SNAPSHOT_QUERY).fetchall():
            key=(str(row["publisher"]),str(row["bundle_id"]),str(row["version"]))
            if key in indexed:
                raise RegistryIntegrityCorruptError()
            indexed[key]=row
        runtime_members=[]
        for selected in lock.payload.resolved:
            row=indexed.get((selected.publisher,selected.id,selected.version))
            if row is None:
                raise RegistrySnapshotStaleError("selected release no longer available")
            record=_record_from_row(row)
            if record.content_hash!=selected.content_hash:
                raise RegistryIntegrityCorruptError()
            # Runtime is allowed here only because this is not the legacy gateway.
            # This does not assert health, approval, binding, resources or readiness.
            policy.evaluate(record,checked_at=checked_at,
                expected_signature_fingerprint=selected.signature_fingerprint,
                expected_evidence_revision=selected.release_evidence_revision)
            if record.manifest.spec.runtime is not None:
                runtime_members.append(selected.id)
        return RuntimeReleaseCheck(checked_at=checked_at,runtime_members=tuple(runtime_members))
