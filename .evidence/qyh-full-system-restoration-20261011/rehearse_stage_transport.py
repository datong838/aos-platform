"""Full restored-data rehearsal of the original restricted staging transport.

Any existing intent is reconciliation-only. The authoritative volume is read
only; all role/HBA changes are confined to the disconnected rehearsal container.
"""
import hashlib
import json
import os
import secrets
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import prepare_volume as P

ROOT = P.R.parents[1]
SOURCE = 'qyh-restored-pg-20261011'
TARGET = 'qyh-stage-transport-rehearsal-20261011'
ADMIN = 'aos_app'
LOGIN = 'qyh_stage_transport_rehearsal_20261011'
DB = 'aos_meta_head'
PRIVATE = P.PRIVATE / 'stage-transport-rehearsal'
DOCKER = ['docker', '--context', P.M.CTX]
RECORD_PREFIX = 'stage-transport-'


def record(name, value):
    with (P.R / (RECORD_PREFIX + name + '.json')).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def run(arguments, *, data=None, output=None, timeout=180):
    result = subprocess.run(DOCKER + arguments, input=data,
        stdout=output if output is not None else subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout)
    if result.returncode:
        private('command-error-'+secrets.token_hex(4)+'.log', result.stderr)
        # SQL/password/log contents never enter the public exception.
        raise RuntimeError('rehearsal command failed; reconcile existing phase')
    return result.stdout


def private(name, contents):
    path = PRIVATE / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def sql(text, *, user=None, tcp=False):
    user = user or ADMIN
    args = ['exec', '-i', TARGET]
    if tcp:
        args += ['env', 'PGPASSFILE=/tmp/qyh-stage-rehearsal.pgpass']
    args += ['psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U',user,'-d',DB]
    if tcp:
        args += ['-h','127.0.0.1']
    return run(args, data=text.encode()).decode().strip()


def absent_query(scope, function, tail):
    return sql("BEGIN; SET LOCAL ROLE aos_configuration_stage_api; "
        "SELECT set_config('aos.org_id','" + scope + "',true); "
        "SELECT set_config('aos.project_id','dev-project',true); "
        "SELECT set_config('aos.subject','user:dev',true); "
        "SELECT json_build_object('absent',public." + function + "('user:dev'," + tail + ") IS NULL); ROLLBACK;",
        user=LOGIN, tcp=True).splitlines()[-1]


