"""Copy the private import through Docker's supported stream, not a host bind."""
import json
import os
from pathlib import Path
import subprocess

OUT = Path('.evidence/qyh-local-admin-login-20261013')
PRIVATE = Path('/Users/ddt/.aos-local-identities/qyh-20261013')
NAME = 'qyh-local-identity-20261013'

def docker(*args):
    r = subprocess.run(['docker', '--context', 'colima-aos-extension', *args],
                       capture_output=True, text=True, timeout=30)
    if r.returncode:
        raise RuntimeError('Identity repair failed; reconcile existing container before any retry')
    return r.stdout.strip()

assert not (OUT / 'startup-r3-intent.json').exists(), 'Existing attempt; do not resend'
old = json.loads(docker('inspect', NAME))[0]
assert not old['State']['Running'] and old['State']['ExitCode'] == 1
assert old['Config']['Labels']['aos.task'] == 'qyh-local-admin-login-20261013'
assert not docker('ps', '-a', '--filter', 'name=^/' + NAME + '-startup-r2$', '--format', '{{.ID}}')
with (OUT / 'startup-r3-intent.json').open('x') as f:
    json.dump({'oldContainerId': old['Id'], 'retainAs': NAME + '-startup-r2',
               'sameIdentityVolumeAndCredentials': True, 'transfer': 'docker cp -a',
               'noAosDatabaseMutation': True}, f, indent=2)
docker('rename', NAME, NAME + '-startup-r2')
command = '''set -eu
target=/opt/keycloak/data/import/qyh-realm.json
if test -d "$target"; then
  test -z "$(ls -A "$target")"
  test ! -e /opt/keycloak/data/import/qyh-realm-invalid-directory-r2
  mv "$target" /opt/keycloak/data/import/qyh-realm-invalid-directory-r2
fi
exec /opt/keycloak/bin/kc.sh start-dev --import-realm --http-port=8080 --hostname http://127.0.0.1:18448
'''
container = docker('create', '--name', NAME,
    '--label', 'aos.task=qyh-local-admin-login-20261013',
    '--label', 'aos.owner=codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2',
    '--restart', 'no', '--memory', '768m', '--user', f'{os.getuid()}:0',
    '-p', '127.0.0.1:18448:8080', '--env-file', str(PRIVATE / 'server-low-memory.env'),
    '-v', 'qyh-local-identity-data-20261013:/opt/keycloak/data',
    '--entrypoint', '/bin/sh', old['Image'], '-c', command)
docker('cp', '-a', str(PRIVATE / 'realm.json'),
       NAME + ':/opt/keycloak/data/import/qyh-realm-v3.json')
docker('start', NAME)
with (OUT / 'startup-r3-terminal.json').open('x') as f:
    json.dump({'containerId': container, 'startCompleted': True,
        'healthAccepted': False, 'humanAuthenticated': False,
        'aosApiOidcIntegrated': False, 'runtimeActivated': False}, f, indent=2)
print('r3 identity candidate started with exact private Realm stream; health pending.')
