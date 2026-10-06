"""Registry physical isolation; complete anchored registration is a later gate."""
from tests.aip.test_provider_capacity_request_pg import original_inputs
from tests.aip.test_provider_capacity_formal_boundary_pg import isolated_owner


def test_publication_registry_default_empty_private(original_inputs):
    from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA, TABLES
    with isolated_owner() as conn:
        schema = conn.execute('SELECT nspowner=%s::regrole AS owner FROM pg_namespace WHERE nspname=%s',
            (OWNER, SCHEMA)).fetchone()
        assert schema == dict(owner=True)
        for name in TABLES:
            assert conn.execute('SELECT count(*) AS n FROM '+SCHEMA+'.'+name).fetchone()['n'] == 0


import hashlib
import psycopg
import pytest
from aos_api.aip_provider_capacity_publication_registry import OWNER, PUBLISHER, SCHEMA, TABLES, reserved_role_sql


@pytest.mark.parametrize('role',[PUBLISHER,'aos_runtime','aos_provider_capacity_issuer'])
def test_existing_callers_cannot_read_write_or_parse_registry(role):
    with isolated_owner() as conn:
        for statement in (f'SELECT * FROM {SCHEMA}.root_snapshot',
                          f'DELETE FROM {SCHEMA}.registry_epoch',
                          f"SELECT {SCHEMA}.read_root_identifier_literal('\"a\"')"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with conn.transaction():
                    conn.execute('SET LOCAL ROLE '+role)
                    conn.execute(statement)


def test_registry_catalog_has_no_login_bypass_or_public_writer():
    with isolated_owner() as conn:
        for role in (OWNER,PUBLISHER):
            r=conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
            assert r and not any(r.values())
        rows=conn.execute('SELECT c.relname,c.relrowsecurity,c.relforcerowsecurity,c.relowner=%s::regrole AS owner FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind=%s',(OWNER,SCHEMA,'r')).fetchall()
        from aos_api.aip_provider_capacity_document_registry import DOCUMENT_TABLES
        assert {r['relname'] for r in rows}==set(TABLES)|set(DOCUMENT_TABLES)
        assert all(r['relrowsecurity'] and r['relforcerowsecurity'] and r['owner'] for r in rows)
        assert conn.execute('SELECT count(*) AS n FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname=%s AND c.contype=%s AND (c.condeferrable OR c.condeferred)',(SCHEMA,'f')).fetchone()['n']==0


def test_owner_scope_and_immutable_snapshot():
    raw=b'{"trustRoots":[]}'
    digest='sha256:'+hashlib.sha256(raw).hexdigest()
    with isolated_owner() as conn:
        # Savepoint rollback leaves the registry empty; administrative fixture is not trusted initialization.
        try:
            with conn.transaction():
                conn.execute('SET LOCAL ROLE '+OWNER)
                conn.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
                conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',('org-org','dev-project',digest,raw))
                for operation in ('UPDATE '+SCHEMA+'.root_snapshot SET root_count=0','DELETE FROM '+SCHEMA+'.root_snapshot'):
                    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_PUBLICATION_IMMUTABLE'):
                        with conn.transaction():conn.execute(operation)
                conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
                assert conn.execute(f'SELECT count(*) AS n FROM {SCHEMA}.root_snapshot').fetchone()['n']==0
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',('org-org','dev-project',digest,raw))
                raise _RollbackFixture()
        except _RollbackFixture:pass


class _RollbackFixture(Exception):pass


@pytest.mark.parametrize('flag',['LOGIN','INHERIT','BYPASSRLS'])
def test_reserved_publisher_drift_is_rejected_without_repair(flag):
    with isolated_owner() as conn:
        try:
            with conn.transaction():
                conn.execute('ALTER ROLE '+PUBLISHER+' '+flag)
                with pytest.raises(psycopg.errors.InsufficientPrivilege,match='CAPACITY_PUBLICATION_RESERVED_ROLE_DRIFT'):
                    with conn.transaction():conn.execute(reserved_role_sql(PUBLISHER))
                raise _RollbackFixture()
        except _RollbackFixture:pass


def test_snapshot_digest_and_origin_parent_links_are_enforced():
    with isolated_owner() as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute(f'INSERT INTO {SCHEMA}.root_snapshot VALUES(%s,%s,%s,%s,0)',
                    ('org-org','dev-project','sha256:'+'0'*64,b'{"trustRoots":[]}'))
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            with conn.transaction():
                raw=b'test-only-untrusted-origin'
                conn.execute(f'INSERT INTO {SCHEMA}.origin VALUES(%s,%s,%s,%s,%s,%s,%s)',
                    ('org-org','dev-project',hashlib.sha256(raw).hexdigest(),raw,b'x'*64,'sha256:'+'1'*64,'sha256:'+'2'*64))


def test_registry_signature_entry_default_is_closed():
    from aos_api.aip_provider_capacity_publication_registry import ORIGIN_REGISTRATION_SQL
    assert 'register_origin' in ORIGIN_REGISTRATION_SQL
    with isolated_owner() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute('SET LOCAL ROLE aos_provider_capacity_issuer')
                conn.execute(f"SELECT {SCHEMA}.register_origin(NULL,NULL,NULL)")


@pytest.mark.parametrize('fault',[None,'signature','snapshot','subject','database','cluster','signer','missing_epoch','wrong_session','verifier_owner','expiry','epoch','missing_root_replay'])
def test_native_signed_origin_registration_derives_complete_roots(tmp_path,fault):
    import base64,json,os,subprocess
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot,ProviderCapacityOriginBootstrap
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_provider_capacity_publication_registry import install_registry_schema,install_origin_registration
    from tests.aip.test_provider_capacity_publication_pg import bootstrap
    target=os.environ.get('AOS_CRYPTO_TEST_CONTAINER')
    if not target:pytest.skip('explicit isolated native crypto instance required')
    prefix=['docker','--context','colima-aos-a0v-test-only']
    state=json.loads(subprocess.check_output(prefix+['inspect',target],text=True))[0]
    assert target.startswith('aos-ed25519-test-') and state['Image']==os.environ['AOS_CRYPTO_TEST_IMAGE']
    assert state['HostConfig']['NetworkMode']=='none' and not state['HostConfig']['PortBindings'] and not state['HostConfig']['Privileged']
    assert state['Config']['Labels']['aos.task']=='gt-capacity-sql-ed25519-20261006'
    runner=prefix+['exec','-i',target,'psql','-U','aos_app','-d','aos_test_ed25519','-Atq','-v','ON_ERROR_STOP=1','-f','-']
    probe=subprocess.run(runner,input="BEGIN READ ONLY; SELECT oid,(SELECT system_identifier FROM pg_control_system()) FROM pg_database WHERE datname=current_database(); COMMIT;",text=True,capture_output=True,check=True,timeout=20).stdout.strip().split('|')
    deployment=dict(host='127.0.0.1',port=5432,database='aos_test_ed25519',databaseOid=int(probe[0]),clusterIdentifier=probe[1],issuerRole='aos_provider_capacity_issuer')
    key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    roots=[dict(publisher='root-'+str(i).zfill(4),keyId='key-\ud800' if i==0 else 'key-'+str(i),algorithm='Ed25519',publicKey=base64.b64encode(public).decode(),notBefore='2020-01-01T00:00:00Z',notAfter='2030-01-01T00:00:00Z',revokedAt=None,revision='sha256:'+'a'*64) for i in range(1001 if fault is None else 2)]
    path=tmp_path/'original-roots.json';path.write_text(json.dumps(dict(trustRoots=roots)));path.chmod(0o600)
    transport=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    raw=bootstrap();raw.update(publisher='anchor-authority',keyId='anchor-key',publisherSubject='controlled-test-subject',deploymentTarget=deployment,rootSnapshotHash=transport.content_hash)
    if fault=='subject':raw['publisherSubject']='different-subject'
    if fault=='database':raw['deploymentTarget']={**deployment,'databaseOid':deployment['databaseOid']+1}
    if fault=='cluster':raw['deploymentTarget']={**deployment,'clusterIdentifier':'1234567890'}
    if fault=='signer':raw['publisher']='caller-authority'
    body=canonical_json(ProviderCapacityOriginBootstrap.model_validate(raw).model_dump(mode='json',by_alias=True));signature=key.sign(body)
    if fault=='expiry':
        from datetime import datetime,timedelta,timezone
        raw['validFrom']=datetime.now(timezone.utc)-timedelta(hours=2)
        raw['validUntil']=datetime.now(timezone.utc)-timedelta(hours=1)
        body=canonical_json(ProviderCapacityOriginBootstrap.model_validate(raw).model_dump(mode='json',by_alias=True));signature=key.sign(body)
    if fault=='signature':signature=bytes([signature[0]^1])+signature[1:]
    root_bytes=transport.canonical_bytes if fault!='snapshot' else b'{"trustRoots":[]}'
    ddl=[];install_registry_schema(ddl.append);install_origin_registration(ddl.append)
    # Controlled administrative test fixture, transaction rolled back; not formal installation/OIDC/SCRAM proof.
    seed="""INSERT INTO aos_capacity_publication_private.deployment_anchor VALUES('org-org','dev-project','sha256:%s','anchor-authority','anchor-key',decode('%s','hex'),'controlled-test-subject',convert_from(decode('%s','hex'),'UTF8')::jsonb);"""%('c'*64,public.hex(),canonical_json(raw['deploymentTarget'] if fault in ('database','cluster') else deployment).hex())
    if fault!='missing_epoch':seed+="INSERT INTO aos_capacity_publication_private.registry_epoch VALUES('org-org','dev-project','sha256:"+'c'*64+"',0,NULL);"
    call="SELECT aos_capacity_publication_private.register_origin(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));"%(body.hex(),signature.hex(),root_bytes.hex())
    if fault=='epoch':seed+='UPDATE aos_capacity_publication_private.registry_epoch SET epoch=1;'
    if fault=='verifier_owner':seed+='ALTER FUNCTION aos_ed25519.verify(bytea,bytea,bytea) OWNER TO '+PUBLISHER+';'
    session=PUBLISHER if fault!='wrong_session' else 'aos_provider_capacity_issuer'
    setup="BEGIN; DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_runtime') THEN CREATE ROLE aos_runtime NOLOGIN; END IF; IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_provider_capacity_issuer') THEN CREATE ROLE aos_provider_capacity_issuer NOLOGIN; END IF; END $$;\n"+'\n'.join(stmt.rstrip().rstrip(';')+';' for stmt in ddl)+'\n'+seed+"\nSELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true);\nSET SESSION AUTHORIZATION "+session+';\n'+call
    if fault=='missing_root_replay':
        setup+='RESET SESSION AUTHORIZATION; TRUNCATE aos_capacity_publication_private.root_entry; SET SESSION AUTHORIZATION '+PUBLISHER+';'+call
    if fault is None:
        setup+=call+"RESET SESSION AUTHORIZATION; SELECT count(*),min(root_ordinal),max(root_ordinal) FROM aos_capacity_publication_private.root_entry; SELECT epoch FROM aos_capacity_publication_private.registry_epoch; SELECT bool_and(e.canonical_root=r.canonical_root AND e.publisher_codepoints=r.publisher_codepoints AND e.key_id_codepoints=r.key_id_codepoints AND e.public_key=r.public_key) FROM aos_capacity_publication_private.root_entry e JOIN aos_capacity_publication_private.root_snapshot s USING(org_id,project_id,snapshot_hash) CROSS JOIN LATERAL aos_capacity_publication_private.read_root_snapshot(s.raw_body) r WHERE e.root_ordinal=r.root_ordinal;"
    result=subprocess.run(runner,input=setup+'\nROLLBACK;',text=True,capture_output=True,timeout=60)
    if fault is None:
        assert result.returncode==0,result.stderr
        output=result.stdout.strip().splitlines();digest=hashlib.sha256(body).hexdigest()
        assert output[-5:]==[digest,digest,'1001|1|1001','1','t']
    else:
        assert result.returncode!=0,result.stdout
        assert 'CAPACITY_ORIGIN_REGISTRATION_DENIED' in result.stderr or 'permission denied' in result.stderr or (fault=='verifier_owner' and 'CAPACITY_ORIGIN_VERIFIER_REQUIRED' in result.stderr)


@pytest.fixture
def committed_native_registry(tmp_path):
    """Retained disposable database; current DB and original crypto template untouched."""
    import base64,json,os,subprocess
    from uuid import uuid4
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot,ProviderCapacityOriginBootstrap
    from aos_api.aip_provider_capacity_publication_registry import install_registry_schema,install_origin_registration
    from tests.aip.test_provider_capacity_publication_pg import bootstrap
    target=os.environ.get('AOS_CRYPTO_TEST_CONTAINER')
    if not target:pytest.skip('explicit isolated native instance required')
    prefix=['docker','--context','colima-aos-a0v-test-only'];state=json.loads(subprocess.check_output(prefix+['inspect',target],text=True))[0]
    assert target.startswith('aos-ed25519-test-') and state['Image']==os.environ['AOS_CRYPTO_TEST_IMAGE']
    assert state['HostConfig']['NetworkMode']=='none' and not state['HostConfig']['PortBindings'] and not state['HostConfig']['Privileged']
    assert state['Config']['Labels']['aos.task']=='gt-capacity-sql-ed25519-20261006'
    database='aos_test_rootcommit_'+uuid4().hex[:12]
    def command(db):return prefix+['exec','-i',target,'psql','-U','aos_app','-d',db,'-Atq','-v','ON_ERROR_STOP=1','-f','-']
    def run(statement,db=database,success=True):
        result=subprocess.run(command(db),input=statement,text=True,capture_output=True,timeout=25)
        if success:assert result.returncode==0,result.stderr
        else:assert result.returncode!=0
        return result
    assert run("SELECT count(*) FROM pg_namespace WHERE nspname='aos_capacity_publication_private';",'aos_test_ed25519').stdout.strip()=='0'
    run('CREATE DATABASE '+database+' TEMPLATE aos_test_ed25519;','postgres')
    probe=run('SELECT oid,(SELECT system_identifier FROM pg_control_system()) FROM pg_database WHERE datname=current_database();').stdout.strip().split('|')
    deployment=dict(host='127.0.0.1',port=5432,database=database,databaseOid=int(probe[0]),clusterIdentifier=probe[1],issuerRole='aos_provider_capacity_issuer')
    key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    roots=[dict(publisher='committed-root',keyId='key-'+str(i),algorithm='Ed25519',publicKey=base64.b64encode(public).decode(),notBefore='2020-01-01T00:00:00Z',notAfter='2030-01-01T00:00:00Z',revokedAt=None,revision='sha256:'+'a'*64) for i in range(2)]
    path=tmp_path/'committed-original-roots.json';path.write_text(json.dumps(dict(trustRoots=roots)));path.chmod(0o600)
    transport=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path));raw=bootstrap();raw.update(publisher='commit-anchor',keyId='commit-anchor-key',publisherSubject='controlled-test-subject',deploymentTarget=deployment,rootSnapshotHash=transport.content_hash)
    body=canonical_json(ProviderCapacityOriginBootstrap.model_validate(raw).model_dump(mode='json',by_alias=True));signature=key.sign(body)
    ddl=[];install_registry_schema(ddl.append);install_origin_registration(ddl.append)
    support="DO $$ BEGIN IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_runtime') THEN CREATE ROLE aos_runtime NOLOGIN; END IF; IF NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='aos_provider_capacity_issuer') THEN CREATE ROLE aos_provider_capacity_issuer NOLOGIN; END IF; END $$;"
    seed="INSERT INTO aos_capacity_publication_private.deployment_anchor VALUES('org-org','dev-project','sha256:%s','commit-anchor','commit-anchor-key',decode('%s','hex'),'controlled-test-subject',convert_from(decode('%s','hex'),'UTF8')::jsonb); INSERT INTO aos_capacity_publication_private.registry_epoch VALUES('org-org','dev-project','sha256:%s',0,NULL);"%('c'*64,public.hex(),canonical_json(deployment).hex(),'c'*64)
    run('BEGIN;'+support+'\n'.join(s.rstrip().rstrip(';')+';' for s in ddl)+seed+'COMMIT;')
    call="SELECT aos_capacity_publication_private.register_origin(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));"%(body.hex(),signature.hex(),transport.canonical_bytes.hex())
    begin="BEGIN; SET LOCAL statement_timeout='10s'; SET LOCAL aos.org_id='org-org'; SET LOCAL aos.project_id='dev-project'; SET SESSION AUTHORIZATION "+PUBLISHER+';'
    yield dict(run=run,command=command(database),database=database,call=call,begin=begin,digest=hashlib.sha256(body).hexdigest(),body=body,signature=signature,root_bytes=transport.canonical_bytes,sign_key=key)
    # Deliberately retain only the uniquely created test database for audit; no DROP/volume deletion.


