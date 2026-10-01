"""Read-only admission against a reviewed migration-derived budget schema.

Never generate or update the accepted manifest from the deployment database.
OID values vary; the migration owner must remain the platform's aos_app role.
"""
import json
from pathlib import Path

from aos_api.aip_budget_cost_issuer import BudgetCostIssuerBlocked


_TABLES = ('aip_budget_cost_proposal', 'aip_budget_cost_proposal_receipt',
           'aip_budget_cost_decision', 'aip_budget_cost_revocation', 'aip_budget_cost_issuer_receipt',
           'aip_budget_cost_runtime_fence')
_FUNCTIONS = ('public.aip_budget_cost_issuer_guard_a0v_125()',
              'public.extension_reject_history_mutation()',
              'public.aip_budget_cost_fence_guard_a0v_126()',
              'public.aip_budget_cost_revoke_fence_a0v_126()')


def budget_schema_snapshot(conn):
    from aos_api.pg_authority_schema import authority_schema_snapshot, AuthoritySchemaBlocked
    try:
        return authority_schema_snapshot(conn, tables=_TABLES,
            function_owners={name: 'aos_app' for name in _FUNCTIONS})
    except AuthoritySchemaBlocked as exc:
        raise BudgetCostIssuerBlocked(str(exc)) from None


def require_budget_schema(conn):
    try:
        safe = conn.execute("""SELECT NOT EXISTS(SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname='aos_runtime' AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
            OR rolreplication OR rolbypassrls))
            AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members WHERE member='aos_runtime'::regrole)
            AND NOT has_schema_privilege('aos_runtime','public','CREATE') AS safe""").fetchone()
        if safe is None or safe['safe'] is not True:
            raise BudgetCostIssuerBlocked('BUDGET_COST_SCHEMA_RUNTIME_UNSAFE')
        expected = json.loads(Path(__file__).with_name('aip_budget_cost_schema.json').read_text())
        if budget_schema_snapshot(conn) != expected:
            raise BudgetCostIssuerBlocked('BUDGET_COST_SCHEMA_DRIFT')
    except BudgetCostIssuerBlocked:
        raise
    except Exception:
        raise BudgetCostIssuerBlocked('BUDGET_COST_SCHEMA_PREFLIGHT_FAILED') from None
