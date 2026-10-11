"""New isolated attempt after exact reconciliation of the failed grant restore."""
import hashlib
import json
import subprocess
import time
import rehearse_stage_transport as B

OLD = B.TARGET
BACKUPS = B.PRIVATE

if __name__ == '__main__':
    B.TARGET = 'qyh-stage-transport-rehearsal-r2-20261011'
    B.ADMIN = 'aos_app'
    B.RECORD_PREFIX = 'stage-transport-r2-'
    B.PRIVATE = BACKUPS / 'r2'
    assert not (B.P.R/'stage-transport-r2-restore-intent.json').exists(), 'Existing r2: reconcile only'
    created = json.loads((B.P.R/'stage-transport-created.json').read_text())
    observed = json.loads(B.run(['inspect','--format',
        '{"Id":{{json .Id}},"Network":{{json .HostConfig.NetworkMode}},"Ports":{{json .HostConfig.PortBindings}}}',OLD]))
    assert observed == {'Id':created['containerId'],'Network':'none','Ports':{}}
    old_dbs = json.loads(B.run(['exec',OLD,'psql','-X','-qAt','-U',
        'qyh_stage_rehearsal_bootstrap','-d','postgres','-c',
        "SELECT coalesce(json_agg(datname ORDER BY datname),'[]') FROM pg_database WHERE datname='aos_meta_head';"]).decode())
    assert old_dbs == []
    grants = B.run(['exec',OLD,'psql','-X','-qAt','-U',
        'qyh_stage_rehearsal_bootstrap','-d','postgres','-c',
        "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.roleid WHERE r.rolname NOT LIKE 'pg_%';"]).decode().strip()
    assert grants == '0'
    manifest = json.loads((B.P.R/'stage-transport-backup-terminal.json').read_text())
    for name in ('current.dump','globals.sql'):
        assert hashlib.sha256((BACKUPS/name).read_bytes()).hexdigest() == manifest[name]['sha256']
        assert (BACKUPS/name).read_bytes() == (BACKUPS/(name+'.second')).read_bytes()
    globals_sql = (BACKUPS/'globals.sql').read_text()
    bootstrap = 'CREATE ROLE aos_app;'
    assert globals_sql.splitlines().count(bootstrap) == 1
    restored_globals = '\n'.join(line for line in globals_sql.splitlines() if line != bootstrap)+'\n'
    assert len(globals_sql)-len(restored_globals) == len(bootstrap)+1
    assert subprocess.run(B.DOCKER+['inspect',B.TARGET],stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL).returncode != 0
    identity = B.P.native_identity(B.SOURCE)
    assert identity['cluster'] == B.P.CLUSTER and identity['schema'] == 'a0v_159'
    assert identity['disabledBindings'] is True
    before = B.P.M.fingerprint(B.SOURCE)
    assert len(before) == 647
    B.PRIVATE.mkdir(mode=0o700)
    B.record('restore-intent',{'source':B.SOURCE,'sourceIdentity':identity,
        'previousAttempt':observed,'previousBusinessDatabaseExists':False,
        'previousNonSystemMemberships':0,'target':B.TARGET,'bootstrap':'aos_app',
        'originalDumpHash':manifest['current.dump']['sha256'],
        'originalGlobalsHash':manifest['globals.sql']['sha256'],
        'skippedExactStatement':bootstrap,'network':'none','ports':[],
        'sourceWrites':False,'authoritativeVolumeAttached':False})
    cid = B.run(['run','--detach','--name',B.TARGET,'--network','none','--tmpfs',
        '/var/lib/postgresql/data:rw,nosuid,size=512m','-e','POSTGRES_HOST_AUTH_METHOD=trust',
        '-e','POSTGRES_USER='+B.ADMIN,B.P.M.IMAGE]).decode().strip()
    B.record('created',{'containerId':cid,'name':B.TARGET})
    ready = False
    for _ in range(30):
        main = subprocess.run(B.DOCKER+['exec',B.TARGET,'cat','/proc/1/comm'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        ready = main.returncode == 0 and main.stdout.strip() == b'postgres'
        if ready:
            ready = subprocess.run(B.DOCKER+['exec',B.TARGET,'pg_isready','-U',B.ADMIN],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
        if ready: break
        time.sleep(.5)
    assert ready, 'Existing target: reconcile only'
    B.run(['exec','-i',B.TARGET,'psql','-X','-q','-v','ON_ERROR_STOP=1',
        '-U',B.ADMIN,'-d','postgres'],data=restored_globals.encode())
    B.run(['exec',B.TARGET,'createdb','-U',B.ADMIN,'-O','aos_app',B.DB])
    B.run(['cp',str(BACKUPS/'current.dump'),B.TARGET+':/tmp/current.dump'])
    B.run(['exec',B.TARGET,'pg_restore','--exit-on-error','-U',B.ADMIN,'-d',B.DB,'/tmp/current.dump'])
    assert before == B.P.M.fingerprint(B.TARGET,B.ADMIN)
    B.record('restore-terminal',{'tables':647,'fullFingerprintEqual':True,
        'ownerAclRestoreEnabled':True,'grantorPreserved':True})
    B.finish_transport(before,cid)
