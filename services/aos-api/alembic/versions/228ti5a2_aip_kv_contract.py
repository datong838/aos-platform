"""TI-5 A2 contract legacy AIP KV into tenant-scoped storage.

Revision ID: 228ti5a2kv
Revises: 228ti5a1aip
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti5a2kv"
down_revision: str | Sequence[str] | None = "228ti5a1aip"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEST_ORG_KEYS = (
    "action_plugin_installs",
    "analytics_notebook_sessions",
    "analytics_vertex_experiments",
    "apollo_ops_changes",
    "channel_outbox",
    "channel_plugin_installs",
    "channel_webhooks",
    "connector_plugin_installs",
    "embedding_plugin_installs",
    "global_circuit_config",
    "llm_provider_configs",
    "llm_provider_custom",
    "llm_provider_installs",
    "llm_provider_ready",
    "model_provider_call_logs",
    "model_provider_credentials",
    "model_provider_security",
    "model_router_v2",
    "model_routes",
    "parser_plugin_installs",
    "tools_config",
    "vector_index:dev-org__dev-project__demo-pipe-wo",
    "widget_plugin_installs",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS meta_aip_kv (
          key TEXT PRIMARY KEY,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE meta_aip_kv ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE meta_aip_kv ADD COLUMN project_id TEXT")
    op.execute(
        """
        CREATE TABLE aip_kv_ownership_ledger (
          ledger_id BIGSERIAL PRIMARY KEY,
          key_hash TEXT NOT NULL,
          decision TEXT NOT NULL CHECK (decision IN ('ASSIGN_TEST_ORG','QUARANTINE')),
          org_id TEXT,
          project_id TEXT,
          payload_hash TEXT NOT NULL,
          rationale TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_aip_kv_ledger_mutation()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          RAISE EXCEPTION 'aip_kv_ownership_ledger is append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_aip_kv_ledger_append_only
        BEFORE UPDATE OR DELETE ON aip_kv_ownership_ledger
        FOR EACH ROW EXECUTE FUNCTION reject_aip_kv_ledger_mutation()
        """
    )
    quoted = ",".join("'" + key.replace("'", "''") + "'" for key in TEST_ORG_KEYS)
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM meta_aip_kv WHERE key NOT IN ({quoted})) THEN
            RAISE EXCEPTION 'meta_aip_kv contains keys outside the frozen test-data allowlist';
          END IF;
          IF EXISTS (SELECT 1 FROM meta_aip_kv) AND NOT EXISTS (
            SELECT 1 FROM twa_workspace
            WHERE org_id='dev-org' AND project_id='dev-project'
          ) THEN
            RAISE EXCEPTION 'test organization workspace is missing';
          END IF;
        END $$
        """
    )
    op.execute(
        f"""
        INSERT INTO aip_kv_ownership_ledger
          (key_hash,decision,org_id,project_id,payload_hash,rationale)
        SELECT md5(key),'ASSIGN_TEST_ORG','dev-org','dev-project',
               md5(payload::text),
               'explicit legacy key allowlist plus user-declared local test-data baseline'
        FROM meta_aip_kv
        WHERE key IN ({quoted})
        """
    )
    op.execute(
        "UPDATE meta_aip_kv SET org_id='dev-org',project_id='dev-project' "
        "WHERE org_id IS NULL AND project_id IS NULL"
    )
    op.execute("ALTER TABLE meta_aip_kv ALTER COLUMN org_id SET NOT NULL")
    op.execute("ALTER TABLE meta_aip_kv ALTER COLUMN project_id SET NOT NULL")
    op.execute("ALTER TABLE meta_aip_kv DROP CONSTRAINT meta_aip_kv_pkey")
    op.execute("ALTER TABLE meta_aip_kv ADD PRIMARY KEY (org_id,project_id,key)")
    op.execute(
        """
        ALTER TABLE meta_aip_kv
          ADD CONSTRAINT fk_meta_aip_kv_workspace_ti5a2
          FOREIGN KEY (org_id,project_id)
          REFERENCES twa_workspace(org_id,project_id)
        """
    )
    op.execute("ALTER TABLE meta_aip_kv ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE meta_aip_kv FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_scope_meta_aip_kv_ti5a2 ON meta_aip_kv
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
    op.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON meta_aip_kv TO aos_runtime")
    op.execute("REVOKE ALL ON aip_kv_ownership_ledger FROM aos_runtime")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT key FROM meta_aip_kv GROUP BY key HAVING COUNT(*) > 1
          ) THEN
            RAISE EXCEPTION 'cannot downgrade meta_aip_kv with cross-scope key collisions';
          END IF;
        END $$
        """
    )
    op.execute("DROP POLICY IF EXISTS tenant_scope_meta_aip_kv_ti5a2 ON meta_aip_kv")
    op.execute("ALTER TABLE meta_aip_kv NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE meta_aip_kv DISABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE meta_aip_kv DROP CONSTRAINT IF EXISTS "
        "fk_meta_aip_kv_workspace_ti5a2"
    )
    op.execute("ALTER TABLE meta_aip_kv DROP CONSTRAINT meta_aip_kv_pkey")
    op.execute("ALTER TABLE meta_aip_kv ADD PRIMARY KEY (key)")
    op.execute("ALTER TABLE meta_aip_kv DROP COLUMN project_id")
    op.execute("ALTER TABLE meta_aip_kv DROP COLUMN org_id")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_aip_kv_ledger_append_only "
        "ON aip_kv_ownership_ledger"
    )
    op.execute("DROP TABLE aip_kv_ownership_ledger")
    op.execute("DROP FUNCTION reject_aip_kv_ledger_mutation()")
