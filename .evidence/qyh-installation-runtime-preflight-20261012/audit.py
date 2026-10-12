"""Read current installation and original runtime release checks; no writes."""
import json
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / '.evidence/qyh-installation-runtime-preflight-20261012'
sys.path.insert(0, str(ROOT / 'services/aos-api'))
from psycopg import connect
from psycopg.rows import dict_row
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.signature import FileTrustRootProvider
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator

data = json.loads((ROOT / '.evidence/qyh-full-system-restoration-20261011/private/restored-identity.json').read_text())

@contextmanager
def factory():
    with connect(host=data['host'], port=data['port'], dbname=data['dbname'],
                 user=data['user'], passfile=data['pgpassfile'], row_factory=dict_row,
                 options='-c default_transaction_read_only=on -c statement_timeout=10000',
                 autocommit=True) as conn:
        conn.execute('SET ROLE aos_runtime')
        conn.autocommit = False
        yield conn

tenant = {'org_id': 'org-org', 'project_id': 'dev-project'}
store = PostgresInstallationStore(connect_factory=factory)
record = store.get_installation(**tenant, installation_id='ab2fd72f-d81c-400d-bbbc-e1589a159d6b')
assert record.state == 'submitted' and record.etag_version == 2
lock = PostgresCompositionStore(connect_factory=factory).get_lock(
    **tenant, composition_id=record.current.composition_id, revision=record.current.lock_revision)
assert len(lock.payload.resolved) == 4 and len(lock.payload.edges) == 3
ui_count = sum(c.kind == 'ui' and c.slot == 'workshop.primary.ecommerce'
               for release in lock.payload.resolved for c in release.contributions)
assert ui_count == 8
old = store.get_installation(**tenant, installation_id='407059df-6f1f-4927-acd7-8e388692838e')
assert old.active_revision == 5
trust = FileTrustRootProvider(ROOT / '.evidence/qyh-full-system-restoration-20261011/restoration-public-trust-roots.json').snapshot()
with factory() as conn:
    with conn.transaction():
        assert conn.execute('SHOW transaction_read_only').fetchone()['transaction_read_only'] == 'on'
        head = conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']
        assert head == 'a0v_161'
        count = conn.execute("SELECT count(*) AS n FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname NOT LIKE 'pg_toast%'").fetchone()['n']
        assert count == 650
        fenced = conn.execute('SELECT count(*) AS n FROM extension_runtime_binding WHERE enabled OR NOT operation_fence').fetchone()['n']
        assert fenced == 0
        checked = RuntimeReleaseRevalidator(release_policy=ReleasePolicy(trust_roots=trust)).revalidate_in_transaction(conn, lock=lock)
result = {'observedAt': datetime.now(timezone.utc).isoformat(), 'tenant': tenant,
          'databaseHead': head, 'tableCount': count, 'installationId': record.installation_id,
          'state': record.state, 'etagVersion': record.etag_version,
          'lockHash': lock.lock_hash, 'uiContributionCount': ui_count,
          'runtimeMembers': list(checked.runtime_members),
          'backendClaimCount': len(checked.backend_claims),
          'selected': [{'id': r.id, 'version': r.version} for r in lock.payload.resolved],
          'predecessorActiveRevision': old.active_revision,
          'unfencedOrEnabledBindings': fenced, 'databaseWrites': 0,
          'releaseCheckPassed': True, 'independentApprovalPassed': False,
          'runtimePreparationPassed': False, 'eightPagesAccepted': False}
with (OUT / 'result.json').open('x') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(result, ensure_ascii=False))
