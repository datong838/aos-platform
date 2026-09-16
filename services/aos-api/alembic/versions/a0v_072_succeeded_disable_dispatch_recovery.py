"""Recover an omitted ecommerce dispatch fence after runtime disable succeeded."""
from alembic import op

revision = 'a0v_072'
down_revision = 'a0v_071'
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    DO $migration$
    DECLARE definition text;
      source_name text := 'extension_dispatch_lifecycle_fence_ar2_017';
      target_name text := 'extension_dispatch_lifecycle_recover_fence_a0v_072';
      old_runtime text := 'v_runtime.phase<>''fencing''
          OR v_runtime.status<>''running''';
      new_runtime text := 'v_runtime.phase<>''succeeded''
          OR v_runtime.status<>''succeeded''';
      old_revision text := 'v_runtime.expected_binding_revision+1<>v_binding.revision';
      new_revision text := 'v_runtime.expected_binding_revision+2<>v_binding.revision';
      old_state text := 'OR v_binding.observed_state<>''draining''';
      new_state text := 'OR v_binding.desired_state<>''disabled''
          OR v_binding.observed_state<>''unknown''';
    BEGIN
      definition := pg_get_functiondef(to_regprocedure(
        'public.extension_dispatch_lifecycle_fence_ar2_017(uuid,text)'));
      IF definition IS NULL
        OR (length(definition)-length(replace(definition,source_name,'')))/length(source_name) <> 1
        OR (length(definition)-length(replace(definition,old_runtime,'')))/length(old_runtime) <> 1
        OR (length(definition)-length(replace(definition,old_revision,'')))/length(old_revision) <> 1
        OR (length(definition)-length(replace(definition,old_state,'')))/length(old_state) <> 1
      THEN RAISE EXCEPTION 'exact current dispatch fence function required'; END IF;
      definition := replace(definition,source_name,target_name);
      definition := replace(definition,old_runtime,new_runtime);
      definition := replace(definition,old_revision,new_revision);
      definition := replace(definition,old_state,new_state);
      definition := replace(definition,'current runtime disable fence is required',
        'succeeded runtime disable recovery is required');
      EXECUTE definition;
    END $migration$;
    REVOKE ALL ON FUNCTION public.extension_dispatch_lifecycle_recover_fence_a0v_072(uuid,text)
      FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.extension_dispatch_lifecycle_recover_fence_a0v_072(uuid,text)
      TO aos_runtime;
    """)


def downgrade():
    raise RuntimeError('succeeded disable dispatch recovery authority must be retained')
