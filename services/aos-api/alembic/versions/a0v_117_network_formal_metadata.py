"""Register exact global network activation metadata and reserve its ObjectType."""

from alembic import op


revision = "a0v_117"
down_revision = "a0v_116"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM public.meta_object_type WHERE id='NetworkPolicyRevision')
         OR EXISTS (SELECT 1 FROM public.meta_action_type WHERE id='aip_activate_network_policy') THEN
        RAISE EXCEPTION 'FORMAL_NETWORK_METADATA_ALREADY_PRESENT' USING ERRCODE='23505';
      END IF;
    END $$""")
    op.execute("""CREATE FUNCTION public.guard_a0v117_network_object_type()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE owner_name TEXT;
      BEGIN
        IF (TG_OP IN ('UPDATE','DELETE') AND OLD.id='NetworkPolicyRevision')
           OR (TG_OP IN ('INSERT','UPDATE') AND NEW.id='NetworkPolicyRevision') THEN
          SELECT pg_get_userbyid(relowner) INTO owner_name
            FROM pg_class WHERE oid='public.meta_object_type'::regclass;
          IF owner_name IS NULL OR current_user <> owner_name THEN
            RAISE EXCEPTION 'system NetworkPolicy ObjectType is reserved' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.guard_a0v117_network_object_type() FROM PUBLIC")
    op.execute("""CREATE TRIGGER trg_a0v117_network_object_type
      BEFORE INSERT OR UPDATE OR DELETE ON public.meta_object_type
      FOR EACH ROW EXECUTE FUNCTION public.guard_a0v117_network_object_type()""")
    op.execute("""INSERT INTO public.meta_object_type
      (id,name,description,published,properties,required_markings)
      VALUES ('NetworkPolicyRevision','网络策略修订','受控网络策略激活目标',TRUE,'[]'::jsonb,'[]'::jsonb)""")
    op.execute("""INSERT INTO public.meta_action_type
      (id,name,object_type,parameters,required_markings,submission_criteria)
      VALUES ('aip_activate_network_policy','激活网络策略','NetworkPolicyRevision',
              '[]'::jsonb,'[]'::jsonb,'[]'::jsonb)""")


def downgrade() -> None:
    raise RuntimeError("formal network metadata and its reserved-ID gate may not be silently removed")
