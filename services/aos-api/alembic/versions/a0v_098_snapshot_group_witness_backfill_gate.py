"""Inert, isolated historical witness writer; no application principal is granted."""

from alembic import op


revision = "a0v_098"
down_revision = "a0v_097"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE v_role text;
    BEGIN
      FOREACH v_role IN ARRAY ARRAY['aos_snapshot_witness_backfill',
                                    'aos_snapshot_witness_operator'] LOOP
        IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname=v_role) THEN
          EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION',v_role);
        END IF;
        IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=v_role AND
          (rolcanlogin OR rolsuper OR rolbypassrls OR rolinherit OR rolcreatedb
           OR rolcreaterole OR rolreplication))
          OR EXISTS(SELECT 1 FROM pg_auth_members
            WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname=v_role))
        THEN RAISE EXCEPTION 'witness role differs or already has members' USING ERRCODE='42501'; END IF;
      END LOOP;
    END $$;
    GRANT SELECT ON public.pipeline_snapshot_group_claim,
      public.pipeline_snapshot_group_input,public.pipeline_snapshot_group_member
      TO aos_snapshot_witness_backfill;
    GRANT SELECT,INSERT ON public.pipeline_snapshot_group_canonical_witness_a0v_097
      TO aos_snapshot_witness_backfill;

    CREATE FUNCTION public.pipeline_snapshot_group_witness_backfill_a0v_098(
      p_org text,p_project text,p_group uuid,p_binding text,p_manifest text)
    RETURNS text LANGUAGE plpgsql SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$
    DECLARE v_claim public.pipeline_snapshot_group_claim%ROWTYPE;
      v_input public.pipeline_snapshot_group_input%ROWTYPE;
      v_existing public.pipeline_snapshot_group_canonical_witness_a0v_097%ROWTYPE;
      v_binding jsonb; v_manifest jsonb; v_member record;
      v_identity record; v_count integer:=0; v_inserted integer;
    BEGIN
      SELECT rolsuper,rolbypassrls INTO v_identity FROM pg_roles WHERE rolname=session_user;
      IF current_setting('role',true) IS DISTINCT FROM 'aos_snapshot_witness_operator'
        OR NOT pg_has_role(session_user,'aos_snapshot_witness_operator','MEMBER')
        OR v_identity.rolsuper IS DISTINCT FROM false
        OR v_identity.rolbypassrls IS DISTINCT FROM false
        OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
        OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
        OR p_org IS NULL OR p_project IS NULL OR p_group IS NULL
        OR current_setting('transaction_isolation') IS DISTINCT FROM 'repeatable read'
        OR current_setting('transaction_read_only') IS DISTINCT FROM 'off'
      THEN RAISE EXCEPTION 'exact witness operator and writable snapshot required' USING ERRCODE='42501'; END IF;
      IF p_binding IS NULL OR p_manifest IS NULL
        OR octet_length(p_binding)>65536 OR octet_length(p_manifest)>65536
      THEN RAISE EXCEPTION 'bounded canonical witness required' USING ERRCODE='23514'; END IF;
      SELECT * INTO v_claim FROM public.pipeline_snapshot_group_claim
        WHERE org_id=p_org AND project_id=p_project AND group_id=p_group;
      SELECT * INTO v_input FROM public.pipeline_snapshot_group_input
        WHERE org_id=p_org AND project_id=p_project AND group_id=p_group;
      IF v_claim.group_id IS NULL OR v_input.group_id IS NULL
        OR v_input.request_hash IS DISTINCT FROM v_claim.request_hash
        OR v_claim.member_count NOT BETWEEN 1 AND 12
      THEN RAISE EXCEPTION 'original witness group/input unavailable' USING ERRCODE='23514'; END IF;
      v_binding:=p_binding::jsonb; v_manifest:=p_manifest::jsonb;
      IF jsonb_typeof(v_binding) IS DISTINCT FROM 'object'
        OR jsonb_typeof(v_manifest) IS DISTINCT FROM 'object'
        OR v_binding IS DISTINCT FROM v_claim.binding
        OR v_manifest IS DISTINCT FROM v_input.manifest
        OR 'sha256:'||encode(sha256(convert_to(p_binding,'UTF8')),'hex') IS DISTINCT FROM v_claim.request_hash
        OR 'sha256:'||encode(sha256(convert_to(p_manifest,'UTF8')),'hex') IS DISTINCT FROM v_input.manifest_hash
        OR v_binding->>'orgId' IS DISTINCT FROM p_org
        OR v_binding->>'projectId' IS DISTINCT FROM p_project
        OR v_binding->>'groupId' IS DISTINCT FROM p_group::text
        OR v_binding->>'actor' IS DISTINCT FROM v_claim.actor
        OR jsonb_typeof(v_binding->'members') IS DISTINCT FROM 'array'
        OR jsonb_typeof(v_manifest->'members') IS DISTINCT FROM 'array'
      THEN RAISE EXCEPTION 'original canonical witness differs' USING ERRCODE='23514'; END IF;
      IF jsonb_array_length(v_binding->'members')<>v_claim.member_count
        OR jsonb_array_length(v_manifest->'members')<>v_claim.member_count
      THEN RAISE EXCEPTION 'original witness membership differs' USING ERRCODE='23514'; END IF;
      FOR v_member IN SELECT ordinal,run_id FROM public.pipeline_snapshot_group_member
        WHERE org_id=p_org AND project_id=p_project AND group_id=p_group
        ORDER BY ordinal LIMIT 13 LOOP
        v_count:=v_count+1;
        IF v_member.ordinal<>v_count
          OR v_binding#>>ARRAY['members',(v_count-1)::text,'runId'] IS DISTINCT FROM v_member.run_id
          OR v_manifest#>>ARRAY['members',(v_count-1)::text,'runId'] IS DISTINCT FROM v_member.run_id
        THEN RAISE EXCEPTION 'original witness member differs' USING ERRCODE='23514'; END IF;
      END LOOP;
      IF v_count<>v_claim.member_count THEN
        RAISE EXCEPTION 'original witness member count differs' USING ERRCODE='23514'; END IF;
      INSERT INTO public.pipeline_snapshot_group_canonical_witness_a0v_097
        (org_id,project_id,group_id,request_hash,manifest_hash,
         binding_canonical_json,manifest_canonical_json)
      VALUES(p_org,p_project,p_group,v_claim.request_hash,v_input.manifest_hash,
        p_binding,p_manifest) ON CONFLICT (org_id,project_id,group_id) DO NOTHING;
      GET DIAGNOSTICS v_inserted=ROW_COUNT;
      IF v_inserted=1 THEN RETURN 'INSERTED'; END IF;
      SELECT * INTO v_existing FROM public.pipeline_snapshot_group_canonical_witness_a0v_097
        WHERE org_id=p_org AND project_id=p_project AND group_id=p_group;
      IF v_existing.group_id IS NULL
        OR v_existing.request_hash IS DISTINCT FROM v_claim.request_hash
        OR v_existing.manifest_hash IS DISTINCT FROM v_input.manifest_hash
        OR v_existing.binding_canonical_json IS DISTINCT FROM p_binding
        OR v_existing.manifest_canonical_json IS DISTINCT FROM p_manifest
      THEN RAISE EXCEPTION 'immutable witness conflict' USING ERRCODE='23514'; END IF;
      RETURN 'ALREADY_PRESENT';
    END $$;
    ALTER FUNCTION public.pipeline_snapshot_group_witness_backfill_a0v_098(text,text,uuid,text,text)
      OWNER TO aos_snapshot_witness_backfill;
    REVOKE ALL ON FUNCTION public.pipeline_snapshot_group_witness_backfill_a0v_098(text,text,uuid,text,text)
      FROM PUBLIC,aos_runtime,aos_extension_directory,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION public.pipeline_snapshot_group_witness_backfill_a0v_098(text,text,uuid,text,text)
      TO aos_snapshot_witness_operator;
    """)


def downgrade() -> None:
    raise RuntimeError("historical witness write gate must not be downgraded")
