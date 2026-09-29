"""Bind one Skill Eval report case to exact Target and Judge persisted receipts."""

from alembic import op


revision = "a0v_114"
down_revision = "a0v_113"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE UNIQUE INDEX aip_eval_report_run_exact_a0v114
      ON aip_eval_report_revision(org_id,project_id,run_id,report_id,revision)""")
    op.execute("""CREATE UNIQUE INDEX aip_eval_receipt_case_exact_a0v114
      ON aip_eval_execution_receipt
      (org_id,project_id,run_id,case_id,purpose,receipt_id,claim_hash)""")
    op.execute("""CREATE TABLE aip_eval_case_execution_proof (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      run_id TEXT NOT NULL, case_id TEXT NOT NULL,
      report_id TEXT NOT NULL, report_revision BIGINT NOT NULL,
      target_purpose TEXT NOT NULL DEFAULT 'target', target_receipt_id TEXT NOT NULL,
      target_claim_hash TEXT NOT NULL,
      judge_purpose TEXT NOT NULL DEFAULT 'judge', judge_receipt_id TEXT NOT NULL,
      judge_claim_hash TEXT NOT NULL,
      verified_at TIMESTAMPTZ NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,run_id,case_id),
      CHECK (target_purpose='target' AND judge_purpose='judge'),
      CHECK (target_receipt_id<>judge_receipt_id),
      CHECK (length(target_receipt_id)=64 AND length(judge_receipt_id)=64
         AND length(target_claim_hash)=64 AND length(judge_claim_hash)=64),
      CHECK (report_revision>=1 AND verified_at<=created_at),
      FOREIGN KEY (org_id,project_id,run_id,report_id,report_revision)
        REFERENCES aip_eval_report_revision
        (org_id,project_id,run_id,report_id,revision),
      FOREIGN KEY (org_id,project_id,run_id,case_id,target_purpose,
                   target_receipt_id,target_claim_hash)
        REFERENCES aip_eval_execution_receipt
        (org_id,project_id,run_id,case_id,purpose,receipt_id,claim_hash),
      FOREIGN KEY (org_id,project_id,run_id,case_id,judge_purpose,
                   judge_receipt_id,judge_claim_hash)
        REFERENCES aip_eval_execution_receipt
        (org_id,project_id,run_id,case_id,purpose,receipt_id,claim_hash)
    )""")
    op.execute("ALTER TABLE aip_eval_case_execution_proof ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE aip_eval_case_execution_proof FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_scope_aip_eval_case_proof_a0v114
      ON aip_eval_case_execution_proof TO aos_runtime
      USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
         AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER trg_aip_eval_case_proof_append_only
      BEFORE UPDATE OR DELETE ON aip_eval_case_execution_proof
      FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER trg_aip_eval_case_proof_truncate_guard
      BEFORE TRUNCATE ON aip_eval_case_execution_proof
      FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("REVOKE ALL ON aip_eval_case_execution_proof FROM PUBLIC,aos_runtime")
    op.execute("GRANT SELECT,INSERT ON aip_eval_case_execution_proof TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("Skill Eval execution proof must not be silently removed")
