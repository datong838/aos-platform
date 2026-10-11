"""Load the retained cluster through a restricted maintenance transport.

An existing intent is reconciliation-only. Password material is private and
never included in process arguments, environment, or public evidence.
"""
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
import prepare_volume as P

R = P.R
TARGET = 'qyh-restored-pg-20261011'
LOGIN = 'qyh_restored_api_login'
PORT = 18446
def docker(*args, **kwargs):
    return P.M.run(['docker', '--context', P.M.CTX, *args], **kwargs)
def private_file(path, content):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        stream.write(content)

if __name__ == '__main__':
    assert not (R / 'volume-load-intent.json').exists(), 'Prior intent: reconcile only'
    assert json.loads((R / 'volume-backup-terminal.json').read_text())['outcome'] == 'EXACT647_VOLUME_FRESH_FULL_BACKUP_GREEN'
    assert P.native_identity() == json.loads((R / 'volume-before.json').read_text())['database']
    assert P.M.fingerprint(P.SOURCE) == json.loads((R / 'volume-fingerprint-before.json').read_text())
    assert subprocess.run(['docker', '--context', P.M.CTX, 'inspect', TARGET], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
    password = secrets.token_hex(32)
    hba = P.PRIVATE / 'restored-pg_hba.conf'
    # Retain local maintenance access; all network users except the one
    # restricted login are rejected. The published host port is loopback only.
    private_file(hba, 'local all all trust\nhost aos_meta_head qyh_restored_api_login 0.0.0.0/0 scram-sha-256\nhost all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n')
    # This policy has no secrets; the container postgres user must read it.
    # The enclosing host directory and all credential files remain private.
    os.chmod(hba, 0o644)
    private_file(P.PRIVATE / 'restored.pgpass', f'127.0.0.1:{PORT}:aos_meta_head:{LOGIN}:{password}\n')
    private_file(P.PRIVATE / 'restored-identity.json', json.dumps({'host': '127.0.0.1', 'port': PORT, 'dbname': 'aos_meta_head', 'user': LOGIN, 'pgpassfile': str(P.PRIVATE / 'restored.pgpass')}))
    P.record('volume-load-intent.json', {'source': P.SOURCE, 'target': TARGET, 'volume': P.VOLUME, 'cluster': P.CLUSTER, 'port': PORT, 'login': LOGIN, 'sourceDataDeletion': False, 'phase': 'CREATE_RESTRICTED_LOGIN_THEN_STOP_SOURCE'})
    sql = "BEGIN; SET LOCAL password_encryption='scram-sha-256'; CREATE ROLE " + LOGIN + " LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '" + password + "'; GRANT aos_runtime TO " + LOGIN + "; COMMIT;"
    # Suppress sensitive SQL/error output completely. Any failure is unknown
    # until read-only reconciliation, never a reason to repeat CREATE ROLE.
    proc = subprocess.run(['docker', '--context', P.M.CTX, 'exec', '-i', P.SOURCE, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', 'aos_app', '-d', P.M.DB], input=sql.encode(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    assert proc.returncode == 0, 'Role operation failed: reconcile only'
    del sql, password
    P.record('volume-login-terminal.json', {'login': LOGIN, 'outcome': 'LIMITED_LOGIN_CREATED', 'businessExecutionAuthority': False})
    docker('stop', '--time', '60', P.SOURCE)
    state = json.loads(docker('inspect', '--format', '{{json .State}}', P.SOURCE))
    assert state['Running'] is False and state['Pid'] == 0
    P.record('volume-source-stopped.json', {'running': False, 'pid': 0, 'containerRetained': True})
    cid = docker('run', '--detach', '--name', TARGET, '--publish', f'127.0.0.1:{PORT}:5432', '--mount', f'type=volume,src={P.VOLUME},dst=/var/lib/postgresql/data', '--mount', f'type=bind,src={hba},dst=/etc/qyh/pg_hba.conf,readonly', P.M.IMAGE, 'postgres', '-c', 'hba_file=/etc/qyh/pg_hba.conf').decode().strip()
    P.record('volume-target-created.json', {'id': cid, 'volume': P.VOLUME, 'image': P.M.IMAGE})
    for _ in range(60):
        ready = subprocess.run(['docker', '--context', P.M.CTX, 'exec', TARGET, 'pg_isready', '-U', 'aos_app', '-d', P.M.DB], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if ready:
            break
        time.sleep(0.5)
    assert ready, 'Target not ready: reconcile existing container'
    identity = P.native_identity(TARGET)
    assert identity['cluster'] == P.CLUSTER and identity['schema'] == 'a0v_159' and identity['loginExists'] == 1 and identity['disabledBindings'] is True
    after = P.M.fingerprint(TARGET)
    assert after == json.loads((R / 'volume-fingerprint-before.json').read_text())
    item = json.loads(docker('inspect', '--format', '{"State":{{json .State}},"Ports":{{json .NetworkSettings.Ports}},"Mounts":{{json .Mounts}},"Image":{{json .Image}}}', TARGET))
    assert item['Ports']['5432/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': str(PORT)}]
    assert any(m.get('Name') == P.VOLUME for m in item['Mounts'])
    P.record('volume-load-terminal.json', {'outcome': 'RETAINED647_VOLUME_LOADED_GREEN', 'identity': identity, 'container': item, 'fingerprintsExact': True, 'originalContainerRetainedStopped': True, 'apiAttached': False, 'eightWorkbenchesVisible': False})
    print('RETAINED647_VOLUME_LOADED_GREEN')
