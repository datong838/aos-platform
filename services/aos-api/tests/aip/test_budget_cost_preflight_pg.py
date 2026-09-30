"""Read-only schema checks on disposable migrated PG, never a live baseline."""
import json

import pytest

from aos_api.aip_budget_cost_preflight import budget_schema_snapshot, require_budget_schema
from aos_api.aip_budget_cost_issuer import BudgetCostIssuerBlocked
from tests.aip.test_budget_cost_connection_pg import configured
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


def test_migrated_schema_matches_reviewed_manifest(configured, tmp_path):
    _, factory = configured
    with factory(SCOPE, True) as conn:
        actual = budget_schema_snapshot(conn)
        candidate = tmp_path / 'budget-schema-candidate.json'
        candidate.write_text(json.dumps(actual, ensure_ascii=False, indent=2)+'\n')
        print('isolated schema candidate:', candidate)
        require_budget_schema(conn)


@pytest.mark.parametrize('mutation', [
    'ALTER TABLE aip_budget_cost_decision DISABLE TRIGGER aip_budget_cost_decision_issuer',
    'ALTER TABLE aip_budget_cost_decision DISABLE ROW LEVEL SECURITY',
    'ALTER TABLE aip_budget_cost_decision NO FORCE ROW LEVEL SECURITY',
    'ALTER TABLE aip_budget_cost_decision DROP CONSTRAINT aip_budget_cost_decision_check',
    'ALTER POLICY aip_budget_cost_decision_tenant ON aip_budget_cost_decision USING (true)',
    'GRANT UPDATE(decision) ON aip_budget_cost_decision TO aos_runtime',
    'GRANT SELECT ON aip_budget_cost_decision TO PUBLIC',
    'GRANT aos_network_consumer_call TO aos_runtime',
    'ALTER FUNCTION public.extension_reject_history_mutation() OWNER TO aos_network_approval_issuer',
    "CREATE OR REPLACE FUNCTION public.aip_budget_cost_issuer_guard_a0v_125() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$",
])
def test_schema_drift_is_rejected_without_effect(mutation):
    # Owner mutates ONLY the isolated fixture within a transaction; always rollback.
    # Admission itself reads only pg_catalog, so mutation is visible on this connection.
    with isolated_owner() as conn:
        conn.execute(mutation)
        conn.execute('SET LOCAL ROLE aos_runtime')
        with pytest.raises(BudgetCostIssuerBlocked, match='SCHEMA'):
            require_budget_schema(conn)
        conn.rollback()
