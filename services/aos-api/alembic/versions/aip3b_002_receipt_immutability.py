"""Make AIP Action Receipt chains database-immutable.

Revision ID: aip3b_002
Revises: aip3b_001
Create Date: 2026-08-11
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "aip3b_002"
down_revision: str | Sequence[str] | None = "aip3b_001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """CREATE FUNCTION guard_aip_action_receipt_immutable() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'AIP_ACTION_RECEIPT_IMMUTABLE' USING ERRCODE='55000';
        END;
        $$ LANGUAGE plpgsql"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_action_receipt_immutable
        BEFORE UPDATE OR DELETE ON aip_action_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_aip_action_receipt_immutable()"""
    )
    op.execute(
        """CREATE TRIGGER trg_aip_action_receipt_truncate_guard
        BEFORE TRUNCATE ON aip_action_receipt
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip_action_receipt_immutable()"""
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_aip_action_receipt_truncate_guard ON aip_action_receipt")
    op.execute("DROP TRIGGER IF EXISTS trg_aip_action_receipt_immutable ON aip_action_receipt")
    op.execute("DROP FUNCTION IF EXISTS guard_aip_action_receipt_immutable()")
