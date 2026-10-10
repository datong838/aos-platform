"""Isolated native ending support. These tests do not authorize admission."""
import hashlib
import json
import os
from pathlib import Path
import uuid
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest

NATIVE = 'aos_admission_native_private.pending_relations()'
OWNER = 'aos_physical_capacity_occupation_owner'

@pytest.fixture(scope='module')
def native_ending_lab():
    spec_path = os.environ.get('AOS_NATIVE_END_TEST_SPEC')
    if not spec_path:
        pytest.skip('Explicit isolated native package specification required')
    spec = json.loads(Path(spec_path).read_text())
    root = Path(__file__).resolve().parents[4]
    package = root / 'services/aos-api/postgres-extensions/aos_admission_end'
    lab = json.loads((root / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
    assert spec['cluster'] == lab['cluster'] and spec['database'] == 'aos_test_05f1a1dcd51f_ti4_test'
    assert spec['library'].startswith('/tmp/aos_admission_end_')
    for name, digest in spec['source_hashes'].items():
        assert hashlib.sha256((package/name).read_bytes()).hexdigest() == digest
    params = dict(host='127.0.0.1', port=lab['port'], user='aos_app',
                  dbname=spec['database'], passfile=lab['passfile'], row_factory=dict_row)
    schema = 'test_owned_native_end_' + uuid.uuid4().hex
    with psycopg.connect(**params) as c:
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
        assert c.execute("SELECT to_regnamespace('aos_admission_native_private') AS n").fetchone()['n'] is None
        c.execute('CREATE SCHEMA aos_admission_native_private AUTHORIZATION '+OWNER)
        ddl = (package/'aos_admission_end--0.1.sql').read_text()
        c.execute(ddl.replace("'MODULE_PATHNAME'", sql.Literal(spec['library']).as_string(c)), prepare=False)
        c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION '+OWNER)
        for table in ('one','two','sample'):
            c.execute('CREATE TABLE '+schema+'.'+table+'(id integer PRIMARY KEY)')
            c.execute('ALTER TABLE '+schema+'.'+table+' OWNER TO '+OWNER)
        c.execute('CREATE TABLE '+schema+'.audit(id integer,pending oid[])')
        c.execute('ALTER TABLE '+schema+'.audit OWNER TO '+OWNER)
        c.execute('CREATE FUNCTION '+schema+'.noop() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$')
        c.execute('ALTER FUNCTION '+schema+'.noop() OWNER TO '+OWNER)
        c.execute('REVOKE ALL ON FUNCTION '+schema+'.noop() FROM PUBLIC')
        c.execute('CREATE FUNCTION '+schema+'.sample() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN INSERT INTO '+schema+'.audit VALUES(NEW.id,aos_admission_native_private.pending_relations()); RETURN NEW; END $$')
        c.execute('ALTER FUNCTION '+schema+'.sample() OWNER TO '+OWNER)
        c.execute('REVOKE ALL ON FUNCTION '+schema+'.sample() FROM PUBLIC')
        for table in ('one','two','sample'):
            fn = 'sample' if table == 'sample' else 'noop'
            c.execute('CREATE CONSTRAINT TRIGGER '+table+'_event AFTER INSERT ON '+schema+'.'+table+' DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+schema+'.'+fn+'()')
        c.commit()
    proof = dict(schema=schema, library=spec['library'], installation_committed=True,
                 formal_admission=False, execution_allowed=False)
    path = Path(spec['evidence'])/'native-proof.json'
    path.open('x').write(json.dumps(proof,indent=2)+'\n')
    return params, schema, path, spec

def store(path, **fields):
    proof = json.loads(path.read_text()); proof.update(fields)
    path.write_text(json.dumps(proof,indent=2)+'\n')

def pending(c):
    return c.execute('SELECT '+NATIVE+' AS relations').fetchone()['relations']

def relation(c, name):
    return c.execute('SELECT %s::regclass::oid AS oid',(name,)).fetchone()['oid']

def test_native_owner_acl_and_metadata(native_ending_lab):
    params, schema, path, spec = native_ending_lab
    with psycopg.connect(**params) as c:
        c.execute('SET TRANSACTION READ ONLY')
        meta = c.execute('SELECT pg_get_userbyid(proowner) AS owner,prosrc,probin,prosecdef,proconfig,provolatile,proparallel,prorettype::regtype::text AS result FROM pg_proc WHERE oid=%s::regprocedure',(NATIVE,)).fetchone()
        assert meta == dict(owner=OWNER, prosrc='aos_admission_pending_relations',
            probin=spec['library'], prosecdef=False, proconfig=['search_path=pg_catalog'],
            provolatile='v', proparallel='u', result='oid[]')
        for role in ('aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_occupation'):
            assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,NATIVE)).fetchone()['allowed']
        assert not c.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE') AS public",(NATIVE,)).fetchone()['public']
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='SHARED_ADMISSION_NATIVE_OWNER_REQUIRED'):
            pending(c)  # Superuser EXECUTE bypass still cannot pass the C Owner check.
    store(path, native_metadata_exact=True, public_runtime_closed=True, non_owner_denied=True)