def test_native_registration_real_commit_and_rollback(committed_native_registry):
    f=committed_native_registry;run=f['run']
    assert run(f['begin']+f['call']+'ROLLBACK;').stdout.strip()==f['digest']
    audit="SELECT (SELECT count(*) FROM aos_capacity_publication_private.root_snapshot),(SELECT count(*) FROM aos_capacity_publication_private.origin),(SELECT count(*) FROM aos_capacity_publication_private.root_entry),epoch,coalesce(head_origin_hash,'none') FROM aos_capacity_publication_private.registry_epoch;"
    assert run(audit).stdout.strip()=='0|0|0|0|none'
    assert run(f['begin']+f['call']+'COMMIT;').stdout.strip()==f['digest']
    assert run(audit).stdout.strip()=='1|1|2|1|'+f['digest']
    original=run("SELECT encode(o.raw_body,'hex'),encode(o.signature,'hex'),encode(s.raw_body,'hex') FROM aos_capacity_publication_private.origin o JOIN aos_capacity_publication_private.root_snapshot s USING(org_id,project_id,snapshot_hash);").stdout.strip().split('|')
    assert original==[f['body'].hex(),f['signature'].hex(),f['root_bytes'].hex()]
    assert run(f['begin']+f['call']+'COMMIT;').stdout.strip()==f['digest']
    assert run(audit).stdout.strip()=='1|1|2|1|'+f['digest']
    print('CAPACITY_ROOT_COMMIT_PROOF '+f['database']+' rollback=empty committed=exact replay=epoch1 formal_installation=false final_commit_ttl=false')


