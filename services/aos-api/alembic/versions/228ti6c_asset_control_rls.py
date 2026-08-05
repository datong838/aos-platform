"""TI-6 2C enforce RLS for asset installation and Integration Case stores.

Revision ID: 228ti6cassets
Revises: 228ti6bcontract
Create Date: 2026-08-05
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti6cassets"
down_revision: str | Sequence[str] | None = "228ti6bcontract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "bundle_composition",
    "bundle_composition_lock",
    "bundle_installation",
    "bundle_installation_command",
    "bundle_installation_decision",
    "bundle_installation_event",
    "bundle_installation_revision",
    "integration_case",
    "integration_case_command",
    "integration_case_projection",
    "integration_evidence",
    "integration_evidence_snapshot",
    "integration_instance",
    "integration_instance_revision",
    "integration_stage_event",
)
PREDICATE = (
    "org_id = current_setting('aos.org_id', true) AND "
    "project_id = current_setting('aos.project_id', true)"
)


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"CREATE POLICY tenant_scope_{table}_ti6 ON {table} FOR ALL TO aos_runtime "
            f"USING ({PREDICATE}) WITH CHECK ({PREDICATE})"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_scope_{table}_ti6 ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
