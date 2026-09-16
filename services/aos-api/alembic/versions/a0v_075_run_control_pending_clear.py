"""Keep Run head physical fields aligned when control returns to PREPARING."""
from alembic import op


revision = "a0v_075"
down_revision = "a0v_074"
branch_labels = depends_on = None


def upgrade():
    op.execute(r"""
    DO $migration$
    DECLARE definition text;
      old_update text := $body$UPDATE ecommerce_investigation_run_state_head SET current_version=p_expected_version+1,
          lifecycle='PREPARING',control=v_target,current_event_sequence=current_event_sequence+1,
          content_hash=p_payload->>'contentHash',authority_data=p_payload,
          updated_at=(p_payload->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;$body$;
      new_update text := $body$UPDATE ecommerce_investigation_run_state_head SET current_version=p_expected_version+1,
          lifecycle='PREPARING',control=v_target,current_event_sequence=current_event_sequence+1,
          content_hash=p_payload->>'contentHash',authority_data=p_payload,
          pending_requirement_ref=NULL,uncertain_command=NULL,
          updated_at=(p_payload->>'createdAt')::timestamptz
          WHERE org_id=v_org AND project_id=v_project AND run_id=p_run_id;$body$;
    BEGIN
      definition:=pg_get_functiondef(to_regprocedure(
        'public.ecommerce_investigation_run_control_biw4_006(text,bigint,text,text,jsonb)'));
      IF definition IS NULL
        OR (length(definition)-length(replace(definition,old_update,'')))/length(old_update)<>1
      THEN RAISE EXCEPTION 'exact BIW4 Run control function required'; END IF;
      EXECUTE replace(definition,old_update,new_update);
    END $migration$;
    """)


def downgrade():
    raise RuntimeError("Run head pending-field consistency repair must be retained")
