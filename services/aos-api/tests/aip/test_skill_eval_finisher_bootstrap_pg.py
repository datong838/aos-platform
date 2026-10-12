"""Explicit maintenance prototype on a new full clone only."""
import os
from uuid import uuid4
import json

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict,make_conninfo
from psycopg.rows import dict_row

from aos_api.aip_skill_eval_finisher_bootstrap import install_skill_finisher_permissions


@pytest.fixture
def bootstrap_database():
    original=os.environ['AOS_DATABASE_URL'];parts=conninfo_to_dict(original)
    assert parts['host']=='127.0.0.1' and parts['port']=='18431'
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    database='aos_test_'+uuid4().hex[:12]+'_ti4_test'
    with psycopg.connect(original,autocommit=True) as admin:
        assert admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone() is None
        admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(parts['dbname'])))
        try:yield make_conninfo(**{**parts,'dbname':database}),database
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(database)))
            if admin.execute("SELECT 1 FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone():
                admin.execute('DROP ROLE aos_skill_eval_finisher')


def baseline(conn):
    return conn.execute("""SELECT c.relname,c.relacl::text,c.relowner,c.relrowsecurity,c.relforcerowsecurity,
        (SELECT json_agg(json_build_object('name',a.attname,'acl',a.attacl::text) ORDER BY a.attnum)
         FROM pg_attribute a WHERE a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped) AS columns,
        (SELECT count(*) FROM aip_eval_run) AS runs,
        (SELECT count(*) FROM aip_eval_run_event) AS events
        FROM pg_class c WHERE c.oid IN ('public.aip_eval_run'::regclass,'public.aip_eval_run_event'::regclass)
        ORDER BY c.relname""").fetchall()


def old_authority(conn):
    return conn.execute("""SELECT c.relname,
        (SELECT json_agg(json_build_object('grantor',a.grantor,'grantee',a.grantee,'privilege',a.privilege_type,'option',a.is_grantable)
         ORDER BY a.grantor,a.grantee,a.privilege_type) FROM aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a
         WHERE a.grantee<>coalesce((SELECT oid FROM pg_roles WHERE rolname='aos_skill_eval_finisher'),'4294967295'::oid)) AS grants,
        (SELECT json_agg(json_build_object('column',at.attname,'grantor',a.grantor,'grantee',a.grantee,'privilege',a.privilege_type,'option',a.is_grantable)
         ORDER BY at.attnum,a.grantee,a.privilege_type) FROM pg_attribute at CROSS JOIN LATERAL aclexplode(at.attacl) a
         WHERE at.attrelid=c.oid AND a.grantee<>coalesce((SELECT oid FROM pg_roles WHERE rolname='aos_skill_eval_finisher'),'4294967295'::oid)) AS column_grants,
        (SELECT json_agg(json_build_object('name',p.polname,'command',p.polcmd,'roles',p.polroles::text,'using',pg_get_expr(p.polqual,p.polrelid),'check',pg_get_expr(p.polwithcheck,p.polrelid)) ORDER BY p.polname)
         FROM pg_policy p WHERE p.polrelid=c.oid AND p.polname NOT LIKE 'skill_finisher_%') AS policies
        FROM pg_class c WHERE c.oid IN ('public.aip_eval_run'::regclass,'public.aip_eval_run_event'::regclass)
        ORDER BY c.relname""").fetchall()


@pytest.mark.parametrize('scenario',['commit','rollback','wrong-database','wrong-cluster','read-committed','writer-update','unsafe-role','policy-collision','member','unknown-grant','owner-drift','schema-grant','unknown-role-policy'])
def test_native_guarded_bootstrap(bootstrap_database,scenario):
    dsn,database=bootstrap_database
    with psycopg.connect(dsn,row_factory=dict_row) as conn:
        before=baseline(conn);authority=old_authority(conn);conn.rollback()
        conn.execute('SET TRANSACTION ISOLATION LEVEL '+('READ COMMITTED' if scenario=='read-committed' else 'SERIALIZABLE'))
        cluster=conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']
        if scenario=='writer-update':conn.execute('GRANT UPDATE(status) ON aip_eval_run TO aos_aip_eval_writer')
        elif scenario=='unsafe-role':conn.execute('CREATE ROLE aos_skill_eval_finisher LOGIN INHERIT')
        elif scenario=='policy-collision':conn.execute('CREATE POLICY skill_finisher_run_read ON aip_eval_run FOR SELECT USING(true)')
        elif scenario=='member':
            conn.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
            conn.execute('CREATE ROLE bootstrap_fixture_peer NOLOGIN')
            conn.execute('GRANT aos_skill_eval_finisher TO bootstrap_fixture_peer')
        elif scenario=='unknown-grant':
            conn.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
            conn.execute('GRANT SELECT ON aip_eval_run TO aos_skill_eval_finisher')
        elif scenario=='schema-grant':
            conn.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
            conn.execute('GRANT USAGE ON SCHEMA public TO aos_skill_eval_finisher')
        elif scenario=='unknown-role-policy':
            conn.execute('CREATE ROLE aos_skill_eval_finisher NOLOGIN NOINHERIT')
            conn.execute('CREATE POLICY unknown_finisher_authority ON aip_eval_run TO aos_skill_eval_finisher USING(true)')
        elif scenario=='owner-drift':conn.execute('ALTER TABLE aip_eval_run OWNER TO aos_runtime')
        if scenario in {'commit','rollback'}:
            install_skill_finisher_permissions(conn,expected_database=database,expected_cluster=cluster)
            assert conn.execute("SELECT rolcanlogin,rolinherit FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone()=={'rolcanlogin':False,'rolinherit':False}
            assert not conn.execute("SELECT has_table_privilege('aos_aip_eval_writer','aip_eval_run','UPDATE') AS writable").fetchone()['writable']
            if scenario=='rollback':conn.rollback()
            else:conn.commit()
        else:
            with pytest.raises(RuntimeError):
                install_skill_finisher_permissions(conn,expected_database='wrong' if scenario=='wrong-database' else database,expected_cluster='0' if scenario=='wrong-cluster' else cluster)
            conn.rollback()
        assert baseline(conn)==before if scenario!='commit' else True
        if scenario!='commit':
            assert conn.execute("SELECT count(*) AS n FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone()['n']==0
        else:
            after=baseline(conn)
            assert old_authority(conn)==authority
            for row,old in zip(after,before,strict=True):
                assert (row['runs'],row['events'],row['relowner'],row['relrowsecurity'],row['relforcerowsecurity'])==(old['runs'],old['events'],old['relowner'],old['relrowsecurity'],old['relforcerowsecurity'])
            assert conn.execute("SELECT count(*) AS n FROM pg_policy WHERE polname LIKE 'skill_finisher_%'").fetchone()['n']==6
            scope_policies=conn.execute("SELECT polpermissive,polroles FROM pg_policy WHERE polname IN ('skill_finisher_run_scope','skill_finisher_event_scope')").fetchall()
            oid=conn.execute("SELECT oid FROM pg_roles WHERE rolname='aos_skill_eval_finisher'").fetchone()['oid']
            assert len(scope_policies)==2 and all(not p['polpermissive'] and p['polroles']==[oid] for p in scope_policies)
            assert conn.execute("SELECT count(*) AS n FROM pg_auth_members WHERE roleid=(SELECT oid FROM pg_roles WHERE rolname='aos_skill_eval_finisher') OR member=(SELECT oid FROM pg_roles WHERE rolname='aos_skill_eval_finisher')").fetchone()['n']==0
            columns=conn.execute("SELECT attname FROM pg_attribute WHERE attrelid='public.aip_eval_run'::regclass AND attnum>0 AND NOT attisdropped AND has_column_privilege('aos_skill_eval_finisher',attrelid,attnum,'UPDATE')").fetchall()
            assert {r['attname'] for r in columns}=={'status','version','started_at','finished_at'}
            assert not conn.execute("SELECT has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS broad").fetchone()['broad']
