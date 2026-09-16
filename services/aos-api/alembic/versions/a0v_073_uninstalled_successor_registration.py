"""Allow successor registration after a fully proven predecessor uninstall."""
from alembic import op

revision = 'a0v_073'
down_revision = 'a0v_072'
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    DO $a0v073$
    DECLARE
      v_definition text;
      v_before text := $before$v_old_binding.desired_state<>'disabled' OR v_old_binding.observed_state<>'unknown'$before$;
      v_after text := $after$
NOT (
          (v_old_binding.desired_state='disabled' AND v_old_binding.observed_state='unknown')
          OR (v_old_binding.desired_state='uninstalled' AND v_old_binding.observed_state='stopped'
            AND EXISTS(
              SELECT 1 FROM public.bundle_installation i
              JOIN public.bundle_installation_revision r
                ON r.org_id=i.org_id AND r.project_id=i.project_id
               AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
              WHERE i.org_id=v_org AND i.project_id=v_project
                AND i.installation_id=v_activation.target_installation_id
                AND i.active_revision IS NULL AND r.state='uninstalled')))$after$;
    BEGIN
      SELECT pg_get_functiondef(
        'public.extension_dispatch_successor_register_a0v_056(jsonb,text)'::regprocedure)
        INTO v_definition;
      IF length(v_definition)-length(replace(v_definition,v_before,''))
           IS DISTINCT FROM length(v_before)
      THEN RAISE EXCEPTION 'a0v056 successor source differs'; END IF;
      EXECUTE replace(v_definition,v_before,v_after);
    END
    $a0v073$;
    COMMENT ON FUNCTION public.extension_dispatch_successor_register_a0v_056(jsonb,text)
      IS 'a0v073: exact detached predecessor may remain disabled or be formally uninstalled';
    """)


def downgrade():
    raise RuntimeError('uninstalled successor registration history must be retained')
