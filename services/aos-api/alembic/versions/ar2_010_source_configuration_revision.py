"""Record opaque source configuration identities without copying secrets."""
from alembic import op

revision = "ar2_010"
down_revision = "ar2_009"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION public.source_configuration_body_ar2_010(
      p_org TEXT,p_project TEXT,p_source TEXT,p_revision UUID,p_prior UUID,
      p_type TEXT,p_status TEXT,p_plugin TEXT) RETURNS JSONB LANGUAGE SQL IMMUTABLE
      SET search_path=pg_catalog,public,pg_temp AS $$ SELECT jsonb_build_object(
        'schemaVersion','aos.source-configuration-identity/v1',
        'tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
        'sourceId',p_source,'revisionId',p_revision,'priorRevisionId',p_prior,
        'type',p_type,'status',p_status,'pluginId',p_plugin,
        'configurationIdentityOnly',true,'secretMaterialVersionKnown',false) $$""")
    op.execute("""CREATE TABLE public.data_source_configuration_revision(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,source_id TEXT NOT NULL,
      revision_id UUID NOT NULL,prior_revision_id UUID,
      source_type TEXT NOT NULL,status TEXT NOT NULL,plugin_id TEXT,
      authority JSONB NOT NULL,content_hash TEXT NOT NULL,
      recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,source_id,revision_id),
      UNIQUE(org_id,project_id,revision_id),
      FOREIGN KEY(org_id,project_id,source_id,prior_revision_id)
        REFERENCES public.data_source_configuration_revision(org_id,project_id,source_id,revision_id),
      CHECK(authority=public.source_configuration_body_ar2_010(org_id,project_id,source_id,
        revision_id,prior_revision_id,source_type,status,plugin_id)),
      CHECK(content_hash=encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(authority),'UTF8'),'sha256'),'hex')))
    """)
    op.execute("ALTER TABLE public.meta_source ADD COLUMN configuration_revision UUID")
    op.execute("UPDATE public.meta_source SET configuration_revision=gen_random_uuid()")
    op.execute("ALTER TABLE public.meta_source ALTER COLUMN configuration_revision SET NOT NULL")
    op.execute("""INSERT INTO public.data_source_configuration_revision
      (org_id,project_id,source_id,revision_id,source_type,status,plugin_id,authority,content_hash)
      SELECT org_id,project_id,id,configuration_revision,type,status,plugin_id,body,
        encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(body),'UTF8'),'sha256'),'hex')
      FROM public.meta_source CROSS JOIN LATERAL (SELECT public.source_configuration_body_ar2_010(
        org_id,project_id,id,configuration_revision,NULL,type,status,plugin_id) AS body) b""")
    op.execute("ALTER TABLE public.data_source_configuration_revision ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.data_source_configuration_revision FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY source_configuration_tenant_ar2_010 ON public.data_source_configuration_revision
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("REVOKE ALL ON public.data_source_configuration_revision FROM PUBLIC,aos_runtime,aos_app")
    op.execute("GRANT SELECT ON public.data_source_configuration_revision TO aos_runtime,aos_app")
    op.execute("""CREATE FUNCTION public.source_configuration_immutable_ar2_010() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$ BEGIN
      RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='source configuration history is immutable'; END $$""")
    op.execute("CREATE TRIGGER source_configuration_immutable BEFORE UPDATE OR DELETE ON public.data_source_configuration_revision FOR EACH ROW EXECUTE FUNCTION public.source_configuration_immutable_ar2_010()")
    op.execute("CREATE TRIGGER source_configuration_no_truncate BEFORE TRUNCATE ON public.data_source_configuration_revision FOR EACH STATEMENT EXECUTE FUNCTION public.source_configuration_immutable_ar2_010()")
    op.execute("""CREATE FUNCTION public.source_configuration_token_ar2_010() RETURNS trigger
      LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $$ BEGIN
      IF TG_OP='INSERT' THEN
        IF NEW.configuration_revision IS NOT NULL THEN
          RAISE EXCEPTION USING ERRCODE='SC001',MESSAGE='source revision is database assigned';
        END IF;
        NEW.configuration_revision:=gen_random_uuid();
      ELSE
        IF (NEW.org_id,NEW.project_id,NEW.id) IS DISTINCT FROM (OLD.org_id,OLD.project_id,OLD.id)
          OR NEW.configuration_revision IS DISTINCT FROM OLD.configuration_revision THEN
          RAISE EXCEPTION USING ERRCODE='SC001',MESSAGE='source identity or revision override rejected';
        END IF;
        IF (NEW.type,NEW.status,NEW.plugin_id,NEW.props) IS DISTINCT FROM (OLD.type,OLD.status,OLD.plugin_id,OLD.props) THEN
          NEW.configuration_revision:=gen_random_uuid();
        END IF;
      END IF;
      RETURN NEW; END $$""")
    op.execute("""CREATE FUNCTION public.source_configuration_history_ar2_010() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_prior UUID; v_body JSONB;
      BEGIN
        IF NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
          OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
          RAISE EXCEPTION USING ERRCODE='SC002',MESSAGE='source configuration scope required';
        END IF;
        IF TG_OP='UPDATE' THEN
          IF NEW.configuration_revision=OLD.configuration_revision THEN RETURN NEW; END IF;
          v_prior:=OLD.configuration_revision;
        END IF;
        v_body:=public.source_configuration_body_ar2_010(NEW.org_id,NEW.project_id,NEW.id,
          NEW.configuration_revision,v_prior,NEW.type,NEW.status,NEW.plugin_id);
        INSERT INTO public.data_source_configuration_revision(org_id,project_id,source_id,revision_id,
          prior_revision_id,source_type,status,plugin_id,authority,content_hash)
          VALUES(NEW.org_id,NEW.project_id,NEW.id,NEW.configuration_revision,v_prior,
            NEW.type,NEW.status,NEW.plugin_id,v_body,
            encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(v_body),'UTF8'),'sha256'),'hex'));
        RETURN NEW;
      END $$""")
    op.execute("CREATE TRIGGER source_configuration_token BEFORE INSERT OR UPDATE ON public.meta_source FOR EACH ROW EXECUTE FUNCTION public.source_configuration_token_ar2_010()")
    op.execute("CREATE TRIGGER source_configuration_history AFTER INSERT OR UPDATE ON public.meta_source FOR EACH ROW EXECUTE FUNCTION public.source_configuration_history_ar2_010()")
    for name in ("public.source_configuration_token_ar2_010", "public.source_configuration_history_ar2_010", "public.source_configuration_immutable_ar2_010"):
        op.execute(f"REVOKE ALL ON FUNCTION {name}() FROM PUBLIC")


def downgrade():
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM public.data_source_configuration_revision)
      THEN RAISE EXCEPTION 'cannot remove source configuration history'; END IF; END $$""")
    op.execute("DROP TRIGGER source_configuration_history ON public.meta_source")
    op.execute("DROP TRIGGER source_configuration_token ON public.meta_source")
    op.execute("DROP FUNCTION public.source_configuration_history_ar2_010()")
    op.execute("DROP FUNCTION public.source_configuration_token_ar2_010()")
    op.execute("ALTER TABLE public.meta_source DROP COLUMN configuration_revision")
    op.execute("DROP TABLE public.data_source_configuration_revision")
    op.execute("DROP FUNCTION public.source_configuration_immutable_ar2_010()")
    op.execute("DROP FUNCTION public.source_configuration_body_ar2_010(TEXT,TEXT,TEXT,UUID,UUID,TEXT,TEXT,TEXT)")