class _NativeSqlSession:
    def __init__(self,command):
        import queue,subprocess,threading
        self.process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        self.lines=queue.Queue();self.errors=[]
        def read():
            for line in self.process.stdout:self.lines.put(line.strip())
            self.lines.put(None)
        def errors():
            for line in self.process.stderr:self.errors.append(line)
        threading.Thread(target=read,daemon=True).start();threading.Thread(target=errors,daemon=True).start()
    def send(self,statement):
        self.process.stdin.write(statement+'\n');self.process.stdin.flush()
    def line(self):
        value=self.lines.get(timeout=12)
        assert value is not None,''.join(self.errors)
        return value
    def close(self):
        try:self.send('ROLLBACK; RESET SESSION AUTHORIZATION; \\q')
        except (BrokenPipeError,ValueError):pass
        try:self.process.wait(timeout=12)
        finally:
            if self.process.poll() is None:self.process.terminate()


@pytest.mark.parametrize('order',['registrar_first','writer_first'])
def test_native_registry_epoch_actual_commit_competition(committed_native_registry,order):
    import time
    f=committed_native_registry;run=f['run']
    run(f['begin']+f['call']+'COMMIT;')
    registrar=_NativeSqlSession(f['command']);writer=_NativeSqlSession(f['command'])
    try:
        registrar.send(f['begin']+"SELECT 'pid:'||pg_backend_pid();");rpid=int(registrar.line().split(':')[1])
        writer.send("BEGIN; SET LOCAL statement_timeout='10s'; SELECT 'pid:'||pg_backend_pid();");wpid=int(writer.line().split(':')[1])
        update="UPDATE aos_capacity_publication_private.registry_epoch SET epoch=epoch+1 WHERE org_id='org-org' AND project_id='dev-project'; SELECT 'writer-ready';"
        if order=='registrar_first':
            registrar.send(f['call']);assert registrar.line()==f['digest']
            writer.send(update);waiting,holding=wpid,rpid
        else:
            writer.send(update);assert writer.line()=='writer-ready'
            registrar.send(f['call']);waiting,holding=rpid,wpid
        deadline=time.monotonic()+4;blocked=False
        while time.monotonic()<deadline:
            observed=run('SELECT '+str(holding)+'=ANY(pg_blocking_pids('+str(waiting)+'));').stdout.strip()
            if observed=='t':blocked=True;break
            time.sleep(.03)
        assert blocked,'native epoch row did not coordinate actual sessions'
        if order=='registrar_first':
            registrar.send("COMMIT; SELECT 'registrar-committed';");assert registrar.line()=='registrar-committed'
            assert writer.line()=='writer-ready'
            writer.send("COMMIT; SELECT 'writer-committed';");assert writer.line()=='writer-committed'
        else:
            writer.send("COMMIT; SELECT 'writer-committed';");assert writer.line()=='writer-committed'
            assert registrar.lines.get(timeout=12) is None
            assert registrar.process.wait(timeout=5)!=0
            assert 'CAPACITY_ORIGIN_REGISTRATION_DENIED' in ''.join(registrar.errors)
        assert run('SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch;').stdout.strip()=='2|'+f['digest']
        failure=run(f['begin']+f['call']+'COMMIT;',success=False)
        assert 'CAPACITY_ORIGIN_REGISTRATION_DENIED' in failure.stderr
        assert run('SELECT count(*) FROM aos_capacity_publication_private.origin;').stdout.strip()=='1'
        print('CAPACITY_ROOT_EPOCH_COMMIT_PROOF '+f['database']+' order='+order+' waiting='+str(waiting)+' holding='+str(holding)+' blocked=true epoch=2 old_origin_rejected=true administrative_invalidation_only=true')
    finally:
        # Release both transactions before waiting on either subprocess.
        for session in (registrar,writer):
            try:session.send('ROLLBACK;')
            except (BrokenPipeError,ValueError):pass
        registrar.close();writer.close()