def rehearse_fresh():
    assert not (P.R / 'stage-transport-backup-intent.json').exists(), 'Existing intent: reconcile only'
    assert subprocess.run(DOCKER + ['inspect',TARGET], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL).returncode != 0, 'Existing rehearsal: reconcile'
    identity = P.native_identity(SOURCE)
    assert identity['cluster'] == P.CLUSTER and identity['schema'] == 'a0v_159'
    assert identity['database'] == DB and identity['disabledBindings'] is True
    source = json.loads(run(['inspect','--format',
        '{"Image":{{json .Image}},"Mounts":{{json .Mounts}}}',SOURCE]))
    assert source['Image'] == P.M.IMAGE
    assert any(x.get('Name') == P.VOLUME for x in source['Mounts'])
    before = P.M.fingerprint(SOURCE)
    assert len(before) == 647
    PRIVATE.mkdir(mode=0o700)
    record('backup-intent', {'at': datetime.now(timezone.utc).isoformat(),
        'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source': SOURCE,'sourceIdentity':identity,'sourceVolume':P.VOLUME,
        'target':TARGET,'sourceWrites':False})
    backups = {}
    for filename, command in (
        ('current.dump',['pg_dump','-U','aos_app','-d',DB,'-Fc']),
        ('globals.sql',['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'])):
        path = PRIVATE / filename
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd,'wb') as stream:
            run(['exec',SOURCE,*command],output=stream)
        copy = private(filename+'.second',path.read_bytes())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == hashlib.sha256(copy.read_bytes()).hexdigest()
        backups[filename] = {'sha256':digest,'bytes':path.stat().st_size,'secondCopyExact':True}
    assert before == P.M.fingerprint(SOURCE)
    record('backup-terminal',backups)
    record('restore-intent',{'target':TARGET,'image':P.M.IMAGE,'network':'none',
        'ports':[],'authoritativeVolumeAttached':False})
    cid = run(['run','--detach','--name',TARGET,'--network','none','--tmpfs',
        '/var/lib/postgresql/data:rw,nosuid,size=512m','-e','POSTGRES_HOST_AUTH_METHOD=trust',
        '-e','POSTGRES_USER='+ADMIN,P.M.IMAGE]).decode().strip()
    record('created',{'containerId':cid,'name':TARGET})
    ready = False
    for _ in range(30):
        main = subprocess.run(DOCKER+['exec',TARGET,'cat','/proc/1/comm'],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        ready = main.returncode == 0 and main.stdout.strip() == b'postgres'
        if ready:
            ready = subprocess.run(DOCKER+['exec',TARGET,'pg_isready','-U',ADMIN],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 0
        if ready: break
        time.sleep(.5)
    assert ready, 'Existing target not ready: reconcile'
    globals_sql = (PRIVATE/'globals.sql').read_text()
    assert globals_sql.splitlines().count('CREATE ROLE aos_app;') == 1
    restored_globals = '\n'.join(line for line in globals_sql.splitlines()
        if line != 'CREATE ROLE aos_app;')+'\n'
    run(['exec','-i',TARGET,'psql','-X','-q','-v','ON_ERROR_STOP=1','-U',ADMIN,'-d','postgres'],
        data=restored_globals.encode())
    run(['exec',TARGET,'createdb','-U',ADMIN,'-O','aos_app',DB])
    run(['cp',str(PRIVATE/'current.dump'),TARGET+':/tmp/current.dump'])
    run(['exec',TARGET,'pg_restore','--exit-on-error','-U',ADMIN,'-d',DB,'/tmp/current.dump'])
    assert before == P.M.fingerprint(TARGET,ADMIN)
    record('restore-terminal',{'tables':647,'fullFingerprintEqual':True})
    finish_transport(before, cid)


def finish_transport(before, cid):
    password = secrets.token_hex(32)
    passfile = private('transport.pgpass',f'127.0.0.1:5432:{DB}:{LOGIN}:{password}\n'.encode())
    hba = private('pg_hba.conf', ('local all all trust\n'
        f'host {DB} {LOGIN} 127.0.0.1/32 scram-sha-256\n'
        'host all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n').encode())
    record('identity-intent',{'target':TARGET,'technicalLogin':LOGIN,
        'logicalRole':'aos_configuration_stage_api','businessOwnerGranted':False,
        'historicalLoginChanged':False})
    sql(f"SET password_encryption='scram-sha-256'; CREATE ROLE {LOGIN} LOGIN PASSWORD '{password}' "
        "NOSUPERUSER NOBYPASSRLS NOINHERIT NOCREATEROLE NOCREATEDB NOREPLICATION; "
        f"GRANT aos_configuration_stage_api TO {LOGIN}; GRANT CONNECT ON DATABASE {DB} TO {LOGIN};")
    run(['cp',str(passfile),TARGET+':/tmp/qyh-stage-rehearsal.pgpass'])
    run(['exec',TARGET,'chmod','600','/tmp/qyh-stage-rehearsal.pgpass'])
    run(['exec','-i',TARGET,'sh','-c','cat > /var/lib/postgresql/data/pg_hba.conf'],data=hba.read_bytes())
    run(['exec',TARGET,'chmod','644','/var/lib/postgresql/data/pg_hba.conf'])
    assert run(['exec',TARGET,'cat','/var/lib/postgresql/data/pg_hba.conf']) == hba.read_bytes()
    assert sql('SELECT pg_reload_conf();') == 't'
    auth_rules = json.loads(sql("SELECT json_agg(auth_method ORDER BY line_number) "
        "FROM pg_hba_file_rules WHERE type='host';"))
    assert auth_rules == ['scram-sha-256','reject','reject']
    role = json.loads(sql("SELECT json_build_object('session',session_user,'current',current_user,"
        "'login',rolcanlogin,'inherit',rolinherit,'super',rolsuper,'bypass',rolbypassrls,"
        "'createRole',rolcreaterole,'createDb',rolcreatedb,'replication',rolreplication) "
        "FROM pg_roles WHERE rolname=session_user;",user=LOGIN,tcp=True))
    assert role == {'session':LOGIN,'current':LOGIN,'login':True,'inherit':False,
        'super':False,'bypass':False,'createRole':False,'createDb':False,'replication':False}
    memberships = json.loads(sql("SELECT coalesce(json_agg(rolname ORDER BY rolname),'[]') "
        "FROM pg_roles WHERE rolname<>session_user AND pg_has_role(session_user,oid,'MEMBER');",
        user=LOGIN,tcp=True))
    assert memberships == ['aos_configuration_stage_api']
    passwordless = subprocess.run(DOCKER+['exec',TARGET,'env',
        'PGPASSFILE=/tmp/nonexistent-qyh-passfile','PGCONNECT_TIMEOUT=5','psql','-X','-w',
        '-h','127.0.0.1','-U',LOGIN,'-d',DB,'-c','SELECT 1;'],
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert passwordless.returncode != 0 and b'no password supplied' in passwordless.stderr
    for function, tail in (
        ('extension_configuration_stage_query_a0v_037',"'00000000-0000-0000-0000-000000000000'::uuid"),
        ('extension_configuration_stage_lookup_a0v_038',"'qyh-rehearsal-absent-key'")):
        assert json.loads(absent_query('org-org',function,tail)) == {'absent':True}
    denials = []
    for label, query in (
        ('direct-stage-table','SELECT * FROM public.extension_runtime_configuration_stage_request LIMIT 1;'),
        ('direct-config-table','SELECT * FROM public.extension_runtime_configuration LIMIT 1;'),
        ('host-function',"SELECT public.extension_ui_read_host_principal_a0v_033('user:dev',ARRAY[]::text[]);"),
        ('negative-tenant',"SELECT set_config('aos.org_id','dev-org',true); SELECT public.extension_configuration_stage_query_a0v_037('user:dev','00000000-0000-0000-0000-000000000000'::uuid);")):
        text = "\\set VERBOSITY verbose\nBEGIN; SET LOCAL ROLE aos_configuration_stage_api; SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true),set_config('aos.subject','user:dev',true); " + query + ' ROLLBACK;'
        result = subprocess.run(DOCKER+['exec','-i',TARGET,'env','PGPASSFILE=/tmp/qyh-stage-rehearsal.pgpass',
            'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-U',LOGIN,'-d',DB],
            input=text.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
        assert result.returncode != 0 and b'42501' in result.stderr, 'Expected privilege rejection missing'
        denials.append(label)
    assert before == P.M.fingerprint(TARGET,ADMIN)
    assert before == P.M.fingerprint(SOURCE)
    record('terminal',{'outcome':'FULL_CLONE_STAGE_SCRAM_TRANSPORT_VERIFIED',
        'target':TARGET,'containerId':cid,'network':'none','ports':[],
        'completeRestoreTables':647,'sourceFingerprintUnchanged':True,
        'rehearsalBusinessFingerprintUnchanged':True,'actualScramLogin':role,
        'reachableMemberRoles':memberships,
        'loadedAuthenticationMethods':auth_rules,'passwordlessConnectionRejected':True,
        'originalQueryAndLookupSucceeded':True,'denials':denials,'enqueueAttempts':0,
        'sourcePrivilegeChanges':0,'formalIdentityProven':False,'hostReady':False,
        'eightWorkshopsRestored':False,'fullGoalAccepted':False})
    print(json.dumps({'outcome':'FULL_CLONE_STAGE_SCRAM_TRANSPORT_VERIFIED','tables':647,'denials':denials}))


if __name__ == '__main__':
    rehearse_fresh()
