"""Pin analysis reconcile transition authority ahead of temporary schemas."""

from alembic import op


revision = "ar2_012"
down_revision = "ar2_011"
branch_labels = depends_on = None
SIGNATURE = "(text,bigint,text,text,text,jsonb)"


def upgrade() -> None:
    op.execute(
        "ALTER FUNCTION public.ecommerce_investigation_run_state_transition_biw4_007"
        f"{SIGNATURE} SET search_path = pg_catalog, public, pg_temp"
    )


def downgrade() -> None:
    op.execute(
        "ALTER FUNCTION public.ecommerce_investigation_run_state_transition_biw4_007"
        f"{SIGNATURE} SET search_path = pg_catalog, public"
    )
