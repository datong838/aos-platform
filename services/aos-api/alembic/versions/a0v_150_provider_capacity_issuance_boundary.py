"""Dedicated read/lock identity for capacity issuance, with no publication grants yet."""
from alembic import op

revision='a0v_150'
down_revision='a0v_149'
branch_labels=depends_on=None
ISSUER='aos_provider_capacity_issuer'
SCOPED=(
    'meta_membership','aip_provider_capacity_request','aip_provider_capacity_candidate',
    'aip_provider_instance_head','aip_provider_instance_revision','aip_evidence_bundle_revision',
    'aip_evidence_bundle_build_provenance','aip_evidence_bundle_revoke_event',
    'aip_production_contract_receipt','aip_action_withdrawal_event',
)
LOCKS=(('meta_membership','subject'),('aip_provider_instance_head','provider_instance_id'),
    ('meta_object_type','id'),('meta_action_type','id'),('aip_action_proposal','proposal_id'))
TENANT="org_id='org-org' AND project_id='dev-project' AND org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),'')"
ACTION="action_type_id IN ('aip_request_provider_capacity','aip_review_provider_capacity_source') AND action_type_snapshot->>'id'=action_type_id"
GUARD_BODY="""
BEGIN
  IF current_user='aos_provider_capacity_issuer' OR session_user='aos_provider_capacity_issuer' THEN
    RAISE EXCEPTION 'CAPACITY_ISSUER_READ_LOCK_ONLY' USING ERRCODE='42501';
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
"""
ISSUER_LOCK_BODY="""
BEGIN
  IF session_user<>'aos_provider_capacity_issuer' THEN
    RAISE EXCEPTION 'CAPACITY_EVIDENCE_PRIVATE_ISSUER_REQUIRED' USING ERRCODE='42501';
  END IF;
  RETURN public.aos_capacity_evidence_epoch_lock(p_org,p_project,p_id);
END;
"""


def upgrade():
    op.execute(f"""DO $$ DECLARE r record; BEGIN
      SELECT * INTO r FROM pg_roles WHERE rolname='{ISSUER}';
      IF NOT FOUND THEN
        CREATE ROLE {ISSUER} NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
      ELSIF r.rolcanlogin OR r.rolinherit OR r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
        OR r.rolreplication OR r.rolbypassrls THEN
        RAISE EXCEPTION 'CAPACITY_ISSUER_RESERVED_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid='{ISSUER}'::regrole OR member='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class WHERE relowner='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_database WHERE datdba='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_class c,LATERAL aclexplode(c.relacl) a WHERE a.grantee='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_attribute c,LATERAL aclexplode(c.attacl) a WHERE a.grantee='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE a.grantee='{ISSUER}'::regrole)
        OR EXISTS(SELECT 1 FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a WHERE a.grantee='{ISSUER}'::regrole) THEN
        RAISE EXCEPTION 'CAPACITY_ISSUER_RESERVED_ROLE_DRIFT' USING ERRCODE='42501';
      END IF;
    END $$""")
    op.execute(f'GRANT USAGE ON SCHEMA public TO {ISSUER}')
    # These legacy trigger functions have no direct-call purpose. Keep their
    # existing triggers/bodies and named grants, closing PUBLIC attachment.
    for name in (
        'extension_dispatch_cutover_history_guard_ar2_014',
        'extension_dispatch_lifecycle_history_guard_ar2_017',
        'extension_event_control_dispatch_history_guard_a0v_054',
        'extension_runtime_uninstall_consistency_ar2_018',
        'snapshot_stalled_group_terminal_guard_a0v_091',
        'snapshot_unaccepted_group_terminal_guard_a0v_083',
        'unaccepted_analysis_terminal_guard_a0v_060'):
        op.execute(f'REVOKE EXECUTE ON FUNCTION public.{name}() FROM PUBLIC')
    for table in SCOPED:
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        op.execute(f'CREATE POLICY capacity_issuer_scope_a0v150 ON public.{table} TO {ISSUER} USING({TENANT}) WITH CHECK({TENANT})')
        op.execute(f'CREATE POLICY capacity_issuer_scope_restrict_a0v150 ON public.{table} AS RESTRICTIVE TO {ISSUER} USING({TENANT}) WITH CHECK({TENANT})')
    for table in ('meta_object_type','meta_action_type'):
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
    op.execute(f'GRANT SELECT ON public.aip_action_proposal TO {ISSUER}')
    op.execute(f'CREATE POLICY capacity_issuer_proposal_a0v150 ON public.aip_action_proposal TO {ISSUER} '
        f'USING({TENANT} AND {ACTION}) WITH CHECK({TENANT} AND {ACTION})')
    op.execute(f'CREATE POLICY capacity_issuer_proposal_restrict_a0v150 ON public.aip_action_proposal AS RESTRICTIVE TO {ISSUER} '
        f'USING({TENANT} AND {ACTION}) WITH CHECK({TENANT} AND {ACTION})')
    for table in ('aip_action_draft','aip_action_approval_event'):
        related=f"EXISTS(SELECT 1 FROM public.aip_action_proposal p WHERE p.org_id={table}.org_id AND p.project_id={table}.project_id AND p.proposal_id={table}.proposal_id)"
        op.execute(f'GRANT SELECT ON public.{table} TO {ISSUER}')
        op.execute(f'CREATE POLICY capacity_issuer_related_a0v150 ON public.{table} TO {ISSUER} '
            f'USING({TENANT} AND {related}) WITH CHECK({TENANT} AND {related})')
        op.execute(f'CREATE POLICY capacity_issuer_related_restrict_a0v150 ON public.{table} AS RESTRICTIVE TO {ISSUER} '
            f'USING({TENANT} AND {related}) WITH CHECK({TENANT} AND {related})')
    for table,column in LOCKS:
        op.execute(f'GRANT UPDATE({column}) ON public.{table} TO {ISSUER}')
    op.execute('CREATE FUNCTION public.capacity_issuer_read_lock_only_a0v150() RETURNS trigger '
        f'LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $body${GUARD_BODY}$body$')
    op.execute('REVOKE ALL ON FUNCTION public.capacity_issuer_read_lock_only_a0v150() FROM PUBLIC')
    for table,_ in LOCKS:
        op.execute(f'CREATE TRIGGER capacity_issuer_read_lock_only_a0v150 BEFORE INSERT OR UPDATE OR DELETE ON public.{table} '
            'FOR EACH ROW EXECUTE FUNCTION public.capacity_issuer_read_lock_only_a0v150()')
    op.execute('CREATE FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(p_org text,p_project text,p_id text) '
        f'RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $body${ISSUER_LOCK_BODY}$body$')
    op.execute('ALTER FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) OWNER TO aos_capacity_evidence_epoch_owner')
    op.execute('REVOKE ALL ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) FROM PUBLIC,aos_runtime')
    op.execute(f'GRANT EXECUTE ON FUNCTION public.aos_capacity_evidence_epoch_issuer_lock(text,text,text) TO {ISSUER}')


def downgrade():
    raise RuntimeError('Capacity issuer identity must not be silently removed')
