"""Reserve future system policy ActionType identities at the database boundary.

No ActionType is registered until a formal policy producer and product preview exist.
"""

from alembic import op


revision = "a0v_115"
down_revision = "a0v_114"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_a0v115_reserved_policy_action_type()
      RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE
        old_reserved BOOLEAN := FALSE;
        new_reserved BOOLEAN := FALSE;
        owner_name TEXT;
      BEGIN
        IF TG_OP IN ('UPDATE', 'DELETE') THEN
          old_reserved := OLD.id IN (
            'aip_activate_egress_policy', 'aip_activate_data_policy',
            'aip_activate_network_policy', 'aip_activate_quota_policy',
            'aip_activate_budget_policy');
        END IF;
        IF TG_OP IN ('INSERT', 'UPDATE') THEN
          new_reserved := NEW.id IN (
            'aip_activate_egress_policy', 'aip_activate_data_policy',
            'aip_activate_network_policy', 'aip_activate_quota_policy',
            'aip_activate_budget_policy');
        END IF;
        IF old_reserved OR new_reserved THEN
          SELECT pg_get_userbyid(relowner) INTO owner_name
            FROM pg_class WHERE oid='public.meta_action_type'::regclass;
          IF owner_name IS NULL OR current_user <> owner_name THEN
            RAISE EXCEPTION 'system policy ActionType is reserved'
              USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP = 'DELETE' THEN
          RETURN OLD;
        END IF;
        RETURN NEW;
      END
      $$""")
    op.execute("""CREATE TRIGGER trg_a0v115_reserved_policy_action_type
      BEFORE INSERT OR UPDATE OR DELETE ON meta_action_type
      FOR EACH ROW EXECUTE FUNCTION guard_a0v115_reserved_policy_action_type()""")


def downgrade() -> None:
    raise RuntimeError("system policy ActionType reservation must not be silently removed")
