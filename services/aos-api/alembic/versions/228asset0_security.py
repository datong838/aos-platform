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
    op.execute("DROP TABLE asset_bundle_version_event")
    op.execute("DROP FUNCTION guard_asset_bundle_version_event_mutation()")
