"""Repair one stale schedule cursor from its authoritative terminal run."""
from alembic import op


revision = "a0v_077"
down_revision = "a0v_076"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    CREATE TABLE public.schedule_cursor_repair_receipt (
      org_id text NOT NULL,
      project_id text NOT NULL,
      receipt_id uuid NOT NULL DEFAULT gen_random_uuid(),
      schedule_id text NOT NULL,
      expected_current_run_id text NOT NULL,
      target_run_id text NOT NULL,
      idempotency_key text NOT NULL,
      request_hash text NOT NULL CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),
      prior_last_run jsonb NOT NULL,
      repaired_last_run jsonb NOT NULL,
      content_hash text NOT NULL CHECK(content_hash ~ '^sha256:[0-9a-f]{64}$'),
      repaired_by text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,idempotency_key)
    );

    CREATE FUNCTION public.guard_schedule_cursor_repair_immutable()
    RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      RAISE EXCEPTION 'schedule cursor repair receipts are immutable' USING ERRCODE='55000';
    END $$;
    CREATE TRIGGER schedule_cursor_repair_immutable
      BEFORE UPDATE OR DELETE ON public.schedule_cursor_repair_receipt
      FOR EACH ROW EXECUTE FUNCTION public.guard_schedule_cursor_repair_immutable();

    REVOKE ALL ON public.schedule_cursor_repair_receipt
      FROM PUBLIC,aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON public.schedule_cursor_repair_receipt TO aos_extension_maintainer;

    CREATE FUNCTION public.schedule_cursor_repair_a0v_077(request jsonb, actor text)
    RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
    SET search_path=pg_catalog,public AS $$
    DECLARE
      v_org text:=request->>'orgId';
      v_project text:=request->>'projectId';
      v_schedule text:=request->>'scheduleId';
      v_expected text:=request->>'expectedCurrentRunId';
      v_target_id text:=request->>'targetRunId';
      v_key text:=request->>'idempotencyKey';
      v_request_hash text;
      v_schedule_row record;
      v_target record;
      v_last jsonb;
      v_receipt record;
      v_body jsonb;
      v_hash text;
    BEGIN
      IF request->>'schemaVersion'<>'aos.schedule-cursor-repair/v1'
        OR v_org IS NULL OR v_project IS NULL OR v_schedule IS NULL
        OR v_expected IS NULL OR v_target_id IS NULL OR v_key IS NULL
        OR actor IS NULL OR btrim(actor)=''
      THEN RAISE EXCEPTION 'exact schedule cursor repair request required' USING ERRCODE='22023'; END IF;
      v_request_hash:='sha256:'||encode(sha256(convert_to(request::text,'UTF8')),'hex');

      SELECT * INTO v_receipt FROM public.schedule_cursor_repair_receipt
        WHERE org_id=v_org AND project_id=v_project AND idempotency_key=v_key;
      IF FOUND THEN
        IF v_receipt.request_hash<>v_request_hash THEN
          RAISE EXCEPTION 'schedule cursor repair idempotency conflict' USING ERRCODE='40001';
        END IF;
        RETURN jsonb_build_object('receiptId',v_receipt.receipt_id,'contentHash',v_receipt.content_hash,
          'scheduleId',v_receipt.schedule_id,'targetRunId',v_receipt.target_run_id,
          'priorLastRun',v_receipt.prior_last_run,'repairedLastRun',v_receipt.repaired_last_run,
          'replayed',true);
      END IF;

      SELECT * INTO v_schedule_row FROM public.meta_schedule
        WHERE org_id=v_org AND project_id=v_project AND id=v_schedule FOR UPDATE;
      IF NOT FOUND OR v_schedule_row.enabled OR v_schedule_row.last_run IS NULL
        OR v_schedule_row.last_run->>'id'<>v_expected
      THEN RAISE EXCEPTION 'exact disabled stale schedule cursor required' USING ERRCODE='40001'; END IF;
      IF EXISTS(SELECT 1 FROM public.meta_schedule_run WHERE org_id=v_org AND project_id=v_project
        AND schedule_id=v_schedule AND status='running')
      THEN RAISE EXCEPTION 'running schedule cannot repair cursor' USING ERRCODE='55000'; END IF;

      SELECT * INTO v_target FROM public.meta_schedule_run
        WHERE org_id=v_org AND project_id=v_project AND schedule_id=v_schedule AND id=v_target_id FOR SHARE;
      IF NOT FOUND OR v_target.status<>'succeeded' OR NOT v_target.executor_stopped
        OR v_target.finished_at IS NULL
        OR EXISTS(SELECT 1 FROM public.meta_schedule_run newer
          WHERE newer.org_id=v_org AND newer.project_id=v_project AND newer.schedule_id=v_schedule
            AND newer.status='succeeded' AND newer.executor_stopped AND newer.finished_at IS NOT NULL
            AND (newer.finished_at, newer.id)>(v_target.finished_at,v_target.id))
      THEN RAISE EXCEPTION 'latest stopped successful schedule run required' USING ERRCODE='40001'; END IF;

      v_last:=jsonb_build_object('id',v_target.id,'at',v_target.finished_at,
        'status','succeeded','trigger',v_target.trigger,'rowsWritten',coalesce(v_target.rows_written,0),
        'durationMs',coalesce(v_target.duration_ms,0),'errorCode',coalesce(v_target.error_code,''));
      UPDATE public.meta_schedule SET last_run=v_last,updated_at=clock_timestamp()
        WHERE org_id=v_org AND project_id=v_project AND id=v_schedule
          AND last_run=v_schedule_row.last_run;
      IF NOT FOUND THEN RAISE EXCEPTION 'schedule cursor changed during repair' USING ERRCODE='40001'; END IF;

      v_body:=jsonb_build_object('schemaVersion','aos.schedule-cursor-repair-receipt/v1',
        'orgId',v_org,'projectId',v_project,'scheduleId',v_schedule,
        'expectedCurrentRunId',v_expected,'targetRunId',v_target_id,
        'priorLastRun',v_schedule_row.last_run,'repairedLastRun',v_last,
        'idempotencyKey',v_key,'repairedBy',actor);
      v_hash:='sha256:'||encode(sha256(convert_to(v_body::text,'UTF8')),'hex');
      INSERT INTO public.schedule_cursor_repair_receipt(org_id,project_id,schedule_id,
        expected_current_run_id,target_run_id,idempotency_key,request_hash,prior_last_run,
        repaired_last_run,content_hash,repaired_by)
      VALUES(v_org,v_project,v_schedule,v_expected,v_target_id,v_key,v_request_hash,
        v_schedule_row.last_run,v_last,v_hash,actor) RETURNING * INTO v_receipt;
      RETURN jsonb_build_object('receiptId',v_receipt.receipt_id,'contentHash',v_hash,
        'scheduleId',v_schedule,'targetRunId',v_target_id,'priorLastRun',v_schedule_row.last_run,
        'repairedLastRun',v_last,'replayed',false);
    END $$;
    REVOKE ALL ON FUNCTION public.schedule_cursor_repair_a0v_077(jsonb,text)
      FROM PUBLIC,aos_runtime;
    GRANT EXECUTE ON FUNCTION public.schedule_cursor_repair_a0v_077(jsonb,text)
      TO aos_extension_maintainer;
    """)


def downgrade():
    raise RuntimeError("schedule cursor repair receipts must be retained")
