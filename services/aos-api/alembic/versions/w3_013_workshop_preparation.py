"""Add tenant-safe Workshop preparation intent and immutable result authority.

Revision ID: w3_013
Revises: w3_011
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "w3_013"
down_revision: str | Sequence[str] | None = "w3_011"
branch_labels = None
depends_on = None


def _tenant_policy(table: str, *, mutable: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_w3_013 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    permissions = "SELECT,INSERT,UPDATE" if mutable else "SELECT,INSERT"
    op.execute(f"GRANT {permissions} ON {table} TO aos_runtime")
    op.execute(f"REVOKE DELETE,TRUNCATE ON {table} FROM aos_runtime")
    if not mutable:
        op.execute(
            f"""CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()"""
        )


def upgrade() -> None:
    op.execute(
        """CREATE TABLE aip_workshop_preparation_intent (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, preparation_id TEXT NOT NULL,
          module_id TEXT NOT NULL, operation TEXT NOT NULL DEFAULT 'prepare',
          idempotency_key TEXT NOT NULL, request_hash TEXT NOT NULL,
          request_body JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,preparation_id),
          UNIQUE(org_id,project_id,operation,idempotency_key),
          CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(request_body)='object'),
          CHECK(status IN ('pending','complete','unknown'))
        )"""
    )
    op.execute(
        """CREATE TABLE aip_workshop_preparation_result (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, preparation_id TEXT NOT NULL,
          revision BIGINT NOT NULL DEFAULT 1, request_hash TEXT NOT NULL,
          result_hash TEXT NOT NULL, result_body JSONB NOT NULL,
          created_by TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY(org_id,project_id,preparation_id,revision),
          UNIQUE(org_id,project_id,preparation_id,result_hash),
          FOREIGN KEY(org_id,project_id,preparation_id)
            REFERENCES aip_workshop_preparation_intent(org_id,project_id,preparation_id),
          CHECK(revision=1), CHECK(request_hash ~ '^[0-9a-f]{64}$'),
          CHECK(result_hash ~ '^[0-9a-f]{64}$'),
          CHECK(jsonb_typeof(result_body)='object')
        )"""
    )
    op.execute(
        """CREATE FUNCTION guard_workshop_preparation_intent_w3_013()
        RETURNS trigger AS $$ BEGIN
          IF NEW.org_id IS DISTINCT FROM OLD.org_id
             OR NEW.project_id IS DISTINCT FROM OLD.project_id
             OR NEW.preparation_id IS DISTINCT FROM OLD.preparation_id
             OR NEW.module_id IS DISTINCT FROM OLD.module_id
             OR NEW.operation IS DISTINCT FROM OLD.operation
             OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
             OR NEW.request_hash IS DISTINCT FROM OLD.request_hash
             OR NEW.request_body IS DISTINCT FROM OLD.request_body
             OR NEW.created_by IS DISTINCT FROM OLD.created_by
             OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Workshop preparation intent identity is immutable'
              USING ERRCODE = '55000';
          END IF;
          IF OLD.status='complete'
             OR NEW.status NOT IN ('complete','unknown')
             OR NEW.updated_at<=OLD.updated_at THEN
            RAISE EXCEPTION 'invalid Workshop preparation status transition'
              USING ERRCODE = '55000';
          END IF;
          RETURN NEW;
        END $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER trg_workshop_preparation_intent_guard_w3_013
        BEFORE UPDATE ON aip_workshop_preparation_intent
        FOR EACH ROW EXECUTE FUNCTION guard_workshop_preparation_intent_w3_013()"""
    )
    _tenant_policy("aip_workshop_preparation_intent", mutable=True)
    _tenant_policy("aip_workshop_preparation_result", mutable=False)
    op.execute(
        "CREATE INDEX aip_workshop_preparation_module_idx ON "
        "aip_workshop_preparation_intent(org_id,project_id,module_id,created_at DESC)"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM aip_workshop_preparation_result LIMIT 1) THEN
          RAISE EXCEPTION 'cannot downgrade w3_013 with canonical preparation results'
            USING ERRCODE = '55000';
        END IF;
        END $$"""
    )
    op.execute("DROP TABLE aip_workshop_preparation_result CASCADE")
    op.execute("DROP TABLE aip_workshop_preparation_intent CASCADE")
    op.execute("DROP FUNCTION guard_workshop_preparation_intent_w3_013()")
