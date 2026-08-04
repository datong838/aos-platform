"""TI-4 C1 add NOT VALID workspace alias foreign keys to e-commerce tables.

Revision ID: 228ti4c1expand
Revises: 228ti3e7contract
Create Date: 2026-08-04
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "228ti4c1expand"
down_revision: str | Sequence[str] | None = "228ti3e7contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ECOM_WORKSPACE_TABLES = (
    "ecom_ingest_receipt",
    "ecom_link",
    "ecom_object",
    "ecom_sync_checkpoint",
    "oauth_token_store",
)


def upgrade() -> None:
    for table in ECOM_WORKSPACE_TABLES:
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT fk_{table}_workspace_ti4 "
            "FOREIGN KEY (org_id, workspace_id) "
            "REFERENCES twa_workspace(org_id, project_id) NOT VALID"
        )


def downgrade() -> None:
    for table in reversed(ECOM_WORKSPACE_TABLES):
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT fk_{table}_workspace_ti4"
        )
