"""Persist new network approval delivery without enabling a worker or replay."""
from alembic import op

revision = 'a0v_123'
down_revision = 'a0v_122'
branch_labels = depends_on = None

OWNER = 'aos_network_consumer_owner'
CALLER = 'aos_network_consumer_call'
MUTABLE = 'status,claim_token,claim_until,attempt,next_attempt,receipt_id'

GUARD = """
    IF session_user<>'aos_network_consumer_call' OR current_user<>'aos_network_consumer_owner'
       OR p_org IS NULL OR p_org='' OR p_org<>btrim(p_org)
       OR p_project IS NULL OR p_project='' OR p_project<>btrim(p_project)
       OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
       OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
       OR p_actor IS NULL OR p_actor='' OR p_actor<>btrim(p_actor) OR p_token IS NULL THEN
        RAISE EXCEPTION 'NETWORK_DELIVERY_IDENTITY_REQUIRED' USING ERRCODE='42501';
    END IF;
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN(session_user,current_user)
        AND (rolsuper OR rolbypassrls OR rolinherit OR rolcreatedb OR rolcreaterole OR rolreplication
             OR (rolname=current_user AND rolcanlogin)))
       OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN(session_user::regrole,current_user::regrole)
                 OR member IN(session_user::regrole,current_user::regrole)) THEN
        RAISE EXCEPTION 'NETWORK_DELIVERY_ROLE_DRIFT' USING ERRCODE='42501';
    END IF;
    PERFORM subject FROM public.meta_membership WHERE org_id=p_org AND project_id=p_project
        AND subject=p_actor AND lower(role) IN ('owner','admin') FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'NETWORK_DELIVERY_MEMBER_REQUIRED' USING ERRCODE='42501';
    END IF;
"""

ENQUEUE = """CREATE FUNCTION public.aip_enqueue_network_delivery_a0v_123() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
BEGIN
    IF NEW.decision='approved' AND EXISTS(SELECT 1 FROM public.aip_action_proposal
        WHERE org_id=NEW.org_id AND project_id=NEW.project_id AND proposal_id=NEW.proposal_id
          AND action_type_id='aip_activate_network_policy') THEN
        IF session_user<>'aos_network_approval_issuer' OR current_user<>'aos_network_consumer_owner'
           OR current_setting('aos.org_id',true) IS DISTINCT FROM NEW.org_id
           OR current_setting('aos.project_id',true) IS DISTINCT FROM NEW.project_id THEN
            RAISE EXCEPTION 'NETWORK_DELIVERY_ISSUER_REQUIRED' USING ERRCODE='42501';
        END IF;
        INSERT INTO public.aip_network_approval_delivery(org_id,project_id,approval_event_id,proposal_id)
            VALUES(NEW.org_id,NEW.project_id,NEW.approval_event_id,NEW.proposal_id);
    END IF;
    RETURN NEW;
END $$"""

CLAIM = """CREATE FUNCTION public.aip_claim_network_delivery_a0v_123(
    p_org text,p_project text,p_actor text,p_token uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.aip_network_approval_delivery%ROWTYPE; mode text;
BEGIN
""" + GUARD + """
    SELECT q.* INTO d FROM public.aip_network_approval_delivery q
        JOIN public.aip_action_proposal p USING(org_id,project_id,proposal_id)
        WHERE q.org_id=p_org AND q.project_id=p_project AND p.created_by=p_actor
          AND p.action_type_id='aip_activate_network_policy'
          AND q.next_attempt<=clock_timestamp()
          AND (q.status IN ('pending','unknown') OR (q.status='claimed' AND q.claim_until<=clock_timestamp()))
        ORDER BY q.next_attempt,q.approval_event_id LIMIT 1 FOR UPDATE OF q SKIP LOCKED;
    IF NOT FOUND THEN RETURN NULL; END IF;
    mode := CASE WHEN d.status='pending' THEN 'dispatch' ELSE 'inquiry' END;
    UPDATE public.aip_network_approval_delivery SET status='claimed',claim_token=p_token,
        claim_until=clock_timestamp()+interval '30 seconds',attempt=attempt+1
        WHERE org_id=p_org AND project_id=p_project AND approval_event_id=d.approval_event_id
        RETURNING * INTO d;
    RETURN jsonb_build_object('mode',mode,'proposalId',d.proposal_id,'approvalEventId',d.approval_event_id,
        'claimToken',d.claim_token,'claimUntil',d.claim_until,'attempt',d.attempt);
END $$"""

