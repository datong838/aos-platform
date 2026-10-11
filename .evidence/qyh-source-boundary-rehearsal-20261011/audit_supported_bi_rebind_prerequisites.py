"""Original BI rebind authentication guard and readonly current source lookup."""
import hashlib
import json
import sys
from pathlib import Path
from contextlib import contextmanager
from urllib.request import Request,urlopen
import real_contract as C
sys.path.insert(0,str(C.ROOT/'.evidence/qyh-full-system-restoration-20261011'))
import release_transition as T
from prepare_public_bundle_root import OUTPUT,fingerprints
from aos_api.auth import resolve_principal
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.aip_responsibility_template_authority import ActiveBIBusinessResolver
from aos_api.ecommerce_business_investigation_aip_authority import SignedBIPlanActiveRebindService
from aos_api.tenant_scope import TenantScope

out=C.R/'bi-rebind-prerequisite-result.json'
assert not out.exists(),'Existing result: read-only reconcile'
called=[]
def never_write(scope):
    called.append(scope.key)
    raise AssertionError('Development identity must fail before connecting')
service=SignedBIPlanActiveRebindService(connect_factory=never_write)
scopes=(C.SCOPE,TenantScope('dev-org','dev-project'))
denials=[]
for scope in scopes:
    principal=resolve_principal(token='dev',header_org=scope.org_id,header_project=scope.project_id)
    assert principal.token_kind=='dev'
    try:
        service.rebind(scope,installation_id='00000000-0000-0000-0000-000000000000',
            plan_id='test-only-no-target-mutation',prepare_key='test-only-no-preparation',
            expected_etag_version=1,expected_plan_version=1,
            principal=principal,idempotency_key='test-only-no-rebind')
    except PermissionError as error:
        assert str(error)=='formal authenticated actor required'
        denials.append({'scope':list(scope.key),'tokenKind':principal.token_kind,'code':str(error)})
    else:raise AssertionError('Formal actor guard did not reject development identity')
assert not called
connections=[]
@contextmanager
def readonly(scope):
    with T.factory() as conn:
        conn.read_only=True
        identity=conn.execute("SELECT current_user AS role,current_database() AS db,current_setting('transaction_read_only') AS readonly,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity=={'role':'aos_runtime','db':'aos_meta_head','readonly':'on','cluster':'7695302940039200809'}
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
        apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
        connections.append(identity)
        yield conn
def never_registry():
    raise AssertionError('No active source rows must not read unrelated Registry snapshots')
before=fingerprints(OUTPUT)
resolver=ActiveBIBusinessResolver(connect_factory=readonly,registry_connect_factory=never_registry,
    release_root=OUTPUT,trust_roots=T.FileTrustRootProvider(T.TRUST),source_alias='a0v-qyh-current')
sources=[]
for scope in scopes:
    with readonly(scope) as conn:
        rows=conn.execute('''SELECT r.state,count(*) AS n,
               count(*) FILTER(WHERE i.active_revision=i.current_revision) AS current_active_pointer
            FROM bundle_installation i JOIN bundle_installation_revision r
              ON r.org_id=i.org_id AND r.project_id=i.project_id
             AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
            WHERE i.org_id=%s AND i.project_id=%s GROUP BY r.state ORDER BY r.state''',scope.key).fetchall()
    selected=resolver.select(scope)
    assert selected is None
    sources.append({'scope':list(scope.key),'installationStates':rows,'originalActiveBISelection':None})
assert fingerprints(OUTPUT)==before
req=Request('http://127.0.0.1:18080/v1/auth/oidc',headers={'Authorization':'Bearer dev','X-Org-Id':'org-org','X-Project-Id':'dev-project'})
with urlopen(req,timeout=8) as response:
    data=json.load(response)
    oidc={'status':response.status,**{k:data.get(k) for k in ('issuer','jwksUrls','tokenUrlConfigured','allowDevToken','grantTypes')}}
result={'task':'qyh-source-boundary-rehearsal-20261011','authority':'AOS-001898',
    'originalRebindRejectsActualResolvedDevelopmentIdentityBeforeConnection':denials,
    'rebindDatabaseConnections':len(called),'readonlyCurrentDatabaseConnections':connections,
    'currentSourceLookup':sources,'liveOIDCConfiguration':oidc,'selectedPackagesUnchanged':True,
    'databaseWrites':0,'installationStateChanged':False,'principalOIDCIdentityFabricated':False,
    'formalPublisherConnected':False,'fullRestorationAccepted':False,
    'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with out.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'developmentIdentityRejectedBeforeDB':len(denials),'currentBISelections':0,
    'installationStateCounts':sources,'databaseWrites':0}))
