"""Retire the same generation after a host stop advances its fence epoch."""
from alembic import op

revision = 'a0v_055'
down_revision = 'a0v_054'
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    DO $migration$
    DECLARE signature text; definition text;
      old_epoch text := 'v_binding.execution_epoch<>v_activation.target_execution_epoch+1';
      old_occurrence text := 'AND o.execution_epoch=v_activation.target_execution_epoch AND o.status=''claimed''';
      old_attempt text := 'AND o.execution_epoch=v_activation.target_execution_epoch AND a.status=''claimed''';
    BEGIN
      FOREACH signature IN ARRAY ARRAY[
        'public.extension_dispatch_lifecycle_fence_ar2_017(uuid,text)',
        'public.extension_dispatch_lifecycle_detach_ar2_017(uuid,text)']
      LOOP
        definition := pg_get_functiondef(to_regprocedure(signature));
        IF definition IS NULL OR
          (length(definition)-length(replace(definition,old_epoch,'')))/length(old_epoch) <> 1
        THEN RAISE EXCEPTION 'exact ar2_017 epoch predicate required'; END IF;
        definition := replace(definition,old_epoch,
          'v_binding.execution_epoch<=v_activation.target_execution_epoch');
        IF signature LIKE '%detach%' THEN
          IF (length(definition)-length(replace(definition,old_occurrence,'')))/length(old_occurrence) <> 1
            OR (length(definition)-length(replace(definition,old_attempt,'')))/length(old_attempt) <> 1
          THEN RAISE EXCEPTION 'exact ar2_017 drain predicates required'; END IF;
          definition := replace(definition,old_occurrence,'AND o.status=''claimed''');
          definition := replace(definition,old_attempt,'AND a.status IN (''claimed'',''unknown'')');
        END IF;
        EXECUTE definition;
      END LOOP;
    END $migration$;
    """)


def downgrade():
    raise RuntimeError('retirement authority and history must be retained')
