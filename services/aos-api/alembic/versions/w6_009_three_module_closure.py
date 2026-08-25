"""Three-module partial, usage, effect and handoff closure bridge (W6-09).

Revision ID: w6_009
Revises: w6_008
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w6_009"
down_revision: str | Sequence[str] | None = "w6_008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BINDING_TABLES = (
    "ecommerce_three_module_usage_binding_revision",
    "ecommerce_three_module_effect_binding_revision",
    "ecommerce_three_module_handoff_binding_revision",
)


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_scope ON {table}
      USING (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
      WITH CHECK (org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
    op.execute(f"GRANT SELECT, INSERT ON {table} TO aos_runtime")


def upgrade() -> None:
    op.execute("""
    CREATE TABLE ecommerce_three_module_closure_revision (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      closure_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision=1),
      module TEXT NOT NULL CHECK(module IN ('creator','price','customer')),
      source_id TEXT NOT NULL,
      content_hash CHAR(64) NOT NULL CHECK(content_hash ~ '^[0-9a-f]{64}$'),
      authority_data JSONB NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
      created_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,closure_id,revision),
      FOREIGN KEY(org_id,project_id) REFERENCES meta_workspace(org_id,project_id)
    )""")
    _scope("ecommerce_three_module_closure_revision")
    op.execute("CREATE INDEX ecommerce_three_module_closure_latest_idx ON ecommerce_three_module_closure_revision(org_id,project_id,module,created_at DESC)")
    for table in _BINDING_TABLES:
        op.execute(f"""
        CREATE TABLE {table} (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          binding_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision=1),
          module TEXT, closure_id TEXT NOT NULL,
          content_hash CHAR(64) NOT NULL CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
          authority_data JSONB NOT NULL CHECK(jsonb_typeof(authority_data)='object'),
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,binding_id,revision),
          FOREIGN KEY(org_id,project_id,closure_id,revision)
            REFERENCES ecommerce_three_module_closure_revision(org_id,project_id,closure_id,revision)
        )""")
        _scope(table)
        op.execute(f"CREATE INDEX {table}_closure_idx ON {table}(org_id,project_id,closure_id,created_at DESC)")


def downgrade() -> None:
    for table in reversed(_BINDING_TABLES):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TABLE ecommerce_three_module_closure_revision")
