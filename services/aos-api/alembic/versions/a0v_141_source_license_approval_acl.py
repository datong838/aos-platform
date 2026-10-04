"""Narrow original source approval ACL; login provisioning stays closed."""
from alembic import op

revision = 'a0v_141'
down_revision = 'a0v_140'
branch_labels = depends_on = None
ISSUER = 'aos_source_license_approval_issuer'
ACTION = 'aip_issue_source_license'
SCOPED_READ = (
    'meta_membership', 'bundle_installation', 'bundle_installation_revision',
    'bundle_composition', 'bundle_composition_lock',
    'aip_evidence_bundle_revision', 'aip_evidence_bundle_build_provenance',
    'aip_evidence_bundle_revoke_event', 'aip_production_contract_receipt',
    'aip_action_withdrawal_event',
)


def upgrade():
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{ISSUER}';
      IF NOT FOUND OR r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb
         OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls
         OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid) THEN
        RAISE EXCEPTION 'SOURCE_APPROVAL_RESERVED_IDENTITY_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {ISSUER}')
    tenant = "org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
    for table in SCOPED_READ:
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        if table in ('meta_membership','bundle_installation'):
            op.execute(f"CREATE POLICY source_approval_read_a0v141 ON public.{table} TO {ISSUER} USING ({tenant}) WITH CHECK ({tenant})")
        else:
            op.execute(f"CREATE POLICY source_approval_read_a0v141 ON public.{table} FOR SELECT TO {ISSUER} USING ({tenant})")
    for table in ('meta_object_type', 'meta_action_type', 'asset_bundle', 'asset_bundle_version',
                  'asset_bundle_artifact', 'asset_bundle_evidence'):
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
    # PostgreSQL requires some UPDATE privilege for FOR SHARE. These columns
    # grant row locking only: invoker triggers below reject actual DML.
    for table, column in (('meta_membership', 'subject'), ('bundle_installation', 'installation_id'),
                          ('meta_object_type', 'id'), ('meta_action_type', 'id')):
        op.execute(f'GRANT UPDATE({column}) ON public.{table} TO {ISSUER}')
    op.execute(f"""CREATE FUNCTION public.source_approval_read_lock_only_a0v141()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF current_user='{ISSUER}' OR session_user='{ISSUER}' THEN
          RAISE EXCEPTION 'SOURCE_APPROVAL_READ_LOCK_ONLY' USING ERRCODE='42501';
        END IF;
        IF TG_OP='DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_approval_read_lock_only_a0v141() FROM PUBLIC')
    for table in ('meta_membership', 'bundle_installation', 'meta_object_type', 'meta_action_type'):
        op.execute(f'CREATE TRIGGER source_approval_read_lock_only_a0v141 BEFORE INSERT OR UPDATE OR DELETE '
                   f'ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.source_approval_read_lock_only_a0v141()')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aos_license_source_initialization_lock(text,text,text,bigint,text,boolean) TO {ISSUER}')
    source = f"action_type_id='{ACTION}' AND action_type_snapshot->>'id'='{ACTION}'"
    op.execute(f'GRANT SELECT,UPDATE(status,version,updated_at) ON public.aip_action_proposal TO {ISSUER}')
    op.execute(f"CREATE POLICY source_approval_proposal_a0v141 ON public.aip_action_proposal TO {ISSUER} USING ({tenant} AND {source}) WITH CHECK ({tenant} AND {source})")
    # Explicit outer aliases prevent correlated predicates from becoming p=p.
    for table in ('aip_action_draft', 'aip_action_approval_event', 'aip_action_event'):
        related = f"EXISTS(SELECT 1 FROM public.aip_action_proposal p WHERE p.org_id={table}.org_id AND p.project_id={table}.project_id AND p.proposal_id={table}.proposal_id AND p.action_type_id='{ACTION}' AND p.action_type_snapshot->>'id'='{ACTION}')"
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        op.execute(f"CREATE POLICY source_approval_related_a0v141 ON public.{table} TO {ISSUER} USING ({tenant} AND {related}) WITH CHECK ({tenant} AND {related})")
    op.execute(f'GRANT UPDATE(status,updated_at) ON public.aip_action_draft TO {ISSUER}')
    op.execute(f'GRANT INSERT ON public.aip_action_approval_event,public.aip_action_event TO {ISSUER}')
    op.execute(f"""CREATE FUNCTION public.source_approval_lifecycle_a0v141()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF TG_OP='INSERT' THEN
          IF (NEW.action_type_id='{ACTION}' OR NEW.action_type_snapshot->>'id'='{ACTION}')
             AND (NEW.status<>'drafted' OR NEW.version<>1) THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_INITIAL_DRAFT_REQUIRED' USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END IF;
        IF OLD.action_type_id='{ACTION}' OR OLD.action_type_snapshot->>'id'='{ACTION}' THEN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_PROPOSAL_DELETE_FORBIDDEN' USING ERRCODE='42501';
          END IF;
          IF NEW.version<>OLD.version+1 THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_VERSION_INVALID' USING ERRCODE='23514';
          END IF;
          IF NOT ((OLD.status='drafted' AND NEW.status IN ('approved','rejected','withdrawn','expired'))
              OR (OLD.status='approved' AND NEW.status IN ('withdrawn','expired'))) THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_TRANSITION_INVALID' USING ERRCODE='42501';
          END IF;
          IF NEW.status IN ('approved','rejected') THEN
            IF session_user<>'{ISSUER}' OR current_user<>'{ISSUER}' THEN
              RAISE EXCEPTION 'SOURCE_LICENSE_INDEPENDENT_APPROVAL_ISSUER_REQUIRED' USING ERRCODE='42501';
            END IF;
            IF NOT EXISTS(SELECT 1 FROM public.aip_action_approval_event e WHERE
              e.org_id=OLD.org_id AND e.project_id=OLD.project_id AND e.proposal_id=OLD.proposal_id
              AND e.proposal_version=OLD.version AND e.proposal_hash=OLD.proposal_hash
              AND e.decision=NEW.status AND e.expires_at>clock_timestamp()) THEN
              RAISE EXCEPTION 'SOURCE_APPROVAL_BOUND_EVENT_REQUIRED' USING ERRCODE='42501';
            END IF;
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_approval_lifecycle_a0v141() FROM PUBLIC')
    op.execute('CREATE TRIGGER zz_source_approval_lifecycle_a0v141 BEFORE INSERT OR UPDATE OR DELETE '
               'ON public.aip_action_proposal FOR EACH ROW EXECUTE FUNCTION public.source_approval_lifecycle_a0v141()')
    op.execute(f"""CREATE FUNCTION public.source_approval_draft_a0v141()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN
        IF OLD.snapshot->'actionType'->>'id'='{ACTION}' THEN
          IF NEW.status IN ('approved','rejected') THEN
            IF current_user<>'{ISSUER}' OR session_user<>'{ISSUER}' THEN
              RAISE EXCEPTION 'SOURCE_LICENSE_INDEPENDENT_APPROVAL_ISSUER_REQUIRED' USING ERRCODE='42501';
            END IF;
            IF NOT EXISTS(SELECT 1 FROM public.aip_action_proposal p WHERE p.org_id=OLD.org_id
              AND p.project_id=OLD.project_id AND p.proposal_id=OLD.proposal_id
              AND p.proposal_hash=OLD.proposal_hash AND p.status=NEW.status) THEN
              RAISE EXCEPTION 'SOURCE_APPROVAL_BOUND_PROPOSAL_REQUIRED' USING ERRCODE='42501';
            END IF;
          END IF;
          IF NOT ((OLD.status='awaiting_approval' AND NEW.status IN ('approved','rejected','withdrawn','expired'))
              OR (OLD.status='approved' AND NEW.status IN ('withdrawn','expired'))) THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_TRANSITION_INVALID' USING ERRCODE='42501';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_approval_draft_a0v141() FROM PUBLIC')
    op.execute('CREATE TRIGGER source_approval_draft_a0v141 BEFORE UPDATE ON public.aip_action_draft '
               'FOR EACH ROW EXECUTE FUNCTION public.source_approval_draft_a0v141()')
    op.execute(f"""CREATE FUNCTION public.source_approval_exact_event_a0v141()
      RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      DECLARE p public.aip_action_proposal%ROWTYPE; checked_at timestamptz;
      BEGIN
        SELECT * INTO p FROM public.aip_action_proposal WHERE org_id=NEW.org_id
          AND project_id=NEW.project_id AND proposal_id=NEW.proposal_id;
        IF p.action_type_id='{ACTION}' OR p.action_type_snapshot->>'id'='{ACTION}' THEN
          PERFORM subject FROM public.meta_membership WHERE org_id=p.org_id AND project_id=p.project_id
            AND subject IN (p.created_by,NEW.actor_id) FOR SHARE;
          checked_at:=clock_timestamp();
          IF p.status<>'drafted' OR p.risk_level<>'R2' OR NEW.actor_id=p.created_by
            OR NEW.proposal_version IS DISTINCT FROM p.version
            OR NEW.proposal_hash IS DISTINCT FROM p.proposal_hash
            OR NEW.action_binding_hash IS DISTINCT FROM p.action_binding_hash
            OR NEW.approval_policy_hash IS DISTINCT FROM p.approval_policy_hash
            OR NEW.slot_id IS DISTINCT FROM 'checker.1'
            OR NEW.eligibility_snapshot_hash IS NULL
            OR NEW.expires_at IS NULL OR NEW.expires_at<=checked_at OR NEW.expires_at>p.expires_at
            OR p.expires_at<=checked_at
            OR (SELECT count(*) FROM public.meta_membership WHERE org_id=p.org_id AND project_id=p.project_id
                 AND subject IN (p.created_by,NEW.actor_id) AND lower(role)='owner')<>2
            OR EXISTS(SELECT 1 FROM public.aip_action_withdrawal_event w WHERE
                 w.org_id=p.org_id AND w.project_id=p.project_id AND w.proposal_id=p.proposal_id) THEN
            RAISE EXCEPTION 'SOURCE_APPROVAL_EXACT_CURRENT_OWNER_EVENT_REQUIRED' USING ERRCODE='42501';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.source_approval_exact_event_a0v141() FROM PUBLIC')
    op.execute('CREATE TRIGGER zz_source_approval_exact_event_a0v141 BEFORE INSERT '
               'ON public.aip_action_approval_event FOR EACH ROW EXECUTE FUNCTION public.source_approval_exact_event_a0v141()')


def downgrade():
    raise RuntimeError('source approval ACL cannot be silently downgraded')
