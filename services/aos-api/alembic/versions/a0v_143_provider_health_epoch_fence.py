"""Fence original Health DML by tenant/provider; never replicate health facts."""
from alembic import op

revision = 'a0v_143'
down_revision = 'a0v_142'
branch_labels = depends_on = None
OWNER = 'aos_provider_health_fence_owner'


def upgrade() -> None:
    op.execute(f"""DO $$ DECLARE r record; BEGIN
        SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
        IF NOT FOUND THEN
            CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
                NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
           OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_FENCE_OWNER_DRIFT' USING ERRCODE='42501';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_auth_members
            WHERE roleid='{OWNER}'::regrole OR member='{OWNER}'::regrole) THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_FENCE_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
        END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
    op.execute("""CREATE TABLE public.aip_provider_health_epoch (
        org_id text NOT NULL, project_id text NOT NULL,
        provider_id text NOT NULL CHECK (provider_id<>'' AND provider_id=btrim(provider_id)),
        epoch bigint NOT NULL DEFAULT 0 CHECK (epoch>=0),
        PRIMARY KEY (org_id,project_id,provider_id))""")
    op.execute(f'ALTER TABLE public.aip_provider_health_epoch OWNER TO {OWNER}')
    op.execute('REVOKE ALL ON public.aip_provider_health_epoch FROM PUBLIC,aos_runtime')
    op.execute('ALTER TABLE public.aip_provider_health_epoch ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_provider_health_epoch FORCE ROW LEVEL SECURITY')
    op.execute(f"""CREATE POLICY aos_provider_health_epoch_tenant
        ON public.aip_provider_health_epoch TO {OWNER}
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE FUNCTION public.aos_provider_health_epoch_lock(
        p_org text,p_project text,p_provider jsonb,p_shared boolean)
        RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public,pg_temp AS $$ DECLARE
        v_epoch bigint; v_id text := p_provider->>'assetId';
    BEGIN
        IF p_org IS NULL OR p_project IS NULL
           OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
           OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_SCOPE_MISMATCH' USING ERRCODE='42501';
        END IF;
        IF p_shared IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_READER_SHARED_REQUIRED' USING ERRCODE='42501';
        END IF;
        IF jsonb_typeof(p_provider) IS DISTINCT FROM 'object'
           OR v_id IS NULL OR v_id='' OR v_id<>btrim(v_id)
           OR p_provider->>'assetType' IS DISTINCT FROM 'ProviderInstanceRevision' THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_REF_INVALID' USING ERRCODE='42501';
        END IF;
        SELECT epoch INTO v_epoch FROM public.aip_provider_health_epoch
            WHERE org_id=p_org AND project_id=p_project AND provider_id=v_id FOR SHARE;
        IF NOT FOUND THEN
            INSERT INTO public.aip_provider_health_epoch(org_id,project_id,provider_id)
                VALUES (p_org,p_project,v_id) ON CONFLICT DO NOTHING;
            SELECT epoch INTO v_epoch FROM public.aip_provider_health_epoch
                WHERE org_id=p_org AND project_id=p_project AND provider_id=v_id FOR SHARE;
        END IF;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_EPOCH_MISSING' USING ERRCODE='42501';
        END IF;
        RETURN v_epoch;
    END $$""")
    signature = 'public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)'
    op.execute(f'ALTER FUNCTION {signature} OWNER TO {OWNER}')
    op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_runtime')

    # Row triggers coordinate both old/new provider IDs. Tenant moves are denied.
    for function, phase in (('touch', 'before'), ('bump', 'after')):
        action = """INSERT INTO public.aip_provider_health_epoch(org_id,project_id,provider_id)
            VALUES(v_org,v_project,v_id) ON CONFLICT DO NOTHING;
            PERFORM epoch FROM public.aip_provider_health_epoch
                WHERE org_id=v_org AND project_id=v_project AND provider_id=v_id FOR UPDATE;""" if phase == 'before' else """
            UPDATE public.aip_provider_health_epoch SET epoch=epoch+1
                WHERE org_id=v_org AND project_id=v_project AND provider_id=v_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'PROVIDER_HEALTH_EPOCH_MISSING' USING ERRCODE='42501';
            END IF;"""
        op.execute(f"""CREATE FUNCTION public.aos_provider_health_epoch_{function}()
            RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
            SET search_path=pg_catalog,public,pg_temp AS $$ DECLARE
            v_org text; v_project text; v_id text; old_id text; new_id text;
        BEGIN
            IF TG_OP='TRUNCATE' THEN
                RAISE EXCEPTION 'PROVIDER_HEALTH_TRUNCATE_DENIED' USING ERRCODE='42501';
            END IF;
            IF TG_OP='UPDATE' AND (OLD.org_id,OLD.project_id)
                IS DISTINCT FROM (NEW.org_id,NEW.project_id) THEN
                RAISE EXCEPTION 'PROVIDER_HEALTH_SCOPE_MISMATCH' USING ERRCODE='42501';
            END IF;
            IF TG_OP='DELETE' THEN
                v_org:=OLD.org_id; v_project:=OLD.project_id;
            ELSE
                v_org:=NEW.org_id; v_project:=NEW.project_id;
            END IF;
            IF v_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
               OR v_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
                RAISE EXCEPTION 'PROVIDER_HEALTH_SCOPE_MISMATCH' USING ERRCODE='42501';
            END IF;
            IF TG_OP='UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
                RETURN NEW;
            END IF;
            IF TG_OP IN ('UPDATE','DELETE') THEN old_id:=OLD.provider_ref->>'assetId'; END IF;
            IF TG_OP IN ('INSERT','UPDATE') THEN new_id:=NEW.provider_ref->>'assetId'; END IF;
            IF (TG_OP IN ('UPDATE','DELETE') AND (old_id IS NULL OR old_id='' OR old_id<>btrim(old_id)))
               OR (TG_OP IN ('INSERT','UPDATE') AND (new_id IS NULL OR new_id='' OR new_id<>btrim(new_id))) THEN
                RAISE EXCEPTION 'PROVIDER_HEALTH_REF_INVALID' USING ERRCODE='42501';
            END IF;
            FOR v_id IN SELECT DISTINCT x FROM unnest(ARRAY[old_id,new_id]) AS t(x)
                WHERE x IS NOT NULL ORDER BY x LOOP
                {action}
            END LOOP;
            IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
        END $$""")
        trigger_signature = f'public.aos_provider_health_epoch_{function}()'
        op.execute(f'ALTER FUNCTION {trigger_signature} OWNER TO {OWNER}')
        op.execute(f'REVOKE ALL ON FUNCTION {trigger_signature} FROM PUBLIC,aos_runtime')
        op.execute(f"""CREATE TRIGGER aos_provider_health_epoch_{phase}
            {phase.upper()} INSERT OR UPDATE OR DELETE ON public.aip_provider_health_observation
            FOR EACH ROW EXECUTE FUNCTION {trigger_signature}""")
    op.execute("""CREATE TRIGGER aos_provider_health_epoch_truncate
        BEFORE TRUNCATE ON public.aip_provider_health_observation
        FOR EACH STATEMENT EXECUTE FUNCTION public.aos_provider_health_epoch_touch()""")


def downgrade() -> None:
    raise RuntimeError('provider health epoch fence cannot be silently disabled')
