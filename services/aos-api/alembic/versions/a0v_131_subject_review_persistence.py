"""Add subject-review signing identities and immutable receipts, default closed."""
from alembic import op

revision = 'a0v_131'
down_revision = 'a0v_130'
branch_labels = depends_on = None


def upgrade() -> None:
    # Preserve existing rows, ACL and reader gates. Their v1 consumers still
    # require eval-execution/target/judge and cannot accept new proof purposes.
    op.execute('ALTER TABLE aip_eval_issuer_root DROP CONSTRAINT aip_eval_issuer_root_purpose_check')
    op.execute("""ALTER TABLE aip_eval_issuer_root ADD CONSTRAINT aip_eval_issuer_root_purpose_check
        CHECK (purpose IN ('eval-execution','subject-review'))""")
    op.execute('ALTER TABLE aip_eval_executor_identity DROP CONSTRAINT aip_eval_executor_identity_purpose_check')
    op.execute("""ALTER TABLE aip_eval_executor_identity ADD CONSTRAINT aip_eval_executor_identity_purpose_check
        CHECK (purpose IN ('target','judge','source-witness'))""")
    op.execute("""CREATE TABLE aip_eval_subject_receipt (
        org_id TEXT NOT NULL, project_id TEXT NOT NULL,
        receipt_id TEXT NOT NULL, eval_run_id TEXT NOT NULL,
        case_id TEXT NOT NULL, envelope_hash TEXT NOT NULL,
        purpose TEXT NOT NULL, identity_id TEXT NOT NULL,
        certificate_hash TEXT NOT NULL, claim_hash TEXT NOT NULL,
        source_purpose TEXT NOT NULL DEFAULT 'source-witness',
        source_receipt_hash TEXT, structure_passed BOOLEAN, detail_code TEXT,
        occurred_at TIMESTAMPTZ NOT NULL, signature_base64 TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (org_id,project_id,receipt_id),
        UNIQUE (org_id,project_id,eval_run_id,case_id,envelope_hash,purpose),
        UNIQUE (org_id,project_id,eval_run_id,case_id,envelope_hash,purpose,claim_hash),
        CHECK (purpose IN ('source-witness','judge') AND source_purpose='source-witness'),
        CHECK (length(receipt_id)=64 AND length(envelope_hash)=64
           AND length(certificate_hash)=64 AND length(claim_hash)=64),
        CHECK (source_receipt_hash IS NULL OR length(source_receipt_hash)=64),
        CHECK (length(signature_base64)>0),
        CHECK ((purpose='source-witness' AND source_receipt_hash IS NULL
                AND structure_passed IS NULL AND detail_code IS NULL)
           OR (purpose='judge' AND source_receipt_hash IS NOT NULL
                AND structure_passed IS NOT NULL AND detail_code IS NOT NULL
                AND length(detail_code)>0)),
        FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id),
        FOREIGN KEY (org_id,project_id,eval_run_id)
           REFERENCES aip_eval_run(org_id,project_id,run_id),
        FOREIGN KEY (org_id,project_id,identity_id,purpose,certificate_hash)
           REFERENCES aip_eval_executor_identity(org_id,project_id,identity_id,purpose,certificate_hash),
        FOREIGN KEY (org_id,project_id,eval_run_id,case_id,envelope_hash,
                     source_purpose,source_receipt_hash)
           REFERENCES aip_eval_subject_receipt(org_id,project_id,eval_run_id,case_id,
                                                envelope_hash,purpose,claim_hash)
    )""")
    op.execute('ALTER TABLE aip_eval_subject_receipt ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE aip_eval_subject_receipt FORCE ROW LEVEL SECURITY')
    op.execute("""CREATE POLICY tenant_scope_aip_eval_subject_receipt_a0v131
        ON aip_eval_subject_receipt TO aos_runtime
        USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
           AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER trg_aip_eval_subject_receipt_append_only
        BEFORE UPDATE OR DELETE ON aip_eval_subject_receipt
        FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute("""CREATE TRIGGER trg_aip_eval_subject_receipt_truncate_guard
        BEFORE TRUNCATE ON aip_eval_subject_receipt
        FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
    op.execute('REVOKE ALL ON aip_eval_subject_receipt FROM PUBLIC,aos_runtime')
    op.execute('GRANT SELECT ON aip_eval_subject_receipt TO aos_runtime')


def downgrade() -> None:
    raise RuntimeError('subject-review evidence may not be silently removed')
