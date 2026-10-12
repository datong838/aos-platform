"""Bounded real login and original AOS verification, without modifying live API."""
import json
import os
from pathlib import Path
import stat
import sys
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path.cwd()
OUT = ROOT / '.evidence/qyh-local-admin-login-20261013'
PRIVATE = Path('/Users/ddt/.aos-local-identities/qyh-20261013')
BASE = 'http://127.0.0.1:18448/realms/qyh-local'
ATTEMPT = 'r4' if sys.argv[1:] == ['--attempt-r4'] else ('r3' if sys.argv[1:] == ['--attempt-r3'] else ('r2' if sys.argv[1:] == ['--attempt-r2'] else 'r1'))
INTENT = f'credential-verification-{ATTEMPT}-intent.json'
TERMINAL = f'credential-verification-{ATTEMPT}-terminal.json'
LOGOUT = f'credential-test-{ATTEMPT}-session-logout.json'
assert not (OUT / INTENT).exists() and not (ATTEMPT == 'r1' and (OUT / 'credential-verification-intent.json').exists()), 'Existing login test; reconcile session before retry'
credential = PRIVATE / 'user-password-input.json'
assert stat.S_IMODE(credential.stat().st_mode) == 0o600
supplied = json.loads(credential.read_text())
human_id = json.loads((PRIVATE / 'realm-scoped.json').read_text())['users'][0]['id']
os.environ.update({'AOS_DOTENV_DISABLED': '1', 'AOS_AUTH_ALLOW_DEV': '0',
    'AOS_AUTH_EXTERNAL_ONLY': '1', 'AOS_OIDC_ISSUER': BASE,
    'AOS_OIDC_AUDIENCE': 'aos-api', 'AOS_OIDC_JWKS_URL': BASE + '/protocol/openid-connect/certs',
    'AOS_OIDC_TOKEN_URL': BASE + '/protocol/openid-connect/token', 'AOS_OIDC_CLIENT_ID': 'aos-api', 'AOS_OIDC_LEEWAY_SECONDS': '2'})
sys.path.insert(0, str(ROOT / 'services/aos-api'))
from aos_api.oidc import issue_password_token
from aos_api.auth import resolve_principal
from aos_api.errors import ApiError

def emit(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

emit(INTENT, {'username': supplied['username'],
    'humanIdentityId': human_id, 'realm': 'qyh-local', 'operator': 'authorized credential self-test',
    'noInteractiveHumanLoginClaim': True, 'noLiveApiEnvironmentChange': True})
tokens = issue_password_token(username=supplied['username'], password=supplied['password'])
try:
    principal = resolve_principal(token=tokens['accessToken'],
        header_org='org-org', header_project='dev-project')
    assert principal.subject == human_id and principal.token_kind == 'oidc'
    assert principal.org_id == 'org-org' and principal.project_id == 'dev-project'
    assert 'admin' in principal.roles and {'public', 'restricted'} <= set(principal.markings)
    rejected = []
    for name, token, org, project in [
        ('crossOrg', tokens['accessToken'], 'dev-org', 'dev-project'),
        ('crossProject', tokens['accessToken'], 'org-org', 'other-project'),
        ('devToken', 'dev', 'org-org', 'dev-project'),
    ]:
        try:
            resolve_principal(token=token, header_org=org, header_project=project)
        except ApiError:
            rejected.append(name)
        else:
            raise AssertionError('Original identity boundary did not reject ' + name)
    emit(TERMINAL, {'username': supplied['username'],
        'humanIdentityId': human_id, 'credentialsAccepted': True,
        'originalAosRsaVerificationPassed': True, 'tenant': 'org-org/dev-project',
        'adminRoleVerified': True, 'markingsVerified': True, 'rejected': rejected,
        'interactiveHumanLoginObserved': False, 'liveApiIntegrated': False,
        'aosDatabaseWrites': 0, 'runtimeActivated': False})
finally:
    refresh = tokens.get('refreshToken')
    assert refresh, 'No refresh token; reconcile only this new auth session'
    opener = build_opener(ProxyHandler({}))
    body = urlencode({'client_id': 'aos-api', 'refresh_token': refresh}).encode()
    with opener.open(Request(BASE + '/protocol/openid-connect/logout', data=body,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST'), timeout=10) as r:
        assert r.status == 204
    emit(LOGOUT, {'username': supplied['username'],
        'onlyNewSelfTestSessionLoggedOut': True, 'otherSessionsUntouched': True})
print('User credentials and original AOS verifier passed; tenant/dev negative gates passed; test session logged out.')
