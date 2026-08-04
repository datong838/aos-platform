"""TI-1 E3 append-only ownership and quarantine ledger.

Revision ID: 228ti1e3ledger
Revises: 228ti1e2dual
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti1e3ledger"
down_revision: str | Sequence[str] | None = "228ti1e2dual"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "tenant_backfill_batch",
    "tenant_backfill_batch_event",
    "tenant_ownership_decision",
    "tenant_quarantine_record",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenant_backfill_batch (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          batch_id UUID NOT NULL,
          environment_hash TEXT NOT NULL CHECK (environment_hash ~ '^[0-9a-f]{64}$'),
          source_snapshot_hash TEXT NOT NULL CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
          code_commit TEXT NOT NULL CHECK (code_commit ~ '^[0-9a-f]{7,64}$'),
          mode TEXT NOT NULL CHECK (mode IN ('DRY_RUN', 'RESTORE_DRILL', 'NON_PROD')),
          status TEXT NOT NULL DEFAULT 'PLANNED' CHECK (status = 'PLANNED'),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          approved_at TIMESTAMPTZ,
          completed_at TIMESTAMPTZ,
          PRIMARY KEY (org_id, project_id, batch_id),
          FOREIGN KEY (org_id, project_id)
            REFERENCES twa_workspace (org_id, project_id),
          CHECK (approved_at IS NULL OR approved_at >= created_at),
          CHECK (completed_at IS NULL OR completed_at >= created_at)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tenant_backfill_batch_event (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          event_id BIGSERIAL NOT NULL,
          batch_id UUID NOT NULL,
          status TEXT NOT NULL CHECK (status IN (
            'PLANNED', 'APPROVED', 'EXECUTING', 'COMPLETED', 'FAILED',
            'ROLLED_BACK', 'ROLLBACK_CONFLICT'
          )),
          evidence_hash TEXT NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
          actor_role TEXT NOT NULL CHECK (actor_role IN (
            'PLANNER', 'APPROVER', 'EXECUTOR', 'VERIFIER'
          )),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, event_id),
          FOREIGN KEY (org_id, project_id, batch_id)
            REFERENCES tenant_backfill_batch (org_id, project_id, batch_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tenant_ownership_decision (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          decision_id BIGSERIAL NOT NULL,
          batch_id UUID NOT NULL,
          resource TEXT NOT NULL,
          key_hash TEXT NOT NULL CHECK (key_hash ~ '^[0-9a-f]{64}$'),
          decision TEXT NOT NULL CHECK (decision IN (
            'ASSIGN', 'QUARANTINE', 'NO_ACTION', 'BLOCKED'
          )),
          evidence_grade TEXT NOT NULL CHECK (evidence_grade IN ('A', 'B', 'C', 'X')),
          evidence_hash TEXT NOT NULL CHECK (evidence_hash ~ '^[0-9a-f]{64}$'),
          candidate_count INTEGER NOT NULL CHECK (candidate_count >= 0),
          target_org_id TEXT,
          target_project_id TEXT,
          before_hash TEXT NOT NULL CHECK (before_hash ~ '^[0-9a-f]{64}$'),
          after_hash TEXT CHECK (after_hash IS NULL OR after_hash ~ '^[0-9a-f]{64}$'),
          reason_code TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, decision_id),
          FOREIGN KEY (org_id, project_id, batch_id)
            REFERENCES tenant_backfill_batch (org_id, project_id, batch_id),
          CHECK (
            (target_org_id IS NULL AND target_project_id IS NULL)
            OR (target_org_id IS NOT NULL AND target_project_id IS NOT NULL)
          ),
          UNIQUE (org_id, project_id, batch_id, resource, key_hash)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE tenant_quarantine_record (
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          quarantine_id BIGSERIAL NOT NULL,
          batch_id UUID NOT NULL,
          resource TEXT NOT NULL,
          key_hash TEXT NOT NULL CHECK (key_hash ~ '^[0-9a-f]{64}$'),
          reason_code TEXT NOT NULL,
          candidate_scope_hashes JSONB NOT NULL DEFAULT '[]'::jsonb
            CHECK (jsonb_typeof(candidate_scope_hashes) = 'array'),
          source_snapshot_hash TEXT NOT NULL CHECK (source_snapshot_hash ~ '^[0-9a-f]{64}$'),
          review_status TEXT NOT NULL DEFAULT 'PENDING'
            CHECK (review_status IN ('PENDING', 'REVIEWED', 'REJECTED')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, quarantine_id),
          FOREIGN KEY (org_id, project_id, batch_id)
            REFERENCES tenant_backfill_batch (org_id, project_id, batch_id),
          UNIQUE (org_id, project_id, batch_id, resource, key_hash)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_backfill_event_batch
          ON tenant_backfill_batch_event (
            org_id, project_id, batch_id, event_id
          )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_ownership_decision_batch
          ON tenant_ownership_decision (
            org_id, project_id, batch_id, resource, decision
          )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_tenant_quarantine_batch
          ON tenant_quarantine_record (
            org_id, project_id, batch_id, resource, review_status
          )
        """
    )
    op.execute(
        """
        CREATE FUNCTION guard_tenant_e3_history_immutable()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
          RAISE EXCEPTION 'tenant E3 history is append-only'
            USING ERRCODE = '23514';
        END;
        $$
        """
    )
    for table in _TABLES:
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_immutable
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_tenant_e3_history_immutable()
            """
        )
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_truncate_guard
            BEFORE TRUNCATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION guard_tenant_e3_history_immutable()
            """
        )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM tenant_backfill_batch LIMIT 1) THEN
            RAISE EXCEPTION 'archive tenant E3 ledger before downgrade';
          END IF;
        END;
        $$
        """
    )
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE IF EXISTS {table}")
    op.execute("DROP FUNCTION IF EXISTS guard_tenant_e3_history_immutable()")
