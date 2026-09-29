"""Reject direct active NetworkPolicy inserts until atomic approval consumption exists."""

from alembic import op


revision = "a0v_116"
down_revision = "a0v_115"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION public.aip_network_active_insert_guard()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      BEGIN
        IF NEW.lifecycle = 'active' THEN
          RAISE EXCEPTION 'NETWORK_ACTIVATION_CONSUMPTION_REQUIRED'
            USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
      END
      $$""")
    op.execute("REVOKE ALL ON FUNCTION public.aip_network_active_insert_guard() FROM PUBLIC")
    op.execute("""CREATE TRIGGER aip_network_active_insert_guard
      BEFORE INSERT ON public.aip_network_policy_revision FOR EACH ROW
      EXECUTE FUNCTION public.aip_network_active_insert_guard()""")


def downgrade() -> None:
    raise RuntimeError("active NetworkPolicy DB gate may not be silently removed")
