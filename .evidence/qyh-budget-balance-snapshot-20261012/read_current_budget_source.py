"""Current restored canonical budget read only; no activation or reservation."""
import json,sys,hashlib
from contextlib import contextmanager
from pathlib import Path
import psycopg
sys.path[:0]=['services/aos-api','.evidence/qyh-source-boundary-rehearsal-20261011','.evidence/qyh-full-system-restoration-20261011']
import real_contract as C
import release_transition as T
from aos_api.aip_budget_balance_snapshot import BudgetBalanceSnapshotReader,BudgetBalanceSnapshotUnavailable
from aos_api.aip_budget_reservation_contracts import ReserveBudgetRequest
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope
R=Path('.evidence/qyh-budget-balance-snapshot-20261012')
out=R/'current-budget-source-readback.json';assert not out.exists()
before=C.S.P.M.fingerprint('qyh-restored-pg-20261011');metadata=C.S.D.metadata('qyh-restored-pg-20261011')
connections=[]
@contextmanager
def read(scope):
    with T.factory() as c:
        c.read_only=True;c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ
        apply_asset_transaction_scope(c,org_id=scope.org_id,project_id=scope.project_id)
        identity=c.execute("SELECT current_user AS role,current_database() AS db,system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity=={'role':'aos_runtime','db':'aos_meta_head','cluster':'7695302940039200809'}
        assert c.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
        connections.append(identity);yield c
results=[]
for scope in [C.SCOPE,TenantScope('dev-org','dev-project')]:
    with read(scope) as c:
        heads=c.execute("SELECT h.budget_id,h.current_revision,r.content_hash,r.lifecycle FROM aip_budget_head h JOIN aip_budget_revision r ON h.org_id=r.org_id AND h.project_id=r.project_id AND h.budget_id=r.budget_id AND h.current_revision=r.revision WHERE h.org_id=%s AND h.project_id=%s",scope.key).fetchall()
    assert len(heads)<=30
    sources=heads or [{'budget_id':'negative:no-current-budget','current_revision':1,'content_hash':'a'*64,'lifecycle':None}]
    ref=lambda k,i:{'resourceType':k,'resourceId':i,'revision':1,'contentHash':'sha256:'+'a'*64}
    for h in sources:
        request=ReserveBudgetRequest(operationId='read-only:observation',invocationKey='no-execution',
            taskRef=ref('Task','unapproved:observation-only'),policyRef={'resourceType':'BudgetRevision',
            'resourceId':h['budget_id'],'revision':h['current_revision'],'contentHash':'sha256:'+h['content_hash']},
            pricingRef=ref('ModelPriceSnapshotRevision','unapproved:observation-only'),
            approvalRef=ref('ActionApprovalEvent','unapproved:observation-only'),upperBoundMinor=1)
        try:
            snapshot=BudgetBalanceSnapshotReader(read).read(scope,request)
            results.append({'scope':list(scope.key),'currentHeads':len(heads),'observed':True,
                'executionAuthorized':snapshot.execution_authorized,'costUpperBoundAuthorized':snapshot.cost_upper_bound_authorized,
                'bucketBlockers':[list(x.blocker_codes) for x in snapshot.buckets]})
        except BudgetBalanceSnapshotUnavailable:
            results.append({'scope':list(scope.key),'currentHeads':len(heads),'observed':False,
                'sourceUnavailable':True,'executionAuthorized':False,'costUpperBoundAuthorized':False})
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011')==before
assert C.S.D.metadata('qyh-restored-pg-20261011')==metadata
result={'authority':'AOS-001900','task':'qyh-budget-balance-snapshot-20261012',
    'nativeReadonlyScopedConnections':connections,'canonicalCurrentSources':results,
    'current647DataAndOriginalMetadataUnchanged':True,'databaseWrites':0,'contentReadinessConnected':False,
    'formalRestorationAccepted':False,'readerSourceHash':hashlib.sha256(Path('services/aos-api/aos_api/aip_budget_balance_snapshot.py').read_bytes()).hexdigest(),
    'scriptHash':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'nativeReadonlyConnections':len(connections),'currentBudgetSources':results,
    'current647DataAndOriginalMetadataUnchanged':True,'databaseWrites':0}))
