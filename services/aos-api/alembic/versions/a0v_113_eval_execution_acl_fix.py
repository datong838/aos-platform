"""Remove inherited default table writes from the four Eval authority tables."""

from alembic import op


revision = "a0v_113"
down_revision = "a0v_112"
branch_labels = depends_on = None


def upgrade() -> None:
    for table in (
        "aip_eval_issuer_root",
        "aip_eval_executor_identity",
        "aip_eval_authority_revocation",
        "aip_eval_execution_receipt",
    ):
        op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC, aos_runtime")
        op.execute(f"GRANT SELECT ON public.{table} TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("Eval authority write revocation may not be silently removed")
