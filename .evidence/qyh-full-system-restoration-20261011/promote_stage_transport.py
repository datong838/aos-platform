"""One-shot technical staging transport preparation, never business authorization.

An existing intent requires read-only reconciliation, not automatic replay.
Passwords and identity DSNs are kept exclusively in owner-only private files.
"""
import hashlib
import json
import os
import secrets
import subprocess
import urllib.request
from datetime import datetime, timezone
import prepare_volume as P
import release_transition as T
import readback_stage_transport as D
from psycopg import connect
from psycopg.conninfo import make_conninfo
from aos_api.extension_runtime.configuration_stage_connection import configuration_stage_connection, CREDENTIAL_FILE
from aos_api.tenant_scope import TenantScope

SOURCE = 'qyh-restored-pg-20261011'
CID = '84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
LOGIN = 'qyh_restored_stage_login_20261011'
PRIVATE = P.PRIVATE / 'stage-transport-current'
HBA = '/etc/qyh_pg_hba.conf'
DOCKER = ['docker', '--context', P.M.CTX]


def record(name, value):
    with (P.R / ('stage-current-' + name + '.json')).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def private(name, contents):
    fd = os.open(PRIVATE / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())
    return PRIVATE / name


def run(args, data=None, output=None):
    result = subprocess.run(DOCKER + args, input=data,
        stdout=output if output is not None else subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=180)
    if result.returncode:
        # No stderr containing SQL or credentials is published.
        raise RuntimeError('Technical transport command failed; reconcile intent before any retry')
    return result.stdout


def sql(value):
    return run(['exec','-i',SOURCE,'psql','-X','-qAt','-v','ON_ERROR_STOP=1',
        '-U','aos_app','-d',P.M.DB], value.encode()).decode().strip()


def metadata():
    result = {}
    for key, query in D.QUERIES.items():
        query = query.replace(D.LOGIN, LOGIN)
        result[key] = json.loads(sql("BEGIN READ ONLY; SELECT coalesce(json_agg(x),'[]') FROM ("+query+") x; COMMIT;"))
    return result


def query(org, statement):
    with configuration_stage_connection(scope=TenantScope(org,'dev-project'),subject='user:dev') as conn:
        return conn.execute(statement).fetchone()


def health():
    with urllib.request.urlopen('http://127.0.0.1:18080/v1/auth/oidc', timeout=10) as response:
        assert response.status == 200
    with urllib.request.urlopen('http://127.0.0.1:18434/org/membership', timeout=10) as response:
        assert response.status == 200


