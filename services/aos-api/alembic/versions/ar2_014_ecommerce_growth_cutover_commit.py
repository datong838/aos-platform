"""Atomic ecommerce growth cutover claim gate and commit authority."""

from alembic import op


revision = "ar2_014"
down_revision = "ar2_013"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""
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

    CREATE TABLE extension_dispatch_claim_gate (
      org_id text NOT NULL,
      project_id text NOT NULL,
      cutover_group_id uuid NOT NULL,
      cutover_operation_id uuid NOT NULL,
      claim_paused boolean NOT NULL,
      revision bigint NOT NULL CHECK(revision > 0),
      updated_by text NOT NULL CHECK(length(updated_by) BETWEEN 1 AND 240),
      updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,cutover_group_id),
      FOREIGN KEY(org_id,project_id,cutover_operation_id)
        REFERENCES extension_dispatch_cutover_operation(org_id,project_id,cutover_operation_id)
    );
    ALTER TABLE extension_dispatch_claim_gate ENABLE ROW LEVEL SECURITY;
    ALTER TABLE extension_dispatch_claim_gate FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_scope ON extension_dispatch_claim_gate
      USING(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true))
      WITH CHECK(org_id=current_setting('aos.org_id',true)
        AND project_id=current_setting('aos.project_id',true));
    REVOKE ALL ON extension_dispatch_claim_gate FROM PUBLIC;
    GRANT SELECT ON extension_dispatch_claim_gate TO aos_runtime,aos_extension_maintainer;
    GRANT SELECT ON automation_occurrence,automation_occurrence_dispatch_attempt,
      extension_runtime_execution_attempt TO aos_extension_maintainer;

    CREATE OR REPLACE FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(
      p_approval_event_id text) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_proposal_id text;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR length(BTRIM(p_approval_event_id)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT a.proposal_id INTO v_proposal_id
          FROM public.aip_action_approval_event a
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND a.approval_event_id=p_approval_event_id FOR SHARE;
        IF v_proposal_id IS NULL THEN
          RAISE EXCEPTION 'cutover approval is unavailable' USING ERRCODE='P0002';
        END IF;
        PERFORM 1 FROM public.aip_action_proposal p
          WHERE p.org_id=v_org AND p.project_id=v_project AND p.proposal_id=v_proposal_id
          FOR SHARE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'cutover proposal is unavailable' USING ERRCODE='P0002';
        END IF;
        PERFORM 1 FROM public.aip_action_draft d
          WHERE d.org_id=v_org AND d.project_id=v_project AND d.proposal_id=v_proposal_id
          FOR SHARE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'cutover proposal draft is unavailable' USING ERRCODE='P0002';
        END IF;
      END $$;

    CREATE FUNCTION extension_dispatch_cutover_history_guard_ar2_014() RETURNS trigger
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
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
      END $$;
    CREATE CONSTRAINT TRIGGER cutover_history_guard
      AFTER UPDATE OF status ON extension_dispatch_cutover_operation
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
      EXECUTE FUNCTION extension_dispatch_cutover_history_guard_ar2_014();

    CREATE FUNCTION extension_dispatch_cutover_pause_claims_ar2_014(
      p_cutover_operation_id uuid,p_actor text) RETURNS timestamptz
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_operation record; v_gate record; v_now timestamptz:=clock_timestamp();
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
        IF NOT FOUND OR v_operation.kind<>'activate'
          OR v_operation.status NOT IN ('prepared','draining')
        THEN RAISE EXCEPTION 'cutover operation cannot pause claims' USING ERRCODE='55000'; END IF;
        IF v_operation.status='prepared' THEN
          UPDATE public.extension_runtime_binding r
            SET enabled=false,operation_fence=true,revision=r.revision+1
            WHERE r.org_id=v_org AND r.project_id=v_project
              AND r.installation_id=v_operation.target_installation_id
              AND r.generation=v_operation.target_generation
              AND r.execution_epoch=v_operation.target_execution_epoch
              AND r.revision=v_operation.target_runtime_revision
              AND r.desired_state='enabled' AND r.observed_state='ready'
              AND r.enabled AND NOT r.operation_fence;
          IF NOT FOUND THEN RAISE EXCEPTION 'target runtime binding is not exact and ready'
            USING ERRCODE='40001'; END IF;
        ELSE
          PERFORM 1 FROM public.extension_runtime_binding r
            WHERE r.org_id=v_org AND r.project_id=v_project
              AND r.installation_id=v_operation.target_installation_id
              AND r.generation=v_operation.target_generation
              AND r.execution_epoch=v_operation.target_execution_epoch
              AND r.revision=v_operation.target_runtime_revision+1
              AND r.desired_state='enabled' AND r.observed_state='ready'
              AND NOT r.enabled AND r.operation_fence FOR UPDATE;
          IF NOT FOUND THEN RAISE EXCEPTION 'target runtime drain fence drifted'
            USING ERRCODE='40001'; END IF;
        END IF;
        SELECT * INTO v_gate FROM public.extension_dispatch_claim_gate
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_group_id=v_operation.cutover_group_id FOR UPDATE;
        IF FOUND THEN
          IF v_gate.cutover_operation_id<>p_cutover_operation_id
            OR v_gate.claim_paused IS DISTINCT FROM TRUE
          THEN RAISE EXCEPTION 'cutover claim gate is owned by another operation'
            USING ERRCODE='40001'; END IF;
        ELSE
          INSERT INTO public.extension_dispatch_claim_gate(
            org_id,project_id,cutover_group_id,cutover_operation_id,
            claim_paused,revision,updated_by,updated_at)
          VALUES(v_org,v_project,v_operation.cutover_group_id,p_cutover_operation_id,
            true,1,BTRIM(p_actor),v_now);
        END IF;
        IF v_operation.status='prepared' THEN
          UPDATE public.extension_dispatch_cutover_operation
            SET status='draining',updated_at=v_now
            WHERE org_id=v_org AND project_id=v_project
              AND cutover_operation_id=p_cutover_operation_id;
        END IF;
        RETURN v_now;
      END $$;

    CREATE FUNCTION extension_dispatch_cutover_commit_ar2_014(
      p_cutover_operation_id uuid,p_actor text) RETURNS bigint
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_operation record; v_snapshot jsonb; v_rows bigint;
        v_approval record; v_proposal record; v_draft record; v_now timestamptz;
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
        IF NOT FOUND OR v_operation.kind<>'activate' OR v_operation.status<>'draining'
        THEN RAISE EXCEPTION 'cutover operation is not draining' USING ERRCODE='55000'; END IF;
        IF jsonb_array_length(v_operation.pending_target_receipt_refs)<>0
        THEN RAISE EXCEPTION 'pending target Receipt reconciliation remains'
          USING ERRCODE='55000'; END IF;
        PERFORM 1 FROM public.extension_dispatch_claim_gate g
          WHERE g.org_id=v_org AND g.project_id=v_project
            AND g.cutover_group_id=v_operation.cutover_group_id
            AND g.cutover_operation_id=p_cutover_operation_id AND g.claim_paused FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover claims are not paused' USING ERRCODE='55000'; END IF;
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
        IF v_snapshot IS DISTINCT FROM v_operation.old_dispatch_snapshot
          OR jsonb_array_length(v_snapshot)<>9
        THEN RAISE EXCEPTION 'legacy dispatch group authority drifted' USING ERRCODE='40001'; END IF;
        PERFORM 1 FROM public.extension_runtime_binding r
          WHERE r.org_id=v_org AND r.project_id=v_project
            AND r.installation_id=v_operation.target_installation_id
            AND r.generation=v_operation.target_generation
            AND r.execution_epoch=v_operation.target_execution_epoch
            AND r.revision=v_operation.target_runtime_revision+1
            AND r.desired_state='enabled' AND r.observed_state='ready'
            AND NOT r.enabled AND r.operation_fence FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'target runtime drain fence drifted'
          USING ERRCODE='40001'; END IF;
        SELECT * INTO v_approval FROM public.aip_action_approval_event a
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND a.approval_event_id=v_operation.approval_ref->>'resourceId' FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover approval is unavailable'
          USING ERRCODE='55000'; END IF;
        SELECT * INTO v_proposal FROM public.aip_action_proposal p
          WHERE p.org_id=v_org AND p.project_id=v_project
            AND p.proposal_id=v_approval.proposal_id FOR SHARE;
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover proposal is unavailable'
          USING ERRCODE='55000'; END IF;
        v_now:=clock_timestamp();
        SELECT * INTO v_draft FROM public.aip_action_draft d
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.proposal_id=v_proposal.proposal_id FOR SHARE;
        IF NOT FOUND OR v_operation.approval_ref->>'resourceType' IS DISTINCT FROM 'ActionApprovalEvent'
          OR (v_operation.approval_ref->>'revision')::bigint IS DISTINCT FROM v_approval.proposal_version
          OR v_operation.approval_ref->>'contentHash' IS NULL
          OR v_operation.approval_ref->>'contentHash' !~ '^sha256:[0-9a-f]{64}$'
          OR v_approval.decision IS DISTINCT FROM 'approved'
          OR (v_approval.expires_at IS NOT NULL AND v_approval.expires_at<=v_now)
          OR v_proposal.status IS DISTINCT FROM 'approved' OR v_proposal.expires_at<=v_now
          OR v_proposal.action_type_id IS DISTINCT FROM 'ecommerce_growth_cutover'
          OR v_proposal.version IS DISTINCT FROM v_approval.proposal_version
          OR v_proposal.proposal_hash IS DISTINCT FROM v_approval.proposal_hash
          OR v_draft.proposal_hash IS DISTINCT FROM v_proposal.proposal_hash
          OR v_proposal.action_binding_hash IS NULL
          OR v_proposal.action_binding_hash IS DISTINCT FROM v_approval.action_binding_hash
          OR v_draft.snapshot->'tenantScope' IS DISTINCT FROM jsonb_build_object('orgId',v_org,'projectId',v_project)
          OR v_draft.snapshot->'actionType' IS DISTINCT FROM v_proposal.action_type_snapshot
          OR v_draft.snapshot->'taskId' IS DISTINCT FROM COALESCE(to_jsonb(v_proposal.task_id),'null'::jsonb)
          OR v_draft.snapshot->'runId' IS DISTINCT FROM COALESCE(to_jsonb(v_proposal.run_id),'null'::jsonb)
          OR v_draft.snapshot->'objectRef' IS DISTINCT FROM COALESCE(v_proposal.object_ref,'null'::jsonb)
          OR v_draft.snapshot->'payload' IS DISTINCT FROM v_proposal.payload
          OR v_draft.snapshot->'policy' IS DISTINCT FROM v_proposal.policy_snapshot
          OR v_draft.snapshot->'diff' IS DISTINCT FROM v_proposal.diff
          OR v_draft.snapshot->'evidenceRefs' IS DISTINCT FROM v_proposal.evidence_refs
          OR v_draft.snapshot->>'purpose' IS DISTINCT FROM v_proposal.purpose
          OR v_draft.snapshot->>'riskLevel' IS DISTINCT FROM v_proposal.risk_level
          OR v_draft.snapshot->>'createdBy' IS DISTINCT FROM v_proposal.created_by
          OR v_draft.snapshot->>'approvalPolicyHash' IS DISTINCT FROM v_proposal.approval_policy_hash
          OR v_draft.snapshot->>'actionBindingHash' IS DISTINCT FROM v_proposal.action_binding_hash
          OR (v_draft.snapshot->>'expiresAt')::timestamptz IS DISTINCT FROM v_proposal.expires_at
          OR (v_proposal.impact_preview_id IS NULL) IS DISTINCT FROM
             (v_proposal.impact_preview_revision IS NULL)
          OR (v_proposal.impact_preview_id IS NULL) IS DISTINCT FROM
             (v_proposal.impact_preview_hash IS NULL)
          OR (v_proposal.source_draft_id IS NULL) IS DISTINCT FROM
             (v_proposal.source_draft_revision IS NULL)
          OR (v_proposal.source_draft_id IS NULL) IS DISTINCT FROM
             (v_proposal.source_draft_hash IS NULL)
          OR v_draft.snapshot->'impactPreviewRef' IS DISTINCT FROM (CASE
            WHEN v_proposal.impact_preview_id IS NULL THEN 'null'::jsonb ELSE jsonb_build_object(
              'resourceType','ImpactPreviewRevision','resourceId',v_proposal.impact_preview_id,
              'revision',v_proposal.impact_preview_revision,'contentHash',v_proposal.impact_preview_hash) END)
          OR v_draft.snapshot->'sourceDraftRef' IS DISTINCT FROM (CASE
            WHEN v_proposal.source_draft_id IS NULL THEN 'null'::jsonb ELSE jsonb_build_object(
              'resourceType','ActionDraftRevision','resourceId',v_proposal.source_draft_id,
              'revision',v_proposal.source_draft_revision,'contentHash',v_proposal.source_draft_hash) END)
          OR v_proposal.payload->>'cutoverGroupId' IS DISTINCT FROM v_operation.cutover_group_id::text
          OR (v_proposal.payload->>'expectedGroupRevision')::bigint IS DISTINCT FROM v_operation.expected_group_revision
          OR v_proposal.payload->>'targetInstallationId' IS DISTINCT FROM v_operation.target_installation_id::text
          OR v_proposal.payload->>'targetGeneration' IS DISTINCT FROM v_operation.target_generation::text
          OR (v_proposal.payload->>'targetExecutionEpoch')::bigint IS DISTINCT FROM v_operation.target_execution_epoch
          OR (v_proposal.payload->>'targetRuntimeRevision')::bigint IS DISTINCT FROM v_operation.target_runtime_revision
          OR v_proposal.payload->'operationIds' IS DISTINCT FROM v_operation.operation_ids
          OR v_proposal.payload->'policyRef' IS DISTINCT FROM v_operation.policy_ref
        THEN RAISE EXCEPTION 'cutover approval is not bound to this exact group'
          USING ERRCODE='55000'; END IF;
        IF EXISTS(SELECT 1 FROM public.automation_occurrence o
          WHERE o.org_id=v_org AND o.project_id=v_project
            AND o.installation_id=v_operation.target_installation_id
            AND o.generation=v_operation.target_generation
            AND o.execution_epoch=v_operation.target_execution_epoch AND o.status='claimed')
          OR EXISTS(SELECT 1 FROM public.automation_occurrence_dispatch_attempt a
            JOIN public.automation_occurrence o USING(org_id,project_id,occurrence_id)
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND o.installation_id=v_operation.target_installation_id
              AND o.generation=v_operation.target_generation
              AND o.execution_epoch=v_operation.target_execution_epoch AND a.status='claimed')
          OR EXISTS(SELECT 1 FROM public.extension_runtime_execution_attempt a
            WHERE a.org_id=v_org AND a.project_id=v_project
              AND a.installation_id=v_operation.target_installation_id
              AND a.generation=v_operation.target_generation
              AND a.execution_epoch=v_operation.target_execution_epoch AND a.state='running')
        THEN RAISE EXCEPTION 'cutover target execution is not drained' USING ERRCODE='55000'; END IF;
        UPDATE public.extension_operation_dispatch_binding d SET
          handler_kind='extension',installation_id=v_operation.target_installation_id,
          generation=v_operation.target_generation,execution_epoch=v_operation.target_execution_epoch,
          operation_fence=false,revision=d.revision+1,
          cutover_group_revision=v_operation.target_group_revision,
          updated_by=BTRIM(p_actor),updated_at=clock_timestamp()
          WHERE d.org_id=v_org AND d.project_id=v_project
            AND d.cutover_group_id=v_operation.cutover_group_id;
        GET DIAGNOSTICS v_rows=ROW_COUNT;
        IF v_rows<>9 THEN RAISE EXCEPTION 'cutover group update was not exact'
          USING ERRCODE='40001'; END IF;
        UPDATE public.extension_dispatch_cutover_operation
          SET status='committed',updated_at=clock_timestamp()
          WHERE org_id=v_org AND project_id=v_project
            AND cutover_operation_id=p_cutover_operation_id AND status='draining';
        IF NOT FOUND THEN RAISE EXCEPTION 'cutover operation commit state drifted'
          USING ERRCODE='40001'; END IF;
        RETURN v_rows;
      END $$;
    """)
    for function in (
        "extension_dispatch_cutover_pause_claims_ar2_014(uuid,text)",
        "extension_dispatch_cutover_commit_ar2_014(uuid,text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {function} FROM PUBLIC,aos_runtime")
        op.execute(f"GRANT EXECUTE ON FUNCTION {function} TO aos_extension_maintainer")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM extension_dispatch_claim_gate LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade ar2_014 with cutover claim gates'
        USING ERRCODE='55000'; END IF;
    END $$""")
    op.execute("DROP FUNCTION extension_dispatch_cutover_commit_ar2_014(uuid,text)")
    op.execute("DROP FUNCTION extension_dispatch_cutover_pause_claims_ar2_014(uuid,text)")
    op.execute("DROP TRIGGER cutover_history_guard ON extension_dispatch_cutover_operation")
    op.execute("DROP FUNCTION extension_dispatch_cutover_history_guard_ar2_014()")
    op.execute("DROP TABLE extension_dispatch_claim_gate")
    op.execute("""CREATE OR REPLACE FUNCTION extension_dispatch_cutover_lock_approval_ar2_013(
      p_approval_event_id text) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_proposal_id text;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL
          OR length(BTRIM(p_approval_event_id)) NOT BETWEEN 1 AND 240
          OR NOT pg_has_role(session_user,'aos_extension_maintainer','member')
          OR EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname=session_user AND (rolsuper OR rolbypassrls))
        THEN RAISE EXCEPTION 'dedicated non-privileged cutover maintainer is required'
          USING ERRCODE='42501'; END IF;
        SELECT a.proposal_id INTO v_proposal_id
          FROM public.aip_action_approval_event a
          WHERE a.org_id=v_org AND a.project_id=v_project
            AND a.approval_event_id=p_approval_event_id;
        IF v_proposal_id IS NULL THEN
          RAISE EXCEPTION 'cutover approval is unavailable' USING ERRCODE='P0002';
        END IF;
        PERFORM 1 FROM public.aip_action_proposal p
          WHERE p.org_id=v_org AND p.project_id=v_project AND p.proposal_id=v_proposal_id
          FOR SHARE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'cutover proposal is unavailable' USING ERRCODE='P0002';
        END IF;
      END $$""")
    op.execute("""
    ALTER TABLE extension_dispatch_cutover_event
      DROP CONSTRAINT extension_dispatch_cutover_event_event_type_check;
    ALTER TABLE extension_dispatch_cutover_event
      ADD CONSTRAINT extension_dispatch_cutover_event_event_type_check CHECK(event_type IN (
        'CUTOVER_PREPARED','CUTOVER_COMMITTED','CUTOVER_FENCED',
        'CUTOVER_DRAINED','CUTOVER_ROLLED_BACK','CUTOVER_NEEDS_ATTENTION'));
    ALTER TABLE extension_dispatch_cutover_receipt
      DROP CONSTRAINT extension_dispatch_cutover_receipt_phase_check;
    ALTER TABLE extension_dispatch_cutover_receipt
      ADD CONSTRAINT extension_dispatch_cutover_receipt_phase_check
      CHECK(phase IN ('prepare','commit','fence','drain','rollback'));
    """)
