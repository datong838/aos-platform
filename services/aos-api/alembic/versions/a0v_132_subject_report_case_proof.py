"""Bind each subject-review case to one exact persisted Eval Report."""
from alembic import op

revision = 'a0v_132'
down_revision = 'a0v_131'
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE UNIQUE INDEX aip_eval_subject_receipt_report_fk_a0v132
        ON aip_eval_subject_receipt
        (org_id,project_id,eval_run_id,case_id,envelope_hash,purpose,receipt_id,claim_hash)""")
    op.execute("""CREATE TABLE aip_eval_subject_case_proof (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        eval_run_id TEXT NOT NULL, case_id TEXT NOT NULL,
        envelope_hash TEXT NOT NULL,
        report_id TEXT NOT NULL, report_revision BIGINT NOT NULL,
        source_purpose TEXT NOT NULL DEFAULT 'source-witness',
        source_receipt_id TEXT NOT NULL, source_claim_hash TEXT NOT NULL,
        judge_purpose TEXT NOT NULL DEFAULT 'judge',
        judge_receipt_id TEXT NOT NULL, judge_claim_hash TEXT NOT NULL,
        verified_at TIMESTAMPTZ NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (org_id,project_id,eval_run_id,case_id),
        CHECK (source_purpose='source-witness' AND judge_purpose='judge'),
        CHECK (source_receipt_id<>judge_receipt_id
           AND source_claim_hash<>judge_claim_hash),
        CHECK (report_revision>=1 AND verified_at<=created_at),
        CHECK (length(envelope_hash)=64 AND length(source_receipt_id)=64
           AND length(source_claim_hash)=64 AND length(judge_receipt_id)=64
           AND length(judge_claim_hash)=64),
        FOREIGN KEY (org_id,project_id,eval_run_id,report_id,report_revision)
           REFERENCES aip_eval_report_revision(org_id,project_id,run_id,report_id,revision),
        FOREIGN KEY (org_id,project_id,eval_run_id,case_id,envelope_hash,
                     source_purpose,source_receipt_id,source_claim_hash)
           REFERENCES aip_eval_subject_receipt(org_id,project_id,eval_run_id,
                     case_id,envelope_hash,purpose,receipt_id,claim_hash),
        FOREIGN KEY (org_id,project_id,eval_run_id,case_id,envelope_hash,
                     judge_purpose,judge_receipt_id,judge_claim_hash)
           REFERENCES aip_eval_subject_receipt(org_id,project_id,eval_run_id,
                     case_id,envelope_hash,purpose,receipt_id,claim_hash)
    )""")
    op.execute('ALTER TABLE aip_eval_subject_case_proof ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE aip_eval_subject_case_proof FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY tenant_scope_aip_eval_subject_case_proof_a0v132
        ON aip_eval_subject_case_proof TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER trg_aip_eval_subject_case_proof_append_only
        BEFORE UPDATE OR DELETE ON aip_eval_subject_case_proof
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER trg_aip_eval_subject_case_proof_truncate_guard
        BEFORE TRUNCATE ON aip_eval_subject_case_proof
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute('REVOKE ALL ON aip_eval_subject_case_proof FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT ON aip_eval_subject_case_proof TO aos_runtime')


def downgrade() -> None:
    raise RuntimeError('subject-review report proof may not be silently removed')
