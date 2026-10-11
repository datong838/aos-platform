"""Read-only verification of actual revocation and denied disclosure receipts."""
import ast
import hashlib
import json
import psycopg
from psycopg.rows import dict_row
import real_contract as C
from aos_api.aip_production_contract_store import AipProductionContractStore

r = C.R
b = json.loads((r / 'evidence-control-business-result.json').read_text())
ref = b['evidenceRef']
with C.runtime(C.SCOPE, read_only=True) as conn:
    store = AipProductionContractStore(lambda scope: C.runtime(scope, read_only=True))
    decision = store.get_evidence_disclosure(C.SCOPE, b['decisionId'], conn=conn, markings=['public'], enforce_current_policy=True)
    assert decision.granted_level is None and decision.display_payload == {}
    assert not decision.redaction_receipt['bodyReturned'] and 'EVIDENCE_REVOKED' in decision.reasons
    revoked = conn.execute('SELECT * FROM aip_evidence_revoke_event WHERE event_id=%s', (b['revokeEventId'],)).fetchone()
    assert (revoked['evidence_id'], revoked['revision'], revoked['content_hash']) == (ref['resourceId'], ref['revision'], ref['contentHash'])
    receipts = conn.execute("SELECT operation,result_ref FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key IN ('qyh-revoke-create','qyh-disclosure-create') ORDER BY operation", C.SCOPE.key).fetchall()
    assert len(receipts) == 2
    actual = {x['operation']: x['result_ref'] for x in receipts}
    assert actual['evidence.revoke'] == {'resourceType': 'EvidenceRevocation', 'resourceId': b['revokeEventId'], 'revision': 1, 'contentHash': ref['contentHash']}
    assert actual['evidence_disclosure.resolve'] == {'resourceType': 'EvidenceDisclosureDecision', 'resourceId': b['decisionId'], 'revision': 1, 'contentHash': decision.decision_hash}
    assert conn.execute("SELECT count(*) AS n FROM aip_production_contract_receipt WHERE idempotency_key IN ('qyh-revoke-rollback','qyh-disclosure-rollback','qyh-revoke-canary','qyh-revoke-drift')").fetchone()['n'] == 0
    assert conn.execute('SELECT count(*) AS n FROM aip_evidence_revoke_event WHERE evidence_id=%s AND content_hash=%s', (ref['resourceId'], ref['contentHash'])).fetchone()['n'] == 1
    assert not conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (C.ROLE,)).fetchone()
    operations = conn.execute("SELECT operation,count(*) AS n FROM aip_production_contract_receipt WHERE created_by='clone:test' GROUP BY operation ORDER BY operation").fetchall()
    payload = conn.execute('SELECT payload FROM aip_evidence WHERE evidence_id=%s', (ref['resourceId'],)).fetchone()['payload']
with psycopg.connect(host='127.0.0.1', port=18431, dbname='aos_meta_head', user='aos_app', row_factory=dict_row) as original:
    original.read_only = True
    assert original.execute('SELECT payload FROM aip_evidence WHERE evidence_id=%s', (ref['resourceId'],)).fetchone()['payload'] == payload
source = 'qyh-restored-pg-20261011'
assert C.S.P.M.fingerprint(source) == C.S.P.M.fingerprint(C.TARGET)
assert C.S.D.metadata(source) == C.S.D.metadata(C.TARGET)
readback = {'twoReceiptsExact': True, 'oneRevokeEventOnly': True, 'originalCurrentPolicyReadDeniedNoBody': True, 'failedRequestsHaveNoReceipt': True, 'temporaryRoleRemoved': True, 'sourceAndOriginalClone647DataExact': True, 'allOriginalMetadataExact': True, 'actualDisclosureAuthorization': False, 'fullRestorationAccepted': False, 'scriptHash': hashlib.sha256((r / 'real_evidence_control.py').read_bytes()).hexdigest()}
with (r / 'evidence-control-independent-readback.json').open('x') as out:
    out.write(json.dumps(readback, indent=2) + '\n')
tree = ast.parse(C.PROTOCOL.read_text())
catalog = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'CONTRACT_OPERATIONS' for t in n.targets))
actual = {x['operation']: x['n'] for x in operations}
with (r / 'contract-operation-coverage-r3.json').open('x') as out:
    out.write(json.dumps({'catalogOperations': len(catalog), 'actualCurrentExperimentalReceiptOperations': actual, 'remainingWithoutCurrentPositiveReceipt': sorted(set(catalog) - set(actual)), 'disclosureReceiptIsDeniedDecisionNotAuthorization': True, 'allStoreCompatibilityAccepted': False}, indent=2) + '\n')
print(json.dumps({'independentReadback': True, 'receiptOperationCoverage': len(actual), 'remainingOperations': len(set(catalog) - set(actual))}))
