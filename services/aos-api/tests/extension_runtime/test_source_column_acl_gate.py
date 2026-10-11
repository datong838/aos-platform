"""Native ACL probes in a new schema of the already-owned disposable clone."""
from pathlib import Path
import json,subprocess,uuid
import pytest
import psycopg
from psycopg import sql
from aos_api.extension_runtime import configuration_stage_preflight as gate

NAMES=('aip_responsibility_plan_head','aip_responsibility_plan_revision','aip_production_contract_receipt')

@pytest.fixture
def acl(monkeypatch):
    root=Path(__file__).resolve().parents[4]
    expected=json.loads((root/'.evidence/qyh-source-boundary-clone-20261011/restore-verified.json').read_text())
    actual=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect','--format','{"Id":{{json .Id}},"Mounts":{{json .Mounts}}}','qyh-source-boundary-clone-20261011'],text=True))
    assert actual['Id']==expected['container']['Id'] and not actual['Mounts']
    schema='qyh_acl_'+uuid.uuid4().hex
    with psycopg.connect(host='127.0.0.1',port=18431,user='aos_app',dbname='postgres',autocommit=True) as conn:
        assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==expected['cloneIdentity']['cluster']
        assert conn.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_runtime'").fetchone()
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            conn.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(schema)))
            for name in NAMES:
                table=sql.Identifier(schema,name)
                conn.execute(sql.SQL('CREATE TABLE {} (id integer)').format(table))
                conn.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(table))
                conn.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(table))
                conn.execute(sql.SQL('GRANT SELECT ON {} TO aos_runtime').format(table))
                conn.execute(sql.SQL('CREATE POLICY qyh_acl_fixture ON {} TO aos_runtime USING (true) WITH CHECK (true)').format(table))
            monkeypatch.setattr(gate,'_SOURCE_TABLES',tuple(schema+'.'+n for n in NAMES))
            yield conn,schema
        finally:conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_original_no_source_write_accepts(acl):
    conn,_=acl
    with conn.transaction():assert gate.configuration_source_acl_ready(conn) is True

@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('right',['INSERT','UPDATE'])
def test_column_write_cannot_hide_behind_absent_table_grant(acl,name,right):
    conn,schema=acl
    conn.execute(sql.SQL('GRANT {}(id) ON {} TO aos_runtime').format(sql.SQL(right),sql.Identifier(schema,name)))
    table=schema+'.'+name
    assert conn.execute("SELECT has_table_privilege('aos_runtime',%s,%s)",(table,right)).fetchone()[0] is False
    assert conn.execute("SELECT has_any_column_privilege('aos_runtime',%s,%s)",(table,right)).fetchone()[0] is True
    with conn.transaction():assert gate.configuration_source_acl_ready(conn) is False


def test_table_write_still_refused(acl):
    conn,schema=acl
    conn.execute(sql.SQL('GRANT INSERT ON {} TO aos_runtime').format(sql.Identifier(schema,NAMES[0])))
    with conn.transaction():assert gate.configuration_source_acl_ready(conn) is False


@pytest.mark.parametrize('right',['INSERT','UPDATE'])
def test_native_column_write_is_real_even_without_table_grant(acl,right):
    conn,schema=acl
    table=sql.Identifier(schema,NAMES[0])
    conn.execute(sql.SQL('INSERT INTO {} (id) VALUES(1)').format(table))
    conn.execute(sql.SQL('GRANT {}(id) ON {} TO aos_runtime').format(sql.SQL(right),table))
    assert conn.execute("SELECT has_table_privilege('aos_runtime',%s,%s)",(schema+'.'+NAMES[0],right)).fetchone()[0] is False
    with conn.transaction(force_rollback=True):
        conn.execute('SET LOCAL ROLE aos_runtime')
        if right=='INSERT':conn.execute(sql.SQL('INSERT INTO {} (id) VALUES(2)').format(table))
        else:conn.execute(sql.SQL('UPDATE {} SET id=2 WHERE id=1').format(table))
        assert conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE id=2').format(table)).fetchone()[0]==1
        assert gate.configuration_source_acl_ready(conn) is False
    assert conn.execute(sql.SQL('SELECT array_agg(id) FROM {}').format(table)).fetchone()[0]==[1]
