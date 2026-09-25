"""Close the unfenced unknown-reconciliation entry before adding a new one."""

from alembic import op


revision = "a0v_096"
down_revision = "a0v_095"
branch_labels = depends_on = None


_SIGNATURE = "(text,bigint,text,jsonb,jsonb)"


def upgrade() -> None:
    # a0v_050 checks the original attempt and dual Receipts, but not the
    # current Host lease or the saved source group. Leave normal claimed
    # completion untouched; unknown remains frozen until a separate guarded
    # entry has its own full transaction and PG rejection proof.
    op.execute(
        "REVOKE ALL ON FUNCTION "
        "public.data_requirement_outbox_reconcile_completed_a0v_050"
        f"{_SIGNATURE} FROM PUBLIC,aos_runtime,"
        "aos_extension_directory,aos_extension_maintainer"
    )


def downgrade() -> None:
    raise RuntimeError(
        "legacy unknown reconciliation EXECUTE must not be restored by downgrade"
    )
