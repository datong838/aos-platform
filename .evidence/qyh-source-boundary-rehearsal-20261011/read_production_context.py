"""Independent readback; no replay of the completed Context transaction."""
import ast
import hashlib
import json
import psycopg
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

R = C.R
intent = json.loads((R / 'production-context-intent.json').read_text())
business = json.loads((R / 'production-context-business-result.json').read_text())
assert intent['scriptHash'] == hashlib.sha256((R / 'real_production_context.py').read_bytes()).hexdigest()
made = business['context']
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
    actual = store.get_production_context(C.SCOPE, made['contextId'], conn=conn)
    assert actual.model_dump(mode='json', by_alias=True) == made
    assert actual.production_profile_ref is None and actual.preparation_ref is None
    receipt = conn.execute("SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key=%s", (*C.SCOPE.key, 'qyh-context-freeze')).fetchall()
    assert len(receipt) == 1 and receipt[0]['operation'] == 'production_context.freeze'
    assert receipt[0]['result_ref'] == {'resourceType': 'ProductionContextRevision',
        'resourceId': made['contextId'], 'revision': 1, 'contentHash': made['contentHash']}
    assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key=ANY(%s)',
        (['qyh-context-drift', 'qyh-context-canary', 'qyh-context-rollback', 'qyh-context-forged'],)).fetchone()['n'] == 0
    for name in ('aip_task_run', 'aip_step_run'):
        assert conn.execute('SELECT count(*) AS n FROM ' + name).fetchone()['n'] == intent['initialCounts'][name]
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    assert not conn.execute('SELECT 1 FROM pg_policies WHERE policyname LIKE %s', ('qyh_context_%',)).fetchone()
    assert not conn.execute("SELECT 1 FROM pg_proc WHERE proname='qyh_context_rollback'").fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
snapshots = []
for database in (C.DB, 'aos_meta_head'):
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=database, user='aos_app', row_factory=dict_row) as conn:
        conn.read_only = True
        old = conn.execute('SELECT * FROM aip_production_context_revision WHERE org_id=%s AND project_id=%s AND context_id=%s',
            (*C.SCOPE.key, intent['historicalContextId'])).fetchone()
        rows = {'oldContext': old}
        for name, table, column in (
            ('brief_ref', 'aip_task_brief_revision', 'brief_id'),
            ('evidence_bundle_ref', 'aip_evidence_bundle_revision', 'bundle_id'),
            ('eval_contract_ref', 'aip_eval_contract_revision', 'contract_id'),
            ('responsibility_plan_ref', 'aip_responsibility_plan_revision', 'plan_id')):
            ref = old[name]
            row = conn.execute(f'SELECT * FROM {table} WHERE org_id=%s AND project_id=%s AND {column}=%s AND revision=%s',
                (*C.SCOPE.key, ref['resourceId'], ref['revision'])).fetchone()
            assert row and row['content_hash'] == ref['contentHash'] and row['lifecycle'] == 'frozen'
            rows[name] = row
        snapshots.append(rows)
assert snapshots[0] == snapshots[1]
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata('qyh-restored-pg-20261011') == C.S.D.metadata(C.TARGET)
readback = {'task': intent['task'], 'thread': '01a107a2-e9e4-7670-bc44-1144fa9b27e2',
    'owner': 'codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2',
    'exactNewContextAndReceipt': True, 'failedRequestsNoReceipt': True,
    'fourHistoricalDependencyRowsAndOldContextUnchanged': True,
    'noNewRunOrStep': True, 'temporaryRoleAndPolicyAndFaultTriggerRemoved': True,
    'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True,
    'historicalStoredFreshnessOnly': True, 'currentSignedInstallationVerified': False,
    'fullRestorationAccepted': False, 'originalScriptHash': intent['scriptHash'],
    'readbackScriptHash': hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
    'storeHash': hashlib.sha256((C.ROOT / 'services/aos-api/aos_api/aip_production_contract_store.py').read_bytes()).hexdigest()}
with (R / 'production-context-independent-readback.json').open('x') as stream:
    stream.write(json.dumps(readback, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual_ops = {x['operation']: x['n'] for x in operations}
with (R / 'contract-operation-coverage-r7.json').open('x') as stream:
    stream.write(json.dumps({'catalogOperations': len(catalog),
        'actualCurrentExperimentalReceiptOperations': actual_ops,
        'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual_ops)),
        'productionContextHistoricalFrozenMetadataOnly': True,
        'reviewIssueOrdinaryMediaOnly': True, 'returnPositiveAccepted': False,
        'stageSourceIsLegacyStaticAllowlist': True, 'disclosureReceiptIsDeniedDecisionNotAuthorization': True,
        'bundleRevokeUnissuedGenericOnly': True, 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual_ops),
                  'remainingOperations': len(set(catalog) - set(actual_ops)), 'noWriteReplay': True}))
