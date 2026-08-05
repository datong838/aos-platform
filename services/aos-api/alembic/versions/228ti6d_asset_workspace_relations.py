"""TI-6 2D anchor asset-control roots to the canonical workspace.

Revision ID: 228ti6drelations
Revises: 228ti6cassets
Create Date: 2026-08-05
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti6drelations"
down_revision: str | Sequence[str] | None = "228ti6cassets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RELATIONS = {
    "bundle_composition": "fk_bundle_composition_workspace_ti6",
    "bundle_installation_command": "fk_bundle_installation_command_workspace_ti6",
    "integration_case": "fk_integration_case_workspace_ti6",
}


def upgrade() -> None:
    for table, constraint in RELATIONS.items():
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {constraint} "
            "FOREIGN KEY (org_id, project_id) "
            "REFERENCES meta_workspace(org_id, project_id) ON DELETE RESTRICT"
        )


def downgrade() -> None:
    for table, constraint in reversed(RELATIONS.items()):
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {constraint}")
