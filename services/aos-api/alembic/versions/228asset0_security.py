"""Add atomic asset bundle lifecycle audit events.

Revision ID: 228assetsecurity
Revises: a93c7e1b4f20
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228assetsecurity"
down_revision: str | Sequence[str] | None = "a93c7e1b4f20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE asset_bundle_version_event (
          event_pk UUID PRIMARY KEY,
          version_pk UUID NOT NULL
            REFERENCES asset_bundle_version(version_pk) ON DELETE RESTRICT,
          sequence BIGINT NOT NULL CHECK (sequence > 0),
          from_status TEXT NOT NULL CHECK (
            from_status IN (
              'draft', 'validated', 'published',
              'deprecated', 'revoked', 'rejected'
            )
          ),
          to_status TEXT NOT NULL CHECK (
            to_status IN (
              'draft', 'validated', 'published',
              'deprecated', 'revoked', 'rejected'
            )
          ),
          actor TEXT NOT NULL CHECK (btrim(actor) <> ''),
          reason TEXT,
          evidence_revision TEXT NOT NULL
            CHECK (evidence_revision ~ '^sha256:[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          UNIQUE (version_pk, sequence),
          CHECK (from_status <> to_status)
        )
        """
    )
    # Backfill pre-audit versions before enabling the strict INSERT guard.  The
    # all-zero evidence revision is an explicit legacy sentinel, not a claim
    # that historical gate evidence was reconstructed.
    op.execute(
        """
        INSERT INTO asset_bundle_version_event (
          event_pk, version_pk, sequence, from_status, to_status,
          actor, reason, evidence_revision, created_at
        )
        SELECT md5(version_pk::TEXT || '-asset-audit-1')::UUID,
               version_pk,
               1,
               'draft',
               CASE WHEN status = 'rejected' THEN 'rejected' ELSE 'validated' END,
               'system:migration',
               'backfilled by 228assetsecurity; historical evidence unavailable',
               'sha256:' || repeat('0', 64),
               updated_at
          FROM asset_bundle_version
         WHERE status <> 'draft'
        """
    )
    op.execute(
        """
        INSERT INTO asset_bundle_version_event (
          event_pk, version_pk, sequence, from_status, to_status,
          actor, reason, evidence_revision, created_at
        )
        SELECT md5(version_pk::TEXT || '-asset-audit-2')::UUID,
               version_pk,
               2,
               'validated',
               'published',
               'system:migration',
               'backfilled by 228assetsecurity; historical evidence unavailable',
               'sha256:' || repeat('0', 64),
               updated_at
          FROM asset_bundle_version
         WHERE status IN ('published', 'deprecated', 'revoked')
        """
    )
    op.execute(
        """
        INSERT INTO asset_bundle_version_event (
          event_pk, version_pk, sequence, from_status, to_status,
          actor, reason, evidence_revision, created_at
        )
        SELECT md5(version_pk::TEXT || '-asset-audit-3')::UUID,
               version_pk,
               3,
               'published',
               status,
               'system:migration',
               'backfilled by 228assetsecurity; historical evidence unavailable',
               'sha256:' || repeat('0', 64),
               updated_at
          FROM asset_bundle_version
         WHERE status IN ('deprecated', 'revoked')
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_asset_bundle_version_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          previous_status TEXT;
          expected_sequence BIGINT;
          current_version_status TEXT;
        BEGIN
          IF TG_OP IN ('UPDATE', 'DELETE', 'TRUNCATE') THEN
            RAISE EXCEPTION
              'asset bundle lifecycle events are append-only'
              USING ERRCODE = '23514';
          END IF;
          SELECT COALESCE(MAX(sequence), 0) + 1,
                 (ARRAY_AGG(to_status ORDER BY sequence DESC))[1]
            INTO expected_sequence, previous_status
            FROM asset_bundle_version_event
           WHERE version_pk = NEW.version_pk;
          IF NEW.sequence <> expected_sequence
             OR (
               NEW.sequence = 1
               AND NEW.from_status <> 'draft'
             )
             OR (
               NEW.sequence > 1
               AND NEW.from_status IS DISTINCT FROM previous_status
             ) THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not extend the event tail'
              USING ERRCODE = '23514';
          END IF;
          SELECT status
            INTO current_version_status
            FROM asset_bundle_version
           WHERE version_pk = NEW.version_pk;
          IF current_version_status IS NULL
             OR NEW.to_status <> current_version_status THEN
            RAISE EXCEPTION
              'asset bundle lifecycle event does not match version status'
              USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_bundle_version_event_guard
        BEFORE INSERT OR UPDATE OR DELETE ON asset_bundle_version_event
        FOR EACH ROW EXECUTE FUNCTION guard_asset_bundle_version_event_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_asset_bundle_version_event_truncate_guard
        BEFORE TRUNCATE ON asset_bundle_version_event
        FOR EACH STATEMENT EXECUTE FUNCTION guard_asset_bundle_version_event_mutation()
        """
    )
    op.execute(
        """
        CREATE FUNCTION lock_asset_bundle_projection_parent()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
          old_version_pk UUID;
          new_version_pk UUID;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            old_version_pk := OLD.version_pk;
          END IF;
          IF TG_OP <> 'DELETE' THEN
            new_version_pk := NEW.version_pk;
          END IF;
          PERFORM 1
            FROM asset_bundle_version
           WHERE version_pk IN (old_version_pk, new_version_pk)
           ORDER BY version_pk
           FOR NO KEY UPDATE;
          RETURN CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
        END;
        $$
        """
    )
    for table in (
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_00_{table}_parent_lock
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION lock_asset_bundle_projection_parent()
            """
        )

    op.execute(
        """
        CREATE FUNCTION ensure_asset_bundle_status_event()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          IF NEW.status IS DISTINCT FROM OLD.status
             AND NOT EXISTS (
               SELECT 1
                 FROM asset_bundle_version_event
                WHERE version_pk = NEW.version_pk
                  AND from_status = OLD.status
                  AND to_status = NEW.status
             ) THEN
            RAISE EXCEPTION
              'asset bundle status transition requires a lifecycle event'
              USING ERRCODE = '23514';
          END IF;
          RETURN NULL;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER trg_asset_bundle_status_event_required
        AFTER UPDATE OF status ON asset_bundle_version
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ensure_asset_bundle_status_event()
        """
    )

    op.execute(
        """
        CREATE FUNCTION guard_asset_registry_truncate()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION
            'canonical asset registry tables cannot be truncated'
            USING ERRCODE = '23514';
        END;
        $$
        """
    )
    for table in (
        "asset_bundle",
        "asset_bundle_version",
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_asset_registry_truncate()
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM asset_bundle_version_event LIMIT 1) THEN
            RAISE EXCEPTION
              'asset registry security downgrade blocked: lifecycle events exist'
              USING ERRCODE = '23514';
          END IF;
        END;
        $$
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_asset_bundle_status_event_required "
        "ON asset_bundle_version"
    )
    for table in (
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_00_{table}_parent_lock ON {table}")
    for table in (
        "asset_bundle",
        "asset_bundle_version",
        "asset_bundle_dependency",
        "asset_bundle_artifact",
        "asset_bundle_evidence",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_truncate_guard ON {table}")
    op.execute("DROP TABLE asset_bundle_version_event")
    op.execute("DROP FUNCTION IF EXISTS guard_asset_registry_truncate()")
    op.execute("DROP FUNCTION IF EXISTS ensure_asset_bundle_status_event()")
    op.execute("DROP FUNCTION IF EXISTS lock_asset_bundle_projection_parent()")
    op.execute("DROP FUNCTION guard_asset_bundle_version_event_mutation()")
