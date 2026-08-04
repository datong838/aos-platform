"""TI-5 A3 contract decision lineage from its draft execution context.

Revision ID: 228ti5a3lineage
Revises: 228ti5a2kv
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti5a3lineage"
down_revision: str | Sequence[str] | None = "228ti5a2kv"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_lineage (
          id TEXT PRIMARY KEY,
          draft_id TEXT,
          action_type_id TEXT,
          object_type TEXT,
          object_id TEXT,
          steps JSONB NOT NULL DEFAULT '[]'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE decision_lineage ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE decision_lineage ADD COLUMN project_id TEXT")
    op.execute(
        """
        CREATE TABLE decision_lineage_ownership_ledger (
          ledger_id BIGSERIAL PRIMARY KEY,
          lineage_id_hash TEXT NOT NULL,
          decision TEXT NOT NULL CHECK (
            decision IN ('ASSIGN_FROM_DRAFT','QUARANTINE')
          ),
          org_id TEXT,
          project_id TEXT,
          row_hash TEXT NOT NULL,
          rationale TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE decision_lineage_orphan_quarantine (
          id TEXT PRIMARY KEY,
          draft_id TEXT,
          action_type_id TEXT,
          object_type TEXT,
          object_id TEXT,
          steps JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          original_row_hash TEXT NOT NULL,
          quarantine_reason TEXT NOT NULL,
          quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_decision_lineage_audit_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'decision lineage ownership evidence is append-only';
        END;
        $$
        """
    )
    for table in (
        "decision_lineage_ownership_ledger",
        "decision_lineage_orphan_quarantine",
    ):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_decision_lineage_audit_mutation()
            """
        )

    # A lineage row is assignable only when exactly one parent Draft matches the
    # deterministic lineage id and all duplicated execution-context fields.
    op.execute(
        """
        INSERT INTO decision_lineage_ownership_ledger
          (lineage_id_hash,decision,org_id,project_id,row_hash,rationale)
        SELECT md5(lineage.id),'ASSIGN_FROM_DRAFT',draft.org_id,draft.project_id,
               md5(row_to_json(lineage)::text),
               'unique draft parent plus deterministic id and action/object equality'
        FROM decision_lineage lineage
        JOIN draft_dataset draft
          ON draft.id=lineage.draft_id
         AND lineage.id='lin-' || lineage.draft_id
         AND lineage.action_type_id IS NOT DISTINCT FROM draft.action_type_id
         AND lineage.object_type IS NOT DISTINCT FROM draft.object_type
         AND lineage.object_id IS NOT DISTINCT FROM draft.object_id
        WHERE 1=(
          SELECT COUNT(*) FROM draft_dataset candidate
          WHERE candidate.id=lineage.draft_id
            AND lineage.id='lin-' || lineage.draft_id
            AND lineage.action_type_id IS NOT DISTINCT FROM candidate.action_type_id
            AND lineage.object_type IS NOT DISTINCT FROM candidate.object_type
            AND lineage.object_id IS NOT DISTINCT FROM candidate.object_id
        )
        """
    )
    op.execute(
        """
        UPDATE decision_lineage lineage
           SET org_id=draft.org_id, project_id=draft.project_id
          FROM draft_dataset draft
         WHERE draft.id=lineage.draft_id
           AND lineage.id='lin-' || lineage.draft_id
           AND lineage.action_type_id IS NOT DISTINCT FROM draft.action_type_id
           AND lineage.object_type IS NOT DISTINCT FROM draft.object_type
           AND lineage.object_id IS NOT DISTINCT FROM draft.object_id
           AND 1=(
             SELECT COUNT(*) FROM draft_dataset candidate
             WHERE candidate.id=lineage.draft_id
               AND lineage.id='lin-' || lineage.draft_id
               AND lineage.action_type_id IS NOT DISTINCT FROM candidate.action_type_id
               AND lineage.object_type IS NOT DISTINCT FROM candidate.object_type
               AND lineage.object_id IS NOT DISTINCT FROM candidate.object_id
           )
        """
    )
    op.execute(
        """
        INSERT INTO decision_lineage_ownership_ledger
          (lineage_id_hash,decision,row_hash,rationale)
        SELECT md5(id),'QUARANTINE',md5(row_to_json(lineage)::text),
               'no unique draft parent with deterministic id and action/object equality'
        FROM decision_lineage lineage
        WHERE org_id IS NULL OR project_id IS NULL
        """
    )
    op.execute(
        """
        INSERT INTO decision_lineage_orphan_quarantine
          (id,draft_id,action_type_id,object_type,object_id,steps,created_at,
           original_row_hash,quarantine_reason)
        SELECT id,draft_id,action_type_id,object_type,object_id,steps,created_at,
               md5(row_to_json(lineage)::text),
               'no unique draft parent with deterministic id and action/object equality'
        FROM decision_lineage lineage
        WHERE org_id IS NULL OR project_id IS NULL
        """
    )
    op.execute(
        "DELETE FROM decision_lineage WHERE org_id IS NULL OR project_id IS NULL"
    )

    op.execute("ALTER TABLE decision_lineage ALTER COLUMN org_id SET NOT NULL")
    op.execute("ALTER TABLE decision_lineage ALTER COLUMN project_id SET NOT NULL")
    op.execute("ALTER TABLE decision_lineage DROP CONSTRAINT decision_lineage_pkey")
    op.execute(
        "ALTER TABLE decision_lineage ADD PRIMARY KEY (org_id,project_id,id)"
    )
    op.execute(
        """
        ALTER TABLE decision_lineage
          ADD CONSTRAINT fk_decision_lineage_workspace_ti5a3
          FOREIGN KEY (org_id,project_id)
          REFERENCES twa_workspace(org_id,project_id)
        """
    )
    op.execute(
        """
        ALTER TABLE decision_lineage
          ADD CONSTRAINT fk_decision_lineage_draft_ti5a3
          FOREIGN KEY (org_id,project_id,draft_id)
          REFERENCES draft_dataset(org_id,project_id,id)
        """
    )
    op.execute("ALTER TABLE decision_lineage ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE decision_lineage FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_scope_decision_lineage_ti5a3 ON decision_lineage
          TO PUBLIC
          USING (
            org_id = NULLIF(current_setting('aos.org_id', TRUE), '')
            AND project_id = NULLIF(current_setting('aos.project_id', TRUE), '')
          )
          WITH CHECK (
            org_id = NULLIF(current_setting('aos.org_id', TRUE), '')
            AND project_id = NULLIF(current_setting('aos.project_id', TRUE), '')
          )
        """
    )
    op.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON decision_lineage TO aos_runtime")
    op.execute("REVOKE ALL ON decision_lineage_ownership_ledger FROM aos_runtime")
    op.execute("REVOKE ALL ON decision_lineage_orphan_quarantine FROM aos_runtime")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT id FROM (
              SELECT id FROM decision_lineage
              UNION ALL
              SELECT id FROM decision_lineage_orphan_quarantine
            ) all_lineage
            GROUP BY id HAVING COUNT(*) > 1
          ) THEN
            RAISE EXCEPTION 'cannot downgrade decision_lineage with id collisions';
          END IF;
        END $$
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_scope_decision_lineage_ti5a3 ON decision_lineage")
    op.execute("ALTER TABLE decision_lineage NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE decision_lineage DISABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE decision_lineage DROP CONSTRAINT IF EXISTS "
        "fk_decision_lineage_draft_ti5a3"
    )
    op.execute(
        "ALTER TABLE decision_lineage DROP CONSTRAINT IF EXISTS "
        "fk_decision_lineage_workspace_ti5a3"
    )
    op.execute("ALTER TABLE decision_lineage DROP CONSTRAINT decision_lineage_pkey")
    op.execute("ALTER TABLE decision_lineage ADD PRIMARY KEY (id)")
    op.execute(
        """
        INSERT INTO decision_lineage
          (id,draft_id,action_type_id,object_type,object_id,steps,created_at,
           org_id,project_id)
        SELECT id,draft_id,action_type_id,object_type,object_id,steps,created_at,
               NULL,NULL
        FROM decision_lineage_orphan_quarantine
        """
    )
    op.execute("ALTER TABLE decision_lineage DROP COLUMN project_id")
    op.execute("ALTER TABLE decision_lineage DROP COLUMN org_id")
    for table in (
        "decision_lineage_ownership_ledger",
        "decision_lineage_orphan_quarantine",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP TABLE decision_lineage_orphan_quarantine")
    op.execute("DROP TABLE decision_lineage_ownership_ledger")
    op.execute("DROP FUNCTION reject_decision_lineage_audit_mutation()")
