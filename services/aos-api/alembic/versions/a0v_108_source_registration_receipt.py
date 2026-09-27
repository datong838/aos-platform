"""Immutable tenant-scoped source registration outcome, without connection secrets."""

from alembic import op


revision = "a0v_108"
down_revision = "a0v_107"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE public.source_registration_receipt (
      org_id text NOT NULL,
      project_id text NOT NULL,
      idempotency_key text NOT NULL CHECK(length(idempotency_key) BETWEEN 1 AND 160),
      request_hash text NOT NULL CHECK(request_hash ~ '^[0-9a-f]{64}$'),
      source_id text NOT NULL,
      configuration_revision uuid NOT NULL,
      response_metadata jsonb NOT NULL CHECK(jsonb_typeof(response_metadata)='object'),
      recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
      PRIMARY KEY(org_id,project_id,idempotency_key),
      FOREIGN KEY(org_id,project_id,source_id,configuration_revision)
        REFERENCES public.data_source_configuration_revision(org_id,project_id,source_id,revision_id)
    )""")
    op.execute("ALTER TABLE public.source_registration_receipt ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.source_registration_receipt FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY source_registration_receipt_tenant_a0v_108
      ON public.source_registration_receipt TO aos_runtime
      USING(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))
      WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'')
        AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE TRIGGER source_registration_receipt_immutable_row
      BEFORE UPDATE OR DELETE ON public.source_registration_receipt
      FOR EACH ROW EXECUTE FUNCTION public.extension_reject_history_mutation()""")
    op.execute("""CREATE TRIGGER source_registration_receipt_immutable_truncate
      BEFORE TRUNCATE ON public.source_registration_receipt
      FOR EACH STATEMENT EXECUTE FUNCTION public.extension_reject_history_mutation()""")
    op.execute("REVOKE ALL ON public.source_registration_receipt FROM PUBLIC,aos_runtime,aos_app")
    op.execute("GRANT SELECT,INSERT ON public.source_registration_receipt TO aos_runtime")


def downgrade() -> None:
    raise RuntimeError("source registration receipts are immutable; downgrade is prohibited")
