"""Independent readback of committed Eval transaction, without any replay."""
import ast
import hashlib
import json
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

R = C.R
intent = json.loads((R / 'eval-freeze-intent.json').read_text())
result = json.loads((R / 'eval-freeze-business-result.json').read_text())
assert intent['scriptHash'] == hashlib.sha256((R / 'real_eval_freeze.py').read_bytes()).hexdigest()
store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
with C.runtime(C.SCOPE, read_only=True) as conn:
    for label in ('revised', 'frozen'):
        expected = result[label]
        actual = store.get_eval_contract(C.SCOPE, expected['contractId'], expected['revision'], conn=conn)
        # Historical revision projection carries the current head's version.
        expected = dict(expected, version=4)
        assert actual.model_dump(mode='json', by_alias=True) == expected
    receipts = conn.execute("SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key=ANY(%s) ORDER BY idempotency_key",
        (*C.SCOPE.key, ['qyh-eval-freeze-revise', 'qyh-eval-freeze-commit'])).fetchall()
    assert len(receipts) == 2
    for receipt in receipts:
        label = 'revised' if receipt['operation'] == 'eval_contract.revise' else 'frozen'
        made = result[label]
        assert receipt['operation'] in {'eval_contract.revise', 'eval_contract.freeze'}
        assert receipt['result_ref'] == {'resourceType': 'EvalContractRevision', 'resourceId': made['contractId'],
            'revision': made['revision'], 'contentHash': made['contentHash']}
    assert conn.execute('SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key=ANY(%s)',
        (['qyh-eval-freeze-missing', 'qyh-eval-freeze-stale', 'qyh-eval-freeze-canary',
          'qyh-eval-freeze-rollback', 'qyh-eval-freeze-frozen', 'qyh-eval-freeze-forged'],)).fetchone()['n'] == 0
    for table in ('aip_task_run', 'aip_step_run'):
        assert conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] == intent['initialCounts'][table]
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    assert not conn.execute('SELECT 1 FROM pg_policies WHERE policyname LIKE %s', ('qyh_eval_freeze_%',)).fetchone()
    assert not conn.execute("SELECT 1 FROM pg_proc WHERE proname='qyh_eval_freeze_rollback'").fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()

snapshots = []
for database in (C.DB, 'aos_meta_head'):
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=database, user='aos_app', row_factory=dict_row) as conn:
        conn.read_only = True
        old = conn.execute('SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=2',
            (*C.SCOPE.key, intent['historicalContractId'])).fetchone()
        assert old and old['lifecycle'] == 'frozen'
        suite = old['suite_ref']
        suite_row = conn.execute('SELECT * FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s AND revision=%s',
            (*C.SCOPE.key, suite['resourceId'], suite['revision'])).fetchone()
        assert suite_row and suite_row['content_hash'] == suite['contentHash']
        publication = conn.execute('SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND event_id=%s',
            (*C.SCOPE.key, old['publication_ref']['resourceId'])).fetchone()
        assert publication
        events = conn.execute('SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND publication_id=%s ORDER BY occurred_at,event_id',
            (*C.SCOPE.key, publication['publication_id'])).fetchall()
        assert events[-1]['event_type'] == 'published'
        gate = conn.execute('SELECT * FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s',
            (*C.SCOPE.key, old['release_gate_ref']['resourceId'])).fetchone()
        assert gate and gate['status'] == 'passed' and gate['decision_hash'] == old['release_gate_ref']['contentHash']
        # Include the preexisting experimental revisions: no rewriting old blocked results.
        previous = conn.execute('SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision<=2 ORDER BY revision',
            (*C.SCOPE.key, intent['experimentalContractId'])).fetchall() if database == C.DB else None
        if previous is not None:
            assert len(previous) == 2 and all(x['publication_ref'] is None and x['release_gate_ref'] is None for x in previous)
        snapshots.append({'contract': old, 'suite': suite_row, 'publicationEvents': events, 'gate': gate})
assert snapshots[0] == snapshots[1]
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata('qyh-restored-pg-20261011') == C.S.D.metadata(C.TARGET)
readback = {'task': intent['task'], 'thread': '01a107a2-e9e4-7670-bc44-1144fa9b27e2',
    'exactNewEvalRevisionsAndTwoReceipts': True, 'failedRequestsNoReceipt': True,
    'oldEvalAndSuiteAndCompletePublicationEventStreamAndGateExact': True,
    'previousBlockedExperimentalRevisionsRetained': True, 'noNewRunOrStep': True,
    'temporaryRolePoliciesAndFaultTriggerRemoved': True,
    'originalAndCurrent647DataExact': True, 'allOriginalMetadataExact': True,
    'historicalMetadataOnly': True, 'formalLoginConnected': False,
    'formalPublisherConnected': False, 'fullRestorationAccepted': False,
    'originalScriptHash': intent['scriptHash'],
    'readbackScriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'storeHash': hashlib.sha256((C.ROOT / 'services/aos-api/aos_api/aip_production_contract_store.py').read_bytes()).hexdigest()}
with (R / 'eval-freeze-independent-readback.json').open('x') as stream:
    stream.write(json.dumps(readback, indent=2)+'\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual_ops = {x['operation']: x['n'] for x in operations}
previous_coverage = json.loads((R / 'contract-operation-coverage-r7.json').read_text())
coverage = dict(previous_coverage, actualCurrentExperimentalReceiptOperations=actual_ops,
    remainingWithoutCurrentPositiveReceipt=sorted(set(catalog)-set(actual_ops)),
    evalFreezeHistoricalPublicationMetadataOnly=True)
with (R / 'contract-operation-coverage-r8.json').open('x') as stream:
    stream.write(json.dumps(coverage, indent=2)+'\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual_ops),
    'remainingOperations': len(set(catalog)-set(actual_ops)), 'noWriteReplay': True}))
