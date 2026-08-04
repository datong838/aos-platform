"""TI-1 E3 append-only execution and role-separation events.

Revision ID: 228ti1e3exec
Revises: 228ti1e3ledger
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti1e3exec"
down_revision: str | Sequence[str] | None = "228ti1e3ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LEGACY_ACTOR_HASH = "0" * 64


def upgrade() -> None:
    op.execute(
        f"""
        ALTER TABLE tenant_backfill_batch_event
          ADD COLUMN actor_hash TEXT NOT NULL DEFAULT '{_LEGACY_ACTOR_HASH}'
            CHECK (actor_hash ~ '^[0-9a-f]{{64}}$')
        """
    )
    op.execute(
        "ALTER TABLE tenant_backfill_batch_event ALTER COLUMN actor_hash DROP DEFAULT"
    )
    op.execute(
        """
        CREATE TABLE tenant_ownership_decision_event (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          event_id BIGSERIAL NOT NULL,
          batch_id UUID NOT NULL,
          resource TEXT NOT NULL,
          key_hash TEXT NOT NULL CHECK (key_hash ~ '^[0-9a-f]{64}$'),
          event_type TEXT NOT NULL CHECK (event_type IN (
            'APPROVED', 'APPLIED', 'VERIFIED', 'ROLLED_BACK', 'CONFLICT'
          )),
          before_hash TEXT NOT NULL CHECK (before_hash ~ '^[0-9a-f]{64}$'),
          after_hash TEXT CHECK (after_hash IS NULL OR after_hash ~ '^[0-9a-f]{64}$'),
          evidence_hash TEXT NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
          actor_role TEXT NOT NULL CHECK (actor_role IN (
            'APPROVER', 'EXECUTOR', 'VERIFIER'
          )),
          actor_hash TEXT NOT NULL CHECK (actor_hash ~ '^[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, event_id),
          FOREIGN KEY (org_id, project_id, batch_id)
            REFERENCES tenant_backfill_batch (org_id, project_id, batch_id),
          UNIQUE (
            org_id, project_id, batch_id, resource, key_hash, event_type
          )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_decision_event_batch
          ON tenant_ownership_decision_event (
            org_id, project_id, batch_id, resource, event_type, event_id
          )
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tenant_ownership_decision_event_immutable
        BEFORE UPDATE OR DELETE ON tenant_ownership_decision_event
        FOR EACH ROW EXECUTE FUNCTION guard_tenant_e3_history_immutable()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tenant_ownership_decision_event_truncate_guard
        BEFORE TRUNCATE ON tenant_ownership_decision_event
        FOR EACH STATEMENT EXECUTE FUNCTION guard_tenant_e3_history_immutable()
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM tenant_ownership_decision_event LIMIT 1)
             OR EXISTS (
               SELECT 1 FROM tenant_backfill_batch_event
                WHERE actor_hash <> '{_LEGACY_ACTOR_HASH}' LIMIT 1
             ) THEN
            RAISE EXCEPTION 'archive tenant E3 execution events before downgrade';
          END IF;
        END;
        $$
        """
    )
    op.execute("DROP TABLE IF EXISTS tenant_ownership_decision_event")
    op.execute("ALTER TABLE tenant_backfill_batch_event DROP COLUMN actor_hash")
