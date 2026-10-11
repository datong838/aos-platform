"""Read-only reconciliation of review mutations and the preserved lock RED."""
import ast
import hashlib
import json
import psycopg
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

r = C.R
b = json.loads((r / 'review-issue-finish-business-result.json').read_text())
intent = json.loads((r / 'review-issue-intent.json').read_text())
resolved, opened = b['resolved'], b['openForReturn']
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
    assert store.get_review_issue(C.SCOPE, resolved['issueId'], conn=conn).model_dump(mode='json', by_alias=True) == resolved
    assert store.get_review_issue(C.SCOPE, opened['issueId'], conn=conn).model_dump(mode='json', by_alias=True) == opened
    events = conn.execute('SELECT sequence,event_type,issue_version,payload FROM aip_review_issue_event WHERE org_id=%s AND project_id=%s AND issue_id=%s ORDER BY sequence', (*C.SCOPE.key, resolved['issueId'])).fetchall()
    assert [(x['sequence'], x['event_type'], x['issue_version']) for x in events] == [(1, 'opened', 1), (2, 'resolved', 2)]
    assert len(events[1]['payload']['resolutionRefs']) == 1
    assert events[1]['payload']['resolutionRefs'][0]['resourceType'] == 'Artifact'
    receipts = conn.execute('SELECT operation,idempotency_key,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE %s ORDER BY idempotency_key', (*C.SCOPE.key, 'qyh-review-%')).fetchall()
    assert len(receipts) == 3
    expected = {'qyh-review-create': ('review_issue.create', resolved['issueId'], 1), 'qyh-review-resolve': ('review_issue.resolve', resolved['issueId'], 2), 'qyh-review-open-for-return': ('review_issue.create', opened['issueId'], 1)}
    for row in receipts:
        assert (row['operation'], row['result_ref']['resourceId'], row['result_ref']['version']) == expected[row['idempotency_key']]
    assert conn.execute('SELECT status FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*C.SCOPE.key, intent['existingExperimentalQueuedRun'])).fetchone()['status'] == 'queued'
    assert conn.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s', (*C.SCOPE.key, intent['existingExperimentalQueuedRun'])).fetchone()['n'] == 0
    assert not conn.execute('SELECT 1 FROM aip_return_decision WHERE org_id=%s AND project_id=%s AND issue_id=%s', (*C.SCOPE.key, opened['issueId'])).fetchone()
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
ref = intent['historicalEvalReportRef']
reports = []
for db in (C.DB, 'aos_meta_head'):
    with psycopg.connect(host='127.0.0.1', port=18431, dbname=db, user='aos_app', row_factory=dict_row) as conn:
        conn.read_only = True
        reports.append(conn.execute('SELECT * FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s', (*C.SCOPE.key, ref['resourceId'], ref['revision'])).fetchone())
assert reports[0] == reports[1] and reports[0]['content_hash'] == ref['contentHash']
assert C.S.P.M.fingerprint('qyh-restored-pg-20261011') == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata('qyh-restored-pg-20261011') == C.S.D.metadata(C.TARGET)
readback = {'twoIssuesAndThreeReceiptsExact': True, 'resolutionHasNonemptyExactArtifactRef': True, 'openedResolvedEventsExact': True, 'historicalEvalReportExactCloneRow': True, 'failedRequestsHaveNoReceipt': True, 'queuedRunNoStepsNoReturnDecision': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'timestampWriteExposureRemains': True, 'contentEvalSubjectAccepted': False, 'returnPositiveAccepted': False, 'fullRestorationAccepted': False, 'originalScriptHash': hashlib.sha256((r / 'real_review_issue.py').read_bytes()).hexdigest(), 'finishScriptHash': hashlib.sha256((r / 'finish_review_issue.py').read_bytes()).hexdigest()}
assert readback['originalScriptHash'] == intent['scriptHash']
assert readback['finishScriptHash'] == json.loads((r / 'review-issue-finish-intent.json').read_text())['finishScriptHash']
with (r / 'review-issue-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual = {x['operation']: x['n'] for x in operations}
with (r / 'contract-operation-coverage-r6.json').open('x') as out:
    out.write(json.dumps({'catalogOperations': len(catalog), 'actualCurrentExperimentalReceiptOperations': actual, 'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual)), 'reviewIssueOrdinaryMediaOnly': True, 'returnPositiveAccepted': False, 'stageSourceIsLegacyStaticAllowlist': True, 'disclosureReceiptIsDeniedDecisionNotAuthorization': True, 'bundleRevokeUnissuedGenericOnly': True, 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual), 'remainingOperations': len(set(catalog) - set(actual)), 'noCompletedWriteReplay': True}))
