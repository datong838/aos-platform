"""Set the explicitly supplied human credentials using the existing IdP admin API."""
import json
from pathlib import Path
import stat
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

OUT = Path('.evidence/qyh-local-admin-login-20261013')
PRIVATE = Path('/Users/ddt/.aos-local-identities/qyh-20261013')
BASE = 'http://127.0.0.1:18448'
opener = build_opener(ProxyHandler({}))

def emit(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

def call(path, *, method='GET', body=None, token=None, form=False):
    data = None if body is None else (urlencode(body).encode() if form else json.dumps(body).encode())
    headers = {'Content-Type': 'application/x-www-form-urlencoded' if form else 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with opener.open(Request(BASE + path, data=data, headers=headers, method=method), timeout=10) as r:
            content = r.read(65537)
            if len(content) > 65536:
                raise RuntimeError('Identity response too large')
            return json.loads(content) if content else None
    except HTTPError as exc:
        raise RuntimeError('Identity API returned HTTP ' + str(exc.code)) from None

def main():
    assert not (OUT / 'human-username-intent.json').exists(), 'Existing attempt; reconcile before retry'
    credential = PRIVATE / 'user-password-input.json'
    assert stat.S_IMODE(credential.stat().st_mode) == 0o600
    supplied = json.loads(credential.read_text())
    assert supplied['username'] == 'datong838' and isinstance(supplied['password'], str) and supplied['password']
    realm = json.loads((PRIVATE / 'realm-scoped.json').read_text())
    human = realm['users'][0]
    identifier = human['id']
    server_env = dict(line.split('=', 1) for line in (PRIVATE / 'server.env').read_text().splitlines() if '=' in line)
    auth = call('/realms/master/protocol/openid-connect/token', method='POST', form=True,
        body={'client_id': 'admin-cli', 'grant_type': 'password',
              'username': server_env['KEYCLOAK_ADMIN'], 'password': server_env['KEYCLOAK_ADMIN_PASSWORD']})
    token = auth['access_token']
    path = '/admin/realms/qyh-local/users/' + identifier
    current = call(path, token=token)
    assert current['username'] == 'qyh-owner'
    if 'attributes' not in current:
        users = call('/admin/realms/qyh-local/users?max=20', token=token)
        assert {u['id'] for u in users} == {identifier}
        profile = call('/admin/realms/qyh-local/users/profile', token=token)
        attributes = list(profile['attributes'])
        names = {a['name'] for a in attributes}
        assert not names.intersection({'org_id', 'project_id', 'markings'})
        for name, values in [('org_id', ['org-org']), ('project_id', ['dev-project']),
                             ('markings', ['public', 'restricted'])]:
            attributes.append({'name': name, 'displayName': name,
                'permissions': {'view': ['admin'], 'edit': ['admin']},
                'multivalued': name == 'markings',
                'validations': {'options': {'options': values}}})
        configured = dict(profile)
        configured['attributes'] = attributes
        emit('human-profile-intent.json', {'realm': 'qyh-local', 'humanUserId': identifier,
            'attributeNames': ['org_id', 'project_id', 'markings'],
            'permissions': 'admin-only', 'preservedOriginalFieldNames': sorted(names)})
        call('/admin/realms/qyh-local/users/profile', method='PUT', body=configured, token=token)
        verified = call('/admin/realms/qyh-local/users/profile', token=token)
        for name in ['org_id', 'project_id', 'markings']:
            field = next(a for a in verified['attributes'] if a['name'] == name)
            assert field['permissions'] == {'view': ['admin'], 'edit': ['admin']}
        emit('human-profile-terminal.json', {'declaredAdminOnlyTenantAttributes': True,
            'originalFieldsPreserved': names <= {a['name'] for a in verified['attributes']}})
        enriched = dict(current)
        enriched['attributes'] = {'org_id': ['org-org'], 'project_id': ['dev-project'],
                                  'markings': ['public', 'restricted']}
        emit('human-tenant-intent.json', {'humanUserId': identifier,
            'tenant': 'org-org/dev-project', 'markings': ['public', 'restricted']})
        call(path, method='PUT', body=enriched, token=token)
        current = call(path, token=token)
        emit('human-tenant-terminal.json', {'humanUserId': identifier,
            'tenantAttributesRecorded': current.get('attributes') == enriched['attributes']})
    assert current['attributes']['org_id'] == ['org-org']
    assert current['attributes']['project_id'] == ['dev-project']
    roles = call(path + '/role-mappings/realm', token=token)
    assert 'admin' in {r['name'] for r in roles}
    emit('human-username-intent.json', {'humanUserId': identifier, 'newUsername': supplied['username'],
        'sameHumanIdentity': True, 'authorizationSource': 'explicit current human user instruction',
        'operatorIdentity': 'existing identity-bootstrap machine administrator',
        'humanAuthenticatedByAgent': False, 'passwordIncludedInEvidence': False})
    updated = dict(current)
    updated['username'] = supplied['username']
    updated['requiredActions'] = [a for a in current.get('requiredActions', []) if a != 'UPDATE_PASSWORD']
    call(path, method='PUT', body=updated, token=token)
    observed = call(path, token=token)
    assert observed['username'] == supplied['username']
    emit('human-username-terminal.json', {'humanUserId': identifier, 'username': observed['username'],
        'tenantAttributesPreserved': observed['attributes'] == current['attributes']})
    emit('human-password-intent.json', {'humanUserId': identifier, 'username': observed['username'],
        'operation': 'original Keycloak reset-password', 'temporary': False,
        'approvalAlreadyRecorded': True, 'passwordIncludedInEvidence': False})
    call(path + '/reset-password', method='PUT', token=token,
         body={'type': 'password', 'value': supplied['password'], 'temporary': False})
    after = call(path, token=token)
    assert after['username'] == supplied['username'] and after['attributes'] == current['attributes']
    assert 'UPDATE_PASSWORD' not in after.get('requiredActions', [])
    after_roles = call(path + '/role-mappings/realm', token=token)
    assert 'admin' in {r['name'] for r in after_roles}
    handoff = '入口：http://127.0.0.1:18448/realms/qyh-local/account/' + chr(10)
    handoff += '账号：' + supplied['username'] + chr(10) + '密码：' + supplied['password'] + chr(10)
    handoff += '当前恢复审批已经记录，不需重复审批；AOS接线另行推进。' + chr(10)
    (PRIVATE / 'login.txt').write_text(handoff)
    assert stat.S_IMODE((PRIVATE / 'login.txt').stat().st_mode) == 0o600
    emit('human-password-terminal.json', {'humanUserId': identifier, 'username': after['username'],
        'passwordUpdateCompleted': True, 'adminRolePreserved': True, 'tenantPreserved': True,
        'approvalAlreadyRecorded': True, 'humanAuthenticatedByAgent': False,
        'aosApiOidcIntegrated': False, 'runtimeActivated': False})
    print('Requested human username and password configured; no credentials printed; approval unchanged.')


if __name__ == '__main__':
    main()
