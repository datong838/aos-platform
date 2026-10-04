"""Fence trusted-source revocation without granting runtime head writes."""
from alembic import op

revision = 'a0v_137'
down_revision = 'a0v_136'
branch_labels = depends_on = None
OWNER = 'aos_license_source_fence_owner'


def upgrade() -> None:
    op.execute(f"""DO $$ DECLARE r record; BEGIN
        SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
        IF NOT FOUND THEN
            CREATE ROLE {OWNER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB
                NOCREATEROLE NOREPLICATION NOBYPASSRLS;
        ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
           OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls THEN
            RAISE EXCEPTION 'LICENSE_FENCE_OWNER_DRIFT' USING ERRCODE='42501';
        END IF;
        IF EXISTS (SELECT 1 FROM pg_auth_members
            WHERE roleid='{OWNER}'::regrole OR member='{OWNER}'::regrole) THEN
            RAISE EXCEPTION 'LICENSE_FENCE_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
        END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {OWNER}')
    for table in ('aip_evidence_bundle_revision','aip_license_source_issuance','aip_license_source_head'):
        op.execute(f'GRANT SELECT ON public.{table} TO {OWNER}')
        op.execute(f"""CREATE POLICY license_fence_owner_{table} ON public.{table}
            TO {OWNER} USING (
                org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (
                org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute(f'GRANT UPDATE(epoch) ON public.aip_license_source_head TO {OWNER}')
    signature = 'public.aos_license_source_lock(text,text,text,bigint,text,boolean)'
    op.execute("""CREATE FUNCTION public.aos_license_source_lock(
        p_org text,p_project text,p_bundle text,p_revision bigint,p_hash text,p_shared boolean)
        RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ DECLARE v_epoch bigint; BEGIN
        IF p_org IS NULL OR p_project IS NULL OR p_bundle IS NULL OR p_revision IS NULL
           OR p_hash IS NULL OR p_shared IS NULL
           OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
           OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_SCOPE_MISMATCH' USING ERRCODE='42501';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.aip_evidence_bundle_revision
            WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
              AND revision=p_revision AND content_hash=p_hash AND lifecycle='frozen') THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_EXACT_FROZEN_MISSING' USING ERRCODE='42501';
        END IF;
        IF p_shared THEN
            SELECT epoch INTO v_epoch FROM public.aip_license_source_head
                WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
                  AND revision=p_revision AND content_hash=p_hash FOR SHARE;
        ELSE
            SELECT epoch INTO v_epoch FROM public.aip_license_source_head
                WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
                  AND revision=p_revision AND content_hash=p_hash FOR UPDATE;
        END IF;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_HEAD_MISSING' USING ERRCODE='42501';
        END IF;
        RETURN v_epoch;
    END $$""")
    op.execute(f'ALTER FUNCTION {signature} OWNER TO {OWNER}')
    op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_runtime')
    op.execute("""CREATE FUNCTION public.aos_license_revoke_fence()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM public.aip_license_source_issuance
            WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND bundle_id=NEW.bundle_id
              AND revision=NEW.revision) THEN
            RETURN NEW;
        END IF;
        IF TG_WHEN='BEFORE' THEN
            PERFORM public.aos_license_source_lock(
                NEW.org_id,NEW.project_id,NEW.bundle_id,NEW.revision,NEW.content_hash,false);
        ELSE
            UPDATE public.aip_license_source_head SET epoch=epoch+1
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                  AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'LICENSE_SOURCE_HEAD_MISSING' USING ERRCODE='42501';
            END IF;
        END IF;
        RETURN NEW;
    END $$""")
    op.execute(f'ALTER FUNCTION public.aos_license_revoke_fence() OWNER TO {OWNER}')
    op.execute('REVOKE ALL ON FUNCTION public.aos_license_revoke_fence() FROM PUBLIC,aos_runtime')
    op.execute("""CREATE TRIGGER aos_license_revoke_before
        BEFORE INSERT ON public.aip_evidence_bundle_revoke_event
        FOR EACH ROW EXECUTE FUNCTION public.aos_license_revoke_fence()""")
    op.execute("""CREATE TRIGGER aos_license_revoke_after
        AFTER INSERT ON public.aip_evidence_bundle_revoke_event
        FOR EACH ROW EXECUTE FUNCTION public.aos_license_revoke_fence()""")


def downgrade() -> None:
    raise RuntimeError('trusted source fence cannot be silently disabled')
