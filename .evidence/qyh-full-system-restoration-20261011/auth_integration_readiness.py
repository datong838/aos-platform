"""Public authentication contract and existing dev scope, without issuing credentials."""
import hashlib
import importlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

TASK = Path(__file__).resolve().parent
ROOT = TASK.parents[1]
OUTPUT = TASK / 'auth-integration-readiness-r2.json'


def get(path, headers=None):
    request = Request('http://127.0.0.1:18080' + path, headers=headers or {})
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def inspect():
    status, auth = get('/v1/auth/oidc')
    assert status == 200
    mode = 'development' if auth.get('allowDevToken') and auth.get('grantTypes') == ['dev'] else 'requires_review'
    status, me = get('/v1/me', {'Authorization': 'Bearer dev',
        'X-Org-Id': 'org-org', 'X-Project-Id': 'dev-project'})
    assert status == 200
    # No subject, personal details, tokens or public key material are persisted.
    assert (me.get('orgId'), me.get('projectId')) == ('org-org', 'dev-project')
    assert me.get('orgName') == '栖月汇商贸有限公司'
    return {'authenticationMode': mode,
        'externalJwksConfigured': bool(auth.get('jwksUrls')),
        'enterprisePasswordGrantConfigured': bool(auth.get('tokenUrlConfigured')),
        'advertisedJwksConfigured': auth.get('jwksConfigured'),
        'advertisedGrantTypes': auth.get('grantTypes'),
        'existingDevMeStatus': status,
        'meResponseKeys': sorted(me),
        'tenantHeaders': ['org-org', 'dev-project'],
        'verifiedTenant': {'orgId': me['orgId'], 'projectId': me['projectId'],
            'orgName': me['orgName'], 'tokenKind': me.get('tokenKind')},
        'formalLoginProven': False, 'independentPublisherProven': False}


if __name__ == '__main__':
    assert not OUTPUT.exists(), 'Existing evidence: read and reconcile'
    sys.path.insert(0, str(ROOT / 'scripts'))
    entry = importlib.import_module('a0v_qyh_restored_http')
    entry.require_api_source_candidate(TASK / 'management-api-frozen-r4.json')
    identity = entry.preflight(TASK / 'private/restored-identity.json')
    first, second = inspect(), inspect()
    assert first == second
    report = {'observedAt': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'volume': identity['volume'], 'observations': first, 'independentReadsStable': True,
        'databaseWrites': 0, 'tokensIssued': 0, 'publishAttempts': 0,
        'eightWorkshopsRestored': False,
        'sourceSha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with OUTPUT.open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps(report, ensure_ascii=False))
