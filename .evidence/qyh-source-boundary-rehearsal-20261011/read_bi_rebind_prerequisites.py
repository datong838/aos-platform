"""Independent exact source-row and runtime-binding readback, no fake resolver."""
import hashlib
import json
import sys
from pathlib import Path
from contextlib import contextmanager
import real_contract as C
sys.path.insert(0,str(C.ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from prepare_public_bundle_root import OUTPUT,fingerprints
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_responsibility_template_authority import ActiveBIBusinessResolver
from aos_api.tenant_scope import TenantScope

first=json.loads((C.R/'bi-rebind-prerequisite-result.json').read_text())
assert first['scriptHash']==hashlib.sha256((C.R/'audit_supported_bi_rebind_prerequisites.py').read_bytes()).hexdigest()
registry_reads=[]
@contextmanager
def read(scope):
    with T.factory() as conn:
        conn.read_only=True
        apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
        assert conn.execute("SELECT current_setting('transaction_read_only') AS r").fetchone()['r']=='on'
        yield conn
@contextmanager
def registry():
    with T.factory() as conn:
        conn.read_only=True
        registry_reads.append(True)
        yield conn
resolver=ActiveBIBusinessResolver(connect_factory=read,registry_connect_factory=registry,
    release_root=OUTPUT,trust_roots=T.FileTrustRootProvider(T.TRUST),source_alias='a0v-qyh-current')
scopes=(C.SCOPE,TenantScope('dev-org','dev-project'))
rows=[]
for scope in scopes:
    # Unlike select(), this original query does not swallow exceptions.
    candidates=resolver._approved_rows(scope)
    assert candidates==[]
    assert resolver.select(scope) is None
    with read(scope) as conn:
        bindings=conn.execute('SELECT count(*) AS total,count(*) FILTER(WHERE enabled) AS enabled,count(*) FILTER(WHERE operation_fence) AS fenced FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s',scope.key).fetchone()
        assert bindings['enabled']==0
        assert bindings['fenced']==bindings['total']
    rows.append({'scope':list(scope.key),'originalCurrentPublishedBISourceRows':len(candidates),'runtimeBindings':bindings})
assert registry_reads==[], 'With no original source rows Registry must not be consulted'
old=json.loads((C.R/'signed-media-source-result.json').read_text())
hashes=fingerprints(OUTPUT)
assert hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()==old['filesHash']
result={'task':first['task'],'authority':'AOS-001898',
    'independentOriginalSourceQueryAndRuntimeBindings':rows,
    'normalReadonlyRegistryFactoryNotCalled':True,
    'resolverNoneIsCorroboratedByOriginalEmptySourceRowsNotExceptionMasking':True,
    'historicalActiveInstallationCountNotRuntimeEnablement':True,
    'all179SignedPackageFilesUnchanged':True,'databaseWrites':0,
    'formalLoginConnected':False,'formalPublisherConnected':False,'fullRestorationAccepted':False,
    'auditScriptHash':first['scriptHash'],'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with (C.R/'bi-rebind-prerequisite-independent-readback.json').open('x') as stream:
    stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'originalPublishedCurrentBISourceRows':0,'positiveScopeRuntimeBindings':rows[0]['runtimeBindings'],
    'normalRegistryFactoryCalls':len(registry_reads),'databaseWrites':0}))
