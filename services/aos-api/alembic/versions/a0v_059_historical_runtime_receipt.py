"""Historical Receipts must survive removal of optional current dispatch rows."""
from alembic import op
revision='a0v_059'
down_revision='a0v_058'
branch_labels=depends_on=None
NAME='ecommerce_growth_runtime_comm_org_id_project_id_operation__fkey'


def upgrade():
    op.execute(f"""DO $$ DECLARE matches int; BEGIN
      SELECT count(*) INTO matches FROM pg_constraint
       WHERE conrelid='public.ecommerce_growth_runtime_command_receipt'::regclass
       AND confrelid='public.extension_operation_dispatch_binding'::regclass
       AND contype='f' AND conname='{NAME}'
       AND pg_get_constraintdef(oid)='FOREIGN KEY (org_id, project_id, operation_id) REFERENCES extension_operation_dispatch_binding(org_id, project_id, operation_id)';
      IF matches<>1 THEN RAISE EXCEPTION 'historical Receipt current-dispatch FK drifted'; END IF;
    END $$""")
    op.execute(f'ALTER TABLE public.ecommerce_growth_runtime_command_receipt DROP CONSTRAINT {NAME}')


def downgrade():
    # Validates every historical row; deliberately fails once an old optional
    # dispatch has been removed. Never discard or rewrite the audit history.
    op.execute(f'''ALTER TABLE public.ecommerce_growth_runtime_command_receipt ADD CONSTRAINT {NAME}
      FOREIGN KEY(org_id,project_id,operation_id) REFERENCES public.extension_operation_dispatch_binding(org_id,project_id,operation_id)''')
