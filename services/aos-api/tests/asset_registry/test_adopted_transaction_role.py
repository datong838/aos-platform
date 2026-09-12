from unittest.mock import MagicMock
import psycopg
import pytest
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope


@pytest.mark.parametrize('role', ['aos_app','aos_runtime'])
def test_adopted_control_role_is_preserved_while_binding_tenant(role):
    conn = MagicMock(spec=psycopg.Connection)
    conn.execute.return_value.fetchone.return_value = {'current_user':role}
    apply_asset_transaction_scope(conn, org_id='org-org', project_id='dev-project')
    calls = conn.execute.call_args_list
    assert len(calls) == 2
    assert calls[-1].args[1] == ('org-org','dev-project')
    assert "set_config('aos.org_id'" in calls[-1].args[0]
    assert not any('SET LOCAL ROLE' in call.args[0] for call in calls)
