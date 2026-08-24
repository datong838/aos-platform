"""Bind Eval runs and reports to exact EvalContract revisions.

Revision ID: w4_002
Revises: w3_018
Create Date: 2026-08-25
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "w4_002"
down_revision: str | Sequence[str] | None = "w3_018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("aip_eval_run", "aip_eval_report_revision"):
        op.execute(f"ALTER TABLE {table} ADD COLUMN eval_contract_ref JSONB")
        op.execute(
            f"""ALTER TABLE {table} ADD CONSTRAINT ck_{table}_eval_contract_ref_w4_002
            CHECK (eval_contract_ref IS NULL OR (
              jsonb_typeof(eval_contract_ref)='object'
              AND eval_contract_ref->>'resourceType'='EvalContractRevision'
              AND char_length(COALESCE(eval_contract_ref->>'resourceId','')) BETWEEN 1 AND 200
              AND (eval_contract_ref->>'revision') ~ '^[1-9][0-9]*$'
              AND (eval_contract_ref->>'contentHash') ~ '^[0-9a-f]{{64}}$'
            ))"""
        )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM aip_eval_run WHERE eval_contract_ref IS NOT NULL)
           OR EXISTS (SELECT 1 FROM aip_eval_report_revision WHERE eval_contract_ref IS NOT NULL)
        THEN RAISE EXCEPTION 'cannot downgrade w4_002 with EvalContract-bound runs or reports'
          USING ERRCODE='55000'; END IF; END $$"""
    )
    for table in ("aip_eval_report_revision", "aip_eval_run"):
        op.execute(f"ALTER TABLE {table} DROP COLUMN eval_contract_ref")
