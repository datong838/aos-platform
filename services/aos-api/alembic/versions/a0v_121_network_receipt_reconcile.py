"""Expose exact read-only network consumption receipts without table grants."""
from alembic import op
revision = 'a0v_121'
down_revision = 'a0v_120'
branch_labels = depends_on = None

RECONCILE_SQL = """CREATE FUNCTION public.aip_reconcile_network_receipt_a0v_121(
    p_org text,p_project text,p_proposal text,p_event text) RETURNS jsonb
    LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE
    r public.aip_network_policy_receipt%ROWTYPE;
    p public.aip_action_proposal%ROWTYPE;
    v public.aip_network_policy_revision%ROWTYPE;
    digest text;
BEGIN
    IF current_setting('transaction_read_only') IS DISTINCT FROM 'on'
       OR session_user<>'aos_network_consumer_call' OR current_user<>'aos_network_consumer_owner'
       OR p_org IS NULL OR p_org='' OR p_org<>btrim(p_org)
       OR p_project IS NULL OR p_project='' OR p_project<>btrim(p_project)
       OR p_proposal IS NULL OR p_proposal='' OR p_proposal<>btrim(p_proposal)
       OR p_event IS NULL OR p_event='' OR p_event<>btrim(p_event)
       OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
       OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project THEN
        RAISE EXCEPTION 'NETWORK_RECONCILE_READ_ONLY_IDENTITY_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN(session_user,current_user)
        AND (rolsuper OR rolbypassrls OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication
             OR (rolname=current_user AND rolcanlogin)))
       OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN(session_user::regrole,current_user::regrole)
                 OR member IN(session_user::regrole,current_user::regrole)) THEN
        RAISE EXCEPTION 'NETWORK_RECONCILE_ROLE_DRIFT' USING ERRCODE='42501';
    END IF;
    SELECT * INTO r FROM public.aip_network_policy_receipt
        WHERE org_id=p_org AND project_id=p_project AND operation='network_policy.activate'
          AND idempotency_key=p_proposal;
    IF NOT FOUND THEN RETURN jsonb_build_object('status','unresolved'); END IF;
    SELECT * INTO p FROM public.aip_action_proposal
        WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal;
    IF NOT FOUND OR p.action_type_id IS DISTINCT FROM 'aip_activate_network_policy' THEN
        RETURN jsonb_build_object('status','conflict');
    END IF;
    digest := public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
        'operation','network_policy.activate','tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
        'proposalId',p_proposal,'approvalEventId',p_event,
        'targetContentHash',p.payload->>'targetContentHash','bindingHash',p.action_binding_hash));
    IF r.request_hash IS DISTINCT FROM digest OR r.receipt_id IS DISTINCT FROM 'network-consume-'||digest
       OR r.result_ref->>'proposalId' IS DISTINCT FROM p_proposal
       OR r.result_ref->>'approvalEventId' IS DISTINCT FROM p_event
       OR r.result_ref->>'receiptId' IS DISTINCT FROM r.receipt_id
       OR r.result_ref->>'resourceType' IS DISTINCT FROM 'NetworkPolicyRevision'
       OR r.result_ref->>'resourceId' IS DISTINCT FROM p.payload->'candidate'->>'policyId'
       OR r.result_ref->'revision' IS DISTINCT FROM p.payload->'candidate'->'revision'
       OR r.result_ref->>'contentHash' IS DISTINCT FROM p.payload->>'targetContentHash' THEN
        RETURN jsonb_build_object('status','conflict');
    END IF;
    SELECT * INTO v FROM public.aip_network_policy_revision
        WHERE org_id=p_org AND project_id=p_project AND policy_id=r.result_ref->>'resourceId'
          AND revision::text=r.result_ref->>'revision';
    IF NOT FOUND OR v.content_hash IS DISTINCT FROM r.result_ref->>'contentHash'
       OR v.content_hash IS DISTINCT FROM public.aip_network_consumer_hash_a0v_120(
           v.payload-ARRAY['tenant','contentHash','createdBy','createdAt'])
       OR v.payload->'tenant' IS DISTINCT FROM jsonb_build_object('orgId',p_org,'projectId',p_project) THEN
        RETURN jsonb_build_object('status','conflict');
    END IF;
    RETURN jsonb_build_object('status','observed','receipt',r.result_ref);
END $$"""


def upgrade():
    op.get_bind().exec_driver_sql(RECONCILE_SQL.replace('%', '%%'))
    signature = 'public.aip_reconcile_network_receipt_a0v_121(text,text,text,text)'
    op.execute(f'ALTER FUNCTION {signature} OWNER TO aos_network_consumer_owner')
    op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_network_consumer_call')


def downgrade():
    raise RuntimeError('receipt reconciliation authority may not be silently removed')
