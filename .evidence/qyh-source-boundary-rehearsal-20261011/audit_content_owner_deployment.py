"""Read existing Content owners and live deployment; never provision storage."""
import ast
import hashlib
import json
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
import real_contract as C

R = Path(__file__).resolve().parent
out = R / 'content-owner-deployment-result.json'
assert not out.exists(), 'Existing result must be reconciled, not overwritten'
paths = [C.ROOT / 'services/aos-api/aos_api' / p for p in (
    'object_store.py', 'tenant_prefix.py', 'routers/wave_ext.py',
    'aip_budget_reservation_store.py', 'aip_content_draft_store.py')]
trees = {p.name: ast.parse(p.read_text()) for p in paths}
media_globals = {t.id for n in trees['wave_ext.py'].body if isinstance(n, ast.AnnAssign)
                 for t in [n.target] if isinstance(t, ast.Name)}
assert {'_media', '_media_bytes'} <= media_globals
store = next(n for n in trees['aip_budget_reservation_store.py'].body
             if isinstance(n, ast.ClassDef) and n.name == 'AipBudgetReservationStore')
bucket_read = next(n for n in store.body if isinstance(n, ast.FunctionDef) and n.name == '_bucket_row')
assert any(isinstance(n, ast.Constant) and isinstance(n.value, str) and 'SELECT * FROM' in n.value
           for n in ast.walk(bucket_read))
live = {}
for path in ('/v1/health', '/v1/auth/oidc', '/v1/object-store/health'):
    req = Request('http://127.0.0.1:18080' + path, headers={
        'Authorization': 'Bearer dev', 'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'})
    with urlopen(req, timeout=15) as response:
        body = json.load(response)
        keep = {'status', 'ok', 'endpoint', 'bucket', 'detail'} if 'oidc' not in path else {
            'issuer', 'jwksUrls', 'tokenUrlConfigured', 'allowDevToken', 'grantTypes'}
        live[path] = {'status': response.status, 'body': {k: v for k, v in body.items() if k in keep}}
docker = subprocess.check_output([
    'docker', '--context', 'colima-aos-extension', 'ps', '-a',
    '--format', '{{.Names}}\t{{.Image}}\t{{.Status}}'], text=True)
storage_candidates = [line for line in docker.splitlines() if 'minio' in line.lower()]
with C.runtime(C.SCOPE, read_only=True) as conn:
    ledger = conn.execute('SELECT count(*) AS n FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s', C.SCOPE.key).fetchone()
    artifacts = conn.execute('SELECT count(*) AS n FROM aip_artifact WHERE org_id=%s AND project_id=%s AND artifact_type=%s', (*C.SCOPE.key, 'content_draft')).fetchone()
result = {
    'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C.ROOT, text=True).strip(),
    'task': 'qyh-source-boundary-rehearsal-20261011', 'authority': 'AOS-001890',
    'scope': list(C.SCOPE.key), 'liveManagement': live,
    'existingS3AdapterReusable': True, 'existingTenantPrefixReusable': True,
    'mediaDirectoryProcessMemory': True, 'durableContentOwnerConnected': False,
    'storageCandidatesInAuthoritativeDockerContext': storage_candidates,
    'experimentalCloneBudgetBucketCount': ledger['n'],
    'experimentalCloneContentDraftCount': artifacts['n'],
    'countsAreNotCurrentBudgetApproval': True,
    'sourceHashes': {str(p.relative_to(C.ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    'scriptHash': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'databaseWrites': 0, 'objectReads': 0, 'objectWrites': 0, 'provisioning': False,
    'formalLoginConnected': False, 'formalPublisherConnected': False,
    'fullRestorationAccepted': False,
}
with out.open('x') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
    f.write('\n')
print(json.dumps({'objectStore': live['/v1/object-store/health']['body'],
                  'mediaDirectoryProcessMemory': True, 'storageCandidates': storage_candidates,
                  'experimentalLedgerRows': ledger['n'], 'databaseWrites': 0}, ensure_ascii=False))
