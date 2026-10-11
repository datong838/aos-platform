"""Read-only independent reconciliation; never repeat business calls."""
import ast
import hashlib
import json
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

r = C.R
b = json.loads((r / 'artifact-family-business-result.json').read_text())
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
    family = store.get_artifact_family(C.SCOPE, b['familyId'], conn=conn)
    assert family.version == b['familyVersion'] == 4
    assert len(family.members) == 2
    rows = conn.execute("SELECT operation,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key LIKE 'qyh-family-%%' ORDER BY operation", C.SCOPE.key).fetchall()
    assert len(rows) == 6
    assert {x['operation'] for x in rows} == {'artifact_family.register', 'artifact_family.member.attach', 'artifact_family.candidate.select', 'artifact_relation.create', 'review_rule.register'}
    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key IN ('qyh-family-rollback','qyh-family-stale','qyh-family-cycle')").fetchone()['n'] == 0
    assert conn.execute('SELECT status FROM aip_task_run WHERE run_id=%s', (b['runId'],)).fetchone()['status'] == 'queued'
    assert conn.execute('SELECT count(*) AS n FROM aip_step_run WHERE run_id=%s', (b['runId'],)).fetchone()['n'] == 0
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    selection = conn.execute('SELECT selected_artifact_id,selected_content_hash,candidate_refs FROM aip_artifact_family_selection_revision WHERE family_id=%s', (b['familyId'],)).fetchone()
    assert (selection['selected_artifact_id'], selection['selected_content_hash']) == (b['fixtures'][2]['artifactId'], b['fixtures'][2]['contentHash'])
    assert len(selection['candidate_refs']) == 2
    assert conn.execute('SELECT count(*) AS n FROM aip_artifact_relation WHERE from_artifact_id=%s OR from_artifact_id=%s', (b['fixtures'][1]['artifactId'], b['fixtures'][2]['artifactId'])).fetchone()['n'] == 3
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
source = 'qyh-restored-pg-20261011'
assert C.S.P.M.fingerprint(source) == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata(source) == C.S.D.metadata(C.TARGET)
readback = {'receipts': rows, 'actualOriginalFamilyReaderAccepted': True, 'exactCandidateSelectionMatched': True, 'threeRelationsOnly': True, 'failedRequestsHaveNoReceipt': True, 'runQueuedAndNoStepRun': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'formalPolicyOrRenderedBusinessOutput': False, 'fullRestorationAccepted': False, 'scriptHash': hashlib.sha256((r / 'real_artifact_family.py').read_bytes()).hexdigest()}
with (r / 'artifact-family-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, default=str, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual = {x['operation']: x['n'] for x in operations}
with (r / 'contract-operation-coverage-r2.json').open('x') as out:
    out.write(json.dumps({'catalogOperations': len(catalog), 'actualCurrentExperimentalReceiptOperations': actual, 'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual)), 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'positiveOperations': len(actual), 'remainingOperations': len(set(catalog) - set(actual))}))
