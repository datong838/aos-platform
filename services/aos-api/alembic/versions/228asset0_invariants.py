"""Seal asset registry status and projection invariants.

Revision ID: 228assetinvariants
Revises: 228assetsecurity
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228assetinvariants"
down_revision: str | Sequence[str] | None = "228assetsecurity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PROJECTION_TABLES = (
    "asset_bundle_dependency",
    "asset_bundle_artifact",
    "asset_bundle_evidence",
)
_CANONICAL_TABLES = (
    "asset_bundle",
    "asset_bundle_version",
    *_PROJECTION_TABLES,
)


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION lock_asset_registry_projection_statement()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          PERFORM pg_advisory_xact_lock(228, 1);
          RETURN NULL;
        END;
        $$
        """
    )
    for table in _PROJECTION_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_00_{table}_statement_lock
            BEFORE INSERT OR UPDATE OR DELETE ON {table}
            FOR EACH STATEMENT
            EXECUTE FUNCTION lock_asset_registry_projection_statement()
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
    for table in _PROJECTION_TABLES:
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
    for table in _CANONICAL_TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_asset_registry_truncate()
            """
        )


def downgrade() -> None:
    for table in _CANONICAL_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}_truncate_guard ON {table}")
    op.execute(
        "DROP TRIGGER trg_asset_bundle_status_event_required ON asset_bundle_version"
    )
    for table in _PROJECTION_TABLES:
        op.execute(f"DROP TRIGGER trg_00_{table}_parent_lock ON {table}")
        op.execute(f"DROP TRIGGER trg_00_{table}_statement_lock ON {table}")
    op.execute("DROP FUNCTION guard_asset_registry_truncate()")
    op.execute("DROP FUNCTION ensure_asset_bundle_status_event()")
    op.execute("DROP FUNCTION lock_asset_bundle_projection_parent()")
    op.execute("DROP FUNCTION lock_asset_registry_projection_statement()")
