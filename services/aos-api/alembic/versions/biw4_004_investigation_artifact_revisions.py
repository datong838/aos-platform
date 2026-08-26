"""Add governed investigation artifact revision schema. Revision ID: biw4_004."""

from collections.abc import Sequence

from alembic import op


revision: str = "biw4_004"
down_revision: str | Sequence[str] | None = "biw4_003"
branch_labels = depends_on = None

ARTIFACT_TABLES = {
    "BusinessDossierRevision": "ecommerce_investigation_business_dossier_revision",
    "ProblemMapRevision": "ecommerce_investigation_problem_map_revision",
    "OpportunityMapRevision": "ecommerce_investigation_opportunity_map_revision",
    "SolutionPortfolioRevision": "ecommerce_investigation_solution_portfolio_revision",
}


def upgrade() -> None:
    op.execute("""CREATE UNIQUE INDEX uq_ecommerce_investigation_case_exact_biw4_004
      ON ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,content_hash)""")
    op.execute("""CREATE UNIQUE INDEX uq_ecommerce_investigation_run_exact_case_biw4_004
      ON ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision)""")
    op.execute("""CREATE FUNCTION ecommerce_investigation_artifact_inputs_valid_biw4_004(
      p_artifact_type text,p_refs jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
      WITH refs AS (SELECT value AS ref FROM jsonb_array_elements(p_refs)), types AS (
        SELECT ref->>'resourceType' AS kind FROM refs
      ) SELECT
        jsonb_typeof(p_refs)='array' AND jsonb_array_length(p_refs) BETWEEN 1 AND 200
        AND NOT EXISTS(SELECT 1 FROM refs WHERE NOT ecommerce_investigation_exact_ref_valid_biw4_001(ref,ref->>'resourceType'))
        AND (SELECT count(*) FROM refs)=(SELECT count(DISTINCT ref) FROM refs)
        AND NOT EXISTS(SELECT 1 FROM types WHERE kind <> ALL(
          CASE p_artifact_type
            WHEN 'BusinessDossierRevision' THEN ARRAY['DataRequirementRevision','DataFulfillmentReceipt','SourceReadinessEnvelope','OntologySnapshotRevision','EvidenceBundleRevision']
            WHEN 'ProblemMapRevision' THEN ARRAY['BusinessDossierRevision','EvidenceBundleRevision','InsightRevision']
            WHEN 'OpportunityMapRevision' THEN ARRAY['BusinessDossierRevision','ProblemMapRevision','EvidenceBundleRevision','InsightRevision','DecisionSummaryRevision']
            WHEN 'SolutionPortfolioRevision' THEN ARRAY['ProblemMapRevision','OpportunityMapRevision','EvidenceBundleRevision','InsightRevision','DecisionSummaryRevision']
            ELSE ARRAY[]::text[] END))
        AND NOT EXISTS(SELECT 1 FROM refs WHERE ref->>'resourceType' IN('DataFulfillmentReceipt','SourceReadinessEnvelope')
          AND COALESCE(BTRIM(ref->>'receiptId'),'')='')
        AND CASE p_artifact_type
          WHEN 'BusinessDossierRevision' THEN EXISTS(SELECT 1 FROM types WHERE kind='DataRequirementRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='SourceReadinessEnvelope')
          WHEN 'ProblemMapRevision' THEN EXISTS(SELECT 1 FROM types WHERE kind='BusinessDossierRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='EvidenceBundleRevision')
          WHEN 'OpportunityMapRevision' THEN EXISTS(SELECT 1 FROM types WHERE kind='BusinessDossierRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='ProblemMapRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='EvidenceBundleRevision')
          WHEN 'SolutionPortfolioRevision' THEN EXISTS(SELECT 1 FROM types WHERE kind='ProblemMapRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='OpportunityMapRevision') AND EXISTS(SELECT 1 FROM types WHERE kind='DecisionSummaryRevision')
          ELSE false END $$""")
    op.execute("""CREATE TABLE ecommerce_investigation_artifact_head(
      org_id TEXT NOT NULL,project_id TEXT NOT NULL,artifact_type TEXT NOT NULL,artifact_id TEXT NOT NULL,
      current_revision BIGINT NOT NULL,current_content_hash TEXT NOT NULL,version BIGINT NOT NULL,
      case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,run_id TEXT NOT NULL,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY(org_id,project_id,artifact_type,artifact_id),
      CHECK(artifact_type IN('BusinessDossierRevision','ProblemMapRevision','OpportunityMapRevision','SolutionPortfolioRevision')),
      CHECK(current_revision>=1),CHECK(version=current_revision),CHECK(current_content_hash ~ '^sha256:[0-9a-f]{64}$'))""")
    for artifact_type, table in ARTIFACT_TABLES.items():
        op.execute(f"""CREATE TABLE {table}(
          org_id TEXT NOT NULL,project_id TEXT NOT NULL,artifact_id TEXT NOT NULL,revision BIGINT NOT NULL,
          version BIGINT NOT NULL,prior_revision BIGINT,prior_content_hash TEXT,content_hash TEXT NOT NULL,
          case_id TEXT NOT NULL,case_revision BIGINT NOT NULL,case_content_hash TEXT NOT NULL,
          run_id TEXT NOT NULL,run_version BIGINT NOT NULL,run_content_hash TEXT NOT NULL,
          input_refs JSONB NOT NULL,created_by TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL,
          PRIMARY KEY(org_id,project_id,artifact_id,revision),
          UNIQUE(org_id,project_id,artifact_id,revision,content_hash),
          FOREIGN KEY(org_id,project_id,case_id,case_revision,case_content_hash)
            REFERENCES ecommerce_investigation_case_revision(org_id,project_id,case_id,revision,content_hash),
          FOREIGN KEY(org_id,project_id,run_id,run_version,run_content_hash,case_id,case_revision)
            REFERENCES ecommerce_investigation_run(org_id,project_id,run_id,version,content_hash,case_id,case_revision),
          FOREIGN KEY(org_id,project_id,artifact_id,prior_revision,prior_content_hash)
            REFERENCES {table}(org_id,project_id,artifact_id,revision,content_hash),
          CHECK(revision>=1),CHECK(version=revision),
          CHECK((revision=1 AND prior_revision IS NULL AND prior_content_hash IS NULL)
            OR (revision>1 AND prior_revision=revision-1 AND prior_content_hash ~ '^sha256:[0-9a-f]{{64}}$')),
          CHECK(content_hash ~ '^sha256:[0-9a-f]{{64}}$'),CHECK(case_content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          CHECK(run_version=1),CHECK(run_content_hash ~ '^sha256:[0-9a-f]{{64}}$'),
          CHECK(ecommerce_investigation_artifact_inputs_valid_biw4_004('{artifact_type}',input_refs)))""")
        op.execute(f"""CREATE TRIGGER trg_{table}_immutable BEFORE UPDATE OR DELETE ON {table}
          FOR EACH ROW EXECUTE FUNCTION guard_ecommerce_investigation_run_biw4_002()""")
    for table in ("ecommerce_investigation_artifact_head", *ARTIFACT_TABLES.values()):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_biw4_004 ON {table} TO aos_runtime
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")
        op.execute(f"REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON {table} FROM aos_runtime")


def downgrade() -> None:
    tables = ("ecommerce_investigation_artifact_head", *ARTIFACT_TABLES.values())
    predicates = " OR ".join(f"EXISTS(SELECT 1 FROM {table} LIMIT 1)" for table in tables)
    op.execute(f"""DO $$ BEGIN IF {predicates}
      THEN RAISE EXCEPTION 'cannot downgrade biw4_004 with governed artifact authority' USING ERRCODE='55000';END IF;END $$""")
    for table in reversed(ARTIFACT_TABLES.values()):
        op.execute(f"DROP TABLE {table}")
    op.execute("DROP TABLE ecommerce_investigation_artifact_head")
    op.execute("DROP FUNCTION ecommerce_investigation_artifact_inputs_valid_biw4_004(text,jsonb)")
    op.execute("DROP INDEX uq_ecommerce_investigation_run_exact_case_biw4_004")
    op.execute("DROP INDEX uq_ecommerce_investigation_case_exact_biw4_004")
