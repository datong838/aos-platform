"""Reserved original Action metadata and independent source approval writer.

No issuer login, business ACL, historical grant, or current-instance migration.
"""
from alembic import op

revision='a0v_140'
down_revision='a0v_139'
branch_labels=depends_on=None
ACTION='aip_issue_source_license'
OBJECT='SourceLicenseRequest'
ISSUER='aos_source_license_approval_issuer'


def upgrade():
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{ISSUER}';
      IF NOT FOUND THEN
        CREATE ROLE {ISSUER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
         OR r.rolreplication OR r.rolbypassrls THEN
        RAISE EXCEPTION 'SOURCE_LICENSE_APPROVAL_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{ISSUER}'::regrole OR member='{ISSUER}'::regrole) THEN
        RAISE EXCEPTION 'SOURCE_LICENSE_APPROVAL_MEMBERSHIP_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM public.meta_object_type WHERE id='{OBJECT}')
        OR EXISTS(SELECT 1 FROM public.meta_action_type WHERE id='{ACTION}') THEN
        RAISE EXCEPTION 'SOURCE_LICENSE_METADATA_ALREADY_PRESENT' USING ERRCODE='23505';
      END IF;
    END $$""")
    op.execute(f"""CREATE FUNCTION public.source_license_metadata_a0v140()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$
      DECLARE protected boolean:=false; table_owner text; BEGIN
        IF TG_TABLE_NAME='meta_action_type' THEN
          protected:=(TG_OP IN ('UPDATE','DELETE') AND OLD.id='{ACTION}')
            OR (TG_OP IN ('INSERT','UPDATE') AND NEW.id='{ACTION}');
        ELSE
          protected:=(TG_OP IN ('UPDATE','DELETE') AND OLD.id='{OBJECT}')
            OR (TG_OP IN ('INSERT','UPDATE') AND NEW.id='{OBJECT}');
        END IF;
        SELECT pg_get_userbyid(relowner) INTO table_owner FROM pg_class WHERE oid=TG_RELID;
        IF protected AND current_user IS DISTINCT FROM table_owner THEN
          RAISE EXCEPTION 'SOURCE_LICENSE_METADATA_RESERVED' USING ERRCODE='42501';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_license_metadata_a0v140() FROM PUBLIC')
    for table in ('meta_object_type','meta_action_type'):
        op.execute(f'CREATE TRIGGER source_license_metadata_a0v140 BEFORE INSERT OR UPDATE OR DELETE '
            f'ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.source_license_metadata_a0v140()')
    op.execute(f"""INSERT INTO public.meta_object_type(id,name,description,published,properties,required_markings)
      VALUES('{OBJECT}','来源许可请求','原Proposal内的精确来源许可声明',true,'[]','[]')""")
    op.execute(f"""INSERT INTO public.meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria)
      VALUES('{ACTION}','申请精确来源许可','{OBJECT}','[]','[]','[]')""")
    op.execute(f"""CREATE FUNCTION public.source_license_proposal_terms_a0v140()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
        IF (OLD.action_type_id='{ACTION}' OR NEW.action_type_id='{ACTION}'
            OR OLD.action_type_snapshot->>'id'='{ACTION}' OR NEW.action_type_snapshot->>'id'='{ACTION}')
          AND (to_jsonb(OLD)-ARRAY['status','version','updated_at']) IS DISTINCT FROM
              (to_jsonb(NEW)-ARRAY['status','version','updated_at']) THEN
          RAISE EXCEPTION 'SOURCE_LICENSE_PROPOSAL_TERMS_IMMUTABLE' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_license_proposal_terms_a0v140() FROM PUBLIC')
    op.execute('CREATE TRIGGER source_license_proposal_terms_a0v140 BEFORE UPDATE ON public.aip_action_proposal '
               'FOR EACH ROW EXECUTE FUNCTION public.source_license_proposal_terms_a0v140()')
    op.execute(f"""CREATE FUNCTION public.source_license_approval_a0v140()
      RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public AS $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.aip_action_proposal p
        WHERE p.org_id=NEW.org_id AND p.project_id=NEW.project_id AND p.proposal_id=NEW.proposal_id
          AND (p.action_type_id='{ACTION}' OR p.action_type_snapshot->>'id'='{ACTION}')) THEN
        IF session_user<>'{ISSUER}' OR current_user<>'{ISSUER}'
          OR NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
          OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'')
          OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname='{ISSUER}'
            AND (NOT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
          OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{ISSUER}'::regrole OR member='{ISSUER}'::regrole) THEN
          RAISE EXCEPTION 'SOURCE_LICENSE_INDEPENDENT_APPROVAL_ISSUER_REQUIRED' USING ERRCODE='42501';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_license_approval_a0v140() FROM PUBLIC')
    op.execute('CREATE TRIGGER source_license_approval_a0v140 BEFORE INSERT ON public.aip_action_approval_event '
               'FOR EACH ROW EXECUTE FUNCTION public.source_license_approval_a0v140()')


def downgrade():
    raise RuntimeError('source license approval boundary cannot be silently downgraded')