def test_native_pending_two_relations_and_savepoint(native_ending_lab):
    params, schema, path, spec = native_ending_lab
    with psycopg.connect(**params) as c:
        c.execute('SET LOCAL ROLE '+OWNER)
        assert pending(c) == []
        one, two = [relation(c,schema+'.'+t) for t in ('one','two')]
        c.execute('INSERT INTO '+schema+'.one VALUES(1)')
        c.execute('INSERT INTO '+schema+'.two VALUES(1)')
        assert set(pending(c)) == {one,two}
        c.execute('SAVEPOINT drain')
        c.execute('SET CONSTRAINTS '+schema+'.one_event IMMEDIATE')
        assert pending(c) == [two]
        c.execute('ROLLBACK TO SAVEPOINT drain')
        assert set(pending(c)) == {one,two}
        xid = c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        c.rollback()
    with psycopg.connect(**params) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(xid,)).fetchone()['state']=='aborted'
        assert all(c.execute('SELECT count(*) AS n FROM '+schema+'.'+t).fetchone()['n']==0 for t in ('one','two'))
    store(path,two_pending_relations=True,exact_scoped_drain=True,rollback_restores_pending=True,drain_xid=xid,drain_xid_aborted=True)

def test_native_reports_executing_and_future_relation_at_actual_commit(native_ending_lab):
    params, schema, path, spec = native_ending_lab
    with psycopg.connect(**params) as c:
        c.execute('SET LOCAL ROLE '+OWNER)
        current, future = [relation(c,schema+'.'+t) for t in ('sample','two')]
        c.execute('INSERT INTO '+schema+'.sample VALUES(2)')
        c.execute('INSERT INTO '+schema+'.two VALUES(2)')
        xid=c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        store(path,commit_intent=dict(xid=xid,relations=[current,future]))
        c.commit()
        store(path,commit_returned=True)
    with psycopg.connect(**params) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT pg_xact_status(%s::xid8) AS state',(xid,)).fetchone()['state']=='committed'
        rows=c.execute('SELECT * FROM '+schema+'.audit').fetchall()
        assert len(rows)==1 and rows[0]['id']==2 and set(rows[0]['pending'])=={current,future}
    store(path, actual_commit_self_and_future_reported=True, commit_xid_committed=True)

