"""Durable receipt-first ecommerce growth result feedback and recovery."""

from alembic import op


revision = "ar2_004"
down_revision = "ar2_003"
branch_labels = None
depends_on = None


_TABLES = (
    "ecommerce_growth_feedback_command",
    "ecommerce_growth_feedback_segment",
    "ecommerce_growth_feedback_checkpoint",
    "ecommerce_growth_feedback_receipt",
)


def _scope(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY tenant_scope_{table}_ar2_004 ON {table} TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
    op.execute(f"GRANT SELECT ON {table} TO aos_runtime")


def _secure(name: str, signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {name}{signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {name}{signature} TO aos_runtime")


def upgrade() -> None:
    op.execute(
        """CREATE TABLE ecommerce_growth_feedback_command (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, command_id TEXT NOT NULL,
          request_hash TEXT NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          decision TEXT NOT NULL CHECK(decision IN ('ACCEPT','RETURN')),
          review_receipt_ref JSONB NOT NULL, artifact_ref JSONB NOT NULL,
          task_ref JSONB NOT NULL, brief_ref JSONB NOT NULL,
          actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,command_id),
          CHECK(jsonb_typeof(review_receipt_ref)='object'),
          CHECK(jsonb_typeof(artifact_ref)='object'),
          CHECK(jsonb_typeof(task_ref)='object'),
          CHECK(jsonb_typeof(brief_ref)='object')
        )"""
    )
    op.execute(
        """CREATE TABLE ecommerce_growth_feedback_segment (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, command_id TEXT NOT NULL,
          sequence INTEGER NOT NULL CHECK(sequence BETWEEN 1 AND 3),
          kind TEXT NOT NULL CHECK(kind IN (
            'daily_review','improvement_observation','memory_candidate','content_return_target')),
          target_id TEXT NOT NULL, payload JSONB NOT NULL,
          state TEXT NOT NULL DEFAULT 'pending'
            CHECK(state IN ('pending','claimed','acked','unknown')),
          attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt>=0),
          lease_token UUID, lease_expires_at TIMESTAMPTZ,
          target_receipt_ref JSONB, reason_code TEXT,
          updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,command_id,sequence),
          UNIQUE(org_id,project_id,kind,target_id),
          FOREIGN KEY(org_id,project_id,command_id)
            REFERENCES ecommerce_growth_feedback_command(org_id,project_id,command_id),
          CHECK(jsonb_typeof(payload)='object'),
          CHECK(target_receipt_ref IS NULL OR jsonb_typeof(target_receipt_ref)='object'),
          CHECK((state='pending' AND attempt=0 AND lease_token IS NULL
                   AND lease_expires_at IS NULL AND target_receipt_ref IS NULL)
             OR (state='claimed' AND attempt>0 AND lease_token IS NOT NULL
                   AND lease_expires_at IS NOT NULL AND target_receipt_ref IS NULL)
             OR (state='unknown' AND attempt>0 AND lease_token IS NOT NULL
                   AND lease_expires_at IS NOT NULL AND target_receipt_ref IS NULL
                   AND reason_code IS NOT NULL)
             OR (state='acked' AND attempt>0 AND lease_token IS NOT NULL
                   AND target_receipt_ref IS NOT NULL))
        )"""
    )
    op.execute(
        """CREATE TABLE ecommerce_growth_feedback_checkpoint (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, command_id TEXT NOT NULL,
          completed_sequence INTEGER NOT NULL DEFAULT 0 CHECK(completed_sequence BETWEEN 0 AND 3),
          version BIGINT NOT NULL DEFAULT 1 CHECK(version>=1),
          updated_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,command_id),
          FOREIGN KEY(org_id,project_id,command_id)
            REFERENCES ecommerce_growth_feedback_command(org_id,project_id,command_id)
        )"""
    )
    op.execute(
        """CREATE TABLE ecommerce_growth_feedback_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL, command_id TEXT NOT NULL,
          receipt_id TEXT NOT NULL, receipt_ref JSONB NOT NULL,
          target_receipt_refs JSONB NOT NULL, content_hash TEXT NOT NULL
            CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
          created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,command_id),
          UNIQUE(org_id,project_id,receipt_id),
          FOREIGN KEY(org_id,project_id,command_id)
            REFERENCES ecommerce_growth_feedback_command(org_id,project_id,command_id),
          CHECK(jsonb_typeof(receipt_ref)='object'),
          CHECK(jsonb_typeof(target_receipt_refs)='array')
        )"""
    )
    for table in _TABLES:
        _scope(table)

    op.execute(
        """CREATE FUNCTION ecommerce_growth_feedback_enqueue_ar2_004(
          p_command_id TEXT,p_request_hash TEXT,p_decision TEXT,
          p_review_receipt_ref JSONB,p_artifact_ref JSONB,p_task_ref JSONB,p_brief_ref JSONB,
          p_segments JSONB,p_actor TEXT,p_occurred_at TIMESTAMPTZ
        ) RETURNS TABLE(command_id TEXT,request_hash TEXT,segment_count INTEGER,replayed BOOLEAN)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');v_existing RECORD;
          v_segment JSONB;v_ordinal BIGINT;v_expected TEXT[];v_count INTEGER;
        BEGIN
          IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR coalesce(btrim(p_command_id),'')=''
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$' OR p_decision NOT IN ('ACCEPT','RETURN')
             OR coalesce(btrim(p_actor),'')='' OR p_occurred_at IS NULL
             OR jsonb_typeof(p_review_receipt_ref)<>'object' OR jsonb_typeof(p_artifact_ref)<>'object'
             OR jsonb_typeof(p_task_ref)<>'object' OR jsonb_typeof(p_brief_ref)<>'object'
             OR jsonb_typeof(p_segments)<>'array'
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid feedback command'; END IF;
          v_expected:=CASE WHEN p_decision='ACCEPT'
            THEN ARRAY['daily_review','improvement_observation','memory_candidate']
            ELSE ARRAY['content_return_target'] END;
          v_count:=jsonb_array_length(p_segments);
          IF v_count<>cardinality(v_expected) THEN
            RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='feedback segment set drifted';
          END IF;
          SELECT * INTO v_existing FROM ecommerce_growth_feedback_command
           WHERE org_id=v_org AND project_id=v_project AND ecommerce_growth_feedback_command.command_id=p_command_id
           FOR UPDATE;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash OR v_existing.decision<>p_decision
            THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='feedback command content drifted'; END IF;
            RETURN QUERY SELECT p_command_id,p_request_hash,v_count,TRUE; RETURN;
          END IF;
          INSERT INTO ecommerce_growth_feedback_command VALUES(
            v_org,v_project,p_command_id,p_request_hash,p_decision,p_review_receipt_ref,
            p_artifact_ref,p_task_ref,p_brief_ref,btrim(p_actor),p_occurred_at);
          FOR v_segment,v_ordinal IN SELECT value,ordinality FROM jsonb_array_elements(p_segments) WITH ORDINALITY LOOP
            IF (v_segment->>'sequence')::INTEGER<>v_ordinal OR v_segment->>'kind'<>v_expected[v_ordinal]
               OR coalesce(btrim(v_segment->>'targetId'),'')='' OR jsonb_typeof(v_segment)<>'object'
            THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='feedback segment order drifted'; END IF;
            INSERT INTO ecommerce_growth_feedback_segment(
              org_id,project_id,command_id,sequence,kind,target_id,payload,state,updated_at)
            VALUES(v_org,v_project,p_command_id,v_ordinal,v_segment->>'kind',v_segment->>'targetId',
              v_segment,'pending',p_occurred_at);
          END LOOP;
          INSERT INTO ecommerce_growth_feedback_checkpoint VALUES(v_org,v_project,p_command_id,0,1,p_occurred_at);
          RETURN QUERY SELECT p_command_id,p_request_hash,v_count,FALSE;
        END $$"""
    )
    op.execute(
        """CREATE FUNCTION ecommerce_growth_feedback_claim_ar2_004(
          p_command_id TEXT,p_worker TEXT,p_lease_seconds INTEGER
        ) RETURNS TABLE(sequence INTEGER,kind TEXT,target_id TEXT,payload JSONB,
          attempt INTEGER,lease_token UUID,checkpoint_version BIGINT)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');v_checkpoint RECORD;v_segment RECORD;
          v_now TIMESTAMPTZ:=clock_timestamp();v_token UUID:=gen_random_uuid();
        BEGIN
          IF coalesce(v_org,'')='' OR coalesce(v_project,'')='' OR coalesce(btrim(p_worker),'')=''
             OR p_lease_seconds<1 OR p_lease_seconds>300
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid feedback claim'; END IF;
          SELECT * INTO v_checkpoint FROM ecommerce_growth_feedback_checkpoint
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION USING ERRCODE='P0002',MESSAGE='feedback command not found'; END IF;
          SELECT * INTO v_segment FROM ecommerce_growth_feedback_segment
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id
             AND ecommerce_growth_feedback_segment.sequence=v_checkpoint.completed_sequence+1 FOR UPDATE;
          IF NOT FOUND THEN RETURN; END IF;
          IF v_segment.state='unknown' OR v_segment.state='acked'
             OR (v_segment.state='claimed' AND v_segment.lease_expires_at>v_now) THEN RETURN; END IF;
          UPDATE ecommerce_growth_feedback_segment SET state='claimed',
            attempt=ecommerce_growth_feedback_segment.attempt+1,
            lease_token=v_token,lease_expires_at=v_now+make_interval(secs=>p_lease_seconds),
            reason_code=NULL,updated_at=v_now
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id
             AND ecommerce_growth_feedback_segment.sequence=v_segment.sequence;
          RETURN QUERY SELECT v_segment.sequence,v_segment.kind,v_segment.target_id,v_segment.payload,
            v_segment.attempt+1,v_token,v_checkpoint.version;
        END $$"""
    )
    op.execute(
        """CREATE FUNCTION ecommerce_growth_feedback_unknown_ar2_004(
          p_command_id TEXT,p_sequence INTEGER,p_lease_token UUID,p_reason_code TEXT
        ) RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');v_count INTEGER;
        BEGIN
          IF coalesce(btrim(p_reason_code),'')='' THEN
            RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='unknown feedback requires reason'; END IF;
          UPDATE ecommerce_growth_feedback_segment SET state='unknown',reason_code=btrim(p_reason_code),
            updated_at=clock_timestamp() WHERE org_id=v_org AND project_id=v_project
            AND command_id=p_command_id AND sequence=p_sequence AND state='claimed'
            AND lease_token=p_lease_token;
          GET DIAGNOSTICS v_count=ROW_COUNT;
          IF v_count<>1 THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='stale feedback lease'; END IF;
        END $$"""
    )
    op.execute(
        """CREATE FUNCTION ecommerce_growth_feedback_ack_ar2_004(
          p_command_id TEXT,p_sequence INTEGER,p_lease_token UUID,p_checkpoint_version BIGINT,
          p_target_receipt_ref JSONB
        ) RETURNS TABLE(completed_sequence INTEGER,checkpoint_version BIGINT,receipt_ref JSONB)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');v_checkpoint RECORD;v_segment RECORD;
          v_total INTEGER;v_targets JSONB;v_hash TEXT;v_receipt JSONB;v_receipt_id TEXT;
        BEGIN
          IF jsonb_typeof(p_target_receipt_ref)<>'object' OR p_target_receipt_ref->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid target receipt ref'; END IF;
          SELECT * INTO v_checkpoint FROM ecommerce_growth_feedback_checkpoint
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id FOR UPDATE;
          IF NOT FOUND OR v_checkpoint.version<>p_checkpoint_version
             OR v_checkpoint.completed_sequence+1<>p_sequence
          THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='feedback checkpoint drifted'; END IF;
          SELECT * INTO v_segment FROM ecommerce_growth_feedback_segment
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id AND sequence=p_sequence FOR UPDATE;
          IF NOT FOUND OR v_segment.state NOT IN ('claimed','unknown') OR v_segment.lease_token<>p_lease_token
          THEN RAISE EXCEPTION USING ERRCODE='40001',MESSAGE='stale feedback lease'; END IF;
          UPDATE ecommerce_growth_feedback_segment SET state='acked',target_receipt_ref=p_target_receipt_ref,
            reason_code=NULL,updated_at=clock_timestamp() WHERE org_id=v_org AND project_id=v_project
            AND command_id=p_command_id AND sequence=p_sequence;
          UPDATE ecommerce_growth_feedback_checkpoint SET completed_sequence=p_sequence,
            version=version+1,updated_at=clock_timestamp() WHERE org_id=v_org AND project_id=v_project
            AND command_id=p_command_id;
          SELECT count(*) INTO v_total FROM ecommerce_growth_feedback_segment
           WHERE org_id=v_org AND project_id=v_project AND command_id=p_command_id;
          v_receipt:=NULL;
          IF p_sequence=v_total THEN
            SELECT jsonb_agg(target_receipt_ref ORDER BY sequence) INTO v_targets
              FROM ecommerce_growth_feedback_segment WHERE org_id=v_org AND project_id=v_project
                AND command_id=p_command_id;
            v_receipt_id:='feedback-receipt-'||substr(encode(public.digest(convert_to(
              p_command_id||v_targets::text,'UTF8'),'sha256'),'hex'),1,40);
            v_hash:='sha256:'||encode(public.digest(convert_to(v_targets::text,'UTF8'),'sha256'),'hex');
            v_receipt:=jsonb_build_object('resourceType','FeedbackReceipt','resourceId',v_receipt_id,
              'revision',1,'contentHash',v_hash,'receiptId',v_receipt_id);
            INSERT INTO ecommerce_growth_feedback_receipt(
              org_id,project_id,command_id,receipt_id,receipt_ref,target_receipt_refs,content_hash,created_at)
            VALUES(v_org,v_project,p_command_id,v_receipt_id,v_receipt,v_targets,v_hash,clock_timestamp())
            ON CONFLICT(org_id,project_id,command_id) DO NOTHING;
          END IF;
          RETURN QUERY SELECT p_sequence,p_checkpoint_version+1,v_receipt;
        END $$"""
    )
    op.execute(
        """CREATE INDEX ecommerce_growth_feedback_claim_idx_ar2_004
        ON ecommerce_growth_feedback_segment(org_id,project_id,command_id,sequence,state,lease_expires_at)"""
    )
    _secure("ecommerce_growth_feedback_enqueue_ar2_004", "(text,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,text,timestamptz)")
    _secure("ecommerce_growth_feedback_claim_ar2_004", "(text,text,integer)")
    _secure("ecommerce_growth_feedback_unknown_ar2_004", "(text,integer,uuid,text)")
    _secure("ecommerce_growth_feedback_ack_ar2_004", "(text,integer,uuid,bigint,jsonb)")


def downgrade() -> None:
    predicates = " OR ".join(f"EXISTS(SELECT 1 FROM {table})" for table in _TABLES)
    op.execute(
        f"""DO $$ BEGIN IF {predicates} THEN RAISE EXCEPTION
          'AR2_004_DOWNGRADE_REQUIRES_EMPTY_FEEDBACK_AUTHORITY' USING ERRCODE='55000'; END IF; END $$"""
    )
    op.execute("DROP FUNCTION ecommerce_growth_feedback_ack_ar2_004(text,integer,uuid,bigint,jsonb)")
    op.execute("DROP FUNCTION ecommerce_growth_feedback_unknown_ar2_004(text,integer,uuid,text)")
    op.execute("DROP FUNCTION ecommerce_growth_feedback_claim_ar2_004(text,text,integer)")
    op.execute("DROP FUNCTION ecommerce_growth_feedback_enqueue_ar2_004(text,text,text,jsonb,jsonb,jsonb,jsonb,jsonb,text,timestamptz)")
    for table in reversed(_TABLES):
        op.execute(f"DROP TABLE {table}")
