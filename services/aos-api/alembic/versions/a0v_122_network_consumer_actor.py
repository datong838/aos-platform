"""Bind trusted consumer-service subjects to exact original-maker authority."""
from alembic import op

revision = 'a0v_122'
down_revision = 'a0v_121'
branch_labels = depends_on = None


def actor_sql(read_only: bool) -> str:
    name = 'reconcile' if read_only else 'consume'
    volatility = 'STABLE' if read_only else 'VOLATILE'
    lock = '' if read_only else 'FOR UPDATE'
    read_guard = "current_setting('transaction_read_only') IS DISTINCT FROM 'on' OR" if read_only else ''
    target = 'aip_reconcile_network_receipt_a0v_121' if read_only else 'aip_consume_network_activation_a0v_120'
    return f"""CREATE FUNCTION public.aip_{name}_network_as_actor_a0v_122(
        p_org text,p_project text,p_proposal text,p_event text,p_actor text,
        p_proposal_hash text,p_target_hash text,p_binding_hash text) RETURNS jsonb
        LANGUAGE plpgsql {volatility} SECURITY DEFINER SET search_path=pg_catalog AS $$
    DECLARE p public.aip_action_proposal%ROWTYPE;
    BEGIN
        IF {read_guard} session_user<>'aos_network_consumer_call'
           OR current_user<>'aos_network_consumer_owner'
           OR current_setting('aos.org_id',true) IS DISTINCT FROM p_org
           OR current_setting('aos.project_id',true) IS DISTINCT FROM p_project
           OR p_actor IS NULL OR p_actor='' OR p_actor<>btrim(p_actor)
           OR p_proposal_hash IS NULL OR p_proposal_hash !~ '^[0-9a-f]{{64}}$'
           OR p_target_hash IS NULL OR p_target_hash !~ '^[0-9a-f]{{64}}$'
           OR p_binding_hash IS NULL OR p_binding_hash !~ '^[0-9a-f]{{64}}$' THEN
            RAISE EXCEPTION 'NETWORK_CONSUMER_ACTOR_AUTHORITY_REQUIRED' USING ERRCODE='42501';
        END IF;
        SELECT * INTO p FROM public.aip_action_proposal
            WHERE org_id=p_org AND project_id=p_project AND proposal_id=p_proposal {lock};
        IF NOT FOUND OR p.created_by IS DISTINCT FROM p_actor
           OR p.action_type_id IS DISTINCT FROM 'aip_activate_network_policy'
           OR p.proposal_hash IS DISTINCT FROM p_proposal_hash
           OR p.payload->>'targetContentHash' IS DISTINCT FROM p_target_hash
           OR p.action_binding_hash IS DISTINCT FROM p_binding_hash
           OR NOT EXISTS(SELECT 1 FROM public.meta_membership
               WHERE org_id=p_org AND project_id=p_project AND subject=p_actor
                 AND lower(role) IN ('owner','admin')) THEN
            RAISE EXCEPTION 'NETWORK_CONSUMER_ACTOR_AUTHORITY_REQUIRED' USING ERRCODE='42501';
        END IF;
        RETURN public.{target}(p_org,p_project,p_proposal,p_event);
    END $$"""


def upgrade():
    for read_only in (False, True):
        op.get_bind().exec_driver_sql(actor_sql(read_only).replace('%', '%%'))
        name = 'reconcile' if read_only else 'consume'
        signature = f'public.aip_{name}_network_as_actor_a0v_122(text,text,text,text,text,text,text,text)'
        op.execute(f'ALTER FUNCTION {signature} OWNER TO aos_network_consumer_owner')
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_network_consumer_call')


def downgrade():
    raise RuntimeError('consumer actor authority may not be silently removed')
