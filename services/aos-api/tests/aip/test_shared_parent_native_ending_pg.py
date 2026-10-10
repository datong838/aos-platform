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
