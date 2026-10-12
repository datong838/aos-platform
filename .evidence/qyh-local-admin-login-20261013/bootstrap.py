"""Provision the authorized loopback-only human identity service, not AOS runtime."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import subprocess
from uuid import uuid4

ROOT = Path.cwd()
OUT = ROOT / '.evidence/qyh-local-admin-login-20261013'
PRIVATE = Path('/Users/ddt/.aos-local-identities/qyh-20261013')
CONTEXT = 'colima-aos-extension'
IMAGE = 'quay.io/keycloak/keycloak:26.0.2'
NAME = 'qyh-local-identity-20261013'
VOLUME = 'qyh-local-identity-data-20261013'
PORT = 18448

def docker(*args):
    result = subprocess.run(['docker', '--context', CONTEXT, *args],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Docker identity preparation failed; inspect exact operation before retry')
    return result.stdout.strip()

def emit(name, value):
    with (OUT / name).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

def secret_file(path, content):
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600), 'w') as f:
        f.write(content)

assert not (OUT / 'bootstrap-intent.json').exists(), 'Existing bootstrap: reconcile; no resend'
image = json.loads(docker('image', 'inspect', IMAGE))[0]
assert image['RepoDigests'] and image['Id'].startswith('sha256:')
assert not docker('ps', '-a', '--filter', 'name=^/' + NAME + '$', '--format', '{{.ID}}')
assert not docker('volume', 'ls', '--filter', 'name=^' + VOLUME + '$', '--format', '{{.Name}}')
with socket.socket() as listener:
    listener.bind(('127.0.0.1', PORT))
PRIVATE.parent.mkdir(mode=0o700, exist_ok=True)
parent = PRIVATE.parent.lstat()
assert stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
assert stat.S_IMODE(parent.st_mode) == 0o700
PRIVATE.mkdir(mode=0o700, exist_ok=False)
realm = json.loads((ROOT / 'deploy/dev/keycloak/aos-realm.json').read_text())
realm.update(realm='qyh-local', displayName='栖月汇 · 本机管理员登录',
             registrationAllowed=False, resetPasswordAllowed=False,
             editUsernameAllowed=False, sslRequired='none')
client = realm['clients'][0]
client.update(redirectUris=['http://127.0.0.1:18434/auth/callback'],
              webOrigins=['http://127.0.0.1:18434'], fullScopeAllowed=False)
client['attributes']['access.token.lifespan'] = '900'
identifier = str(uuid4())
human_password, bootstrap_password = secrets.token_urlsafe(24), secrets.token_urlsafe(32)
realm['users'] = [{'id': identifier, 'username': 'qyh-owner', 'enabled': True,
    'firstName': '栖月汇', 'lastName': '管理员', 'realmRoles': ['admin'],
    'attributes': {'org_id': ['org-org'], 'project_id': ['dev-project'],
                   'markings': ['public', 'restricted']},
    'credentials': [{'type': 'password', 'value': human_password, 'temporary': True}]}]
secret_file(PRIVATE / 'realm.json', json.dumps(realm, ensure_ascii=False))
secret_file(PRIVATE / 'server.env', 'KEYCLOAK_ADMIN=identity-bootstrap' + chr(10)
    + 'KEYCLOAK_ADMIN_PASSWORD=' + bootstrap_password + chr(10)
    + 'KC_HTTP_ENABLED=true' + chr(10) + 'KC_HOSTNAME_STRICT=false' + chr(10))
secret_file(PRIVATE / 'login.txt', '仅供本人登录，首次登录须修改初始密码。' + chr(10)
    + '入口：http://127.0.0.1:18448/realms/qyh-local/account/' + chr(10)
    + '账号：qyh-owner' + chr(10) + '初始密码：' + human_password + chr(10)
    + '本次恢复审批已经记录，不需要再次审批。' + chr(10))
emit('bootstrap-intent.json', {'context': CONTEXT, 'name': NAME, 'volume': VOLUME,
    'imageId': image['Id'], 'repoDigests': image['RepoDigests'], 'port': PORT,
    'tenant': 'org-org/dev-project', 'humanUsername': 'qyh-owner', 'humanIdentityId': identifier,
    'userAuthenticated': False, 'aosApprovalAlreadyRecorded': True,
    'secretDirectory': str(PRIVATE), 'noAosDataVolumeMutation': True})
docker('volume', 'create', '--label', 'aos.task=qyh-local-admin-login-20261013', VOLUME)
container = docker('run', '-d', '--name', NAME,
    '--label', 'aos.task=qyh-local-admin-login-20261013',
    '--label', 'aos.owner=codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2',
    '--restart', 'unless-stopped', '--memory', '1g', '--user', f'{os.getuid()}:0',
    '-p', f'127.0.0.1:{PORT}:8080', '--env-file', str(PRIVATE / 'server.env'),
    '-v', VOLUME + ':/opt/keycloak/data',
    '-v', str(PRIVATE / 'realm.json') + ':/opt/keycloak/data/import/qyh-realm.json:ro',
    image['Id'], 'start-dev', '--import-realm', '--http-port=8080',
    '--hostname', 'http://127.0.0.1:18448')
emit('bootstrap-terminal.json', {'containerId': container, 'state': 'started_pending_health',
    'userAuthenticated': False, 'aosApiOidcIntegrated': False,
    'runtimeActivated': False, 'eightPagesAccepted': False})
print('Identity container started; human credentials saved privately; public health still pending.')
