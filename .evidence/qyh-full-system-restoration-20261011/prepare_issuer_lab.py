"""One-shot isolated PG lab for the original fixed-port issuer fixtures."""
import json
import socket
import subprocess
import time
import promote_stage_transport as E

NAME='qyh-source-writer-lab-20261011'


if __name__=='__main__':
    intent=E.P.R/'issuer-lab-intent.json'
    assert not intent.exists(), 'Existing intent requires reconciliation'
    with socket.socket() as probe:
        assert probe.connect_ex(('127.0.0.1',18432))!=0, 'Test port occupied; do not take over'
    existing=subprocess.run(E.DOCKER+['inspect',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    assert existing.returncode!=0, 'Existing lab requires reconciliation'
    source=E.P.native_identity(E.SOURCE)
    assert source['cluster']==E.P.CLUSTER and source['disabledBindings'] is True
    before=E.P.M.fingerprint(E.SOURCE)
    assert len(before)==647
    with intent.open('x') as stream:
        json.dump({'name':NAME,'image':E.P.M.IMAGE,'authority':'existing isolated implementation and restoration testing',
            'port':'127.0.0.1:18432','data':'tmpfs disposable','sourceVolumeAttached':False,
            'testIdentityIsBusinessAuthority':False},stream,indent=2)
    cid=E.run(['run','--detach','--name',NAME,'--label','aos.task=qyh-full-system-restoration-20261011',
        '--publish','127.0.0.1:18432:5432','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=512m',
        '-e','POSTGRES_USER=postgres','-e','POSTGRES_HOST_AUTH_METHOD=trust',E.P.M.IMAGE]).decode().strip()
    for attempt in range(30):
        main=subprocess.run(E.DOCKER+['exec',NAME,'cat','/proc/1/comm'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        ready=subprocess.run(E.DOCKER+['exec',NAME,'pg_isready','-U','postgres'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if main.returncode==0 and main.stdout.strip()==b'postgres' and ready.returncode==0:
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Lab startup not confirmed: reconcile existing container')
    item=json.loads(E.run(['inspect','--format',
        '{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Tmpfs":{{json .HostConfig.Tmpfs}},"Ports":{{json .HostConfig.PortBindings}}}',NAME]))
    assert item['Id']==cid and item['Image']==E.P.M.IMAGE
    assert item['Ports']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18432'}]}
    assert all(m.get('Name')!=E.P.VOLUME for m in item['Mounts'])
    assert '/var/lib/postgresql/data' in item['Tmpfs']
    with E.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',connect_timeout=5) as conn:
        identity=conn.execute('SELECT current_database(),session_user,system_identifier::text FROM pg_control_system()').fetchone()
    assert identity[0:2]==('postgres','postgres') and identity[2]!=E.P.CLUSTER
    assert E.P.M.fingerprint(E.SOURCE)==before
    with (E.P.R/'issuer-lab-created.json').open('x') as stream:
        json.dump({'container':item,'testCluster':identity[2],'source647Unchanged':True,
            'formalRestorationAccepted':False},stream,indent=2)
    print('ISOLATED_ISSUER_LAB_READY_SOURCE_UNCHANGED')
