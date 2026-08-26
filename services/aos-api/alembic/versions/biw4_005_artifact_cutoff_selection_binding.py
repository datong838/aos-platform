"""Add artifact cutoff and atomic selection binding. Revision ID: biw4_005."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_005"
down_revision: str | Sequence[str] | None = "biw4_004"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE ecommerce_investigation_artifact_binding(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,binding_id TEXT NOT NULL,binding_hash TEXT NOT NULL,
      artifact_type TEXT NOT NULL,artifact_id TEXT NOT NULL,artifact_revision BIGINT NOT NULL,artifact_hash TEXT NOT NULL,
      channel_id TEXT NOT NULL,channel_revision BIGINT NOT NULL,channel_hash TEXT NOT NULL,
      business_entity_id TEXT NOT NULL,business_entity_revision BIGINT NOT NULL,business_entity_hash TEXT NOT NULL,
      case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,case_hash TEXT NOT NULL,
      run_id TEXT NOT NULL,run_version BIGINT NOT NULL,run_hash TEXT NOT NULL,
      selection_revision BIGINT NOT NULL,data_cutoff TIMESTAMPTZ NOT NULL,lineage_ref JSONB NOT NULL,
      binding_data JSONB NOT NULL,bound_by TEXT NOT NULL,bound_at TIMESTAMPTZ NOT NULL,
      PRIMARY KEY(org_id,project_id,binding_id),
      UNIQUE(org_id,project_id,artifact_type,artifact_id,artifact_revision,artifact_hash),
      FOREIGN KEY(org_id,project_id,case_id,case_revision,case_hash)
        REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,content_hash),
      FOREIGN KEY(org_id,project_id,run_id,run_version,run_hash,case_id,case_revision)
        REFERENCES ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision),
      CHECK(binding_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(artifact_type IN('BusinessDossierRevision','ProblemMapRevision','OpportunityMapRevision','SolutionPortfolioRevision')),
      CHECK(artifact_revision>=1),CHECK(artifact_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(channel_revision>=1),CHECK(channel_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(business_entity_revision>=1),CHECK(business_entity_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(case_revision>=1),CHECK(case_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(run_version=1),CHECK(run_hash ~ '^sha256:[0-9a-f]{64}$'),
      CHECK(selection_revision>=1),CHECK(data_cutoff<=bound_at),CHECK(jsonb_typeof(binding_data)='object'))""")
    op.execute("""CREATE FUNCTION ecommerce_investigation_artifact_binding_guard_biw4_005()
      RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE v_case record;v_artifact_exists boolean:=false;v_data jsonb:=NEW.binding_data;
      BEGIN
        IF v_data->>'schemaVersion'<>'aos.ecommerce.business-investigation-artifact-binding/v1'
          OR v_data#>>'{tenant,orgId}'<>NEW.org_id OR v_data#>>'{tenant,projectId}'<>NEW.project_id
          OR v_data->>'bindingId'<>NEW.binding_id OR v_data->>'bindingHash'<>NEW.binding_hash
          OR NOT ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'artifactRef',NEW.artifact_type)
          OR v_data#>>'{artifactRef,resourceId}'<>NEW.artifact_id
          OR (v_data#>>'{artifactRef,revision}')::bigint<>NEW.artifact_revision
          OR v_data#>>'{artifactRef,contentHash}'<>NEW.artifact_hash
          OR NOT ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'selectedChannelRef','ChannelRevision')
          OR NOT ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'selectedEntityRef','BusinessEntityRevision')
          OR NOT ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'caseRef','BusinessInvestigationCaseRevision')
          OR NOT ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'runRef','BusinessInvestigationRun')
          OR NOT (ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'lineageRef','LineageEventRevision')
            OR ecommerce_investigation_exact_ref_valid_biw4_001(v_data->'lineageRef','LineageRevision'))
          OR (v_data->>'selectionRevision')::bigint<>NEW.selection_revision
          OR (v_data->>'dataCutoff')::timestamptz<>NEW.data_cutoff
        THEN RAISE EXCEPTION USING ERRCODE='BO001',MESSAGE='artifact binding data violates exact contract';END IF;
        SELECT * INTO v_case FROM ecommerce_investigation_case_revision c
          WHERE c.org_id=NEW.org_id AND c.project_id=NEW.project_id AND c.case_id=NEW.case_id
            AND c.revision=NEW.case_revision AND c.content_hash=NEW.case_hash;
        IF v_case IS NULL OR v_case.channel_id<>NEW.channel_id OR v_case.business_entity_id<>NEW.business_entity_id
          OR v_data#>>'{selectedChannelRef,resourceId}'<>NEW.channel_id
          OR v_data#>>'{selectedEntityRef,resourceId}'<>NEW.business_entity_id
          OR v_data#>>'{caseRef,resourceId}'<>NEW.case_id
          OR (v_data#>>'{caseRef,revision}')::bigint<>NEW.case_revision OR v_data#>>'{caseRef,contentHash}'<>NEW.case_hash
          OR v_data#>>'{runRef,resourceId}'<>NEW.run_id
          OR (v_data#>>'{runRef,revision}')::bigint<>NEW.run_version OR v_data#>>'{runRef,contentHash}'<>NEW.run_hash
        THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='artifact selection does not match exact Case/Run';END IF;
        CASE NEW.artifact_type
          WHEN 'BusinessDossierRevision' THEN SELECT EXISTS(SELECT 1 FROM ecommerce_investigation_business_dossier_revision a WHERE a.org_id=NEW.org_id AND a.project_id=NEW.project_id AND a.artifact_id=NEW.artifact_id AND a.revision=NEW.artifact_revision AND a.content_hash=NEW.artifact_hash AND a.case_id=NEW.case_id AND a.case_revision=NEW.case_revision AND a.run_id=NEW.run_id) INTO v_artifact_exists;
          WHEN 'ProblemMapRevision' THEN SELECT EXISTS(SELECT 1 FROM ecommerce_investigation_problem_map_revision a WHERE a.org_id=NEW.org_id AND a.project_id=NEW.project_id AND a.artifact_id=NEW.artifact_id AND a.revision=NEW.artifact_revision AND a.content_hash=NEW.artifact_hash AND a.case_id=NEW.case_id AND a.case_revision=NEW.case_revision AND a.run_id=NEW.run_id) INTO v_artifact_exists;
          WHEN 'OpportunityMapRevision' THEN SELECT EXISTS(SELECT 1 FROM ecommerce_investigation_opportunity_map_revision a WHERE a.org_id=NEW.org_id AND a.project_id=NEW.project_id AND a.artifact_id=NEW.artifact_id AND a.revision=NEW.artifact_revision AND a.content_hash=NEW.artifact_hash AND a.case_id=NEW.case_id AND a.case_revision=NEW.case_revision AND a.run_id=NEW.run_id) INTO v_artifact_exists;
          WHEN 'SolutionPortfolioRevision' THEN SELECT EXISTS(SELECT 1 FROM ecommerce_investigation_solution_portfolio_revision a WHERE a.org_id=NEW.org_id AND a.project_id=NEW.project_id AND a.artifact_id=NEW.artifact_id AND a.revision=NEW.artifact_revision AND a.content_hash=NEW.artifact_hash AND a.case_id=NEW.case_id AND a.case_revision=NEW.case_revision AND a.run_id=NEW.run_id) INTO v_artifact_exists;
          ELSE v_artifact_exists:=false;
        END CASE;
        IF NOT v_artifact_exists THEN RAISE EXCEPTION USING ERRCODE='BO003',MESSAGE='exact governed artifact revision is required';END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_artifact_binding_validate
      BEFORE INSERT ON ecommerce_investigation_artifact_binding FOR EACH ROW
      EXECUTE FUNCTION ecommerce_investigation_artifact_binding_guard_biw4_005()""")
    op.execute("""CREATE TRIGGER trg_ecommerce_investigation_artifact_binding_immutable
      BEFORE UPDATE OR DELETE ON ecommerce_investigation_artifact_binding FOR EACH ROW
      EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    op.execute("ALTER TABLE ecommerce_investigation_artifact_binding ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ecommerce_investigation_artifact_binding FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_ecommerce_investigation_artifact_binding_biw4_005
      ON ecommerce_investigation_artifact_binding TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("GRANT SELECT ON ecommerce_investigation_artifact_binding TO aos_runtime")
    op.execute("REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON ecommerce_investigation_artifact_binding FROM aos_runtime")


def downgrade() -> None:
    op.execute("""DO $$ BEGIN IF EXISTS(SELECT 1 FROM ecommerce_investigation_artifact_binding LIMIT 1)
      THEN RAISE EXCEPTION 'cannot downgrade biw4_005 with artifact binding authority' USING ERRCODE='55000';END IF;END $$""")
    op.execute("DROP TABLE ecommerce_investigation_artifact_binding")
    op.execute("DROP FUNCTION ecommerce_investigation_artifact_binding_guard_biw4_005()")
