"""Include optional event control in the exact host Receipt journal."""
from alembic import op

revision = 'a0v_058'
down_revision = 'a0v_057'
branch_labels = depends_on = None

_BASE = (
    'ecommerce_growth_investigation_describe', 'ecommerce_growth_case_put',
    'ecommerce_growth_schedule_put', 'ecommerce_growth_schedule_trigger',
    'ecommerce_growth_data_fulfill', 'ecommerce_growth_analysis_advance',
    'ecommerce_growth_review_advance', 'ecommerce_growth_content_generate',
    'ecommerce_growth_content_review',
)
_EVENT = 'ecommerce_growth_event_control'
_SIGNATURE = 'public.ecommerce_growth_runtime_receipt_put_ar2_005(text,text,text,bigint,uuid,uuid,bigint,uuid,bigint,bigint,jsonb,jsonb,text,timestamp with time zone)'


def _change(include_event):
    # Replace only the allow-list tail in the existing function. Its owner,
    # grants, locks, authority checks and Receipt semantics remain unchanged.
    old = "'ecommerce_growth_content_review'"
    new = old + ", 'ecommerce_growth_event_control'"
    before, after = (old, new) if include_event else (new, old)
    op.execute(f"""DO $migration$ DECLARE definition text; BEGIN
      SELECT pg_get_functiondef('{_SIGNATURE}'::regprocedure) INTO definition;
      IF (length(definition)-length(replace(definition,$needle${before}$needle$,'')))
          <>length($needle${before}$needle$)
        THEN RAISE EXCEPTION 'runtime Receipt function definition drifted'; END IF;
      EXECUTE replace(definition,$needle${before}$needle$,$replacement${after}$replacement$);
    END $migration$""")
    allowed = _BASE + ((_EVENT,) if include_event else ())
    literals = ','.join("'" + value + "'" for value in allowed)
    op.execute('ALTER TABLE public.ecommerce_growth_runtime_command_receipt DROP CONSTRAINT ecommerce_growth_runtime_command_receipt_operation_id_check')
    op.execute(f'ALTER TABLE public.ecommerce_growth_runtime_command_receipt ADD CONSTRAINT ecommerce_growth_runtime_command_receipt_operation_id_check CHECK(operation_id IN ({literals}))')


def upgrade():
    _change(True)
    op.execute("REVOKE INSERT,UPDATE,DELETE ON public.ecommerce_growth_runtime_command_receipt FROM aos_runtime")


def downgrade():
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM public.ecommerce_growth_runtime_command_receipt
        WHERE operation_id='ecommerce_growth_event_control') THEN
        RAISE EXCEPTION 'event control runtime Receipts are not empty'; END IF;
    END $$""")
    _change(False)