FINISH = """CREATE FUNCTION public.aip_finish_network_delivery_a0v_123(
    p_org text,p_project text,p_actor text,p_event text,p_token uuid) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE d public.aip_network_approval_delivery%ROWTYPE; p public.aip_action_proposal%ROWTYPE;
    r public.aip_network_policy_receipt%ROWTYPE; digest text;
BEGIN
""" + GUARD + """
    SELECT q.* INTO d FROM public.aip_network_approval_delivery q
        JOIN public.aip_action_proposal a USING(org_id,project_id,proposal_id)
        WHERE q.org_id=p_org AND q.project_id=p_project AND q.approval_event_id=p_event
          AND a.created_by=p_actor AND a.action_type_id='aip_activate_network_policy'
        FOR UPDATE OF q;
    IF NOT FOUND OR d.status<>'claimed' OR d.claim_token IS DISTINCT FROM p_token
       OR d.claim_until<=clock_timestamp() THEN
        RAISE EXCEPTION 'NETWORK_DELIVERY_CLAIM_REQUIRED' USING ERRCODE='42501';
    END IF;
    SELECT * INTO p FROM public.aip_action_proposal
        WHERE org_id=p_org AND project_id=p_project AND proposal_id=d.proposal_id;
    SELECT * INTO r FROM public.aip_network_policy_receipt
        WHERE org_id=p_org AND project_id=p_project AND operation='network_policy.activate'
          AND idempotency_key=d.proposal_id;
    IF NOT FOUND THEN
        UPDATE public.aip_network_approval_delivery SET status='unknown',claim_token=NULL,claim_until=NULL,
            next_attempt=clock_timestamp()+interval '30 seconds'
            WHERE org_id=p_org AND project_id=p_project AND approval_event_id=p_event;
        RETURN jsonb_build_object('status','unknown');
    END IF;
    -- The original consumer's canonical hash binds tenant, proposal, event, target and binding.
    -- This acknowledges its immutable result; it never grants fresh execution authority.
    digest := public.aip_network_consumer_hash_a0v_120(jsonb_build_object(
        'operation','network_policy.activate','tenant',jsonb_build_object('orgId',p_org,'projectId',p_project),
        'proposalId',d.proposal_id,'approvalEventId',p_event,
        'targetContentHash',p.payload->>'targetContentHash','bindingHash',p.action_binding_hash));
    IF r.request_hash IS DISTINCT FROM digest OR r.receipt_id IS DISTINCT FROM 'network-consume-'||digest
       OR r.result_ref->>'proposalId' IS DISTINCT FROM d.proposal_id
       OR r.result_ref->>'approvalEventId' IS DISTINCT FROM p_event
       OR r.result_ref->>'receiptId' IS DISTINCT FROM r.receipt_id
       OR r.result_ref->>'resourceType' IS DISTINCT FROM 'NetworkPolicyRevision'
       OR r.result_ref->>'resourceId' IS DISTINCT FROM p.payload->'candidate'->>'policyId'
       OR r.result_ref->'revision' IS DISTINCT FROM p.payload->'candidate'->'revision'
       OR r.result_ref->>'contentHash' IS DISTINCT FROM p.payload->>'targetContentHash' THEN
        RAISE EXCEPTION 'NETWORK_DELIVERY_RECEIPT_CONFLICT' USING ERRCODE='23514';
    END IF;
    UPDATE public.aip_network_approval_delivery SET status='delivered',receipt_id=r.receipt_id,
        claim_token=NULL,claim_until=NULL
        WHERE org_id=p_org AND project_id=p_project AND approval_event_id=p_event;
    RETURN jsonb_build_object('status','delivered','receiptId',r.receipt_id);
END $$"""


