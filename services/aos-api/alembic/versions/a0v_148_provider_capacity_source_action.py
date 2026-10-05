"""Reserved Provider allocation approval metadata; no execution grant."""

from alembic import op

revision = "a0v_148"
down_revision = "a0v_147"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.meta_object_type WHERE id='ProviderCapacitySourceReview')
         OR EXISTS(SELECT 1 FROM public.meta_action_type WHERE id='aip_review_provider_capacity_source') THEN
        RAISE EXCEPTION 'PROVIDER_CAPACITY_METADATA_ALREADY_PRESENT' USING ERRCODE='23505';
      END IF;
    END $$""")
    op.execute("""CREATE FUNCTION public.provider_capacity_metadata_a0v148()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE object_name text; protected_id text; owner_name text; BEGIN
        object_name := CASE WHEN TG_TABLE_NAME='meta_object_type'
          THEN 'ProviderCapacitySourceReview' ELSE 'aip_review_provider_capacity_source' END;
        protected_id := CASE WHEN TG_OP='DELETE' THEN OLD.id ELSE NEW.id END;
        IF protected_id=object_name OR (TG_OP='UPDATE' AND OLD.id=object_name) THEN
          SELECT pg_get_userbyid(relowner) INTO owner_name FROM pg_class
            WHERE oid=format('public.%I',TG_TABLE_NAME)::regclass;
          IF current_user IS DISTINCT FROM owner_name THEN
            RAISE EXCEPTION 'PROVIDER_CAPACITY_METADATA_RESERVED' USING ERRCODE='42501';
          END IF;
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute("REVOKE ALL ON FUNCTION public.provider_capacity_metadata_a0v148() FROM PUBLIC")
    for table in ("meta_object_type", "meta_action_type"):
        op.execute(f"""CREATE TRIGGER provider_capacity_metadata_a0v148
          BEFORE INSERT OR UPDATE OR DELETE ON public.{table}
          FOR EACH ROW EXECUTE FUNCTION public.provider_capacity_metadata_a0v148()""")
    op.execute("""INSERT INTO public.meta_object_type
      (id,name,description,published,properties,required_markings)
      VALUES('ProviderCapacitySourceReview','Provider容量来源审查','仅供独立审批的不可执行Source条款',TRUE,'[]','[]')""")
    op.execute("""INSERT INTO public.meta_action_type
      (id,name,object_type,parameters,required_markings,submission_criteria)
      VALUES('aip_review_provider_capacity_source','审查Provider容量来源','ProviderCapacitySourceReview','[]','[]','[]')""")


def downgrade():
    raise RuntimeError("Provider allocation approval metadata cannot be silently removed")
