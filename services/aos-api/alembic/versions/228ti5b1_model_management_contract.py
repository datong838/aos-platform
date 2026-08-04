"""TI-5 B1 tenant contract for model-management tables.

Revision ID: 228ti5b1models
Revises: 228ti5a3lineage
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti5b1models"
down_revision: str | Sequence[str] | None = "228ti5a3lineage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = (
    "model_catalog",
    "model_provider",
    "registered_models",
    "provider_health",
    "model_route",
    "capacity_limits",
    "capacity_usage",
)


def upgrade() -> None:
    # Legacy development bootstrap created these tables lazily. B1 transfers
    # ownership to Alembic while preserving the existing column contract.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS model_catalog (
          id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL,
          display_name TEXT NOT NULL DEFAULT '',
          capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
          context_window INTEGER NOT NULL DEFAULT 4096,
          input_price NUMERIC(12,6) NOT NULL DEFAULT 0,
          output_price NUMERIC(12,6) NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'ga', description TEXT NOT NULL DEFAULT '',
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS model_provider (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, base_url TEXT NOT NULL DEFAULT '',
          api_key_masked TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'normal',
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS registered_models (
          id TEXT PRIMARY KEY, model_id TEXT NOT NULL, alias TEXT NOT NULL DEFAULT '',
          quota JSONB NOT NULL DEFAULT '{}'::jsonb,
          status TEXT NOT NULL DEFAULT 'enabled',
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS provider_health (
          id TEXT PRIMARY KEY, provider_id TEXT NOT NULL,
          p50_latency_ms INTEGER NOT NULL DEFAULT 0,
          availability_pct NUMERIC(6,3) NOT NULL DEFAULT 100.000,
          checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project'
        );
        CREATE TABLE IF NOT EXISTS model_route (
          id TEXT PRIMARY KEY, task_type TEXT NOT NULL, primary_model TEXT NOT NULL,
          fallback_model TEXT NOT NULL DEFAULT '',
          outbound_policy TEXT NOT NULL DEFAULT 'deny_public',
          priority INTEGER NOT NULL DEFAULT 100, enabled BOOLEAN NOT NULL DEFAULT TRUE,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS capacity_limits (
          id TEXT PRIMARY KEY, scope TEXT NOT NULL, scope_key TEXT NOT NULL DEFAULT '',
          rpm_limit INTEGER NOT NULL DEFAULT 60,
          tpm_limit INTEGER NOT NULL DEFAULT 60000,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS capacity_usage (
          id TEXT PRIMARY KEY, day DATE NOT NULL,
          total_requests INTEGER NOT NULL DEFAULT 0,
          total_tokens BIGINT NOT NULL DEFAULT 0,
          cost NUMERIC(14,6) NOT NULL DEFAULT 0,
          peak_rpm INTEGER NOT NULL DEFAULT 0,
          org_id TEXT NOT NULL DEFAULT 'dev-org',
          project_id TEXT NOT NULL DEFAULT 'dev-project',
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_model_route_task
          ON model_route (org_id,project_id,task_type);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_capacity_limits_scope
          ON capacity_limits (org_id,project_id,scope,scope_key);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_capacity_usage_day
          ON capacity_usage (org_id,project_id,day);
        CREATE INDEX IF NOT EXISTS idx_provider_health_provider
          ON provider_health (provider_id,checked_at DESC);
        CREATE INDEX IF NOT EXISTS idx_registered_models_org
          ON registered_models (org_id,project_id);
        """
    )
    # Refuse to infer ownership. The existing 65 rows already carry a scope;
    # every scope and child must be valid before any structural change begins.
    for table in TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT 1 FROM {table} resource
                LEFT JOIN twa_workspace workspace
                  ON workspace.org_id=resource.org_id
                 AND workspace.project_id=resource.project_id
                WHERE resource.org_id IS NULL OR resource.project_id IS NULL
                   OR workspace.org_id IS NULL
              ) THEN
                RAISE EXCEPTION '{table} contains unowned or unknown workspace rows';
              END IF;
            END $$
            """
        )
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM provider_health health
            LEFT JOIN model_provider provider
              ON provider.org_id=health.org_id
             AND provider.project_id=health.project_id
             AND provider.id=health.provider_id
            WHERE provider.id IS NULL
          ) THEN
            RAISE EXCEPTION 'provider_health contains a missing scoped provider';
          END IF;
          IF EXISTS (
            SELECT 1 FROM registered_models registration
            LEFT JOIN model_catalog catalog
              ON catalog.org_id=registration.org_id
             AND catalog.project_id=registration.project_id
             AND catalog.id=registration.model_id
            WHERE catalog.id IS NULL
          ) THEN
            RAISE EXCEPTION 'registered_models contains a missing scoped catalog model';
          END IF;
        END $$
        """
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN org_id DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN project_id DROP DEFAULT")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (org_id,project_id,id)")
        op.execute(
            f"""
            ALTER TABLE {table}
              ADD CONSTRAINT fk_{table}_workspace_ti5b1
              FOREIGN KEY (org_id,project_id)
              REFERENCES twa_workspace(org_id,project_id)
            """
        )

    op.execute(
        """
        ALTER TABLE provider_health
          ADD CONSTRAINT fk_provider_health_provider_ti5b1
          FOREIGN KEY (org_id,project_id,provider_id)
          REFERENCES model_provider(org_id,project_id,id)
          ON DELETE CASCADE
        """
    )
    op.execute(
        """
        ALTER TABLE registered_models
          ADD CONSTRAINT fk_registered_models_catalog_ti5b1
          FOREIGN KEY (org_id,project_id,model_id)
          REFERENCES model_catalog(org_id,project_id,id)
        """
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_scope_{table}_ti5b1 ON {table}
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
        op.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO aos_runtime")


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"""
            DO $$
            BEGIN
              IF EXISTS (
                SELECT id FROM {table} GROUP BY id HAVING COUNT(*) > 1
              ) THEN
                RAISE EXCEPTION 'cannot downgrade {table} with cross-scope id collisions';
              END IF;
            END $$
            """
        )

    op.execute(
        "ALTER TABLE provider_health DROP CONSTRAINT IF EXISTS "
        "fk_provider_health_provider_ti5b1"
    )
    op.execute(
        "ALTER TABLE registered_models DROP CONSTRAINT IF EXISTS "
        "fk_registered_models_catalog_ti5b1"
    )
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_scope_{table}_ti5b1 ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS fk_{table}_workspace_ti5b1"
        )
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(f"ALTER TABLE {table} ADD PRIMARY KEY (id)")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN org_id SET DEFAULT 'dev-org'")
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN project_id SET DEFAULT 'dev-project'"
        )
