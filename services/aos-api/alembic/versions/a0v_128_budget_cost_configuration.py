"""Derive paired development configuration from a consumed cost decision."""
from pathlib import Path
from alembic import op

revision = 'a0v_128'
down_revision = 'a0v_127'
branch_labels = depends_on = None
TABLES = ('aip_model_price_snapshot_head', 'aip_model_price_snapshot_revision',
          'aip_model_governance_policy_head', 'aip_model_governance_policy_revision',
          'aip_model_governance_policy_receipt')
FUNCTIONS = ('aip_budget_consumption_fact_a0v_128', 'aip_cost_configuration_expected_a0v_128',
             'aip_cost_configuration_fact_a0v_128', 'aip_reconcile_cost_configuration_a0v_128',
             'aip_configure_budget_cost_a0v_128')


def upgrade():
    for table in TABLES:
        op.execute(f'GRANT SELECT,INSERT ON public.{table} TO aos_budget_consumer_owner')
        op.execute(f"""CREATE POLICY budget_configuration_a0v128 ON public.{table} TO aos_budget_consumer_owner
          USING(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))
          WITH CHECK(org_id=NULLIF(current_setting('aos.org_id',true),'') AND project_id=NULLIF(current_setting('aos.project_id',true),''))""")
    op.execute("""CREATE FUNCTION public.aip_cost_configuration_write_guard_a0v_128() RETURNS trigger
      LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$
      DECLARE protected boolean;
      BEGIN
       IF TG_TABLE_NAME='aip_model_governance_policy_receipt' THEN
        protected:=NEW.operation='budget_cost.configure';
       ELSE
        protected:=NEW.lifecycle='active' AND NEW.payload ? 'developmentCostAuthorization'
          AND NEW.payload->'developmentCostAuthorization'<>'null'::jsonb;
       END IF;
       IF protected AND (session_user<>'aos_budget_consumer_call' OR current_user<>'aos_budget_consumer_owner') THEN
        RAISE EXCEPTION 'COST_CONFIGURATION_CONSUMER_REQUIRED' USING ERRCODE='42501'; END IF;
       RETURN NEW;
      END $$""")
    op.execute('REVOKE ALL ON FUNCTION public.aip_cost_configuration_write_guard_a0v_128() FROM PUBLIC')
    for table in ('aip_model_price_snapshot_revision', 'aip_model_governance_policy_revision', 'aip_model_governance_policy_receipt'):
        op.execute(f'CREATE TRIGGER cost_configuration_write_guard BEFORE INSERT ON public.{table} FOR EACH ROW EXECUTE FUNCTION public.aip_cost_configuration_write_guard_a0v_128()')
    source = Path(__file__).resolve().parents[2] / 'aos_api/aip_budget_cost_configuration.sql'
    op.get_bind().exec_driver_sql(source.read_text().replace('%', '%%'))
    for name in FUNCTIONS:
        signature = 'public.' + name + '(' + ','.join(['text']*6) + ')'
        op.execute(f'ALTER FUNCTION {signature} OWNER TO aos_budget_consumer_owner')
        op.execute(f'REVOKE ALL ON FUNCTION {signature} FROM PUBLIC')
        if name in ('aip_reconcile_cost_configuration_a0v_128', 'aip_configure_budget_cost_a0v_128'):
            op.execute(f'GRANT EXECUTE ON FUNCTION {signature} TO aos_budget_consumer_call')


def downgrade():
    raise RuntimeError('derived cost configuration and its authority history must not be removed')
