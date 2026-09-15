"""Lock Case/Policy before an approval event exists, without table write grants."""
from alembic import op
revision='a0v_057'
down_revision='a0v_056'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE FUNCTION public.ecommerce_product_event_proposal_lock_a0v_057(
      p_case text,p_policy text) RETURNS void
      LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
      DECLARE v_org text:=nullif(current_setting('aos.org_id',true),'');
        v_project text:=nullif(current_setting('aos.project_id',true),''); v_id text;
      BEGIN
        IF v_org IS NULL OR v_project IS NULL OR current_setting('role') IS DISTINCT FROM 'aos_runtime'
        THEN RAISE EXCEPTION 'scoped proposal runtime required' USING ERRCODE='42501'; END IF;
        FOREACH v_id IN ARRAY ARRAY[p_case,p_policy] LOOP
          IF (length(v_id) BETWEEN 1 AND 240 AND v_id=btrim(v_id)) IS NOT TRUE THEN
            RAISE EXCEPTION 'exact proposal authority identity required' USING ERRCODE='23514'; END IF;
        END LOOP;
        PERFORM 1 FROM public.ecommerce_investigation_case_head
          WHERE org_id=v_org AND project_id=v_project AND case_id=p_case FOR UPDATE;
        IF NOT FOUND THEN RAISE EXCEPTION 'current proposal Case unavailable' USING ERRCODE='23514'; END IF;
        PERFORM 1 FROM public.ecommerce_investigation_schedule_policy_head
          WHERE org_id=v_org AND project_id=v_project AND schedule_policy_id=p_policy FOR UPDATE;
      END $$''')
    op.execute('REVOKE ALL ON FUNCTION public.ecommerce_product_event_proposal_lock_a0v_057(text,text) FROM PUBLIC')
    op.execute('GRANT EXECUTE ON FUNCTION public.ecommerce_product_event_proposal_lock_a0v_057(text,text) TO aos_runtime')


def downgrade():
    op.execute('DROP FUNCTION public.ecommerce_product_event_proposal_lock_a0v_057(text,text)')