def test_native_same_statement_new_relation_visibility(native_ending_lab):
    params, schema, path, spec = native_ending_lab
    with psycopg.connect(**params) as c:
        c.execute('SET LOCAL ROLE '+OWNER)
        c.execute('DO $$ BEGIN CREATE TABLE '+schema+'.new_relation(id integer); CREATE CONSTRAINT TRIGGER new_event AFTER INSERT ON '+schema+'.new_relation DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+schema+'.noop(); INSERT INTO '+schema+".new_relation VALUES(1); IF NOT '"+schema+".new_relation'::regclass::oid=ANY(aos_admission_native_private.pending_relations()) THEN RAISE EXCEPTION 'NEW_RELATION_PENDING_NOT_VISIBLE'; END IF; END $$")
        c.rollback()
    with psycopg.connect(**params) as c:
        c.execute('SET TRANSACTION READ ONLY')
        assert c.execute('SELECT to_regclass(%s) AS rel',(schema+'.new_relation',)).fetchone()['rel'] is None
    store(path, same_statement_new_relation_visible=True, new_relation_rolled_back=True)

MODULES = 'aos_admission_native_private.loaded_module_paths()'

@pytest.fixture
def native_module_lab():
    """New SQL tail is transaction-owned; original installed reader is retained."""
    spec_path = os.environ.get('AOS_NATIVE_MODULE_TEST_SPEC')
    if not spec_path:
        pytest.skip('Explicit isolated native module specification required')
    import subprocess
    spec = json.loads(Path(spec_path).read_text())
    root = Path(__file__).resolve().parents[4]
    package = root/'services/aos-api/postgres-extensions/aos_admission_end'
    lab = json.loads((root/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
    assert spec['cluster'] == lab['cluster'] and spec['database'] == 'aos_test_05f1a1dcd51f_ti4_test'
    assert spec['library'].startswith('/tmp/aos_admission_modules_')
    for name,digest in spec['source_hashes'].items():
        assert hashlib.sha256((package/name).read_bytes()).hexdigest()==digest
    assert subprocess.check_output(['docker','exec',lab['name'],'sha256sum',spec['library']],text=True).split()[0]==spec['library_sha256']
    params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile'],row_factory=dict_row)
    proof=Path(spec['evidence'])/'module-proof.json'
    if not proof.exists():
        proof.open('x').write(json.dumps(dict(full_admission=False,execution_allowed=False,full_task_delivered=False),indent=2)+'\n')
    with psycopg.connect(**params) as c:
        assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
        assert c.execute('SELECT to_regprocedure(%s) AS p',(MODULES,)).fetchone()['p'] is None
        original=c.execute('SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid=%s::regprocedure',(NATIVE,)).fetchone()
        flags=c.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(OWNER,)).fetchone()
        assert not any(flags.values())
        assert c.execute('SELECT count(*) AS n FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',(OWNER,OWNER)).fetchone()['n']==0
        ddl=(package/'aos_admission_end--0.1.sql').read_text().split('-- Supported loader observation, never a caller-supplied package allowlist.',1)[1]
        c.execute(ddl.replace("'MODULE_PATHNAME'",sql.Literal(spec['library']).as_string(c)),prepare=False)
        try:
            yield c,lab,spec,proof
        finally:
            c.rollback()
    with psycopg.connect(**params) as other:
        other.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert other.execute('SELECT to_regprocedure(%s) AS p',(MODULES,)).fetchone()['p'] is None
        assert other.execute('SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid=%s::regprocedure',(NATIVE,)).fetchone()==original
    store(proof,rollback_only_installation_absent=True,original_pending_reader_exact=True)


def module_paths(c):
    return c.execute('SELECT '+MODULES+' AS paths').fetchone()['paths']


def backend_map_paths(c,lab):
    import subprocess
    pid=c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
    raw=subprocess.check_output(['docker','exec',lab['name'],'cat','/proc/'+str(pid)+'/maps'],text=True)
    paths=sorted({line.split(maxsplit=5)[5] for line in raw.splitlines()
        if len(line.split(maxsplit=5))==6 and line.split(maxsplit=5)[5].startswith('/')
        and not line.split(maxsplit=5)[5].endswith(' (deleted)')})
    # A data-only ELF library need not have an executable mapping (ICU data).
    elf=[p for p in paths if subprocess.check_output(['docker','exec',lab['name'],'head','-c','4',p])==b'\x7fELF']
    return sorted({subprocess.check_output(['docker','exec',lab['name'],'readlink','-f',p],text=True).strip() for p in elf})


def test_native_modules_owner_acl_and_exact_metadata(native_module_lab):
    c,lab,spec,proof=native_module_lab
    meta=c.execute('SELECT pg_get_userbyid(proowner) AS owner,prosrc,probin,prosecdef,proconfig,provolatile,proparallel,pronargs,prorettype::regtype::text AS result FROM pg_proc WHERE oid=%s::regprocedure',(MODULES,)).fetchone()
    assert meta==dict(owner=OWNER,prosrc='aos_admission_loaded_module_paths',probin=spec['library'],prosecdef=False,proconfig=['search_path=pg_catalog'],provolatile='v',proparallel='u',pronargs=0,result='text[]')
    for role in ('aos_runtime','aos_provider_capacity_issuer','aos_provider_capacity_occupation'):
        assert not c.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",(role,MODULES)).fetchone()['allowed']
    assert not c.execute("SELECT EXISTS(SELECT 1 FROM pg_proc p CROSS JOIN LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) a WHERE p.oid=%s::regprocedure AND a.grantee=0 AND a.privilege_type='EXECUTE') AS public",(MODULES,)).fetchone()['public']
    c.execute('SAVEPOINT non_owner')
    with pytest.raises(psycopg.errors.InsufficientPrivilege,match='SHARED_ADMISSION_NATIVE_OWNER_REQUIRED'):
        module_paths(c)
    c.execute('ROLLBACK TO SAVEPOINT non_owner')
    store(proof,metadata_exact=True,no_caller_allowlist=True,public_runtime_closed=True,direct_superuser_denied=True)


def test_native_modules_match_independent_backend_maps(native_module_lab):
    c,lab,spec,proof=native_module_lab
    c.execute('DO $$ BEGIN NULL; END $$')
    c.execute("SELECT digest(''::text,'sha256')")
    assert c.execute("SELECT aos_ed25519.verify(''::bytea,''::bytea,''::bytea) AS valid").fetchone()['valid'] is False
    c.execute('SET LOCAL ROLE '+OWNER)
    paths=module_paths(c)
    assert paths==sorted(set(paths))
    disk=[p for p in paths if not p.startswith('virtual:')]
    assert disk==backend_map_paths(c,lab)
    assert '/usr/local/bin/postgres' in paths and spec['library'] in paths
    assert '/usr/local/lib/postgresql/plpgsql.so' in paths
    assert '/usr/local/lib/postgresql/aos_ed25519.so' in paths
    assert module_paths(c)==paths
    import struct,subprocess
    pid=c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
    aux_raw=subprocess.check_output(['docker','exec',lab['name'],'cat','/proc/'+str(pid)+'/auxv'])
    assert len(aux_raw)%16==0
    aux=dict(struct.iter_unpack('<QQ',aux_raw))
    raw_maps=subprocess.check_output(['docker','exec',lab['name'],'cat','/proc/'+str(pid)+'/maps'],text=True)
    vdso=[line for line in raw_maps.splitlines() if line.endswith('[vdso]')]
    assert len(vdso)==1 and int(vdso[0].split('-')[0],16)==aux[33]
    assert [p for p in paths if p.startswith('virtual:')]==['virtual:linux-vdso.so.1']
    store(proof,actual_backend_maps_match=True,repeated_observation_stable=True,loaded_paths=paths,virtual_vdso_matches_kernel_auxv=True)


def test_native_modules_observe_later_foreign_library_without_arming(native_module_lab):
    c,lab,spec,proof=native_module_lab
    import subprocess
    c.execute('SET LOCAL ROLE '+OWNER)
    before=module_paths(c)
    foreign=spec['foreign_library']
    assert foreign.startswith('/tmp/aos_order_') and foreign not in before
    assert subprocess.check_output(['docker','exec',lab['name'],'sha256sum',foreign],text=True).split()[0]==spec['foreign_library_sha256']
    c.execute('RESET ROLE')
    schema='test_owned_module_'+uuid.uuid4().hex
    c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION aos_app')
    c.execute(sql.SQL('CREATE FUNCTION '+schema+".uninvoked(oid,oid,boolean) RETURNS void AS {},'aos_test_order_arm' LANGUAGE c STRICT VOLATILE SET search_path=pg_catalog").format(sql.Literal(foreign)))
    c.execute('REVOKE ALL ON FUNCTION '+schema+'.uninvoked(oid,oid,boolean) FROM PUBLIC')
    c.execute('SET LOCAL ROLE '+OWNER)
    after=module_paths(c)
    assert set(after)-set(before)=={foreign}
    assert [p for p in after if not p.startswith('virtual:')]==backend_map_paths(c,lab)
    store(proof,later_foreign_module_observed=True,foreign_arm_invoked=False,foreign_library=foreign)


def test_native_modules_leave_original_pending_queue_unchanged(native_module_lab):
    c,lab,spec,proof=native_module_lab
    schema='test_owned_module_queue_'+uuid.uuid4().hex
    c.execute('CREATE SCHEMA '+schema+' AUTHORIZATION '+OWNER)
    c.execute(sql.SQL('CREATE FUNCTION '+schema+".pending() RETURNS oid[] AS {},'aos_admission_pending_relations' LANGUAGE c VOLATILE PARALLEL UNSAFE SET search_path=pg_catalog").format(sql.Literal(spec['library'])))
    c.execute('ALTER FUNCTION '+schema+'.pending() OWNER TO '+OWNER)
    c.execute('REVOKE ALL ON FUNCTION '+schema+'.pending() FROM PUBLIC')
    c.execute('CREATE TABLE '+schema+'.sample(id integer PRIMARY KEY)')
    c.execute('ALTER TABLE '+schema+'.sample OWNER TO '+OWNER)
    c.execute('CREATE FUNCTION '+schema+'.noop() RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$')
    c.execute('ALTER FUNCTION '+schema+'.noop() OWNER TO '+OWNER)
    c.execute('REVOKE ALL ON FUNCTION '+schema+'.noop() FROM PUBLIC')
    c.execute('CREATE CONSTRAINT TRIGGER owned_event AFTER INSERT ON '+schema+'.sample DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION '+schema+'.noop()')
    c.execute('SET LOCAL ROLE '+OWNER)
    def queue():
        return c.execute('SELECT '+schema+'.pending() AS relations').fetchone()['relations']
    assert queue()==[]
    oid=relation(c,schema+'.sample')
    c.execute('INSERT INTO '+schema+'.sample VALUES(1)')
    assert queue()==[oid]
    assert spec['library'] in module_paths(c)
    assert queue()==[oid]
    c.execute('SAVEPOINT queue_drain')
    c.execute('SET CONSTRAINTS '+schema+'.owned_event IMMEDIATE')
    assert queue()==[]
    c.execute('ROLLBACK TO SAVEPOINT queue_drain')
    assert queue()==[oid]
    store(proof,new_binary_original_pending_api_native_verified=True,module_observation_does_not_drain_events=True,savepoint_pending_restored=True)
