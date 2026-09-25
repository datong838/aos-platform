"""Analysis-only pending Outbox claim; ambiguous attempts need separate review."""

from alembic import op


revision = "a0v_095"
down_revision = "a0v_094"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE FUNCTION public.data_requirement_outbox_claim_pending_a0v_095(
      p_topic text,p_worker_id text,p_lease_token text,p_lease_seconds integer)
      RETURNS TABLE(outbox_id text,requirement_id text,requirement_revision bigint,
        event_id text,topic text,payload jsonb,content_hash text,attempt integer,
        lease_token text,lease_expires_at timestamptz)
      LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
    DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
      v_project text:=NULLIF(current_setting('aos.project_id',true),'');
      v_row record; v_lease_expires_at timestamptz;
    BEGIN
      IF v_org IS NULL OR v_project IS NULL OR p_topic IS NULL
        OR p_worker_id IS NULL OR p_lease_token IS NULL
        OR btrim(p_topic)='' OR btrim(p_worker_id)='' OR btrim(p_lease_token)=''
        OR p_lease_seconds IS NULL OR p_lease_seconds<1 OR p_lease_seconds>3600
      THEN RAISE EXCEPTION USING ERRCODE='DO001',
        MESSAGE='invalid tenant-bound pending claim'; END IF;
      INSERT INTO public.data_requirement_outbox_delivery(org_id,project_id,outbox_id)
      SELECT o.org_id,o.project_id,o.outbox_id
        FROM public.data_requirement_outbox o
       WHERE o.org_id=v_org AND o.project_id=v_project AND o.topic=p_topic
      ON CONFLICT DO NOTHING;
      SELECT o.outbox_id,o.requirement_id,o.requirement_revision,o.event_id,
             o.topic,o.payload,o.content_hash,d.attempt INTO v_row
        FROM public.data_requirement_outbox_delivery d
        JOIN public.data_requirement_outbox o USING(org_id,project_id,outbox_id)
       WHERE d.org_id=v_org AND d.project_id=v_project AND o.topic=p_topic
         AND d.state='pending'
       ORDER BY o.created_at,o.outbox_id
       FOR UPDATE OF d SKIP LOCKED LIMIT 1;
      IF NOT FOUND THEN RETURN; END IF;
      v_lease_expires_at:=NOW()+make_interval(secs=>p_lease_seconds);
      UPDATE public.data_requirement_outbox_delivery d
         SET state='claimed',attempt=d.attempt+1,worker_id=p_worker_id,
             lease_token=p_lease_token,lease_expires_at=v_lease_expires_at,
             failure_code=NULL,reconciliation_receipt_id=NULL,updated_at=NOW()
       WHERE d.org_id=v_org AND d.project_id=v_project
         AND d.outbox_id=v_row.outbox_id;
      RETURN QUERY SELECT v_row.outbox_id,v_row.requirement_id,
        v_row.requirement_revision,v_row.event_id,v_row.topic,v_row.payload,
        btrim(v_row.content_hash),v_row.attempt+1,p_lease_token,v_lease_expires_at;
    END $$;
    REVOKE ALL ON FUNCTION
      public.data_requirement_outbox_claim_pending_a0v_095(text,text,text,integer)
      FROM PUBLIC,aos_extension_directory,aos_extension_maintainer;
    GRANT EXECUTE ON FUNCTION
      public.data_requirement_outbox_claim_pending_a0v_095(text,text,text,integer)
      TO aos_runtime;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION public.data_requirement_outbox_claim_pending_a0v_095(text,text,text,integer)")
