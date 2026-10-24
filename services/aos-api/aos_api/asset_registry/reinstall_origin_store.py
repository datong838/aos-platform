"""Unwired same-transaction origin append primitive.

Requires a separately qualified immutable relation and current/native checker.
This appender deliberately cannot satisfy ReinstallOriginPort on its own.
"""
from typing import Any
from uuid import UUID

from aos_api.asset_registry.composition_contracts import InstallationRecord
from aos_api.asset_registry.installation_store import LockedInstallation, _normalized_text
from aos_api.asset_registry.reinstall_contracts import ReinstallSourceRef
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.tenant_scope import TenantScope


_APPEND = """
WITH appended AS (
  INSERT INTO public.bundle_installation_reinstall_origin (
    org_id, project_id, target_installation_pk, target_revision,
    source_installation_pk, source_terminal_revision, source_lock_hash,
    target_lock_hash, actor
  )
  SELECT s.org_id, s.project_id, t.installation_pk, 1,
         s.installation_pk, sr.revision, sr.lock_hash, tr.lock_hash, %(actor)s
  FROM public.bundle_installation s
  JOIN public.bundle_installation_revision sr
    ON (sr.org_id, sr.project_id, sr.installation_pk, sr.revision) =
       (s.org_id, s.project_id, s.installation_pk, s.current_revision)
  JOIN public.bundle_installation t
    ON (t.org_id, t.project_id) = (s.org_id, s.project_id)
  JOIN public.bundle_installation_revision tr
    ON (tr.org_id, tr.project_id, tr.installation_pk, tr.revision) =
       (t.org_id, t.project_id, t.installation_pk, t.current_revision)
  WHERE s.org_id = %(org_id)s AND s.project_id = %(project_id)s
    AND s.installation_id = %(source_id)s AND s.installation_pk = %(source_pk)s
    AND s.current_revision = %(source_revision)s
    AND s.etag_version = %(source_revision)s AND sr.state = 'uninstalled'
    AND sr.lock_hash = %(source_hash)s
    AND t.installation_id = %(target_id)s AND t.installation_pk <> s.installation_pk
    AND t.current_revision = 1 AND t.etag_version = 1 AND tr.state = 'draft'
    AND tr.lock_hash = %(target_hash)s
    AND t.created_by = %(actor)s AND tr.requested_by = %(actor)s
  RETURNING org_id, project_id, target_installation_pk, target_revision,
            source_installation_pk, source_terminal_revision, source_lock_hash,
            target_lock_hash, actor
)
SELECT a.*, s.installation_id AS source_installation_id,
       t.installation_id AS target_installation_id
FROM appended a
JOIN public.bundle_installation s
  ON (s.org_id, s.project_id, s.installation_pk) =
     (a.org_id, a.project_id, a.source_installation_pk)
JOIN public.bundle_installation t
  ON (t.org_id, t.project_id, t.installation_pk) =
     (a.org_id, a.project_id, a.target_installation_pk)
"""


class PostgresReinstallOriginAppender:
    """No connector, DDL, transaction ownership, replay or current-proof port."""

    def append_origin(
        self, conn: Any, *, org_id: str, project_id: str, actor: str,
        source: ReinstallSourceRef, locked_source: LockedInstallation,
        target_record: InstallationRecord,
    ) -> None:
        TenantScope(org_id, project_id)
        actor = _normalized_text(actor, "actor")
        if (type(source) is not ReinstallSourceRef
                or type(locked_source) is not LockedInstallation
                or type(locked_source.record) is not InstallationRecord
                or type(target_record) is not InstallationRecord):
            raise TypeError("exact trusted origin inputs required")
        source = ReinstallSourceRef.model_validate(source.model_dump(mode="python", by_alias=True))
        record = InstallationRecord.model_validate(
            locked_source.record.model_dump(mode="python", by_alias=True))
        target = InstallationRecord.model_validate(
            target_record.model_dump(mode="python", by_alias=True))
        if (locked_source.org_id != org_id or locked_source.project_id != project_id
                or type(locked_source.installation_pk) is not UUID):
            raise ValueError("locked source scope or physical identity mismatch")
        if (record.installation_id != source.installation_id
                or record.state != "uninstalled"
                or record.current_revision != source.terminal_revision
                or record.etag_version != source.terminal_revision
                or record.current.lock_hash != source.lock_hash):
            raise ValueError("terminal source snapshot mismatch")
        if (target.installation_id == source.installation_id
                or target.state != "draft" or target.current_revision != 1
                or target.etag_version != 1 or target.current.requested_by != actor):
            raise ValueError("new target draft snapshot mismatch")
        require_runtime_role(
            conn, org_id=org_id, project_id=project_id,
            protected_tables=("public.bundle_installation", "public.bundle_installation_revision",
                              "public.bundle_installation_reinstall_origin"),
        )
        params = dict(org_id=org_id, project_id=project_id, actor=actor,
                      source_id=UUID(source.installation_id), source_pk=locked_source.installation_pk,
                      source_revision=source.terminal_revision, source_hash=source.lock_hash,
                      target_id=UUID(target.installation_id), target_hash=target.current.lock_hash)
        rows = conn.execute(_APPEND, params).fetchall()
        if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
            raise ValueError("exactly one complete stored origin required")
        row = rows[0]
        expected = dict(org_id=org_id, project_id=project_id, actor=actor,
                        source_installation_pk=locked_source.installation_pk,
                        source_terminal_revision=source.terminal_revision,
                        source_lock_hash=source.lock_hash, target_lock_hash=target.current.lock_hash,
                        target_revision=1, source_installation_id=source.installation_id,
                        target_installation_id=target.installation_id)
        if set(row) != set(expected) | {"target_installation_pk"}:
            raise ValueError("stored origin columns mismatch")
        if (type(row["target_installation_pk"]) is not UUID
                or row["target_installation_pk"] == locked_source.installation_pk):
            raise ValueError("stored target physical identity mismatch")
        for key, value in expected.items():
            # PostgreSQL UUID columns are natively UUID, public DTO IDs are text.
            actual = row[key]
            if key.endswith("_installation_id") and type(actual) is UUID:
                actual = str(actual)
            if type(actual) is not type(value) or actual != value:
                raise ValueError("stored origin lineage mismatch")
