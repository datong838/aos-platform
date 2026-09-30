"""Persist unapproved first-budget cost proposals, never activation authority."""
from alembic import op

revision = 'a0v_124'
down_revision = 'a0v_123'
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE public.aip_budget_cost_proposal (
      org_id text NOT NULL, project_id text NOT NULL, proposal_id text NOT NULL,
      budget_id text NOT NULL, maker_subject text NOT NULL, checker_subject text NOT NULL,
      proposal_hash text NOT NULL CHECK(proposal_hash ~ '^[0-9a-f]{64}$'),
      payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),
      status text NOT NULL DEFAULT 'proposed' CHECK(status='proposed'),
      source_verification text NOT NULL DEFAULT 'pending' CHECK(source_verification='pending'),
      activation_eligible boolean NOT NULL DEFAULT false CHECK(activation_eligible=false),
      created_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
      PRIMARY KEY(org_id,project_id,proposal_id),
      CHECK(maker_subject<>checker_subject AND expires_at>created_at),
      FOREIGN KEY(org_id,project_id,budget_id) REFERENCES public.aip_budget_head(org_id,project_id,budget_id)
    )""")
    op.execute("""CREATE TABLE public.aip_budget_cost_proposal_receipt (
      org_id text NOT NULL, project_id text NOT NULL, actor_subject text NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      proposal_id text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,actor_subject,idempotency_key),
      FOREIGN KEY(org_id,project_id,proposal_id) REFERENCES public.aip_budget_cost_proposal(org_id,project_id,proposal_id)
    )""")
    for table in ('aip_budget_cost_proposal', 'aip_budget_cost_proposal_receipt'):
        op.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f"""CREATE POLICY {table}_tenant ON public.{table} TO aos_runtime
            USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))
            WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
              AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
        op.execute(f"""CREATE TRIGGER {table}_immutable_row BEFORE UPDATE OR DELETE ON public.{table}
            FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation()""")
        op.execute(f"""CREATE TRIGGER {table}_immutable_truncate BEFORE TRUNCATE ON public.{table}
            FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation()""")
        op.execute(f'REVOKE ALL ON public.{table} FROM PUBLIC,aos_runtime,aos_app')
        op.execute(f'GRANT SELECT,INSERT ON public.{table} TO aos_runtime')


def downgrade():
    raise RuntimeError('budget cost proposal history is immutable; downgrade is prohibited')
