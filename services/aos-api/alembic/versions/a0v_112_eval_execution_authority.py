"""Default-empty, tenant-scoped Eval issuer, identity, revocation and receipt authority."""

from alembic import op


revision = "a0v_112"
down_revision = "a0v_111"
branch_labels = depends_on = None

_TABLES = (
    "aip_eval_issuer_root",
    "aip_eval_executor_identity",
    "aip_eval_authority_revocation",
    "aip_eval_execution_receipt",
)


def upgrade() -> None:
    op.execute("""CREATE TABLE aip_eval_issuer_root (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      issuer_id TEXT NOT NULL, key_id TEXT NOT NULL,
      purpose TEXT NOT NULL, public_key_base64 TEXT NOT NULL,
      public_key_hash TEXT NOT NULL,
      valid_from TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ NOT NULL,
      owner_ref TEXT NOT NULL, approval_ref JSONB NOT NULL,
      source_hash TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,issuer_id,key_id),
      CHECK (purpose='eval-execution'),
      CHECK (length(public_key_hash)=64 AND length(source_hash)=64),
      CHECK (valid_from<valid_until AND length(owner_ref)>0),
      CHECK (jsonb_typeof(approval_ref)='object' AND approval_ref<>'{}'::jsonb),
      FOREIGN KEY (org_id,project_id) REFERENCES twa_workspace(org_id,project_id)
    )""")
    op.execute("""CREATE TABLE aip_eval_executor_identity (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      identity_id TEXT NOT NULL, purpose TEXT NOT NULL,
      executor_ref JSONB NOT NULL,
      issuer_id TEXT NOT NULL, issuer_key_id TEXT NOT NULL,
      certificate_json JSONB NOT NULL, certificate_hash TEXT NOT NULL,
      public_key_base64 TEXT NOT NULL, public_key_hash TEXT NOT NULL,
      valid_from TIMESTAMPTZ NOT NULL, valid_until TIMESTAMPTZ NOT NULL,
      owner_ref TEXT NOT NULL, approval_ref JSONB NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,identity_id),
      UNIQUE (org_id,project_id,identity_id,purpose,certificate_hash),
      UNIQUE (org_id,project_id,public_key_hash),
      CHECK (purpose IN ('target','judge')),
      CHECK (jsonb_typeof(executor_ref)='object' AND jsonb_typeof(certificate_json)='object'),
      CHECK (length(certificate_hash)=64 AND length(public_key_hash)=64),
      CHECK (valid_from<valid_until AND length(owner_ref)>0),
      CHECK (jsonb_typeof(approval_ref)='object' AND approval_ref<>'{}'::jsonb),
      FOREIGN KEY (org_id,project_id,issuer_id,issuer_key_id)
        REFERENCES aip_eval_issuer_root(org_id,project_id,issuer_id,key_id)
    )""")
    op.execute("""CREATE TABLE aip_eval_authority_revocation (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, event_id TEXT NOT NULL,
      identity_id TEXT, issuer_id TEXT, issuer_key_id TEXT,
      revoked_at TIMESTAMPTZ NOT NULL, owner_ref TEXT NOT NULL,
      approval_ref JSONB NOT NULL, reason_hash TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,event_id),
      CHECK ((identity_id IS NOT NULL AND issuer_id IS NULL AND issuer_key_id IS NULL)
          OR (identity_id IS NULL AND issuer_id IS NOT NULL AND issuer_key_id IS NOT NULL)),
      CHECK (length(owner_ref)>0 AND length(reason_hash)=64),
      CHECK (jsonb_typeof(approval_ref)='object' AND approval_ref<>'{}'::jsonb),
      FOREIGN KEY (org_id,project_id,identity_id)
        REFERENCES aip_eval_executor_identity(org_id,project_id,identity_id),
      FOREIGN KEY (org_id,project_id,issuer_id,issuer_key_id)
        REFERENCES aip_eval_issuer_root(org_id,project_id,issuer_id,key_id)
    )""")
    op.execute("""CREATE UNIQUE INDEX aip_eval_revoked_identity_once
      ON aip_eval_authority_revocation(org_id,project_id,identity_id)
      WHERE identity_id IS NOT NULL""")
    op.execute("""CREATE UNIQUE INDEX aip_eval_revoked_root_once
      ON aip_eval_authority_revocation(org_id,project_id,issuer_id,issuer_key_id)
      WHERE issuer_id IS NOT NULL""")
    op.execute("""CREATE TABLE aip_eval_execution_receipt (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL,
      receipt_id TEXT NOT NULL, run_id TEXT NOT NULL,
      case_id TEXT NOT NULL, purpose TEXT NOT NULL,
      identity_id TEXT NOT NULL, certificate_hash TEXT NOT NULL,
      suite_ref JSONB NOT NULL, executor_ref JSONB NOT NULL,
      claim_hash TEXT NOT NULL, input_hash TEXT NOT NULL,
      output_hash TEXT NOT NULL, actual_hash TEXT, expected_hash TEXT,
      passed BOOLEAN, detail_code TEXT,
      occurred_at TIMESTAMPTZ NOT NULL, signature_base64 TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      PRIMARY KEY (org_id,project_id,receipt_id),
      UNIQUE (org_id,project_id,run_id,case_id,purpose),
      CHECK (purpose IN ('target','judge')),
      CHECK (length(receipt_id)=64 AND length(certificate_hash)=64
         AND length(claim_hash)=64 AND length(input_hash)=64 AND length(output_hash)=64),
      CHECK (actual_hash IS NULL OR length(actual_hash)=64),
      CHECK (expected_hash IS NULL OR length(expected_hash)=64),
      CHECK (jsonb_typeof(suite_ref)='object' AND jsonb_typeof(executor_ref)='object'),
      CHECK (length(signature_base64)>0),
      CHECK ((purpose='target' AND actual_hash IS NULL AND expected_hash IS NULL
              AND passed IS NULL AND detail_code IS NULL)
          OR (purpose='judge' AND actual_hash IS NOT NULL AND passed IS NOT NULL
              AND detail_code IS NOT NULL AND length(detail_code)>0)),
      FOREIGN KEY (org_id,project_id,run_id)
        REFERENCES aip_eval_run(org_id,project_id,run_id),
      FOREIGN KEY (org_id,project_id,identity_id,purpose,certificate_hash)
        REFERENCES aip_eval_executor_identity(org_id,project_id,identity_id,purpose,certificate_hash)
    )""")
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""CREATE POLICY tenant_scope_{table}_a0v112 ON {table}
          TO aos_runtime
          USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
             AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
             AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"""CREATE TRIGGER trg_{table}_append_only
          BEFORE UPDATE OR DELETE ON {table}
          FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()""")
        op.execute(f"""CREATE TRIGGER trg_{table}_truncate_guard
          BEFORE TRUNCATE ON {table}
          FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()""")
        op.execute(f"REVOKE ALL ON {table} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON {table} TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("Eval execution authority evidence may not be silently removed")