def upgrade():
    # Deployment must enter its separately approved zero-execution migration window.
    op.execute("""DO $$ BEGIN
        IF (SELECT count(*) FROM pg_roles WHERE rolname IN
            ('aos_network_consumer_call','aos_network_consumer_owner'))<>2
           OR EXISTS(SELECT 1 FROM pg_roles WHERE rolname IN
            ('aos_network_consumer_call','aos_network_consumer_owner') AND
            (rolcanlogin OR rolinherit OR rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication))
           OR EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid IN
            ('aos_network_consumer_call'::regrole,'aos_network_consumer_owner'::regrole) OR member IN
            ('aos_network_consumer_call'::regrole,'aos_network_consumer_owner'::regrole)) THEN
            RAISE EXCEPTION 'NETWORK_DELIVERY_ROLE_DRIFT' USING ERRCODE='42501';
        END IF;
    END $$""")
    op.execute("""CREATE TABLE public.aip_network_approval_delivery(
        org_id text NOT NULL,project_id text NOT NULL,approval_event_id text NOT NULL,proposal_id text NOT NULL,
        status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','claimed','unknown','delivered')),
        claim_token uuid,claim_until timestamptz,attempt bigint NOT NULL DEFAULT 0 CHECK(attempt>=0),
        next_attempt timestamptz NOT NULL DEFAULT clock_timestamp(),receipt_id text,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(org_id,project_id,approval_event_id),
        FOREIGN KEY(org_id,project_id,approval_event_id)
            REFERENCES public.aip_action_approval_event(org_id,project_id,approval_event_id),
        FOREIGN KEY(org_id,project_id,proposal_id)
            REFERENCES public.aip_action_proposal(org_id,project_id,proposal_id),
        CHECK((status='claimed')=(claim_token IS NOT NULL AND claim_until IS NOT NULL)),
        CHECK((status='delivered')=(receipt_id IS NOT NULL))
    )""")
    op.execute("CREATE INDEX aip_network_delivery_ready ON public.aip_network_approval_delivery"
               "(org_id,project_id,next_attempt,approval_event_id) WHERE status<>'delivered'")
    op.execute('ALTER TABLE public.aip_network_approval_delivery ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.aip_network_approval_delivery FORCE ROW LEVEL SECURITY')
    op.execute(f"""CREATE POLICY network_delivery_scope ON public.aip_network_approval_delivery TO {OWNER}
        USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
        WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""")
    op.execute(f'REVOKE ALL ON public.aip_network_approval_delivery FROM PUBLIC,aos_runtime,{CALLER},aos_network_approval_issuer')
    op.execute(f'GRANT SELECT,INSERT ON public.aip_network_approval_delivery TO {OWNER}')
    op.execute(f'GRANT UPDATE({MUTABLE}) ON public.aip_network_approval_delivery TO {OWNER}')
    for definition, signature in (
        (ENQUEUE, 'aip_enqueue_network_delivery_a0v_123()'),
        (CLAIM, 'aip_claim_network_delivery_a0v_123(text,text,text,uuid)'),
        (FINISH, 'aip_finish_network_delivery_a0v_123(text,text,text,text,uuid)'),
    ):
        op.get_bind().exec_driver_sql(definition.replace('%', '%%'))
        op.execute(f'ALTER FUNCTION public.{signature} OWNER TO {OWNER}')
        op.execute(f'REVOKE ALL ON FUNCTION public.{signature} FROM PUBLIC')
        if definition != ENQUEUE:
            op.execute(f'GRANT EXECUTE ON FUNCTION public.{signature} TO {CALLER}')
    op.execute('CREATE TRIGGER aip_enqueue_network_delivery_a0v_123 AFTER INSERT ON public.aip_action_approval_event '
               'FOR EACH ROW EXECUTE FUNCTION public.aip_enqueue_network_delivery_a0v_123()')


def downgrade():
    raise RuntimeError('network delivery history may not be silently removed')
