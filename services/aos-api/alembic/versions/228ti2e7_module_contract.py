"""TI-2 E7 contract Module identities and tenant-scoped primary keys.

Revision ID: 228ti2e7contract
Revises: 228ti2e6rls
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti2e7contract"
down_revision: str | Sequence[str] | None = "228ti2e6rls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ID_CHILDREN = (
    "module_deployment",
    "module_events",
    "module_query",
    "module_variable",
    "module_widget_instance",
)
_MODULE_CHILDREN = ("module_canvas_config", "module_interface")
_ALL_CHILDREN = (*_MODULE_CHILDREN, *_ID_CHILDREN)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE module_event_orphan_quarantine (
          id TEXT NOT NULL,
          module_id TEXT NOT NULL,
          name TEXT NOT NULL,
          trigger_config JSONB NOT NULL,
          action_config JSONB NOT NULL,
          enabled BOOLEAN NOT NULL,
          sort_order INTEGER NOT NULL,
          org_id TEXT NOT NULL,
          project_id TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL,
          reason_code TEXT NOT NULL DEFAULT 'MISSING_PARENT_MODULE',
          source_revision TEXT NOT NULL DEFAULT '228ti2e6rls',
          quarantined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          PRIMARY KEY (org_id, project_id, id)
        )
        """
    )
    op.execute("REVOKE ALL ON module_event_orphan_quarantine FROM aos_runtime")
    op.execute(
        """
        INSERT INTO module_event_orphan_quarantine (
          id, module_id, name, trigger_config, action_config, enabled,
          sort_order, org_id, project_id, created_at, updated_at
        )
        SELECT id, module_id, name, trigger_config, action_config, enabled,
               sort_order, org_id, project_id, created_at, updated_at
          FROM module_events
         WHERE module_pk IS NULL
        """
    )
    op.execute("DELETE FROM module_events WHERE module_pk IS NULL")

    op.execute("ALTER TABLE meta_module ALTER COLUMN module_pk SET NOT NULL")
    op.execute("ALTER TABLE meta_module ALTER COLUMN module_id SET NOT NULL")
    for table in _ALL_CHILDREN:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN module_pk SET NOT NULL")

    op.execute("ALTER TABLE meta_module DROP CONSTRAINT meta_module_pkey")
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT meta_module_pkey "
        "PRIMARY KEY (org_id, project_id, module_pk)"
    )
    for table in _MODULE_CHILDREN:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            "PRIMARY KEY (org_id, project_id, module_pk)"
        )
    for table in _ID_CHILDREN:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            "PRIMARY KEY (org_id, project_id, id)"
        )


def downgrade() -> None:
    checks = [
        "EXISTS (SELECT 1 FROM meta_module GROUP BY id HAVING COUNT(*) > 1)",
        *(
            f"EXISTS (SELECT 1 FROM {table} GROUP BY module_id HAVING COUNT(*) > 1)"
            for table in _MODULE_CHILDREN
        ),
        *(
            f"EXISTS (SELECT 1 FROM {table} GROUP BY id HAVING COUNT(*) > 1)"
            for table in _ID_CHILDREN
        ),
        "EXISTS (SELECT 1 FROM module_event_orphan_quarantine q "
        "JOIN module_events e ON e.id=q.id)",
    ]
    op.execute(
        "DO $contract$ BEGIN "
        f"IF {' OR '.join(checks)} THEN "
        "RAISE EXCEPTION 'TI-2 E7 downgrade blocked by legacy key collision' "
        "USING ERRCODE='23505'; END IF; END $contract$;"
    )

    for table in reversed(_ID_CHILDREN):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey PRIMARY KEY (id)"
        )
    for table in reversed(_MODULE_CHILDREN):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {table}_pkey")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_pkey "
            "PRIMARY KEY (module_id)"
        )
    op.execute("ALTER TABLE meta_module DROP CONSTRAINT meta_module_pkey")
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT meta_module_pkey PRIMARY KEY (id)"
    )

    op.execute("ALTER TABLE meta_module ALTER COLUMN module_pk DROP NOT NULL")
    op.execute("ALTER TABLE meta_module ALTER COLUMN module_id DROP NOT NULL")
    for table in _ALL_CHILDREN:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN module_pk DROP NOT NULL")

    op.execute(
        """
        INSERT INTO module_events (
          id, module_id, name, trigger_config, action_config, enabled,
          sort_order, org_id, project_id, created_at, updated_at, module_pk
        )
        SELECT id, module_id, name, trigger_config, action_config, enabled,
               sort_order, org_id, project_id, created_at, updated_at, NULL
          FROM module_event_orphan_quarantine
        """
    )
    op.execute("DROP TABLE module_event_orphan_quarantine")
