"""Exact ecommerce growth host invocation Receipts and cutover authority."""

from alembic import op


revision = "ar2_005"
down_revision = "ar2_004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE TABLE ecommerce_growth_runtime_command_receipt (
          org_id TEXT NOT NULL, project_id TEXT NOT NULL,
          operation_id TEXT NOT NULL CHECK(operation_id IN (
            'ecommerce_growth_investigation_describe','ecommerce_growth_case_put',
            'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger',
            'ecommerce_growth_data_fulfill','ecommerce_growth_analysis_advance',
            'ecommerce_growth_review_advance','ecommerce_growth_content_generate',
            'ecommerce_growth_content_review')),
          idempotency_key TEXT NOT NULL CHECK(length(btrim(idempotency_key)) BETWEEN 1 AND 200),
          request_hash TEXT NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
          dispatch_revision BIGINT NOT NULL CHECK(dispatch_revision>0),
          installation_id UUID NOT NULL, generation UUID NOT NULL,
          execution_epoch BIGINT NOT NULL CHECK(execution_epoch>0),
          cutover_group_id UUID NOT NULL,
          cutover_group_revision BIGINT NOT NULL CHECK(cutover_group_revision>0),
          runtime_revision BIGINT NOT NULL CHECK(runtime_revision>0),
          response JSONB NOT NULL CHECK(jsonb_typeof(response)='object'),
          target_receipt_ref JSONB NOT NULL CHECK(jsonb_typeof(target_receipt_ref)='object'),
          actor TEXT NOT NULL CHECK(length(btrim(actor)) BETWEEN 1 AND 240),
          occurred_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,operation_id,idempotency_key),
          FOREIGN KEY(org_id,project_id,operation_id)
            REFERENCES extension_operation_dispatch_binding(org_id,project_id,operation_id),
          FOREIGN KEY(org_id,project_id,installation_id,generation)
            REFERENCES extension_runtime_binding(org_id,project_id,installation_id,generation)
        )"""
    )
    op.execute("ALTER TABLE ecommerce_growth_runtime_command_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_growth_runtime_command_receipt FORCE ROW LEVEL SECURITY")
    op.execute(
        """CREATE POLICY tenant_scope_ecommerce_growth_runtime_receipt_ar2_005
          ON ecommerce_growth_runtime_command_receipt TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
            AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute("REVOKE ALL ON ecommerce_growth_runtime_command_receipt FROM PUBLIC")
    op.execute("GRANT SELECT ON ecommerce_growth_runtime_command_receipt TO aos_runtime")
    op.execute(
        """CREATE FUNCTION ecommerce_growth_runtime_receipt_put_ar2_005(
          p_operation_id TEXT,p_idempotency_key TEXT,p_request_hash TEXT,
          p_dispatch_revision BIGINT,p_installation_id UUID,p_generation UUID,
          p_execution_epoch BIGINT,p_cutover_group_id UUID,p_cutover_group_revision BIGINT,
          p_runtime_revision BIGINT,p_response JSONB,p_target_receipt_ref JSONB,
          p_actor TEXT,p_occurred_at TIMESTAMPTZ
        ) RETURNS TABLE(response JSONB,replayed BOOLEAN)
        LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
        DECLARE v_org TEXT:=NULLIF(current_setting('aos.org_id',true),'');
          v_project TEXT:=NULLIF(current_setting('aos.project_id',true),'');
          v_existing RECORD;v_dispatch RECORD;v_runtime RECORD;
        BEGIN
          IF coalesce(v_org,'')='' OR coalesce(v_project,'')=''
             OR p_operation_id NOT IN (
               'ecommerce_growth_investigation_describe','ecommerce_growth_case_put',
               'ecommerce_growth_schedule_put','ecommerce_growth_schedule_trigger',
               'ecommerce_growth_data_fulfill','ecommerce_growth_analysis_advance',
               'ecommerce_growth_review_advance','ecommerce_growth_content_generate',
               'ecommerce_growth_content_review')
             OR length(btrim(coalesce(p_idempotency_key,''))) NOT BETWEEN 1 AND 200
             OR p_request_hash !~ '^sha256:[0-9a-f]{64}$'
             OR p_dispatch_revision<1 OR p_execution_epoch<1
             OR p_cutover_group_revision<1 OR p_runtime_revision<1
             OR jsonb_typeof(p_response)<>'object' OR p_response='{}'::jsonb
             OR jsonb_typeof(p_target_receipt_ref)<>'object'
             OR length(btrim(coalesce(p_actor,''))) NOT BETWEEN 1 AND 240
             OR p_occurred_at IS NULL
          THEN RAISE EXCEPTION USING ERRCODE='22023',MESSAGE='invalid ecommerce runtime Receipt'; END IF;
          -- A missing row cannot be protected by FOR UPDATE.  Serialize the
          -- tenant/operation/idempotency identity before the first read so a
          -- concurrent replay deterministically observes the winning Receipt.
          PERFORM pg_advisory_xact_lock(hashtextextended(
            v_org||E'\x1f'||v_project||E'\x1f'||p_operation_id||E'\x1f'||btrim(p_idempotency_key),0));
          SELECT * INTO v_dispatch FROM extension_operation_dispatch_binding
           WHERE org_id=v_org AND project_id=v_project AND operation_id=p_operation_id
           FOR UPDATE;
          IF NOT FOUND OR v_dispatch.handler_kind<>'extension'
             OR v_dispatch.installation_id IS DISTINCT FROM p_installation_id
             OR v_dispatch.generation IS DISTINCT FROM p_generation
             OR v_dispatch.execution_epoch IS DISTINCT FROM p_execution_epoch
             OR v_dispatch.operation_fence IS DISTINCT FROM FALSE
             OR v_dispatch.revision<>p_dispatch_revision
             OR v_dispatch.cutover_group_id<>p_cutover_group_id
             OR v_dispatch.cutover_group_revision<>p_cutover_group_revision
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='ecommerce runtime dispatch authority drifted'; END IF;
          SELECT * INTO v_runtime FROM extension_runtime_binding
           WHERE org_id=v_org AND project_id=v_project
             AND installation_id=p_installation_id AND generation=p_generation
           FOR UPDATE;
          IF NOT FOUND OR v_runtime.execution_epoch<>p_execution_epoch
             OR v_runtime.revision<>p_runtime_revision
             OR v_runtime.desired_state<>'enabled' OR v_runtime.observed_state<>'ready'
             OR v_runtime.enabled IS DISTINCT FROM TRUE
             OR v_runtime.operation_fence IS DISTINCT FROM FALSE
          THEN RAISE EXCEPTION USING ERRCODE='23514',MESSAGE='ecommerce runtime binding is not executable'; END IF;
          SELECT * INTO v_existing FROM ecommerce_growth_runtime_command_receipt
           WHERE org_id=v_org AND project_id=v_project AND operation_id=p_operation_id
             AND idempotency_key=btrim(p_idempotency_key) FOR UPDATE;
          IF FOUND THEN
            IF v_existing.request_hash<>p_request_hash
               OR v_existing.dispatch_revision<>p_dispatch_revision
               OR v_existing.installation_id<>p_installation_id
               OR v_existing.generation<>p_generation
               OR v_existing.execution_epoch<>p_execution_epoch
               OR v_existing.cutover_group_id<>p_cutover_group_id
               OR v_existing.cutover_group_revision<>p_cutover_group_revision
               OR v_existing.runtime_revision<>p_runtime_revision
               OR v_existing.response IS DISTINCT FROM p_response
               OR v_existing.target_receipt_ref IS DISTINCT FROM p_target_receipt_ref
            THEN RAISE EXCEPTION USING ERRCODE='23505',MESSAGE='ecommerce runtime Receipt drifted'; END IF;
            RETURN QUERY SELECT v_existing.response,TRUE; RETURN;
          END IF;
          INSERT INTO ecommerce_growth_runtime_command_receipt(
            org_id,project_id,operation_id,idempotency_key,request_hash,dispatch_revision,
            installation_id,generation,execution_epoch,cutover_group_id,cutover_group_revision,
            runtime_revision,response,target_receipt_ref,actor,occurred_at)
          VALUES(v_org,v_project,p_operation_id,btrim(p_idempotency_key),p_request_hash,
            p_dispatch_revision,p_installation_id,p_generation,p_execution_epoch,p_cutover_group_id,
            p_cutover_group_revision,p_runtime_revision,p_response,p_target_receipt_ref,btrim(p_actor),p_occurred_at);
          RETURN QUERY SELECT p_response,FALSE;
        END $$"""
    )
    op.execute(
        "REVOKE ALL ON FUNCTION ecommerce_growth_runtime_receipt_put_ar2_005(TEXT,TEXT,TEXT,BIGINT,UUID,UUID,BIGINT,UUID,BIGINT,BIGINT,JSONB,JSONB,TEXT,TIMESTAMPTZ) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION ecommerce_growth_runtime_receipt_put_ar2_005(TEXT,TEXT,TEXT,BIGINT,UUID,UUID,BIGINT,UUID,BIGINT,BIGINT,JSONB,JSONB,TEXT,TIMESTAMPTZ) TO aos_runtime"
    )


def downgrade() -> None:
    op.execute(
        """DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_growth_runtime_command_receipt LIMIT 1)
          THEN RAISE EXCEPTION 'ecommerce growth runtime authority is not empty'; END IF; END $$"""
    )
    op.execute(
        "DROP FUNCTION ecommerce_growth_runtime_receipt_put_ar2_005(TEXT,TEXT,TEXT,BIGINT,UUID,UUID,BIGINT,UUID,BIGINT,BIGINT,JSONB,JSONB,TEXT,TIMESTAMPTZ)"
    )
    op.execute("DROP TABLE ecommerce_growth_runtime_command_receipt")
