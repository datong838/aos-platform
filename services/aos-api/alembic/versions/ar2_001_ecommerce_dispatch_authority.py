"""Tenant-scoped ecommerce operation dispatch authority; empty by default."""

from alembic import op

revision = "ar2_001"
down_revision = "ar1_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE extension_operation_dispatch_binding (
      org_id text NOT NULL,
      project_id text NOT NULL,
      operation_id text NOT NULL CHECK(
        length(operation_id) BETWEEN 1 AND 160
        AND operation_id ~ '^[A-Za-z][A-Za-z0-9_]*$'
      ),
      handler_kind text NOT NULL CHECK(handler_kind IN ('legacy','extension')),
      installation_id uuid,
      generation uuid,
      execution_epoch bigint CHECK(execution_epoch > 0),
      operation_fence boolean NOT NULL DEFAULT true,
      revision bigint NOT NULL CHECK(revision > 0),
      cutover_group_id uuid NOT NULL,
      cutover_group_revision bigint NOT NULL CHECK(cutover_group_revision > 0),
      updated_by text NOT NULL CHECK(length(updated_by) BETWEEN 1 AND 240),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id, project_id, operation_id),
      FOREIGN KEY(org_id, project_id, installation_id, generation)
        REFERENCES extension_runtime_binding(org_id, project_id, installation_id, generation),
      CHECK(
        (handler_kind='legacy' AND installation_id IS NULL
          AND generation IS NULL AND execution_epoch IS NULL)
        OR
        (handler_kind='extension' AND installation_id IS NOT NULL
          AND generation IS NOT NULL AND execution_epoch IS NOT NULL)
      )
    );
    CREATE INDEX extension_operation_dispatch_cutover_group
      ON extension_operation_dispatch_binding(
        org_id, project_id, cutover_group_id, operation_id,
        installation_id, generation
      );
    ALTER TABLE extension_operation_dispatch_binding ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_operation_dispatch_binding FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_operation_dispatch_binding
      USING(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON extension_operation_dispatch_binding FROM PUBLIC;
    GRANT SELECT ON extension_operation_dispatch_binding TO aos_runtime;
    """)


def downgrade():
    raise RuntimeError("operation dispatch authority must be retained")
