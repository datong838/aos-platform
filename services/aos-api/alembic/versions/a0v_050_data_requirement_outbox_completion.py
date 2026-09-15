"""Require fulfillment and running analysis Receipts before Outbox completion."""
from alembic import op

revision = 'a0v_050'
down_revision = 'a0v_049'
branch_labels = depends_on = None

COMPLETE_SIGNATURE = '(text,bigint,text,jsonb,jsonb)'


def _secure(name):
    op.execute(f'REVOKE ALL ON FUNCTION {name}{COMPLETE_SIGNATURE} FROM PUBLIC')
    op.execute(f'GRANT EXECUTE ON FUNCTION {name}{COMPLETE_SIGNATURE} TO aos_runtime')


def upgrade():
    op.execute('''ALTER TABLE data_requirement_outbox_delivery
        ADD COLUMN completion_fulfillment_ref JSONB,
        ADD COLUMN completion_analysis_ref JSONB,
        ADD CONSTRAINT ck_data_requirement_outbox_completion_refs_a0v_050 CHECK (
            (completion_fulfillment_ref IS NULL)=(completion_analysis_ref IS NULL)
            AND (completion_fulfillment_ref IS NULL OR
                (jsonb_typeof(completion_fulfillment_ref)='object'
                 AND jsonb_typeof(completion_analysis_ref)='object')))''')
    op.execute('''CREATE FUNCTION data_requirement_outbox_completion_evidence_a0v_050(
        p_outbox_id text,p_fulfillment_ref jsonb,p_analysis_ref jsonb)
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog,public AS $$
        SELECT count(*)=1 FROM public.data_requirement_outbox o
        JOIN public.data_requirement_revision q
          ON q.org_id=o.org_id AND q.project_id=o.project_id
         AND q.requirement_id=o.requirement_id AND q.revision=o.requirement_revision
        JOIN public.data_fulfillment_receipt f
          ON f.org_id=o.org_id AND f.project_id=o.project_id
         AND f.receipt_id=p_fulfillment_ref->>'receiptId'
        JOIN public.ecommerce_growth_runtime_command_receipt a
          ON a.org_id=o.org_id AND a.project_id=o.project_id
         AND a.operation_id='ecommerce_growth_analysis_advance'
         AND a.target_receipt_ref=p_analysis_ref
        WHERE o.org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND o.project_id=NULLIF(current_setting('aos.project_id',true),'')
          AND o.outbox_id=p_outbox_id
          AND btrim(o.content_hash)=btrim(q.content_hash)
          AND p_fulfillment_ref=jsonb_build_object(
            'resourceType','DataFulfillmentReceipt','resourceId',f.receipt_id,
            'revision',1,'contentHash','sha256:'||btrim(f.content_hash),'receiptId',f.receipt_id)
          AND f.requirement_id=o.requirement_id
          AND f.requirement_revision=o.requirement_revision
          AND f.status='fulfilled'
          AND jsonb_typeof(f.authority_data)='object'
          AND f.authority_data->'tenant'=jsonb_build_object('orgId',o.org_id,'projectId',o.project_id)
          AND f.authority_data->'requirementRef'=jsonb_build_object(
            'resourceType','DataRequirementRevision','resourceId',o.requirement_id,
            'revision',o.requirement_revision,'contentHash','sha256:'||btrim(o.content_hash),
            'receiptId',NULL)
          AND f.authority_data->>'status'='fulfilled'
          AND f.authority_data->>'receiptId'=f.receipt_id
          AND f.authority_data->>'contentHash'='sha256:'||btrim(f.content_hash)
          AND p_analysis_ref=a.response->'receiptRef'
          AND a.response->'receiptRef'=a.target_receipt_ref
          AND a.response->>'phase' IS DISTINCT FROM 'PREPARING'
          AND a.response->>'phase' IS DISTINCT FROM 'RECONCILING'
          AND a.response->>'phase' IS NOT DISTINCT FROM 'RUNNING'
          AND a.response->'completed'='false'::jsonb
          AND a.response->>'requestHash'=a.request_hash
          AND a.response->'requirementRef'=jsonb_build_object(
            'resourceType','DataRequirementRevision','resourceId',o.requirement_id,
            'revision',o.requirement_revision,'contentHash','sha256:'||btrim(o.content_hash))
          AND a.response->'fulfillmentRef'=p_fulfillment_ref
          AND q.run_ref->'receiptId'='null'::jsonb
          AND a.response->'runRef'=q.run_ref-'receiptId'
        $$''')
    op.execute('REVOKE ALL ON FUNCTION data_requirement_outbox_completion_evidence_a0v_050(text,jsonb,jsonb) FROM PUBLIC')

    op.execute('''CREATE FUNCTION data_requirement_outbox_complete_a0v_050(
        p_outbox_id text,p_attempt bigint,p_lease_token text,
        p_fulfillment_ref jsonb,p_analysis_ref jsonb)
        RETURNS TABLE(state text,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_row record;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR coalesce(length(btrim(p_outbox_id)),0) NOT BETWEEN 1 AND 200
             OR p_attempt IS NULL OR p_attempt<1
             OR coalesce(length(btrim(p_lease_token)),0) NOT BETWEEN 1 AND 200
             OR jsonb_typeof(p_fulfillment_ref) IS DISTINCT FROM 'object'
             OR jsonb_typeof(p_analysis_ref) IS DISTINCT FROM 'object'
          THEN RAISE EXCEPTION USING ERRCODE='DO001',MESSAGE='invalid exact Outbox completion'; END IF;
          SELECT d.state,d.attempt,d.lease_token,d.lease_expires_at,
                 d.completion_fulfillment_ref,d.completion_analysis_ref INTO v_row
            FROM public.data_requirement_outbox_delivery d
           WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='DO002',MESSAGE='outbox delivery not found'; END IF;
          IF v_row.state='acked' AND v_row.attempt=p_attempt AND v_row.lease_token=p_lease_token
             AND v_row.completion_fulfillment_ref=p_fulfillment_ref
             AND v_row.completion_analysis_ref=p_analysis_ref
          THEN RETURN QUERY SELECT 'acked'::text,true; RETURN; END IF;
          IF v_row.state<>'claimed' OR v_row.attempt<>p_attempt OR v_row.lease_token<>p_lease_token
             OR v_row.lease_expires_at<=NOW()
             OR public.data_requirement_outbox_completion_evidence_a0v_050(
                  p_outbox_id,p_fulfillment_ref,p_analysis_ref) IS NOT TRUE
          THEN RAISE EXCEPTION USING ERRCODE='DO003',MESSAGE='Outbox completion lacks current dual Receipt evidence'; END IF;
          UPDATE public.data_requirement_outbox_delivery SET state='acked',failure_code=NULL,
            reconciliation_receipt_id=p_fulfillment_ref->>'receiptId',
            completion_fulfillment_ref=p_fulfillment_ref,completion_analysis_ref=p_analysis_ref,updated_at=NOW()
           WHERE org_id=v_org AND project_id=v_project AND outbox_id=p_outbox_id;
          RETURN QUERY SELECT 'acked'::text,false;
        END $$''')

    op.execute('''CREATE FUNCTION data_requirement_outbox_reconcile_completed_a0v_050(
        p_outbox_id text,p_attempt bigint,p_lease_token text,
        p_fulfillment_ref jsonb,p_analysis_ref jsonb)
        RETURNS TABLE(state text,replayed boolean)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
          v_project text:=NULLIF(current_setting('aos.project_id',true),'');v_row record;
        BEGIN
          IF v_org IS NULL OR v_project IS NULL OR coalesce(length(btrim(p_outbox_id)),0) NOT BETWEEN 1 AND 200
             OR p_attempt IS NULL OR p_attempt<1
             OR coalesce(length(btrim(p_lease_token)),0) NOT BETWEEN 1 AND 200
             OR jsonb_typeof(p_fulfillment_ref) IS DISTINCT FROM 'object'
             OR jsonb_typeof(p_analysis_ref) IS DISTINCT FROM 'object'
          THEN RAISE EXCEPTION USING ERRCODE='DO001',MESSAGE='invalid exact Outbox reconciliation'; END IF;
          SELECT d.state,d.attempt,d.lease_token,d.completion_fulfillment_ref,d.completion_analysis_ref INTO v_row
            FROM public.data_requirement_outbox_delivery d
           WHERE d.org_id=v_org AND d.project_id=v_project AND d.outbox_id=p_outbox_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='DO002',MESSAGE='outbox delivery not found'; END IF;
          IF v_row.state='acked' AND v_row.attempt=p_attempt AND v_row.lease_token=p_lease_token
             AND v_row.completion_fulfillment_ref=p_fulfillment_ref
             AND v_row.completion_analysis_ref=p_analysis_ref
          THEN RETURN QUERY SELECT 'acked'::text,true; RETURN; END IF;
          IF v_row.state<>'unknown' OR v_row.attempt<>p_attempt OR v_row.lease_token<>p_lease_token
             OR public.data_requirement_outbox_completion_evidence_a0v_050(
                  p_outbox_id,p_fulfillment_ref,p_analysis_ref) IS NOT TRUE
          THEN RAISE EXCEPTION USING ERRCODE='DO003',MESSAGE='unknown Outbox lacks exact dual Receipt evidence'; END IF;
          UPDATE public.data_requirement_outbox_delivery SET state='acked',failure_code=NULL,
            reconciliation_receipt_id=p_fulfillment_ref->>'receiptId',
            completion_fulfillment_ref=p_fulfillment_ref,completion_analysis_ref=p_analysis_ref,updated_at=NOW()
           WHERE org_id=v_org AND project_id=v_project AND outbox_id=p_outbox_id;
          RETURN QUERY SELECT 'acked'::text,false;
        END $$''')
    _secure('data_requirement_outbox_complete_a0v_050')
    _secure('data_requirement_outbox_reconcile_completed_a0v_050')


def downgrade():
    op.execute('''DO $$ BEGIN IF EXISTS(SELECT 1 FROM data_requirement_outbox_delivery
        WHERE completion_fulfillment_ref IS NOT NULL OR completion_analysis_ref IS NOT NULL)
        THEN RAISE EXCEPTION 'cannot discard dual Receipt Outbox completion authority'
          USING ERRCODE='55000'; END IF; END $$''')
    op.execute(f'DROP FUNCTION data_requirement_outbox_reconcile_completed_a0v_050{COMPLETE_SIGNATURE}')
    op.execute(f'DROP FUNCTION data_requirement_outbox_complete_a0v_050{COMPLETE_SIGNATURE}')
    op.execute('DROP FUNCTION data_requirement_outbox_completion_evidence_a0v_050(text,jsonb,jsonb)')
    op.execute('ALTER TABLE data_requirement_outbox_delivery DROP CONSTRAINT ck_data_requirement_outbox_completion_refs_a0v_050, DROP COLUMN completion_analysis_ref, DROP COLUMN completion_fulfillment_ref')
