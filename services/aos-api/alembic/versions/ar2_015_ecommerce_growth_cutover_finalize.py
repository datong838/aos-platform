"""Validated activation resume authority; additive and closed by default."""

from alembic import op


revision = "ar2_015"
down_revision = "ar2_014"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
    ALTER TABLE extension_dispatch_cutover_operation
      DROP CONSTRAINT extension_dispatch_cutover_operation_status_check;
    ALTER TABLE extension_dispatch_cutover_operation
      ADD CONSTRAINT extension_dispatch_cutover_operation_status_check CHECK(status IN (
        'prepared','committing','committed','validated','resumed','fencing','draining',
        'rolled_back','needs_attention'));
    ALTER TABLE extension_dispatch_cutover_event
      DROP CONSTRAINT extension_dispatch_cutover_event_event_type_check;
    ALTER TABLE extension_dispatch_cutover_event
      ADD CONSTRAINT extension_dispatch_cutover_event_event_type_check CHECK(event_type IN (
        'CUTOVER_PREPARED','CUTOVER_CLAIMS_PAUSED','CUTOVER_COMMITTED','CUTOVER_VALIDATED',
        'CUTOVER_RESUMED','CUTOVER_FENCED','CUTOVER_DRAINED','CUTOVER_ROLLED_BACK',
        'CUTOVER_NEEDS_ATTENTION'));
    ALTER TABLE extension_dispatch_cutover_receipt
      DROP CONSTRAINT extension_dispatch_cutover_receipt_phase_check;
    ALTER TABLE extension_dispatch_cutover_receipt
      ADD CONSTRAINT extension_dispatch_cutover_receipt_phase_check
      CHECK(phase IN ('prepare','pause','commit','validate','resume','fence','drain','rollback'));

    CREATE OR REPLACE FUNCTION extension_dispatch_cutover_history_guard_ar2_014() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_phase text;
      BEGIN
        v_phase:=CASE NEW.status
          WHEN 'draining' THEN 'pause'
          WHEN 'committed' THEN 'commit'
          WHEN 'validated' THEN 'validate'
          WHEN 'resumed' THEN 'resume'
          ELSE NULL END;
        IF v_phase IS NOT NULL AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.cutover_operation_id=NEW.cutover_operation_id AND r.phase=v_phase)
        THEN RAISE EXCEPTION '% cutover requires % Receipt',NEW.status,v_phase
          USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$;

    CREATE FUNCTION extension_dispatch_cutover_resume_ar2_015(
      p_cutover_operation_id uuid,p_actor text) RETURNS timestamptz
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_operation record; v_gate record; v_snapshot jsonb; v_now timestamptz:=clock_timestamp();
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR length(BTRIM(p_actor)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT * INTO v_operation FROM public.extension_dispatch_cutover_operation
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id FOR UPDATE;
        IF NOT FOUND OR v_operation.kind<>'activate' OR v_operation.status<>'validated'
        THEN RAISE EXCEPTION 'cutover operation is not validated' USING ERRCODE='55000'; END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_operation.cutover_group_id FOR UPDATE;
        IF NOT FOUND OR v_gate.cutover_operation_id<>p_cutover_operation_id
          OR NOT v_gate.claim_paused
        THEN RAISE EXCEPTION 'cutover claim gate is not exact and paused'
          USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id
          ORDER BY d.operation_id FOR UPDATE;
        SELECT jsonb_agg(jsonb_build_object(
          'operationId',d.operation_id,'handlerKind',d.handler_kind,
          'installationId',d.installation_id::text,'generation',d.generation::text,
          'executionEpoch',d.execution_epoch,'operationFence',d.operation_fence,
          'revision',d.revision,'cutoverGroupId',d.cutover_group_id::text,
          'cutoverGroupRevision',d.cutover_group_revision) ORDER BY d.operation_id)
          INTO v_snapshot FROM public.extension_operation_dispatch_binding d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id;
        IF v_snapshot IS DISTINCT FROM v_operation.new_dispatch_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'committed dispatch group authority drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_runtime_binding r SET
          enabled=true,operation_fence=false,revision=r.revision+1
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.installation_id=v_operation.target_installation_id
            AND r.generation=v_operation.target_generation
            AND r.execution_epoch=v_operation.target_execution_epoch
            AND r.revision=v_operation.target_runtime_revision+1
            AND r.desired_state='enabled' AND r.observed_state='ready'
            AND NOT r.enabled AND r.operation_fence;
        IF NOT FOUND THEN RAISE EXCEPTION 'target runtime drain fence drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_claim_gate g SET
          claim_paused=false,revision=g.revision+1,updated_by=BTRIM(p_actor),updated_at=v_now
          WHERE g.org_id=v_org AND g.project_id=v_project
            AND g.cutover_group_id=v_operation.cutover_group_id
            AND g.cutover_operation_id=p_cutover_operation_id AND g.claim_paused;
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover claim gate resume drifted'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_cutover_operation SET
          status='resumed',updated_at=v_now
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id AND status='validated';
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover resume state drifted'
          USING ERRCODE='40001'; END IF;
        RETURN v_now;
      END $$;
    """)
    op.execute(
        "REVOKE ALL ON FUNCTION extension_dispatch_cutover_resume_ar2_015(uuid,text) "
        "FROM PUBLIC,aos_runtime"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION extension_dispatch_cutover_resume_ar2_015(uuid,text) "
        "TO aos_extension_maintainer"
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_cutover_receipt
        WHERE phase IN ('validate','resume'))
        OR EXISTS(SELECT 1 FROM extension_dispatch_cutover_operation
          WHERE status IN ('validated','resumed'))
        OR EXISTS(SELECT 1 FROM extension_dispatch_claim_gate WHERE NOT claim_paused)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_015 with finalized cutover authority'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute("DROP FUNCTION extension_dispatch_cutover_resume_ar2_015(uuid,text)")
    op.execute("""CREATE OR REPLACE FUNCTION extension_dispatch_cutover_history_guard_ar2_014()
      RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public,pg_temp AS $$
      BEGIN
        IF NEW.status='draining' AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.cutover_operation_id=NEW.cutover_operation_id AND r.phase='pause')
        THEN RAISE EXCEPTION 'draining cutover requires pause Receipt' USING ERRCODE='23514'; END IF;
        IF NEW.status='committed' AND OLD.status IS DISTINCT FROM NEW.status
          AND NOT EXISTS(SELECT 1 FROM public.extension_dispatch_cutover_receipt r
            WHERE r.org_id=NEW.org_id AND r.project_id=NEW.project_id
              AND r.cutover_operation_id=NEW.cutover_operation_id AND r.phase='commit')
        THEN RAISE EXCEPTION 'committed cutover requires commit Receipt' USING ERRCODE='23514'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""
    ALTER TABLE extension_dispatch_cutover_operation
      DROP CONSTRAINT extension_dispatch_cutover_operation_status_check;
    ALTER TABLE extension_dispatch_cutover_operation
      ADD CONSTRAINT extension_dispatch_cutover_operation_status_check CHECK(status IN (
        'prepared','committing','committed','fencing','draining','rolled_back','needs_attention'));
    ALTER TABLE extension_dispatch_cutover_event
      DROP CONSTRAINT extension_dispatch_cutover_event_event_type_check;
    ALTER TABLE extension_dispatch_cutover_event
      ADD CONSTRAINT extension_dispatch_cutover_event_event_type_check CHECK(event_type IN (
        'CUTOVER_PREPARED','CUTOVER_CLAIMS_PAUSED','CUTOVER_COMMITTED','CUTOVER_FENCED',
        'CUTOVER_DRAINED','CUTOVER_ROLLED_BACK','CUTOVER_NEEDS_ATTENTION'));
    ALTER TABLE extension_dispatch_cutover_receipt
      DROP CONSTRAINT extension_dispatch_cutover_receipt_phase_check;
    ALTER TABLE extension_dispatch_cutover_receipt
      ADD CONSTRAINT extension_dispatch_cutover_receipt_phase_check
      CHECK(phase IN ('prepare','pause','commit','fence','drain','rollback'));
    """)
