"""Read-only reconciliation, never repeat the lifecycle mutations."""
import ast
import hashlib
import json
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_stage_template_authority import resolve_stage_template_source

r = C.R
b = json.loads((r / 'stage-lifecycle-business-result.json').read_text())
frozen = b['frozen']
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True), stage_template_source_resolver=resolve_stage_template_source)
    actual = store.get_stage_template(C.SCOPE, frozen['templateId'], conn=conn)
    assert actual.model_dump(mode='json', by_alias=True) == frozen
    revisions = conn.execute('SELECT revision,lifecycle,content_hash,seal_hash FROM aip_stage_template_revision WHERE org_id=%s AND project_id=%s AND template_id=%s ORDER BY revision', (*C.SCOPE.key, frozen['templateId'])).fetchall()
    assert [(x['revision'], x['lifecycle']) for x in revisions] == [(1, 'draft'), (2, 'draft'), (3, 'frozen')]
    assert revisions[-1]['seal_hash'] == frozen['sealHash']
    receipts = conn.execute("SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key IN ('qyh-stage-create','qyh-stage-revise','qyh-stage-freeze') ORDER BY operation", C.SCOPE.key).fetchall()
    assert len(receipts) == 3
    for row in receipts:
        assert row['result_ref']['resourceId'] == frozen['templateId']
        expected = {'stage_template.create': 1, 'stage_template.revise': 2, 'stage_template.freeze': 3}[row['operation']]
        assert row['result_ref']['revision'] == expected
    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key IN ('qyh-stage-stale','qyh-stage-frozen-revise','qyh-stage-drift-freeze','qyh-stage-rollback','qyh-stage-forged')").fetchone()['n'] == 0
    drift = store.get_stage_template(C.SCOPE, b['drifted']['templateId'], conn=conn)
    assert drift.lifecycle.value == 'draft' and drift.readiness.value == 'blocked'
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata('qyh-restored-pg-20261011') == C.S.D.metadata(C.TARGET)
readback = {'exactFrozenRevisionAndSeal': True, 'threeLifecycleReceiptsExact': True, 'driftedDraftNotFrozen': True, 'failedRequestsNoReceipt': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'legacyStaticSourceOnly': True, 'currentSignedInstallationVerified': False, 'fullRestorationAccepted': False, 'scriptHash': hashlib.sha256((r / 'real_stage_template.py').read_bytes()).hexdigest()}
with (r / 'stage-lifecycle-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual = {x['operation']: x['n'] for x in operations}
with (r / 'contract-operation-coverage-r5.json').open('x') as out:
    out.write(json.dumps({'catalogOperations': len(catalog), 'actualCurrentExperimentalReceiptOperations': actual, 'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual)), 'stageSourceIsLegacyStaticAllowlist': True, 'disclosureReceiptIsDeniedDecisionNotAuthorization': True, 'bundleRevokeUnissuedGenericOnly': True, 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual), 'remainingOperations': len(set(catalog) - set(actual))}))
