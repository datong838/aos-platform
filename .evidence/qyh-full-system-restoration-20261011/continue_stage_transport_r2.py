"""Continue only the verified zero-effect failed globals phase, never replay blindly."""
import hashlib
import json
import rehearse_stage_transport as B

if __name__ == '__main__':
    backups = B.PRIVATE
    B.TARGET = 'qyh-stage-transport-rehearsal-r2-20261011'
    B.ADMIN = 'aos_app'
    B.RECORD_PREFIX = 'stage-transport-r2-'
    B.PRIVATE = backups / 'r2'
    assert not (B.P.R/'stage-transport-r2-resume-final-postgres-intent.json').exists(), 'Reconcile only'
    created = json.loads((B.P.R/'stage-transport-r2-created.json').read_text())
    observed = json.loads(B.run(['inspect','--format',
        '{"Id":{{json .Id}},"Image":{{json .Image}},"Network":{{json .HostConfig.NetworkMode}},"Ports":{{json .HostConfig.PortBindings}},"Mounts":{{json .Mounts}}}',B.TARGET]))
    assert observed['Id'] == created['containerId'] and observed['Image'] == B.P.M.IMAGE
    assert observed['Network'] == 'none' and observed['Ports'] == {}
    assert all(x.get('Name') != B.P.VOLUME for x in observed['Mounts'])
    assert B.run(['exec',B.TARGET,'cat','/proc/1/comm']).strip() == b'postgres'
    state = json.loads(B.run(['exec',B.TARGET,'psql','-X','-qAt','-U',B.ADMIN,
        '-d','postgres','-c',"SELECT json_build_object('roles',(SELECT json_agg(rolname ORDER BY rolname) FROM pg_roles WHERE rolname NOT LIKE 'pg_%'),'businessDatabase',(SELECT count(*) FROM pg_database WHERE datname='aos_meta_head')); "]).decode())
    assert state == {'roles':['aos_app'],'businessDatabase':0}
    manifest = json.loads((B.P.R/'stage-transport-backup-terminal.json').read_text())
    for name in ('current.dump','globals.sql'):
        assert hashlib.sha256((backups/name).read_bytes()).hexdigest() == manifest[name]['sha256']
        assert (backups/name).read_bytes() == (backups/(name+'.second')).read_bytes()
    original = (backups/'globals.sql').read_text()
    assert original.splitlines().count('CREATE ROLE aos_app;') == 1
    remaining = '\n'.join(line for line in original.splitlines() if line != 'CREATE ROLE aos_app;')+'\n'
    before = B.P.M.fingerprint(B.SOURCE)
    assert len(before) == 647
    B.record('resume-final-postgres-intent',{'containerId':created['containerId'],
        'reconciledState':state,'pid1':'postgres','sourceWrites':False,
        'originalDumpHash':manifest['current.dump']['sha256'],
        'originalGlobalsHash':manifest['globals.sql']['sha256']})
    B.run(['exec','-i',B.TARGET,'psql','-X','-q','-v','ON_ERROR_STOP=1',
        '-U',B.ADMIN,'-d','postgres'],data=remaining.encode())
    B.run(['exec',B.TARGET,'createdb','-U',B.ADMIN,'-O','aos_app',B.DB])
    B.run(['cp',str(backups/'current.dump'),B.TARGET+':/tmp/current.dump'])
    B.run(['exec',B.TARGET,'pg_restore','--exit-on-error','-U',B.ADMIN,'-d',B.DB,'/tmp/current.dump'])
    assert before == B.P.M.fingerprint(B.TARGET,B.ADMIN)
    B.record('restore-terminal',{'tables':647,'fullFingerprintEqual':True,
        'ownerAclRestoreEnabled':True,'grantorPreserved':True})
    B.finish_transport(before,created['containerId'])
