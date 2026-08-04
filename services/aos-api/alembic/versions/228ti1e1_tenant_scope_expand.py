"""TI-1 E1 nullable tenant scope and NOT VALID relationship expansion.

Revision ID: 228ti1e1expand
Revises: 228assetintegration
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti1e1expand"
down_revision: str | Sequence[str] | None = "228assetintegration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FOREIGN_KEYS = (
    (
        "fk_meta_workspace_org_ti1",
        "meta_workspace",
        "(org_id)",
        "meta_org",
        "(id)",
    ),
    (
        "fk_meta_membership_workspace_ti1",
        "meta_membership",
        "(org_id, project_id)",
        "meta_workspace",
        "(org_id, project_id)",
    ),
    (
        "fk_twa_ws_member_workspace_ti1",
        "twa_ws_member",
        "(org_id, project_id)",
        "twa_workspace",
        "(org_id, project_id)",
    ),
    (
        "fk_twa_invite_workspace_ti1",
        "twa_invite",
        "(org_id, project_id)",
        "twa_workspace",
        "(org_id, project_id)",
    ),
    (
        "fk_twa_join_request_workspace_ti1",
        "twa_join_request",
        "(org_id, project_id)",
        "twa_workspace",
        "(org_id, project_id)",
    ),
    (
        "fk_twa_audit_workspace_ti1",
        "twa_audit",
        "(org_id, project_id)",
        "twa_workspace",
        "(org_id, project_id)",
    ),
    (
        "fk_authz_tuple_workspace_ti1",
        "authz_tuple",
        "(org_id, project_id)",
        "twa_workspace",
        "(org_id, project_id)",
    ),
)


def upgrade() -> None:
    op.execute("ALTER TABLE authz_tuple ADD COLUMN org_id TEXT")
    op.execute("ALTER TABLE authz_tuple ADD COLUMN project_id TEXT")
    op.execute(
        """
        CREATE INDEX idx_authz_tuple_tenant_lookup
          ON authz_tuple (org_id, project_id, user_key, relation, object_key)
         WHERE org_id IS NOT NULL AND project_id IS NOT NULL
        """
    )
    for name, child, child_columns, parent, parent_columns in _FOREIGN_KEYS:
        op.execute(
            f"ALTER TABLE {child} ADD CONSTRAINT {name} "
            f"FOREIGN KEY {child_columns} REFERENCES {parent} {parent_columns} "
            "NOT VALID"
        )


def downgrade() -> None:
    for name, child, *_rest in reversed(_FOREIGN_KEYS):
        op.execute(f"ALTER TABLE {child} DROP CONSTRAINT IF EXISTS {name}")
    op.execute("DROP INDEX IF EXISTS idx_authz_tuple_tenant_lookup")
    op.execute("ALTER TABLE authz_tuple DROP COLUMN IF EXISTS project_id")
    op.execute("ALTER TABLE authz_tuple DROP COLUMN IF EXISTS org_id")
