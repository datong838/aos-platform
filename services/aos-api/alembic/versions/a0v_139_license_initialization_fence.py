"""Coordinate first source issuance with revoke before any license head exists."""
from alembic import op

revision = 'a0v_139'
down_revision = 'a0v_138'
branch_labels = depends_on = None
OWNER = 'aos_license_source_fence_owner'


def upgrade() -> None:
    # Reuse the already isolated fence identity; never repair an unsafe role.
    op.execute(f"""DO $$ DECLARE r record; BEGIN
        SELECT * INTO r FROM pg_roles WHERE rolname='{OWNER}';
        IF NOT FOUND OR r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
           OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
           OR EXISTS(SELECT 1 FROM pg_auth_members
               WHERE roleid=r.oid OR member=r.oid) THEN
            RAISE EXCEPTION 'LICENSE_FENCE_OWNER_DRIFT' USING ERRCODE='42501';
        END IF;
    END $$""")
    # This neutral coordination row grants no license. Legacy source rows are
    # not backfilled, rehashed, promoted or changed by the migration.
    table='public.aip_license_source_initialization_fence'
    op.execute(f"""CREATE TABLE {table} (
        org_id TEXT NOT NULL,project_id TEXT NOT NULL,bundle_id TEXT NOT NULL,
        revision BIGINT NOT NULL CHECK(revision>=1),
        content_hash TEXT NOT NULL CHECK(content_hash ~ '^[0-9a-f]{{64}}$'),
        epoch BIGINT NOT NULL CHECK(epoch>=0),
        PRIMARY KEY(org_id,project_id,bundle_id,revision,content_hash),
        FOREIGN KEY(org_id,project_id,bundle_id,revision,content_hash)
            REFERENCES public.aip_evidence_bundle_revision
                (org_id,project_id,bundle_id,revision,content_hash)
    )""")
    op.execute(f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime')
    op.execute(f'GRANT SELECT ON {table} TO aos_runtime')
    op.execute(f'GRANT SELECT,INSERT ON {table} TO {OWNER}')
    op.execute(f'GRANT UPDATE(epoch) ON {table} TO {OWNER}')
    op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
    for role in ('aos_runtime',OWNER):
        op.execute(f"""CREATE POLICY license_initialization_{role} ON {table}
            TO {role} USING (
                org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK (
                org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    signature='public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean)'
    op.execute("""CREATE FUNCTION public.aos_license_source_initialization_lock(
        p_org text,p_project text,p_bundle text,p_revision bigint,p_hash text,p_shared boolean)
        RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ DECLARE v_epoch bigint; BEGIN
        IF p_org IS NULL OR p_project IS NULL OR p_bundle IS NULL OR p_revision IS NULL
           OR p_hash IS NULL OR p_shared IS NULL
           OR p_org IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
           OR p_project IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_SCOPE_MISMATCH' USING ERRCODE='42501';
        END IF;
        IF NOT EXISTS(SELECT 1 FROM public.aip_evidence_bundle_revision
            WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
                AND revision=p_revision AND content_hash=p_hash) THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_EXACT_FROZEN_MISSING' USING ERRCODE='42501';
        END IF;
        INSERT INTO public.aip_license_source_initialization_fence
            (org_id,project_id,bundle_id,revision,content_hash,epoch)
            VALUES(p_org,p_project,p_bundle,p_revision,p_hash,0)
            ON CONFLICT DO NOTHING;
        IF p_shared THEN
            SELECT epoch INTO v_epoch FROM public.aip_license_source_initialization_fence
                WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
                    AND revision=p_revision AND content_hash=p_hash FOR SHARE;
        ELSE
            SELECT epoch INTO v_epoch FROM public.aip_license_source_initialization_fence
                WHERE org_id=p_org AND project_id=p_project AND bundle_id=p_bundle
                    AND revision=p_revision AND content_hash=p_hash FOR UPDATE;
        END IF;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'LICENSE_SOURCE_INITIALIZATION_FENCE_MISSING' USING ERRCODE='42501';
        END IF;
        RETURN v_epoch;
    END $$""")
    op.execute(f'ALTER FUNCTION {signature} OWNER TO {OWNER}')
    op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_runtime')
    op.execute("""CREATE OR REPLACE FUNCTION public.aos_license_revoke_fence()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$ BEGIN
        IF TG_WHEN='BEFORE' THEN
            -- Always coordinate, even before the first issuance/head is made.
            PERFORM public.aos_license_source_initialization_lock(
                NEW.org_id,NEW.project_id,NEW.bundle_id,NEW.revision,NEW.content_hash,false);
            IF EXISTS(SELECT 1 FROM public.aip_license_source_issuance
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                    AND bundle_id=NEW.bundle_id AND revision=NEW.revision) THEN
                PERFORM public.aos_license_source_lock(
                    NEW.org_id,NEW.project_id,NEW.bundle_id,NEW.revision,NEW.content_hash,false);
            END IF;
        ELSE
            -- AFTER only runs for an inserted event; ON CONFLICT/replay cannot
            -- move either epoch. Both epochs roll back with the event.
            UPDATE public.aip_license_source_initialization_fence SET epoch=epoch+1
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                    AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'LICENSE_SOURCE_INITIALIZATION_FENCE_MISSING' USING ERRCODE='42501';
            END IF;
            IF EXISTS(SELECT 1 FROM public.aip_license_source_issuance
                WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                    AND bundle_id=NEW.bundle_id AND revision=NEW.revision) THEN
                UPDATE public.aip_license_source_head SET epoch=epoch+1
                    WHERE org_id=NEW.org_id AND project_id=NEW.project_id
                        AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'LICENSE_SOURCE_HEAD_MISSING' USING ERRCODE='42501';
                END IF;
            END IF;
        END IF;
        RETURN NEW;
    END $$""")
    op.execute(f'ALTER FUNCTION public.aos_license_revoke_fence() OWNER TO {OWNER}')
    op.execute('REVOKE ALL ON FUNCTION public.aos_license_revoke_fence() FROM PUBLIC,aos_runtime')


def downgrade() -> None:
    raise RuntimeError('first source initialization fence cannot be silently disabled')
