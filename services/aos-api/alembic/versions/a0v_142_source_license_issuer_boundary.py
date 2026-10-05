"""Dedicated source issuance identity; original approval and receipt remain authority."""
from alembic import op

revision = 'a0v_142'
down_revision = 'a0v_141'
branch_labels = depends_on = None
ISSUER = 'aos_source_license_issuer'
ACTION = 'aip_issue_source_license'
SCOPED_READ = (
    'meta_membership', 'bundle_installation', 'bundle_installation_revision',
    'bundle_composition', 'bundle_composition_lock', 'aip_evidence_bundle_revision',
    'aip_evidence_bundle_build_provenance', 'aip_evidence_bundle_revoke_event',
    'aip_production_contract_receipt', 'aip_action_withdrawal_event',
)
LOCK_COLUMNS = (
    ('meta_membership', 'subject'), ('bundle_installation', 'installation_id'),
    ('meta_object_type', 'id'), ('meta_action_type', 'id'),
    ('aip_action_proposal', 'proposal_id'), ('aip_action_draft', 'draft_id'),
    ('aip_action_approval_event', 'approval_event_id'),
    ('asset_bundle_version', 'version_pk'), ('asset_bundle_evidence', 'version_pk'),
)


def upgrade():
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_catalog.pg_roles WHERE rolname='{ISSUER}';
      IF NOT FOUND THEN
        CREATE ROLE {ISSUER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls
        OR EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE roleid=r.oid OR member=r.oid) THEN
        RAISE EXCEPTION 'SOURCE_ISSUER_RESERVED_IDENTITY_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {ISSUER}')
    tenant = "org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
    for table in SCOPED_READ:
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        op.execute(f'CREATE POLICY source_issuer_read_a0v142 ON public.{table} TO {ISSUER} '
                   f'USING ({tenant}) WITH CHECK ({tenant})')
    for table in ('meta_object_type', 'meta_action_type', 'asset_bundle', 'asset_bundle_version',
                  'asset_bundle_artifact', 'asset_bundle_evidence'):
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
    source = f"action_type_id='{ACTION}' AND action_type_snapshot->>'id'='{ACTION}'"
    op.execute(f'GRANT SELECT ON public.aip_action_proposal TO {ISSUER}')
    op.execute(f'CREATE POLICY source_issuer_proposal_a0v142 ON public.aip_action_proposal TO {ISSUER} '
               f'USING ({tenant} AND {source}) WITH CHECK ({tenant} AND {source})')
    for table in ('aip_action_draft', 'aip_action_approval_event'):
        related = f"EXISTS(SELECT 1 FROM public.aip_action_proposal p WHERE p.org_id={table}.org_id AND p.project_id={table}.project_id AND p.proposal_id={table}.proposal_id AND {source})"
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        op.execute(f'CREATE POLICY source_issuer_related_a0v142 ON public.{table} TO {ISSUER} '
                   f'USING ({tenant} AND {related}) WITH CHECK ({tenant} AND {related})')
    for table, column in LOCK_COLUMNS:
        op.execute(f'GRANT UPDATE({column}) ON public.{table} TO {ISSUER}')
    op.execute(f"""CREATE FUNCTION public.source_issuer_read_lock_only_a0v142()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF current_user='{ISSUER}' OR session_user='{ISSUER}' THEN
          RAISE EXCEPTION 'SOURCE_ISSUER_READ_LOCK_ONLY' USING ERRCODE='42501';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF; RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_issuer_read_lock_only_a0v142() FROM PUBLIC')
    for table, _ in LOCK_COLUMNS:
        op.execute(f'CREATE TRIGGER aaa_source_issuer_read_lock_only_a0v142 BEFORE INSERT OR UPDATE OR DELETE '
                   f'ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.source_issuer_read_lock_only_a0v142()')
    for table in ('aip_license_source_issuance', 'aip_license_source_head', 'aip_agent_registry_receipt'):
        op.execute(f'GRANT SELECT,INSERT ON public.{table} TO {ISSUER}')
        op.execute(f'CREATE POLICY source_issuer_write_a0v142 ON public.{table} TO {ISSUER} '
                   f'USING ({tenant}) WITH CHECK ({tenant})')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean) TO {ISSUER}')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aos_license_source_lock(text,text,text,bigint,text,boolean) TO {ISSUER}')
    op.execute(f"""CREATE FUNCTION public.source_issuer_receipt_a0v142()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF current_user='{ISSUER}' OR session_user='{ISSUER}' THEN
          IF current_user<>'{ISSUER}' OR session_user<>'{ISSUER}' OR NEW.operation<>'source_license.issue'
            OR current_setting('transaction_isolation')<>'serializable' THEN
            RAISE EXCEPTION 'SOURCE_ISSUER_RECEIPT_OPERATION_REQUIRED' USING ERRCODE='42501';
          END IF;
        ELSIF NEW.operation='source_license.issue' AND current_user<>(
          SELECT r.rolname FROM pg_class c JOIN pg_roles r ON r.oid=c.relowner
            WHERE c.oid='public.aip_agent_registry_receipt'::regclass) THEN
          RAISE EXCEPTION 'SOURCE_LICENSE_INDEPENDENT_ISSUER_REQUIRED' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_issuer_receipt_a0v142() FROM PUBLIC')
    op.execute('CREATE TRIGGER source_issuer_receipt_a0v142 BEFORE INSERT ON public.aip_agent_registry_receipt '
               'FOR EACH ROW EXECUTE FUNCTION public.source_issuer_receipt_a0v142()')
    op.execute("""CREATE FUNCTION public.source_issuer_atomic_triple_a0v142()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF NEW.operation<>'source_license.issue' THEN RETURN NEW; END IF;
        IF NOT EXISTS(
          SELECT 1 FROM public.aip_license_source_issuance s JOIN public.aip_license_source_head h
            ON h.org_id=s.org_id AND h.project_id=s.project_id AND h.issuance_id=s.issuance_id
            AND h.bundle_id=s.bundle_id AND h.revision=s.revision AND h.content_hash=s.content_hash
          WHERE s.org_id=NEW.org_id AND s.project_id=NEW.project_id AND s.receipt_id=NEW.receipt_id
            AND s.issued_at<=clock_timestamp() AND s.expires_at>clock_timestamp()
            AND NEW.result_ref->>'resourceType'='SourceLicenseIssuance'
            AND NEW.result_ref->>'resourceId'=s.issuance_id) THEN
          RAISE EXCEPTION 'SOURCE_ISSUER_ATOMIC_TRIPLE_REQUIRED' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_issuer_atomic_triple_a0v142() FROM PUBLIC')
    op.execute('CREATE CONSTRAINT TRIGGER source_issuer_atomic_triple_a0v142 '
               'AFTER INSERT ON public.aip_agent_registry_receipt DEFERRABLE INITIALLY DEFERRED '
               'FOR EACH ROW EXECUTE FUNCTION public.source_issuer_atomic_triple_a0v142()')
    op.execute(f"""CREATE FUNCTION public.source_issuer_insert_a0v142()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      DECLARE p public.aip_action_proposal%ROWTYPE; e public.aip_action_approval_event%ROWTYPE;
        s public.aip_license_source_issuance%ROWTYPE; r public.aip_agent_registry_receipt%ROWTYPE;
        grant_terms jsonb; checked_at timestamptz; v_epoch bigint;
      BEGIN
        IF current_user<>(SELECT x.rolname FROM pg_class c JOIN pg_roles x ON x.oid=c.relowner WHERE c.oid=TG_RELID)
          AND (current_user<>'{ISSUER}' OR session_user<>'{ISSUER}') THEN
          RAISE EXCEPTION 'SOURCE_LICENSE_INDEPENDENT_ISSUER_REQUIRED' USING ERRCODE='42501';
        END IF;
        -- Original table owner retains isolated fixture/maintenance access.
        -- That access is never supplied by this migration or command.
        IF current_user<>'{ISSUER}' THEN RETURN NEW; END IF;
        IF current_setting('transaction_isolation')<>'serializable'
          OR NEW.org_id IS DISTINCT FROM NULLIF(current_setting('aos.org_id',true),'')
          OR NEW.project_id IS DISTINCT FROM NULLIF(current_setting('aos.project_id',true),'') THEN
          RAISE EXCEPTION 'SOURCE_ISSUER_SCOPE_OR_TRANSACTION_DRIFT' USING ERRCODE='42501';
        END IF;
        v_epoch:=public.aos_license_source_initialization_lock(
          NEW.org_id,NEW.project_id,NEW.bundle_id,NEW.revision,NEW.content_hash,false);
        IF TG_TABLE_NAME='aip_license_source_head' THEN
          SELECT * INTO s FROM public.aip_license_source_issuance WHERE org_id=NEW.org_id
            AND project_id=NEW.project_id AND issuance_id=NEW.issuance_id
            AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash;
          SELECT * INTO r FROM public.aip_agent_registry_receipt WHERE org_id=NEW.org_id
            AND project_id=NEW.project_id AND receipt_id=s.receipt_id;
          IF NOT FOUND OR NEW.epoch<>v_epoch OR s.expires_at<=clock_timestamp()
            OR s.owner_authorization_ref->>'schema' IS DISTINCT FROM 'aos-source-license-authorization/v1'
            OR r.operation IS DISTINCT FROM 'source_license.issue'
            OR r.status IS DISTINCT FROM 'applied'
            OR r.result_ref->>'resourceType' IS DISTINCT FROM 'SourceLicenseIssuance'
            OR r.result_ref->>'resourceId' IS DISTINCT FROM NEW.issuance_id THEN
            RAISE EXCEPTION 'SOURCE_ISSUER_EXACT_HEAD_REQUIRED' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END IF;
        SELECT * INTO p FROM public.aip_action_proposal WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND proposal_id=NEW.owner_authorization_ref->'approvedProposal'->>'resourceId' FOR SHARE;
        SELECT * INTO e FROM public.aip_action_approval_event WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND approval_event_id=NEW.owner_authorization_ref->>'approvalEventId' AND proposal_id=p.proposal_id FOR SHARE;
        grant_terms:=p.payload->'requestedGrant';
        PERFORM subject FROM public.meta_membership WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND subject IN (p.created_by,e.actor_id) FOR SHARE;
        PERFORM installation_id FROM public.bundle_installation WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND installation_id=NEW.installation_id FOR SHARE;
        checked_at:=clock_timestamp();
        SELECT * INTO r FROM public.aip_agent_registry_receipt WHERE org_id=NEW.org_id AND project_id=NEW.project_id
          AND receipt_id=NEW.receipt_id;
        IF p.proposal_id IS NULL OR e.approval_event_id IS NULL OR r.receipt_id IS NULL
          OR p.action_type_id<>'{ACTION}' OR p.action_type_snapshot->>'id'<>'{ACTION}' OR p.status<>'approved'
          OR NEW.owner_authorization_ref->>'schema' IS DISTINCT FROM 'aos-source-license-authorization/v1'
          OR NEW.owner_authorization_ref->'approvedProposal'->>'resourceType' IS DISTINCT FROM 'ActionProposal'
          OR NEW.owner_authorization_ref->'approvedProposal'->>'revision' IS DISTINCT FROM p.version::text
          OR NEW.owner_authorization_ref->'approvedProposal'->>'contentHash' IS DISTINCT FROM p.proposal_hash
          OR NEW.owner_authorization_ref->>'maker' IS DISTINCT FROM p.created_by
          OR NEW.owner_authorization_ref->>'checker' IS DISTINCT FROM e.actor_id
          OR NEW.owner_authorization_ref->>'grantBindingHash' IS DISTINCT FROM p.action_binding_hash
          OR NEW.owner_authorization_ref->'requestedGrant' IS DISTINCT FROM grant_terms
          OR e.actor_id=p.created_by OR e.decision<>'approved' OR e.slot_id IS DISTINCT FROM 'checker.1'
          OR e.proposal_version<>p.version-1 OR e.proposal_hash<>p.proposal_hash
          OR e.action_binding_hash IS DISTINCT FROM p.action_binding_hash
          OR e.approval_policy_hash IS DISTINCT FROM p.approval_policy_hash
          OR e.expires_at IS NULL OR e.expires_at<=checked_at OR p.expires_at<=checked_at
          OR (SELECT count(*) FROM public.aip_action_approval_event WHERE org_id=p.org_id AND project_id=p.project_id
               AND proposal_id=p.proposal_id AND decision='approved')<>1
          OR (SELECT count(*) FROM public.meta_membership WHERE org_id=p.org_id AND project_id=p.project_id
               AND subject IN (p.created_by,e.actor_id) AND lower(role)='owner')<>2
          OR EXISTS(SELECT 1 FROM public.aip_action_withdrawal_event WHERE org_id=p.org_id AND project_id=p.project_id AND proposal_id=p.proposal_id)
          OR grant_terms->'source'->>'resourceId' IS DISTINCT FROM NEW.bundle_id
          OR grant_terms->'source'->>'revision' IS DISTINCT FROM NEW.revision::text
          OR grant_terms->'source'->>'contentHash' IS DISTINCT FROM NEW.content_hash
          OR grant_terms->>'installationId' IS DISTINCT FROM NEW.installation_id::text
          OR grant_terms->>'installationEtag' IS DISTINCT FROM NEW.installation_etag::text
          OR NEW.policy_ref IS DISTINCT FROM grant_terms->'policyRef'
          OR NOT EXISTS(SELECT 1 FROM public.bundle_installation WHERE org_id=NEW.org_id AND project_id=NEW.project_id
               AND installation_id=NEW.installation_id AND etag_version=NEW.installation_etag
               AND current_revision=active_revision AND current_revision::text=grant_terms->>'installationRevision')
          OR EXISTS(SELECT 1 FROM public.aip_evidence_bundle_revoke_event WHERE org_id=NEW.org_id AND project_id=NEW.project_id
               AND bundle_id=NEW.bundle_id AND revision=NEW.revision AND content_hash=NEW.content_hash)
          OR NEW.issued_at>checked_at OR NEW.issued_at<(grant_terms->>'validFrom')::timestamptz
          OR NEW.expires_at<=checked_at OR NEW.expires_at>p.expires_at OR NEW.expires_at>e.expires_at
          OR NEW.expires_at>(grant_terms->>'validUntil')::timestamptz
          OR r.operation<>'source_license.issue' OR r.status<>'applied' OR r.created_by<>p.created_by
          OR r.resource_ref->>'resourceType' IS DISTINCT FROM 'ActionProposal'
          OR r.resource_ref->>'resourceId' IS DISTINCT FROM p.proposal_id
          OR r.resource_ref->>'revision' IS DISTINCT FROM p.version::text
          OR r.result_ref->>'resourceType' IS DISTINCT FROM 'SourceLicenseIssuance'
          OR r.result_ref->>'resourceId' IS DISTINCT FROM NEW.issuance_id THEN
          RAISE EXCEPTION 'SOURCE_ISSUER_ORIGINAL_APPROVAL_OR_GRANT_DRIFT' USING ERRCODE='42501';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_issuer_insert_a0v142() FROM PUBLIC')
    for table in ('aip_license_source_issuance', 'aip_license_source_head'):
        op.execute(f'CREATE TRIGGER source_issuer_insert_a0v142 BEFORE INSERT ON public.{table} '
                   'FOR EACH ROW EXECUTE FUNCTION public.source_issuer_insert_a0v142()')


def downgrade():
    raise RuntimeError('source issuance authority cannot be silently downgraded')
