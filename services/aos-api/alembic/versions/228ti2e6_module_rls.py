"""TI-2 E6 enforce tenant RLS for the Module instance family.

Revision ID: 228ti2e6rls
Revises: 228ti2e4validate
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti2e6rls"
down_revision: str | Sequence[str] | None = "228ti2e4validate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLE = "aos_runtime"
SCOPED_TABLES = (
    "meta_module",
    "module_canvas_config",
    "module_deployment",
    "module_events",
    "module_interface",
    "module_query",
    "module_variable",
    "module_widget_instance",
    "module_instance_overlay",
    "module_user_view_preference",
)
ORG_TABLES = ("module_organization_profile",)

_ORG_MATCH = "org_id = current_setting('aos.org_id', true)"
_SCOPE_MATCH = (
    _ORG_MATCH
    + " AND project_id = current_setting('aos.project_id', true)"
)


def upgrade() -> None:
    op.execute(
        f"""
        DO $role$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{RUNTIME_ROLE}') THEN
            CREATE ROLE {RUNTIME_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB
              NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
          END IF;
          ALTER ROLE {RUNTIME_ROLE} NOLOGIN NOSUPERUSER NOCREATEDB
            NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
          IF NOT pg_has_role(current_user, '{RUNTIME_ROLE}', 'MEMBER') THEN
            EXECUTE format('GRANT {RUNTIME_ROLE} TO %I', current_user);
          END IF;
        END
        $role$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {RUNTIME_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        f"TO {RUNTIME_ROLE}"
    )
    op.execute(
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {RUNTIME_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {RUNTIME_ROLE}"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT USAGE, SELECT ON SEQUENCES TO {RUNTIME_ROLE}"
    )
    for table in (*SCOPED_TABLES, *ORG_TABLES):
        predicate = _SCOPE_MATCH if table in SCOPED_TABLES else _ORG_MATCH
        policy = f"tenant_scope_{table}_ti2"
        op.execute(
            f"CREATE POLICY {policy} ON {table} FOR ALL TO {RUNTIME_ROLE} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed((*SCOPED_TABLES, *ORG_TABLES)):
        policy = f"tenant_scope_{table}_ti2"
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
