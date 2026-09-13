import os
from types import SimpleNamespace
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_lifecycle_pg import database
from test_cutover_action_binding import inputs
from aos_api.tenant_scope import TenantScope
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, APPROVE_INSTALLATION_OPERATION

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


@pytest.mark.parametrize('case', ['maker', 'checker', 'installer-cannot-check', 'revoked', 'drift', 'missing-action', 'wrong-scope', 'extra-marking'])
def test_gate_reads_current_authority_in_callers_transaction(database, monkeypatch, case):
    from aos_api.ecommerce_growth_cutover_proposal_gate import require_internal_cutover_binding
    from aos_api.asset_registry.errors import AssetRegistryError
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    conn, _, _ = database
    conn.row_factory = dict_row
    scope = TenantScope('org-org', 'dev-project')
    snapshot, payload = inputs()
    conn.execute('CREATE TABLE meta_membership(org_id text, project_id text, subject text, role text)')
    conn.execute('CREATE TABLE authz_tuple(org_id text, project_id text, user_key text, relation text, object_key text)')
    conn.execute('CREATE TABLE meta_action_type(id text, name text, object_type text, parameters jsonb, required_markings jsonb, submission_criteria jsonb)')
    role = 'asset-install-approver' if case == 'checker' else 'asset-installer'
    if case != 'revoked':
        conn.execute("INSERT INTO meta_membership VALUES('org-org','dev-project','operator',%s)", (role,))
    conn.execute("INSERT INTO authz_tuple VALUES('org-org','dev-project','user:operator','bearer','marking:public')")
    conn.execute("INSERT INTO bundle_installation(org_id,project_id,installation_id) VALUES('org-org','dev-project',%s)", (payload['targetInstallationId'],))
    if case == 'extra-marking':
        from aos_api.aip_action_store import canonical_hash
        snapshot['requiredMarkings'] = ['sensitive']
        snapshot['revisionHash'] = canonical_hash({k:v for k,v in snapshot.items() if k != 'revisionHash'})
    if case != 'missing-action':
        conn.execute('INSERT INTO meta_action_type VALUES(%s,%s,%s,%s,%s,%s)',
            (snapshot['id'], 'changed' if case == 'drift' else snapshot['name'], snapshot['objectType'],
             Jsonb(snapshot['parameters']), Jsonb(snapshot['requiredMarkings']), Jsonb(snapshot['submissionCriteria'])))
    locked = SimpleNamespace(org_id=scope.org_id, project_id=scope.project_id)
    calls = []
    def lock(self, actual_conn, **kwargs):
        assert actual_conn is conn
        calls.append(kwargs)
        return locked
    monkeypatch.setattr('aos_api.asset_registry.installation_store.PostgresInstallationStore.lock_for_transition_in_transaction', lock)
    monkeypatch.setattr('aos_api.extension_runtime.current_permission._load_current_lock', lambda *a, **kw:
        SimpleNamespace(payload=SimpleNamespace(permission_diff=SimpleNamespace(target=SimpleNamespace(markings=['public'])))))
    monkeypatch.delenv('AOS_OPENFGA_API_URL', raising=False)
    operation = APPROVE_INSTALLATION_OPERATION if case in {'checker','installer-cannot-check'} else APPLY_INSTALLATION_OPERATION
    with conn.transaction():
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true)", ('dev-org' if case == 'wrong-scope' else 'org-org',))
        before = conn.execute('SELECT txid_current() AS id').fetchone()['id']
        if case in {'maker','checker'}:
            binding, roles = require_internal_cutover_binding(conn=conn, scope=scope, actor='operator',
                action_snapshot=snapshot, payload=payload, operation=operation)
            assert len(binding) == 64 and roles == (role,)
            assert conn.execute('SELECT txid_current() AS id').fetchone()['id'] == before
            assert calls[0]['installation_id'] == payload['targetInstallationId']
        else:
            with pytest.raises((AssetRegistryError, RuntimeConflict, ValueError)):
                require_internal_cutover_binding(conn=conn, scope=scope, actor='operator',
                    action_snapshot=snapshot, payload=payload, operation=operation)
