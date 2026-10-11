"""Real isolated PG scope/identity tests; no formal business credential claim."""
import os
import secrets
from uuid import uuid4
import psycopg
from psycopg import sql
import pytest
from aos_api.tenant_scope import TenantScope
from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig, BIIssuerDatabaseBlocked
from aos_api.aip_source_issuer_connection import (
    SourceIssuerDatabaseConfig, connect_source_issuer_write, connect_source_issuer_read_only,
)

pytestmark=pytest.mark.skipif(os.getenv('AOS_SOURCE_ISSUER_PG_TEST')!='1',reason='isolated PG opt-in required')
SCOPE=TenantScope('org-org','dev-project')
ROLES={'plan':'aos_bi_plan_issuer','content':'aos_content_source_issuer','contract':'aos_contract_source_issuer'}


@pytest.fixture
def issuer_case(tmp_path):
    schema='source_conn_'+uuid4().hex[:12]
    parent=tmp_path/'identities';parent.mkdir(mode=0o700)
    configs={}
    with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True) as admin:
        assert admin.execute("SELECT count(*) FROM pg_roles WHERE rolname=ANY(%s)",(list(ROLES.values()),)).fetchone()[0]==0
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        try:
            admin.execute(sql.SQL('CREATE TABLE {}.scoped(org_id text,project_id text,value text)').format(sql.Identifier(schema)))
            admin.execute(sql.SQL('ALTER TABLE {}.scoped ENABLE ROW LEVEL SECURITY').format(sql.Identifier(schema)))
            admin.execute(sql.SQL('ALTER TABLE {}.scoped FORCE ROW LEVEL SECURITY').format(sql.Identifier(schema)))
            for kind,role in ROLES.items():
                password=secrets.token_hex(24)
                admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
                path=parent/(kind+'.pgpass');path.write_text(f'127.0.0.1:18432:postgres:{role}:{password}\n');path.chmod(0o600)
                admin.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
                admin.execute(sql.SQL('GRANT SELECT,INSERT ON {}.scoped TO {}').format(sql.Identifier(schema),sql.Identifier(role)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {}.scoped TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(kind),sql.Identifier(schema),sql.Identifier(role)))
                configs[kind]=SourceIssuerDatabaseConfig(kind,BIIssuerDatabaseConfig('127.0.0.1',18432,'postgres',path))
            yield configs,schema,admin
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            for role in ROLES.values():
                if admin.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone():
                    admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
                    admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


@pytest.mark.parametrize('kind',list(ROLES))
def test_actual_fixed_identity_scope_and_original_commit_rebind(issuer_case,kind):
    configs,schema,admin=issuer_case
    with connect_source_issuer_write(configs[kind],SCOPE) as conn:
        row=conn.execute("SELECT session_user,current_user,current_setting('aos.org_id') AS org,current_setting('aos.project_id') AS project,current_setting('transaction_isolation') AS isolation").fetchone()
        assert row=={'session_user':ROLES[kind],'current_user':ROLES[kind],'org':SCOPE.org_id,'project':SCOPE.project_id,'isolation':'serializable'}
        conn.execute(sql.SQL('INSERT INTO {}.scoped VALUES(%s,%s,%s)').format(sql.Identifier(schema)),(*SCOPE.key,'committed'))
        conn.commit()
        assert conn.execute("SELECT current_setting('aos.org_id') AS org").fetchone()['org']==SCOPE.org_id
        conn.execute(sql.SQL('INSERT INTO {}.scoped VALUES(%s,%s,%s)').format(sql.Identifier(schema)),(*SCOPE.key,'rolled-back'))
        conn.rollback()
        assert conn.execute("SELECT current_setting('aos.project_id') AS project").fetchone()['project']==SCOPE.project_id
    assert admin.execute(sql.SQL('SELECT value FROM {}.scoped').format(sql.Identifier(schema))).fetchall()==[('committed',)]
    with connect_source_issuer_read_only(configs[kind],TenantScope('dev-org','dev-project')) as conn:
        assert conn.execute(sql.SQL('SELECT value FROM {}.scoped').format(sql.Identifier(schema))).fetchall()==[]
        assert conn.execute("SHOW transaction_read_only").fetchone()['transaction_read_only']=='on'


@pytest.mark.parametrize('kind',list(ROLES))
def test_cross_tenant_write_and_role_membership_rejected(issuer_case,kind):
    configs,schema,admin=issuer_case
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_source_issuer_write(configs[kind],SCOPE) as conn:
            conn.execute(sql.SQL('INSERT INTO {}.scoped VALUES(%s,%s,%s)').format(sql.Identifier(schema)),('dev-org','dev-project','forbidden'))
    # A third-party group is unsafe even without direct runtime membership.
    other='source_unsafe_'+uuid4().hex[:12]
    admin.execute(sql.SQL('CREATE ROLE {} NOLOGIN').format(sql.Identifier(other)))
    try:
        admin.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(other),sql.Identifier(ROLES[kind])))
        with pytest.raises(BIIssuerDatabaseBlocked):
            with connect_source_issuer_write(configs[kind],SCOPE):
                raise AssertionError('unsafe connection opened')
    finally:
        admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(other)))


def test_config_and_environment_reject_before_connect(issuer_case,monkeypatch):
    configs,_,_=issuer_case
    with pytest.raises(BIIssuerDatabaseBlocked):
        SourceIssuerDatabaseConfig('runtime',configs['plan'].database)
    monkeypatch.setenv('PGPASSWORD','untrusted-test-value')
    with pytest.raises(BIIssuerDatabaseBlocked):
        with connect_source_issuer_write(configs['plan'],SCOPE):
            raise AssertionError('environment override opened a connection')


def test_private_credentials_rechecked_before_connect(issuer_case):
    configs,_,_=issuer_case
    configs['contract'].database.passfile.chmod(0o644)
    with pytest.raises(BIIssuerDatabaseBlocked):
        with connect_source_issuer_write(configs['contract'],SCOPE):
            raise AssertionError('unprotected credential accepted')


@pytest.mark.parametrize('attribute',['CREATEROLE','CREATEDB','REPLICATION'])
def test_elevated_issuer_attributes_are_rejected(issuer_case,attribute):
    configs,_,admin=issuer_case
    admin.execute(sql.SQL('ALTER ROLE {} {}').format(sql.Identifier(ROLES['contract']),sql.SQL(attribute)))
    with pytest.raises(BIIssuerDatabaseBlocked):
        with connect_source_issuer_write(configs['contract'],SCOPE):
            raise AssertionError('elevated issuer opened a connection')
