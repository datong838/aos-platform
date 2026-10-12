"""Resume known-failed username edit without replaying existing successful intents."""
import importlib.util
import json
from pathlib import Path
import stat

path = Path('.evidence/qyh-local-admin-login-20261013/configure_human_account.py')
spec = importlib.util.spec_from_file_location('identity_account_http', path)
http = importlib.util.module_from_spec(spec)
spec.loader.exec_module(http)
assert not (http.OUT / 'human-username-r2-intent.json').exists(), 'Existing continuation; reconcile only'
supplied = json.loads((http.PRIVATE / 'user-password-input.json').read_text())
env = dict(line.split('=', 1) for line in (http.PRIVATE / 'server.env').read_text().splitlines() if '=' in line)
token = http.call('/realms/master/protocol/openid-connect/token', method='POST', form=True,
    body={'client_id': 'admin-cli', 'grant_type': 'password',
          'username': env['KEYCLOAK_ADMIN'], 'password': env['KEYCLOAK_ADMIN_PASSWORD']})['access_token']
identifier = json.loads((http.PRIVATE / 'realm-scoped.json').read_text())['users'][0]['id']
user_path = '/admin/realms/qyh-local/users/' + identifier
current = http.call(user_path, token=token)
assert current['username'] == 'qyh-owner'
assert current['attributes']['org_id'] == ['org-org']
assert current['attributes']['project_id'] == ['dev-project']
realm = http.call('/admin/realms/qyh-local', token=token)
editable = realm['editUsernameAllowed']
assert editable is False
http.emit('human-username-r2-intent.json', {'humanUserId': identifier,
    'currentUsername': current['username'], 'requestedUsername': supplied['username'],
    'originalEditUsernameAllowed': editable, 'temporaryPolicyChange': True,
    'noNewHumanOrRole': True, 'noAosDataMutation': True})
http.call('/admin/realms/qyh-local', method='PUT', token=token,
          body={'realm': 'qyh-local', 'editUsernameAllowed': True})
try:
    updated = dict(current)
    updated['username'] = supplied['username']
    updated['requiredActions'] = [a for a in current.get('requiredActions', []) if a != 'UPDATE_PASSWORD']
    http.call(user_path, method='PUT', body=updated, token=token)
finally:
    http.call('/admin/realms/qyh-local', method='PUT', token=token,
              body={'realm': 'qyh-local', 'editUsernameAllowed': editable})
after = http.call(user_path, token=token)
assert after['username'] == supplied['username'] and after['attributes'] == current['attributes']
assert http.call('/admin/realms/qyh-local', token=token)['editUsernameAllowed'] is False
http.emit('human-username-r2-terminal.json', {'humanUserId': identifier,
    'username': after['username'], 'tenantPreserved': True, 'usernamePolicyRestored': True})
assert not (http.OUT / 'human-password-intent.json').exists()
http.emit('human-password-intent.json', {'humanUserId': identifier,
    'username': after['username'], 'operation': 'original reset-password',
    'temporary': False, 'approvalAlreadyRecorded': True, 'passwordIncludedInEvidence': False})
http.call(user_path + '/reset-password', method='PUT', token=token,
    body={'type': 'password', 'value': supplied['password'], 'temporary': False})
verified = http.call(user_path, token=token)
assert verified['username'] == supplied['username'] and verified['attributes'] == current['attributes']
assert 'UPDATE_PASSWORD' not in verified.get('requiredActions', [])
roles = http.call(user_path + '/role-mappings/realm', token=token)
assert 'admin' in {r['name'] for r in roles}
(http.PRIVATE / 'login.txt').write_text('入口：http://127.0.0.1:18448/realms/qyh-local/account/' + chr(10)
    + '账号：' + supplied['username'] + chr(10) + '密码：' + supplied['password'] + chr(10)
    + '本次恢复审批已经记录，无需再次审批。' + chr(10))
assert stat.S_IMODE((http.PRIVATE / 'login.txt').stat().st_mode) == 0o600
http.emit('human-password-terminal.json', {'humanUserId': identifier,
    'username': verified['username'], 'passwordUpdateCompleted': True,
    'tenantAndAdminRolePreserved': True, 'humanAuthenticatedByAgent': False,
    'approvalAlreadyRecorded': True, 'aosApiIntegrated': False})
print('Requested human credentials configured through original IdP; tenant/admin preserved; approval unchanged.')
