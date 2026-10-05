"""Coordinate provider-health currentness with a neutral epoch fence.

The health observation table accepts raw INSERT/UPDATE/DELETE/TRUNCATE from
several code paths (record_health, list readers, maintenance). A plain SERIAL
snapshot plus a row lock on the latest observation does NOT guarantee the
observation is still latest at proof-commit time (see the b90 mechanism probe:
reader205684 / writer205685). This fence adds a neutral coordinator row per
(tenant, provider) that every reachable health DML path shares: writers take an
exclusive lock and bump the epoch on effective change; the formal evaluator
takes a shared lock and reads the latest observation afterwards. A post-snapshot
epoch change therefore forces the serializable evaluator to a 40001 failure
instead of certifying a stale healthy status.

The fence stores only tenant/resource/epoch. No health-status replica, no source
approval or cost backfill. Owned by a NOLOGIN neutral function owner with no
members and no business write rights, mirroring a0v_137.
"""
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

    # Neutral coordinator: tenant + provider key + monotonic epoch only.
    # jsonb has no default btree operator class, so the provider key is hashed.
    op.execute(f"""CREATE TABLE public.aip_provider_health_epoch (
        org_id text NOT NULL,
        project_id text NOT NULL,
        provider_ref jsonb NOT NULL,
        provider_ref_hash char(32) NOT NULL,
        epoch bigint NOT NULL DEFAULT 1,
        updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (org_id, project_id, provider_ref_hash),
        CONSTRAINT provider_ref_is_object CHECK (jsonb_typeof(provider_ref)='object')
    )""")
    op.execute(f'ALTER TABLE public.aip_provider_health_epoch OWNER TO {OWNER}')
    op.execute(f'ALTER TABLE public.aip_provider_health_epoch ENABLE ROW LEVEL SECURITY')
    op.execute(f"""CREATE POLICY aos_provider_health_epoch_tenant ON public.aip_provider_health_epoch
        TO {OWNER} USING (
            org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (
            org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")

    op.execute(f"""CREATE FUNCTION public.aos_provider_health_epoch_lock(
        p_org text, p_project text, p_provider jsonb, p_shared boolean)
        RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ DECLARE
        v_epoch bigint; v_hash text := md5(p_provider::text);
    BEGIN
        IF p_org IS NULL OR p_project IS NULL OR p_provider IS NULL OR p_shared IS NULL
           OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
           OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_SCOPE_MISMATCH' USING ERRCODE='42501';
        END IF;
        IF jsonb_typeof(p_provider) IS DISTINCT FROM 'object' THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_REF_NOT_OBJECT' USING ERRCODE='42501';
        END IF;
        INSERT INTO public.aip_provider_health_epoch(org_id,project_id,provider_ref,provider_ref_hash)
            VALUES (p_org,p_project,p_provider,v_hash)
            ON CONFLICT (org_id,project_id,provider_ref_hash) DO NOTHING;
        IF p_shared THEN
            SELECT epoch INTO v_epoch FROM public.aip_provider_health_epoch
                WHERE org_id=p_org AND project_id=p_project AND provider_ref_hash=v_hash FOR SHARE;
        ELSE
            SELECT epoch INTO v_epoch FROM public.aip_provider_health_epoch
                WHERE org_id=p_org AND project_id=p_project AND provider_ref_hash=v_hash FOR UPDATE;
        END IF;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'PROVIDER_HEALTH_EPOCH_MISSING' USING ERRCODE='42501';
        END IF;
        RETURN v_epoch;
    END $$""")
    op.execute(f'ALTER FUNCTION public.aos_provider_health_epoch_lock(text,text,jsonb,boolean) OWNER TO {OWNER}')
    op.execute(f'REVOKE ALL ON FUNCTION public.aos_provider_health_epoch_lock(text,text,jsonb,boolean) FROM PUBLIC')
    op.execute(f"""DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aos_aip_binding_evaluator') THEN
            GRANT EXECUTE ON FUNCTION public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)
                TO aos_aip_binding_evaluator;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aos_runtime') THEN
            GRANT EXECUTE ON FUNCTION public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)
                TO aos_runtime;
        END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='aos_app') THEN
            GRANT EXECUTE ON FUNCTION public.aos_provider_health_epoch_lock(text,text,jsonb,boolean)
                TO aos_app;
        END IF;
    END $$""")

    op.execute(f"""CREATE FUNCTION public.aos_provider_health_epoch_touch()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ DECLARE
        v_org text := COALESCE(NEW.org_id, OLD.org_id);
        v_project text := COALESCE(NEW.project_id, OLD.project_id);
        v_ref jsonb := COALESCE(NEW.provider_ref, OLD.provider_ref);
        v_hash text := md5(v_ref::text);
        v_epoch bigint;
    BEGIN
        INSERT INTO public.aip_provider_health_epoch(org_id,project_id,provider_ref,provider_ref_hash)
            VALUES (v_org,v_project,v_ref,v_hash)
            ON CONFLICT (org_id,project_id,provider_ref_hash) DO NOTHING;
        SELECT epoch INTO v_epoch FROM public.aip_provider_health_epoch
            WHERE org_id=v_org AND project_id=v_project AND provider_ref_hash=v_hash FOR UPDATE;
        RETURN COALESCE(NEW, OLD);
    END $$""")
    op.execute(f'ALTER FUNCTION public.aos_provider_health_epoch_touch() OWNER TO {OWNER}')

    op.execute(f"""CREATE FUNCTION public.aos_provider_health_epoch_bump()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ DECLARE
        v_org text := COALESCE(NEW.org_id, OLD.org_id);
        v_project text := COALESCE(NEW.project_id, OLD.project_id);
        v_ref jsonb := COALESCE(NEW.provider_ref, OLD.provider_ref);
        v_hash text := md5(v_ref::text);
    BEGIN
        UPDATE public.aip_provider_health_epoch
            SET epoch=epoch+1, updated_at=now()
            WHERE org_id=v_org AND project_id=v_project AND provider_ref_hash=v_hash;
        RETURN COALESCE(NEW, OLD);
    END $$""")
    op.execute(f'ALTER FUNCTION public.aos_provider_health_epoch_bump() OWNER TO {OWNER}')

    op.execute(f"""CREATE TRIGGER aos_provider_health_epoch_before
        BEFORE INSERT OR UPDATE OR DELETE ON public.aip_provider_health_observation
        FOR EACH ROW EXECUTE FUNCTION public.aos_provider_health_epoch_touch()""")
    op.execute(f"""CREATE TRIGGER aos_provider_health_epoch_after
        AFTER INSERT OR UPDATE OR DELETE ON public.aip_provider_health_observation
        FOR EACH ROW EXECUTE FUNCTION public.aos_provider_health_epoch_bump()""")


def downgrade() -> None:
    raise RuntimeError('provider health epoch fence cannot be silently disabled')
