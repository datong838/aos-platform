"""Independent read-only reconciliation of the fenced generic bundle revoke."""
import ast
import hashlib
import json
import psycopg
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

r = C.R
b = json.loads((r / 'bundle-revoke-business-result.json').read_text())
ref = b['bundleRef']
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
    bundle = store.get_evidence_bundle(C.SCOPE, ref['resourceId'], ref['revision'], conn=conn)
    assert bundle.revoked and bundle.content_hash == ref['contentHash']
    receipt = conn.execute("SELECT result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='evidence_bundle.revoke' AND idempotency_key='qyh-bundle-revoke'", C.SCOPE.key).fetchone()
    assert receipt['result_ref'] == ref
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence_bundle_revoke_event WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s', (*C.SCOPE.key, ref['resourceId'], ref['revision'], ref['contentHash'])).fetchone()['n'] == 1
    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key IN ('qyh-bundle-denied','qyh-bundle-drift','qyh-bundle-canary','qyh-bundle-rollback')").fetchone()['n'] == 0
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
with psycopg.connect(host='127.0.0.1', port=18431, dbname=C.DB, user='aos_app', row_factory=dict_row) as conn:
    conn.read_only = True
    assert not conn.execute('SELECT 1 FROM aip_license_source_issuance WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s', (*C.SCOPE.key, ref['resourceId'], ref['revision'])).fetchone()
    fence = conn.execute('SELECT epoch FROM aip_license_source_initialization_fence WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s', (*C.SCOPE.key, ref['resourceId'], ref['revision'], ref['contentHash'])).fetchone()
    # Original AFTER INSERT trigger invalidates the source exactly once.
    assert fence and fence['epoch'] == 1
    capacity = conn.execute('SELECT epoch FROM aip_capacity_evidence_epoch WHERE org_id=%s AND project_id=%s AND bundle_id=%s', (*C.SCOPE.key, ref['resourceId'])).fetchone()
    assert capacity and capacity['epoch'] == 1
    funcs = conn.execute("SELECT p.proname,p.proacl::text AS acl,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname IN ('aos_license_source_initialization_lock','aos_license_source_lock') ORDER BY p.proname").fetchall()
    frozen = json.loads((r / 'bundle-revoke-dependency-readback.json').read_text())['functions']
    assert len(funcs) == len(frozen) == 2
    for actual, expected in zip(funcs, frozen):
        assert actual['proname'] == expected['proname']
        assert actual['acl'] == expected['acl']
        assert hashlib.sha256(actual['definition'].encode()).hexdigest() == expected['definitionHash']
source = 'qyh-restored-pg-20261011'
assert C.S.P.M.fingerprint(source) == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata(source) == C.S.D.metadata(C.TARGET)
readback = {'originalStoreReadRevoked': True, 'receiptExact': True, 'oneRevokeEventOnly': True, 'failedRequestsHaveNoReceipt': True, 'unissuedBundleInitializationFenceEpoch': fence['epoch'], 'capacityEvidenceEpoch': capacity['epoch'], 'originalBothFunctionSourceAndACLUnchanged': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'issuedSourcePathAccepted': False, 'fullRestorationAccepted': False, 'scriptHash': hashlib.sha256((r / 'real_bundle_revoke.py').read_bytes()).hexdigest()}
with (r / 'bundle-revoke-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual = {x['operation']: x['n'] for x in operations}
with (r / 'contract-operation-coverage-r4.json').open('x') as out:
    out.write(json.dumps({'catalogOperations': len(catalog), 'actualCurrentExperimentalReceiptOperations': actual, 'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual)), 'disclosureReceiptIsDeniedDecisionNotAuthorization': True, 'bundleRevokeUnissuedGenericOnly': True, 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual), 'remainingOperations': len(set(catalog) - set(actual))}))
