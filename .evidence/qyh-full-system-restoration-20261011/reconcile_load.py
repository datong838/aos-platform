"""Continue the proven no-container outcome, without replaying role writes."""
import json
import subprocess
import time
import prepare_volume as P
from load_volume import TARGET, LOGIN, PORT, docker

if __name__ == '__main__':
    assert not (P.R / 'volume-create-reconciled-intent.json').exists(), 'Existing attempt: reconcile only'
    assert json.loads((P.R / 'volume-login-terminal.json').read_text())['outcome'] == 'LIMITED_LOGIN_CREATED'
    source = json.loads(docker('inspect', '--format', '{{json .State}}', P.SOURCE))
    assert source['Running'] is False and source['Pid'] == 0 and source['ExitCode'] == 0
    assert subprocess.run(['docker', '--context', P.M.CTX, 'inspect', TARGET], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0
    P.record('volume-load-failure-reconciled.json', {'originalRunExit': 125, 'targetExists': False, 'sourceStoppedCleanly': True, 'reason': 'Colima host bind path unavailable', 'roleReplay': False})
    P.record('volume-create-reconciled-intent.json', {'target': TARGET, 'volume': P.VOLUME, 'cluster': P.CLUSTER, 'port': PORT, 'hbaTransfer': 'container copy before start', 'roleWrites': False})
    cid = docker('create', '--name', TARGET, '--publish', f'127.0.0.1:{PORT}:5432', '--mount', f'type=volume,src={P.VOLUME},dst=/var/lib/postgresql/data', P.M.IMAGE, 'postgres', '-c', 'hba_file=/etc/qyh_pg_hba.conf').decode().strip()
    P.record('volume-target-created.json', {'id': cid, 'volume': P.VOLUME, 'image': P.M.IMAGE})
    docker('cp', str(P.PRIVATE / 'restored-pg_hba.conf'), TARGET + ':/etc/qyh_pg_hba.conf')
    P.record('volume-hba-copied.json', {'secretIncluded': False, 'path': '/etc/qyh_pg_hba.conf', 'hostTrust': False})
    docker('start', TARGET)
    for _ in range(60):
        ready = subprocess.run(['docker', '--context', P.M.CTX, 'exec', TARGET, 'pg_isready', '-U', 'aos_app', '-d', P.M.DB], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if ready:
            break
        time.sleep(0.5)
    assert ready, 'Reconcile existing target; no recreate'
    identity = P.native_identity(TARGET)
    assert identity['cluster'] == P.CLUSTER and identity['schema'] == 'a0v_159' and identity['loginExists'] == 1 and identity['disabledBindings'] is True
    after = P.M.fingerprint(TARGET)
    assert after == json.loads((P.R / 'volume-fingerprint-before.json').read_text())
    item = json.loads(docker('inspect', '--format', '{"State":{{json .State}},"Ports":{{json .NetworkSettings.Ports}},"Mounts":{{json .Mounts}},"Image":{{json .Image}}}', TARGET))
    assert item['Ports']['5432/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': str(PORT)}]
    assert item['Image'] == P.M.IMAGE and len(item['Mounts']) == 1 and item['Mounts'][0]['Name'] == P.VOLUME
    P.record('volume-load-terminal.json', {'outcome': 'RETAINED647_VOLUME_LOADED_GREEN', 'identity': identity, 'container': item, 'fingerprintsExact': True, 'originalContainerRetainedStopped': True, 'apiAttached': False, 'eightWorkbenchesVisible': False})
    print('RETAINED647_VOLUME_LOADED_GREEN')
