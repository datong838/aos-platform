"""Append-only new-purpose holds. A hold grants no execution authority."""


def judge_budget_statements():
    statements = ["""CREATE TABLE aip_model_judge_budget_reservation (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, reservation_id UUID NOT NULL,
      purpose TEXT NOT NULL CHECK (purpose='model-judge-call'),
      request_id TEXT NOT NULL, request_hash TEXT NOT NULL,
      proposal_id TEXT NOT NULL, proposal_hash TEXT NOT NULL,
      approval_event_id TEXT NOT NULL, approval_ref JSONB NOT NULL,
      budget_policy_ref JSONB NOT NULL, budget_revision_ref JSONB NOT NULL,
      price_ref JSONB NOT NULL, currency TEXT NOT NULL CHECK (currency='CNY'),
      upper_bound_minor BIGINT NOT NULL CHECK (upper_bound_minor BETWEEN 1 AND 100000000),
      state TEXT NOT NULL CHECK (state='held'),
      content_hash TEXT NOT NULL CHECK (content_hash ~ '^sha256:[0-9a-f]{64}$'),
      created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY (org_id,project_id,reservation_id),
      UNIQUE (org_id,project_id,request_id), UNIQUE (org_id,project_id,approval_event_id),
      FOREIGN KEY (org_id,project_id,approval_event_id)
        REFERENCES aip_action_approval_event(org_id,project_id,approval_event_id),
      CHECK (request_hash ~ '^[0-9a-f]{64}$' AND proposal_hash ~ '^[0-9a-f]{64}$'),
      CHECK (jsonb_typeof(approval_ref)='object' AND jsonb_typeof(budget_policy_ref)='object'
        AND jsonb_typeof(budget_revision_ref)='object' AND jsonb_typeof(price_ref)='object')
    )""", """CREATE TABLE aip_model_judge_budget_reservation_bucket (
      org_id TEXT NOT NULL, project_id TEXT NOT NULL, reservation_id UUID NOT NULL,
      bucket_kind TEXT NOT NULL CHECK (bucket_kind IN ('task','daily','pilot')),
      account_id TEXT NOT NULL, period_start TIMESTAMPTZ NOT NULL,
      currency TEXT NOT NULL CHECK (currency='CNY'),
      reserved_minor BIGINT NOT NULL CHECK (reserved_minor BETWEEN 1 AND 100000000),
      PRIMARY KEY (org_id,project_id,reservation_id,bucket_kind),
      FOREIGN KEY (org_id,project_id,reservation_id)
        REFERENCES aip_model_judge_budget_reservation(org_id,project_id,reservation_id),
      FOREIGN KEY (org_id,project_id,bucket_kind,account_id,period_start,currency)
        REFERENCES aip_budget_bucket(org_id,project_id,bucket_kind,account_id,period_start,currency)
    )"""]
    for table in ('aip_model_judge_budget_reservation', 'aip_model_judge_budget_reservation_bucket'):
        statements.extend([
            f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY',
            f"""CREATE POLICY tenant_scope_{table}_a0v159 ON {table} TO aos_runtime
              USING (org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))
              WITH CHECK (org_id=NULLIF(current_setting('aos.org_id',true),'')
                AND project_id=NULLIF(current_setting('aos.project_id',true),''))""",
            f'CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION guard_aip4_append_only()',
            f'CREATE TRIGGER trg_{table}_truncate_guard BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION guard_aip4_append_only()',
            f'REVOKE ALL ON {table} FROM PUBLIC,aos_runtime',
            f'GRANT SELECT,INSERT ON {table} TO aos_runtime',
        ])
    return tuple(statements)
