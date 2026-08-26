"""Add controlled investigation Artifact publication. Revision ID: biw6_002."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw6_002"
down_revision: str | Sequence[str] | None = "biw6_001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE ecommerce_investigation_artifact_publication_receipt(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,receipt_id TEXT NOT NULL,command_id TEXT NOT NULL,
      request_hash TEXT NOT NULL,artifact_type TEXT NOT NULL,artifact_id TEXT NOT NULL,artifact_revision BIGINT NOT NULL,
      artifact_hash TEXT NOT NULL,binding_id TEXT NOT NULL,binding_hash TEXT NOT NULL,
      eval_report_id TEXT NOT NULL,eval_report_revision BIGINT NOT NULL,eval_report_hash TEXT NOT NULL,
      step_run_id TEXT NOT NULL,step_attempt BIGINT NOT NULL,step_input_hash TEXT NOT NULL,
      case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,case_hash TEXT NOT NULL,
      run_id TEXT NOT NULL,run_version BIGINT NOT NULL,run_hash TEXT NOT NULL,
      data_cutoff TIMESTAMPTZ NOT NULL,receipt_data JSONB NOT NULL,published_by TEXT NOT NULL,published_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,receipt_id),UNIQUE(org_id,project_id,command_id),
      UNIQUE(org_id,project_id,artifact_type,artifact_id,artifact_revision,artifact_hash),
      FOREIGN KEY(org_id,project_id,binding_id) REFERENCES ecommerce_investigation_artifact_binding(org_id,project_id,binding_id),
      FOREIGN KEY(org_id,project_id,eval_report_id,eval_report_revision) REFERENCES aip_eval_report_revision(org_id,project_id,report_id,revision),
      FOREIGN KEY(org_id,project_id,step_run_id) REFERENCES aip_step_run(org_id,project_id,step_run_id),
      FOREIGN KEY(org_id,project_id,case_id,case_revision,case_hash) REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,content_hash),
      FOREIGN KEY(org_id,project_id,run_id,run_version,run_hash,case_id,case_revision) REFERENCES ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision),
      CHECK(request_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(binding_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(eval_report_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(step_input_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(case_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(run_hash ~ '^sha256:[0-9a-f]{64}$'),CHECK(data_cutoff<=published_at),CHECK(jsonb_typeof(receipt_data)='object'))""")
    op.execute("""CREATE FUNCTION ecommerce_investigation_publish_artifact_biw6_002(
      p_org_id text,p_project_id text,p_expected_head_revision bigint,p_artifact jsonb,p_binding jsonb,p_receipt jsonb)
      RETURNS TABLE(receipt_data jsonb,replayed boolean) LANGUAGE plpgsql SECURITY DEFINER
      SET search_path=pg_catalog,public AS $$
      DECLARE v_scope_org text:=NULLIF(current_setting('aos.org_id',true),'');
        v_scope_project text:=NULLIF(current_setting('aos.project_id',true),'');
        v_existing record;v_head record;v_eval record;v_artifact_type text:=p_artifact->>'artifactType';
        v_artifact_id text:=p_artifact->>'artifactId';v_revision bigint:=(p_artifact->>'revision')::bigint;
        v_artifact_hash text:=p_artifact->>'contentHash';v_command_id text:=p_receipt->>'commandId';
        v_request_hash text:=p_receipt->>'requestHash';v_receipt_id text:=p_receipt->>'receiptId';
      BEGIN
        IF v_scope_org IS NULL OR v_scope_project IS NULL OR p_org_id<>v_scope_org OR p_project_id<>v_scope_project
          THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='artifact publication tenant scope is required';END IF;
        IF p_expected_head_revision<0 THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='expected head revision is invalid';END IF;
        IF p_artifact-ARRAY['schemaVersion','tenant','artifactId','artifactType','revision','version','priorRef','contentHash','caseRef','runRef','inputRefs','createdBy','createdAt']<>'{}'::jsonb
          OR p_binding-ARRAY['schemaVersion','tenant','bindingId','bindingHash','artifactRef','selectedChannelRef','selectedEntityRef','caseRef','runRef','selectionRevision','dataCutoff','lineageRef','boundBy','boundAt']<>'{}'::jsonb
          OR p_receipt-ARRAY['schemaVersion','tenant','receiptId','commandId','requestHash','artifactRef','bindingRef','evalReportRef','stageAttemptRef','caseRef','runRef','dataCutoff','publishedBy','publishedAt']<>'{}'::jsonb
          OR p_artifact::text ~* '"(secret|token|cookie|password|credential)[^"]*"[[:space:]]*:'
          OR p_binding::text ~* '"(secret|token|cookie|password|credential)[^"]*"[[:space:]]*:'
          OR p_receipt::text ~* '"(secret|token|cookie|password|credential)[^"]*"[[:space:]]*:'
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='artifact publication payload contains unsupported fields';END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended(p_org_id||':'||p_project_id||':'||v_command_id,0));
        SELECT r.receipt_data,r.request_hash INTO v_existing FROM ecommerce_investigation_artifact_publication_receipt r
          WHERE r.org_id=p_org_id AND r.project_id=p_project_id AND r.command_id=v_command_id;
        IF v_existing IS NOT NULL THEN
          IF v_existing.request_hash<>v_request_hash THEN RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='artifact publication command conflicts with prior payload';END IF;
          RETURN QUERY SELECT v_existing.receipt_data,true;RETURN;
        END IF;
        IF p_artifact#>>'{tenant,orgId}'<>p_org_id OR p_artifact#>>'{tenant,projectId}'<>p_project_id
          OR p_binding#>>'{tenant,orgId}'<>p_org_id OR p_binding#>>'{tenant,projectId}'<>p_project_id
          OR p_receipt#>>'{tenant,orgId}'<>p_org_id OR p_receipt#>>'{tenant,projectId}'<>p_project_id
          OR p_receipt->>'schemaVersion'<>'aos.ecommerce.business-investigation-artifact-publication-receipt/v1'
          OR p_receipt#>>'{artifactRef,resourceType}'<>v_artifact_type OR p_receipt#>>'{artifactRef,resourceId}'<>v_artifact_id
          OR (p_receipt#>>'{artifactRef,revision}')::bigint<>v_revision OR p_receipt#>>'{artifactRef,contentHash}'<>v_artifact_hash
          OR p_binding#>>'{artifactRef,resourceType}'<>v_artifact_type OR p_binding#>>'{artifactRef,resourceId}'<>v_artifact_id
          OR (p_binding#>>'{artifactRef,revision}')::bigint<>v_revision OR p_binding#>>'{artifactRef,contentHash}'<>v_artifact_hash
          OR p_receipt#>>'{bindingRef,resourceId}'<>p_binding->>'bindingId'
          OR p_receipt#>>'{bindingRef,contentHash}'<>p_binding->>'bindingHash'
          OR p_receipt#>>'{caseRef}'<>p_artifact#>>'{caseRef}' OR p_receipt#>>'{runRef}'<>p_artifact#>>'{runRef}'
          OR (p_receipt->>'dataCutoff')::timestamptz<>(p_binding->>'dataCutoff')::timestamptz
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='artifact publication payload violates exact contract';END IF;
        SELECT * INTO v_eval FROM aip_eval_report_revision e WHERE e.org_id=p_org_id AND e.project_id=p_project_id
          AND e.report_id=p_receipt#>>'{evalReportRef,resourceId}'
          AND e.revision=(p_receipt#>>'{evalReportRef,revision}')::bigint
          AND e.content_hash=replace(p_receipt#>>'{evalReportRef,contentHash}','sha256:','') AND e.gate_passed=true;
        IF v_eval IS NULL OR v_eval.subject_artifact_ref#>>'{resourceId}'<>v_artifact_id
          OR v_eval.subject_artifact_ref#>>'{contentHash}'<>replace(v_artifact_hash,'sha256:','')
          OR v_eval.stage_attempt_ref#>>'{runId}'<>p_artifact#>>'{runRef,resourceId}'
          OR v_eval.stage_attempt_ref#>>'{stepRunId}'<>p_receipt#>>'{stageAttemptRef,resourceId}'
          OR (v_eval.stage_attempt_ref#>>'{attempt}')::bigint<>(p_receipt#>>'{stageAttemptRef,revision}')::bigint
          OR v_eval.stage_attempt_ref#>>'{inputHash}'<>replace(p_receipt#>>'{stageAttemptRef,contentHash}','sha256:','')
          OR v_eval.evidence_cutoff_at<>(p_binding->>'dataCutoff')::timestamptz
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='exact passed EvalReport and StageAttempt are required';END IF;
        SELECT * INTO v_head FROM ecommerce_investigation_artifact_head h WHERE h.org_id=p_org_id AND h.project_id=p_project_id
          AND h.artifact_type=v_artifact_type AND h.artifact_id=v_artifact_id FOR UPDATE;
        IF p_expected_head_revision=0 THEN
          IF v_head IS NOT NULL OR v_revision<>1 OR COALESCE(p_artifact->'priorRef','null'::jsonb)<>'null'::jsonb THEN
            RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='artifact head expected-version conflict';END IF;
        ELSIF v_head IS NULL OR v_head.current_revision<>p_expected_head_revision OR v_head.version<>p_expected_head_revision
          OR v_revision<>p_expected_head_revision+1
          OR p_artifact#>>'{priorRef,resourceType}'<>v_artifact_type OR p_artifact#>>'{priorRef,resourceId}'<>v_artifact_id
          OR (p_artifact#>>'{priorRef,revision}')::bigint<>v_head.current_revision
          OR p_artifact#>>'{priorRef,contentHash}'<>v_head.current_content_hash
        THEN RAISE EXCEPTION USING ERRCODE='BO002',MESSAGE='artifact head expected-version conflict';END IF;
        CASE v_artifact_type
          WHEN 'BusinessDossierRevision' THEN INSERT INTO ecommerce_investigation_business_dossier_revision VALUES(
            p_org_id,p_project_id,v_artifact_id,v_revision,v_revision,(p_artifact#>>'{priorRef,revision}')::bigint,p_artifact#>>'{priorRef,contentHash}',v_artifact_hash,
            p_artifact#>>'{caseRef,resourceId}',(p_artifact#>>'{caseRef,revision}')::bigint,p_artifact#>>'{caseRef,contentHash}',p_artifact#>>'{runRef,resourceId}',(p_artifact#>>'{runRef,revision}')::bigint,p_artifact#>>'{runRef,contentHash}',p_artifact->'inputRefs',p_artifact->>'createdBy',(p_artifact->>'createdAt')::timestamptz);
          WHEN 'ProblemMapRevision' THEN INSERT INTO ecommerce_investigation_problem_map_revision VALUES(
            p_org_id,p_project_id,v_artifact_id,v_revision,v_revision,(p_artifact#>>'{priorRef,revision}')::bigint,p_artifact#>>'{priorRef,contentHash}',v_artifact_hash,
            p_artifact#>>'{caseRef,resourceId}',(p_artifact#>>'{caseRef,revision}')::bigint,p_artifact#>>'{caseRef,contentHash}',p_artifact#>>'{runRef,resourceId}',(p_artifact#>>'{runRef,revision}')::bigint,p_artifact#>>'{runRef,contentHash}',p_artifact->'inputRefs',p_artifact->>'createdBy',(p_artifact->>'createdAt')::timestamptz);
          WHEN 'OpportunityMapRevision' THEN INSERT INTO ecommerce_investigation_opportunity_map_revision VALUES(
            p_org_id,p_project_id,v_artifact_id,v_revision,v_revision,(p_artifact#>>'{priorRef,revision}')::bigint,p_artifact#>>'{priorRef,contentHash}',v_artifact_hash,
            p_artifact#>>'{caseRef,resourceId}',(p_artifact#>>'{caseRef,revision}')::bigint,p_artifact#>>'{caseRef,contentHash}',p_artifact#>>'{runRef,resourceId}',(p_artifact#>>'{runRef,revision}')::bigint,p_artifact#>>'{runRef,contentHash}',p_artifact->'inputRefs',p_artifact->>'createdBy',(p_artifact->>'createdAt')::timestamptz);
          WHEN 'SolutionPortfolioRevision' THEN INSERT INTO ecommerce_investigation_solution_portfolio_revision VALUES(
            p_org_id,p_project_id,v_artifact_id,v_revision,v_revision,(p_artifact#>>'{priorRef,revision}')::bigint,p_artifact#>>'{priorRef,contentHash}',v_artifact_hash,
            p_artifact#>>'{caseRef,resourceId}',(p_artifact#>>'{caseRef,revision}')::bigint,p_artifact#>>'{caseRef,contentHash}',p_artifact#>>'{runRef,resourceId}',(p_artifact#>>'{runRef,revision}')::bigint,p_artifact#>>'{runRef,contentHash}',p_artifact->'inputRefs',p_artifact->>'createdBy',(p_artifact->>'createdAt')::timestamptz);
          ELSE RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='unsupported artifact type';
        END CASE;
        IF p_expected_head_revision=0 THEN INSERT INTO ecommerce_investigation_artifact_head VALUES(
          p_org_id,p_project_id,v_artifact_type,v_artifact_id,v_revision,v_artifact_hash,v_revision,p_artifact#>>'{caseRef,resourceId}',(p_artifact#>>'{caseRef,revision}')::bigint,p_artifact#>>'{runRef,resourceId}',(p_receipt->>'publishedAt')::timestamptz);
        ELSE UPDATE ecommerce_investigation_artifact_head SET current_revision=v_revision,current_content_hash=v_artifact_hash,version=v_revision,
          case_id=p_artifact#>>'{caseRef,resourceId}',case_revision=(p_artifact#>>'{caseRef,revision}')::bigint,run_id=p_artifact#>>'{runRef,resourceId}',updated_at=(p_receipt->>'publishedAt')::timestamptz
          WHERE org_id=p_org_id AND project_id=p_project_id AND artifact_type=v_artifact_type AND artifact_id=v_artifact_id;END IF;
        INSERT INTO ecommerce_investigation_artifact_binding VALUES(
          p_org_id,p_project_id,p_binding->>'bindingId',p_binding->>'bindingHash',v_artifact_type,v_artifact_id,v_revision,v_artifact_hash,
          p_binding#>>'{selectedChannelRef,resourceId}',(p_binding#>>'{selectedChannelRef,revision}')::bigint,p_binding#>>'{selectedChannelRef,contentHash}',
          p_binding#>>'{selectedEntityRef,resourceId}',(p_binding#>>'{selectedEntityRef,revision}')::bigint,p_binding#>>'{selectedEntityRef,contentHash}',
          p_binding#>>'{caseRef,resourceId}',(p_binding#>>'{caseRef,revision}')::bigint,p_binding#>>'{caseRef,contentHash}',
          p_binding#>>'{runRef,resourceId}',(p_binding#>>'{runRef,revision}')::bigint,p_binding#>>'{runRef,contentHash}',
          (p_binding->>'selectionRevision')::bigint,(p_binding->>'dataCutoff')::timestamptz,p_binding->'lineageRef',p_binding,p_binding->>'boundBy',(p_binding->>'boundAt')::timestamptz);
        INSERT INTO ecommerce_investigation_artifact_publication_receipt VALUES(
          p_org_id,p_project_id,v_receipt_id,v_command_id,v_request_hash,v_artifact_type,v_artifact_id,v_revision,v_artifact_hash,
          p_binding->>'bindingId',p_binding->>'bindingHash',p_receipt#>>'{evalReportRef,resourceId}',(p_receipt#>>'{evalReportRef,revision}')::bigint,p_receipt#>>'{evalReportRef,contentHash}',
          p_receipt#>>'{stageAttemptRef,resourceId}',(p_receipt#>>'{stageAttemptRef,revision}')::bigint,p_receipt#>>'{stageAttemptRef,contentHash}',
          p_receipt#>>'{caseRef,resourceId}',(p_receipt#>>'{caseRef,revision}')::bigint,p_receipt#>>'{caseRef,contentHash}',
          p_receipt#>>'{runRef,resourceId}',(p_receipt#>>'{runRef,revision}')::bigint,p_receipt#>>'{runRef,contentHash}',
          (p_receipt->>'dataCutoff')::timestamptz,p_receipt,p_receipt->>'publishedBy',(p_receipt->>'publishedAt')::timestamptz);
        RETURN QUERY SELECT p_receipt,false;
      END $$""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_artifact_publication_receipt_immutable
      BEFORE UPDATE OR DELETE ON ecommerce_investigation_artifact_publication_receipt FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    op.execute("ALTER TABLE ecommerce_investigation_artifact_publication_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_investigation_artifact_publication_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_ecommerce_investigation_artifact_publication_receipt_biw6_002
      ON ecommerce_investigation_artifact_publication_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON ecommerce_investigation_artifact_publication_receipt TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON ecommerce_investigation_artifact_publication_receipt FROM aos_runtime")
    op.execute("REVOKE ALL ON FUNCTION ecommerce_investigation_publish_artifact_biw6_002(text,text,bigint,jsonb,jsonb,jsonb) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION ecommerce_investigation_publish_artifact_biw6_002(text,text,bigint,jsonb,jsonb,jsonb) TO aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_artifact_publication_receipt LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw6_002 with Artifact publication authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute("DROP FUNCTION ecommerce_investigation_publish_artifact_biw6_002(text,text,bigint,jsonb,jsonb,jsonb)")
    op.execute("DROP TABLE ecommerce_investigation_artifact_publication_receipt")