def test_native_signed_registration_near_transport_bound_commit(committed_native_registry):
    import json,subprocess
    from aos_api.asset_registry.canonical_json import canonical_json
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap
    from tests.aip.test_provider_capacity_publication_pg import _root_snapshot_fixture_row
    f=committed_native_registry
    roots=[_root_snapshot_fixture_row('key-%05d-'%i+'\x7f'*85) for i in range(10000)]
    full=json.dumps(dict(trustRoots=roots),sort_keys=True,separators=(',',':')).encode('ascii')
    assert len(full)==8190016
    payload=json.loads(f['body']);payload['rootSnapshotHash']='sha256:'+hashlib.sha256(full).hexdigest()
    body=canonical_json(ProviderCapacityOriginBootstrap.model_validate(payload).model_dump(mode='json',by_alias=True));signature=f['sign_key'].sign(body)
    chunks=['%s\t%s'%(i,full[n:n+32768].hex()) for i,n in enumerate(range(0,len(full),32768))]
    load="BEGIN; SET LOCAL statement_timeout='90s'; CREATE TEMP TABLE full_root_parts(n integer,hex text); COPY full_root_parts FROM STDIN;\n"+'\n'.join(chunks)+'\n\\.\n'+"CREATE TEMP TABLE full_root_input AS SELECT decode(string_agg(hex,'' ORDER BY n),'hex') AS body FROM full_root_parts; GRANT SELECT ON full_root_input TO "+PUBLISHER+';'
    load+="SELECT encode(sha256(body),'hex') FROM full_root_input; SET LOCAL aos.org_id='org-org'; SET LOCAL aos.project_id='dev-project'; SET SESSION AUTHORIZATION "+PUBLISHER+';'
    load+="SELECT aos_capacity_publication_private.register_origin(decode('%s','hex'),decode('%s','hex'),(SELECT body FROM pg_temp.full_root_input)); COMMIT;"%(body.hex(),signature.hex())
    result=subprocess.run(f['command'],input=load,text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip().splitlines()==[hashlib.sha256(full).hexdigest(),hashlib.sha256(body).hexdigest()]
    observed=f['run']("SELECT count(*),min(root_ordinal),max(root_ordinal) FROM aos_capacity_publication_private.root_entry; SELECT root_count,octet_length(raw_body),encode(sha256(raw_body),'hex') FROM aos_capacity_publication_private.root_snapshot; SELECT epoch,head_origin_hash FROM aos_capacity_publication_private.registry_epoch;").stdout.strip().splitlines()
    assert observed==['10000|1|10000','10000|8190016|'+hashlib.sha256(full).hexdigest(),'1|'+hashlib.sha256(body).hexdigest()]
    print('CAPACITY_ROOT_MAXIMUM_COMMIT_PROOF '+f['database']+' count=10000 bytes=8190016 sha256='+hashlib.sha256(full).hexdigest()+' native_memory=256MiB original_file_provenance=false committed=true')
