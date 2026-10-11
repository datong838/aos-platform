"""Independently classify retained Eval contracts without granting media authority."""
import json
import sys
from pathlib import Path
import psycopg
sys.path[:0] = ['services/aos-api', '.evidence/qyh-full-system-restoration-20261011']
import release_transition as T
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope

output = Path('.evidence/qyh-media-restored-authority-20261012/lifecycle.json')
assert not output.exists()
reads = []
for org in ['org-org', 'dev-org']:
    with T.factory() as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        apply_asset_transaction_scope(conn, org_id=org, project_id='dev-project')
        identity = conn.execute("SELECT current_user AS role,current_database() AS db,current_setting('transaction_read_only') AS readonly,current_setting('transaction_isolation') AS isolation").fetchone()
        assert identity == dict(role='aos_runtime', db='aos_meta_head', readonly='on', isolation='repeatable read')
        rows = conn.execute("SELECT lifecycle,count(*) AS count FROM public.aip_eval_contract_revision WHERE org_id=%s AND project_id=%s GROUP BY lifecycle ORDER BY lifecycle", (org, 'dev-project')).fetchall()
        policies = conn.execute("SELECT gate_policy_ref->>'resourceType' AS policy_type,count(*) AS count FROM public.aip_eval_run WHERE org_id=%s AND project_id=%s GROUP BY gate_policy_ref->>'resourceType' ORDER BY policy_type", (org, 'dev-project')).fetchall()
        reads.append(dict(scope=[org,'dev-project'], contracts=rows, evalRunPolicyTypes=policies))
body = dict(reads=reads, databaseWrites=0, formalMediaAuthorityGranted=False)
with output.open('x') as file:
    json.dump(body,file,indent=2)
    file.write('\n')
print(json.dumps(body))
