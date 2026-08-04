"""TI-2 E4 validate Module identity foreign keys.

Revision ID: 228ti2e4validate
Revises: 228ti2e1expand
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti2e4validate"
down_revision: str | Sequence[str] | None = "228ti2e1expand"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CHILDREN = (
    "module_canvas_config",
    "module_deployment",
    "module_events",
    "module_interface",
    "module_query",
    "module_variable",
    "module_widget_instance",
)

_CONSTRAINTS = (
    ("meta_module", "fk_meta_module_installation_ti2"),
    ("meta_module", "fk_meta_module_active_overlay_ti2"),
    *((table, f"fk_{table}_module_ti2") for table in _CHILDREN),
    ("module_instance_overlay", "fk_module_instance_overlay_module_ti2"),
    (
        "module_user_view_preference",
        "fk_module_user_view_preference_module_ti2",
    ),
)


def upgrade() -> None:
    for table, constraint in _CONSTRAINTS:
        op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {constraint}")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE module_user_view_preference "
        "DROP CONSTRAINT fk_module_user_view_preference_module_ti2"
    )
    op.execute(
        "ALTER TABLE module_user_view_preference "
        "ADD CONSTRAINT fk_module_user_view_preference_module_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk) "
        "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
    )
    op.execute(
        "ALTER TABLE module_instance_overlay "
        "DROP CONSTRAINT fk_module_instance_overlay_module_ti2"
    )
    op.execute(
        "ALTER TABLE module_instance_overlay "
        "ADD CONSTRAINT fk_module_instance_overlay_module_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk) "
        "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
    )
    for table in reversed(_CHILDREN):
        constraint = f"fk_{table}_module_ti2"
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            "FOREIGN KEY (org_id, project_id, module_pk) "
            "REFERENCES meta_module (org_id, project_id, module_pk) NOT VALID"
        )
    op.execute(
        "ALTER TABLE meta_module DROP CONSTRAINT fk_meta_module_active_overlay_ti2"
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT fk_meta_module_active_overlay_ti2 "
        "FOREIGN KEY (org_id, project_id, module_pk, active_overlay_revision) "
        "REFERENCES module_instance_overlay "
        "(org_id, project_id, module_pk, overlay_revision) NOT VALID"
    )
    op.execute(
        "ALTER TABLE meta_module DROP CONSTRAINT fk_meta_module_installation_ti2"
    )
    op.execute(
        "ALTER TABLE meta_module ADD CONSTRAINT fk_meta_module_installation_ti2 "
        "FOREIGN KEY (org_id, project_id, installation_id) "
        "REFERENCES bundle_installation "
        "(org_id, project_id, installation_pk) NOT VALID"
    )
