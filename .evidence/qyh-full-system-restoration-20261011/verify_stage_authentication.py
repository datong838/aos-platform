"""Correct and independently prove the isolated container's actual SCRAM boundary."""
import hashlib
import json
import subprocess
import rehearse_stage_transport as B

if __name__ == '__main__':
    B.TARGET = 'qyh-stage-transport-rehearsal-r2-20261011'
    B.ADMIN = 'aos_app'
    B.RECORD_PREFIX = 'stage-transport-r2-'
    B.PRIVATE = B.PRIVATE / 'r2'
    assert not (B.P.R/'stage-transport-r2-auth-repair-intent.json').exists(), 'Reconcile existing intent'
    created = json.loads((B.P.R/'stage-transport-r2-created.json').read_text())
    container = json.loads(B.run(['inspect','--format',
        '{"Id":{{json .Id}},"Network":{{json .HostConfig.NetworkMode}},"Ports":{{json .HostConfig.PortBindings}},"Mounts":{{json .Mounts}}}',B.TARGET]))
    assert container['Id'] == created['containerId'] and container['Network'] == 'none'
    assert container['Ports'] == {} and all(x.get('Name') != B.P.VOLUME for x in container['Mounts'])
    assert B.run(['exec',B.TARGET,'cat','/proc/1/comm']).strip() == b'postgres'
    hba = B.PRIVATE / 'pg_hba.conf'
    expected = ('local all all trust\n'
        f'host {B.DB} {B.LOGIN} 127.0.0.1/32 scram-sha-256\n'
        'host all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n').encode()
    assert hba.read_bytes() == expected
    old = B.run(['exec',B.TARGET,'cat','/var/lib/postgresql/data/pg_hba.conf'])
    assert old != expected, 'Different evidence: reconcile'
    B.record('auth-repair-intent',{'containerId':created['containerId'],'network':'none',
        'priorHbaHash':hashlib.sha256(old).hexdigest(),
        'intendedHbaHash':hashlib.sha256(expected).hexdigest(),
        'priorTerminalPasswordProofRejected':True,'sourceWrites':False})
    B.run(['exec','-i',B.TARGET,'sh','-c','cat > /var/lib/postgresql/data/pg_hba.conf'],data=expected)
    B.run(['exec',B.TARGET,'chmod','644','/var/lib/postgresql/data/pg_hba.conf'])
    assert B.run(['exec',B.TARGET,'cat','/var/lib/postgresql/data/pg_hba.conf']) == expected
    assert B.sql('SELECT pg_reload_conf();') == 't'
    actual = json.loads(B.sql("SELECT json_agg(json_build_object('database',database,'users',user_name,"
        "'address',address,'authMethod',auth_method,'error',error) ORDER BY line_number) "
        "FROM pg_hba_file_rules WHERE type='host';"))
    assert [x['authMethod'] for x in actual] == ['scram-sha-256','reject','reject']
    assert actual[0]['users'] == [B.LOGIN] and all(x['error'] is None for x in actual)
    session = B.sql('SELECT session_user;',user=B.LOGIN,tcp=True)
    assert session == B.LOGIN
    no_password = subprocess.run(B.DOCKER+['exec',B.TARGET,'env',
        'PGPASSFILE=/tmp/nonexistent-qyh-passfile','PGCONNECT_TIMEOUT=5','psql','-X','-w',
        '-h','127.0.0.1','-U',B.LOGIN,'-d',B.DB,'-c','SELECT 1;'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert no_password.returncode != 0 and b'no password supplied' in no_password.stderr
    for function, tail in (
        ('extension_configuration_stage_query_a0v_037',"'00000000-0000-0000-0000-000000000000'::uuid"),
        ('extension_configuration_stage_lookup_a0v_038',"'qyh-rehearsal-absent-key'")):
        assert json.loads(B.absent_query('org-org',function,tail)) == {'absent':True}
    result = {'outcome':'STAGE_REHEARSAL_ACTUAL_SCRAM_AUTHENTICATION_VERIFIED',
        'containerId':created['containerId'],'network':'none','ports':[],
        'actualHbaSha256':hashlib.sha256(expected).hexdigest(),'loadedHba':actual,
        'passwordConnectionSucceeded':True,'passwordlessConnectionRejected':True,
        'originalQueryAndLookupSucceededAfterRepair':True,
        'priorProvisionalTerminalAcceptedAsPasswordProof':False,
        'sourceVolumeAttached':False,'sourceRoleChanges':0,'businessWrites':0,
        'currentServicesRestarted':False,'formalOwnerOrPublisherProven':False,
        'fullRestorationAccepted':False}
    B.record('authentication-independent-readback',result)
    print(json.dumps({'outcome':result['outcome'],'passwordlessRejected':True,'currentServicesRestarted':False}))
