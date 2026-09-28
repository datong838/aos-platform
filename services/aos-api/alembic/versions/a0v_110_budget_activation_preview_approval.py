"""Immutable tenant-scoped budget activation preview and decision evidence."""

from alembic import op


revision = "a0v_110"
down_revision = "a0v_109"
branch_labels = depends_on = None

TABLES = (
    "aip_budget_activation_preview",
    "aip_budget_activation_decision",
    "aip_budget_activation_revocation",
    "aip_budget_activation_receipt",
)


def _protect(table: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {table}_tenant_a0v_110 ON public.{table} TO aos_runtime
        USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))
        WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
          AND project_id=NULLIF(current_setting('aos.project_id',true),''))"""
    )
    op.execute(
        f"""CREATE TRIGGER {table}_immutable_row BEFORE UPDATE OR DELETE
        ON public.{table} FOR EACH ROW
        EXECUTE FUNCTION public.extension_reject_history_mutation()"""
    )
    op.execute(
        f"""CREATE TRIGGER {table}_immutable_truncate BEFORE TRUNCATE
        ON public.{table} FOR EACH STATEMENT
        EXECUTE FUNCTION public.extension_reject_history_mutation()"""
    )
    op.execute(f"REVOKE ALL ON public.{table} FROM PUBLIC,aos_runtime,aos_app")
    op.execute(f"GRANT SELECT,INSERT ON public.{table} TO aos_runtime")


def upgrade() -> None:
    op.execute("""CREATE TABLE public.aip_budget_activation_preview (
      org_id text NOT NULL,
      project_id text NOT NULL,
      preview_id text NOT NULL,
      budget_id text NOT NULL,
      draft_revision bigint NOT NULL CHECK(draft_revision>=1),
      expected_head_version bigint NOT NULL CHECK(expected_head_version>=1),
      target_revision bigint NOT NULL CHECK(target_revision>=2),
      target_hash text NOT NULL CHECK(target_hash ~ '^[0-9a-f]{64}$'),
      target_payload jsonb NOT NULL CHECK(jsonb_typeof(target_payload)='object'),
      preview_hash text NOT NULL CHECK(preview_hash ~ '^[0-9a-f]{64}$'),
      maker_subject text NOT NULL,
      checker_subject text NOT NULL,
      internal_ledger_checked_at timestamptz NOT NULL,
      external_usage_proven boolean NOT NULL DEFAULT false CHECK(external_usage_proven=false),
      expires_at timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,preview_id),
      CHECK(length(preview_id) BETWEEN 1 AND 200),
      CHECK(length(maker_subject) BETWEEN 1 AND 200),
      CHECK(length(checker_subject) BETWEEN 1 AND 200),
      CHECK(maker_subject<>checker_subject),
      CHECK(expires_at>internal_ledger_checked_at),
      FOREIGN KEY(org_id,project_id,budget_id)
        REFERENCES public.aip_budget_head(org_id,project_id,budget_id)
    )""")
    op.execute("""CREATE TABLE public.aip_budget_activation_decision (
      org_id text NOT NULL,
      project_id text NOT NULL,
      decision_id text NOT NULL,
      preview_id text NOT NULL,
      preview_hash text NOT NULL CHECK(preview_hash ~ '^[0-9a-f]{64}$'),
      target_hash text NOT NULL CHECK(target_hash ~ '^[0-9a-f]{64}$'),
      checker_subject text NOT NULL,
      decision text NOT NULL CHECK(decision IN ('approved','rejected')),
      reason text NOT NULL DEFAULT '',
      expires_at timestamptz NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,decision_id),
      UNIQUE(org_id,project_id,preview_id),
      FOREIGN KEY(org_id,project_id,preview_id)
        REFERENCES public.aip_budget_activation_preview(org_id,project_id,preview_id)
    )""")
    op.execute("""CREATE TABLE public.aip_budget_activation_revocation (
      org_id text NOT NULL,
      project_id text NOT NULL,
      revocation_id text NOT NULL,
      decision_id text NOT NULL,
      actor_subject text NOT NULL,
      reason text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,revocation_id),
      UNIQUE(org_id,project_id,decision_id),
      FOREIGN KEY(org_id,project_id,decision_id)
        REFERENCES public.aip_budget_activation_decision(org_id,project_id,decision_id)
    )""")
    op.execute("""CREATE TABLE public.aip_budget_activation_receipt (
      org_id text NOT NULL,
      project_id text NOT NULL,
      receipt_id text NOT NULL,
      operation text NOT NULL CHECK(operation IN ('preview','decision','revoke')),
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      result_ref jsonb NOT NULL CHECK(jsonb_typeof(result_ref)='object'),
      actor_subject text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,receipt_id),
      UNIQUE(org_id,project_id,operation,idempotency_key)
    )""")
    for table in TABLES:
        _protect(table)
    op.execute("CREATE INDEX aip_budget_activation_preview_budget_idx "
               "ON public.aip_budget_activation_preview(org_id,project_id,budget_id,created_at)")


def downgrade() -> None:
    raise RuntimeError("budget activation authority history is immutable; downgrade is prohibited")