def main():
    assert not (P.R/'stage-current-intent.json').exists(), 'Existing intent: reconciliation only'
    assert not PRIVATE.exists(), 'Existing private preparation: reconciliation only'
    T.H.preflight(P.R/'private/restored-identity.json')
    item = json.loads(run(['inspect','--format',
        '{"Id":{{json .Id}},"Image":{{json .Image}},"Mounts":{{json .Mounts}},"Ports":{{json .HostConfig.PortBindings}},"StartedAt":{{json .State.StartedAt}}}',SOURCE]))
    assert item['Id'] == CID and item['Image'] == P.M.IMAGE
    assert len(item['Mounts']) == 1 and item['Mounts'][0]['Name'] == P.VOLUME
    assert item['Mounts'][0]['Destination'] == '/var/lib/postgresql/data'
    assert item['Ports'] == {'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'18446'}]}
    identity = P.native_identity(SOURCE)
    assert identity['cluster'] == P.CLUSTER and identity['schema'] == 'a0v_159'
    assert identity['database'] == P.M.DB and identity['disabledBindings'] is True
    assert identity['name'] == '栖月汇商贸有限公司'
    assert sql('SHOW hba_file;') == HBA
    assert sql("SELECT count(*) FROM pg_roles WHERE rolname='"+LOGIN+"';") == '0'
    assert sql("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state NOT IN ('idle');") == '0'
    before = P.M.fingerprint(SOURCE)
    assert len(before) == 647
    old_metadata = metadata()
    baseline = json.loads((P.R/'stage-transport-r2-independent-readback.json').read_text())['metadataEquality']
    for key, rows in old_metadata.items():
        assert hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest() == baseline[key]['sha256']
    rehearsal = json.loads((P.R/'stage-transport-r2-authentication-independent-readback.json').read_text())
    assert rehearsal['passwordConnectionSucceeded'] and rehearsal['passwordlessConnectionRejected']
    old_hba = run(['exec',SOURCE,'cat',HBA])
    expected = ('local all all trust\n'
        'host aos_meta_head qyh_restored_api_login 0.0.0.0/0 scram-sha-256\n'
        'host all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n').encode()
    assert old_hba == expected, 'Unexpected current HBA: reconcile'
    health()
    PRIVATE.mkdir(mode=0o700)
    record('intent',{'task':'qyh-full-system-restoration-20261011',
        'thread':'01a107a2-e9e4-7670-bc44-1144fa9b27e2',
        'at':datetime.now(timezone.utc).isoformat(),
        'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=T.ROOT,text=True).strip(),
        'container':item,'database':identity,'newTechnicalLogin':LOGIN,
        'businessIdentityCreated':False,'businessWritesAuthorized':False,
        'phase':'FRESH_BACKUP_BEFORE_ROLE_AND_HBA'})
    private('original-hba.conf',old_hba)
    backups = {}
    for name, command in [('current.dump',['pg_dump','-U','aos_app','-d',P.M.DB,'-Fc']),
                         ('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])]:
        path = private(name,b'')
        with path.open('wb') as out:
            run(['exec',SOURCE,*command],output=out)
        second = private(name+'.second',path.read_bytes())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == hashlib.sha256(second.read_bytes()).hexdigest()
        backups[name] = {'sha256':digest,'bytes':path.stat().st_size,'secondCopyExact':True}
    assert P.M.fingerprint(SOURCE) == before and metadata() == old_metadata
    record('backup',backups)
    password = secrets.token_hex(32)
    passfile = private('stage.pgpass',f'127.0.0.1:18446:{P.M.DB}:{LOGIN}:{password}\n'.encode())
    dsn = make_conninfo(host='127.0.0.1',port=18446,dbname=P.M.DB,user=LOGIN,passfile=str(passfile))
    identity_file = private('stage-identity.json',json.dumps({
        'schemaVersion':'aos.runtime-configuration-api-identity/v1','role':LOGIN,'dsn':dsn}).encode())
    record('role-intent',{'containerId':CID,'login':LOGIN,'memberOnly':'aos_configuration_stage_api'})
    sql("BEGIN; SET LOCAL password_encryption='scram-sha-256'; CREATE ROLE "+LOGIN+
        " LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '"+
        password+"'; GRANT aos_configuration_stage_api TO "+LOGIN+"; COMMIT;")
    del password
    new_hba = old_hba.replace(b'host all all 0.0.0.0/0 reject',
        f'host aos_meta_head {LOGIN} 0.0.0.0/0 scram-sha-256\nhost all all 0.0.0.0/0 reject'.encode())
    record('hba-intent',{'priorSha256':hashlib.sha256(old_hba).hexdigest(),
        'intendedSha256':hashlib.sha256(new_hba).hexdigest(),'restart':False})
    assert run(['exec',SOURCE,'cat',HBA]) == old_hba
    run(['exec','-i',SOURCE,'sh','-c','cat > /etc/qyh_pg_hba.conf'],new_hba)
    assert run(['exec',SOURCE,'cat',HBA]) == new_hba
    assert sql('SELECT pg_reload_conf();') == 't'
    rules = json.loads(sql("SELECT json_agg(json_build_object('users',user_name,'method',auth_method,'error',error) ORDER BY line_number) FROM pg_hba_file_rules WHERE type='host';"))
    assert [r['method'] for r in rules] == ['scram-sha-256','scram-sha-256','reject','reject']
    assert rules[1]['users'] == [LOGIN] and all(r['error'] is None for r in rules)
    empty = private('empty.pgpass',b'')
    rejected = False
    try:
        with connect(host='127.0.0.1',port=18446,dbname=P.M.DB,user=LOGIN,
                     passfile=str(empty),password='',connect_timeout=5):
            pass
    except Exception as error:
        rejected = 'no password supplied' in str(error)
    assert rejected, 'Passwordless negative did not prove rejection'
    previous = os.environ.get(CREDENTIAL_FILE)
    os.environ[CREDENTIAL_FILE] = str(identity_file)
    try:
        assert query('org-org',"SELECT public.extension_configuration_stage_query_a0v_037('user:dev','00000000-0000-0000-0000-000000000000'::uuid) AS value;")['value'] is None
        assert query('org-org',"SELECT public.extension_configuration_stage_lookup_a0v_038('user:dev','qyh-current-absent-key-20261011') AS value;")['value'] is None
        denied = []
        for label, org, statement in [
            ('wrongTenant','dev-org',"SELECT public.extension_configuration_stage_query_a0v_037('user:dev','00000000-0000-0000-0000-000000000000'::uuid);"),
            ('directStage','org-org','SELECT * FROM public.extension_runtime_configuration_stage_request LIMIT 0;'),
            ('directConfiguration','org-org','SELECT * FROM public.extension_runtime_configuration LIMIT 0;'),
            ('hostFunction','org-org',"SELECT public.extension_ui_read_host_principal_a0v_033('user:dev',ARRAY[]::text[]);")]:
            try:
                query(org,statement)
            except Exception as error:
                assert getattr(error,'sqlstate',None) == '42501', 'Negative failed for a different reason'
                denied.append(label)
            else:
                raise RuntimeError('Expected restricted API denial did not occur')
    finally:
        if previous is None:
            os.environ.pop(CREDENTIAL_FILE,None)
        else:
            os.environ[CREDENTIAL_FILE] = previous
    assert P.M.fingerprint(SOURCE) == before and metadata() == old_metadata
    health()
    final_item = json.loads(run(['inspect','--format','{"StartedAt":{{json .State.StartedAt}}}',SOURCE]))
    assert final_item['StartedAt'] == item['StartedAt']
    record('terminal',{'outcome':'CURRENT_QYH_TECHNICAL_STAGE_CONNECTION_VERIFIED',
        'tables':647,'businessFingerprintUnchanged':True,'sixOldMetadataScopesUnchanged':True,
        'correctPasswordOriginalConnectorSucceeded':True,'passwordlessRejected':True,
        'queryLookupAbsent':True,'denials':denied,'loadedHba':rules,
        'databaseRestarted':False,'apiStartupCredentialInjected':False,
        'businessRowsWritten':0,'sourceAclChanged':False,'formalPublisherConnected':False,
        'eightWorkbenchesRestored':False,'fullRestorationAccepted':False})
    print('CURRENT_QYH_TECHNICAL_STAGE_CONNECTION_VERIFIED')


if __name__ == '__main__':
    main()
