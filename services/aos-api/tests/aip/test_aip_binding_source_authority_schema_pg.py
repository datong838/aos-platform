"""Storage/ACL evidence only; maintenance fixtures are not trusted issuance."""
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from aos_api.db import get_dsn

TABLES = ('aip_license_source_issuance', 'aip_license_source_head',
          'aip_binding_evaluation_proof')


@pytest.fixture
def owner():
    assert conninfo_to_dict(get_dsn())['dbname'].startswith('aos_test_')
    with psycopg.connect(get_dsn()) as conn:
        yield conn
        conn.rollback()


def test_source_schema_exists_without_implicit_issuance(owner):
    for table in TABLES:
        assert owner.execute('SELECT to_regclass(%s)', ('public.' + table,)).fetchone()[0]
        assert owner.execute("""SELECT relrowsecurity,relforcerowsecurity,
            NOT EXISTS (SELECT 1 FROM aclexplode(relacl) a WHERE a.grantee=0)
            FROM pg_class WHERE oid=%s::regclass""", ('public.' + table,)).fetchone() == (True,True,True)
    config=Config()
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[2]/'alembic'))
    assert owner.execute('SELECT version_num FROM alembic_version').fetchall() == [(ScriptDirectory.from_config(config).get_current_head(),)]


@pytest.fixture
def source(owner):
    suffix = uuid4().hex
    bundle, issuance, receipt, binding = ('b82.' + suffix + name for name in ('bundle','issuance','receipt','binding'))
    installation = uuid4()
    issuance_count=owner.execute('SELECT count(*) FROM aip_license_source_issuance').fetchone()[0]
    owner.execute("INSERT INTO twa_org(id,name) VALUES('org-org','test-only') ON CONFLICT DO NOTHING")
    owner.execute("INSERT INTO twa_workspace(org_id,project_id,name) VALUES('org-org','dev-project','test-only') ON CONFLICT DO NOTHING")
    owner.execute("""INSERT INTO aip_evidence_bundle_revision
        (org_id,project_id,bundle_id,revision,brief_ref,subject_refs,cutoff_at,item_refs,
         coverage,missing,conflicts,uncertainties,freshness,marking,license_summary,
         content_hash,lifecycle,created_by)
        VALUES('org-org','dev-project',%s,1,'{}','[]',NOW(),'[]','complete','[]','[]',
         '[]','fresh','{}','{"license":"ordinary-test-only"}',%s,'frozen','test-only')""", (bundle, 'a'*64))
    # Ordinary nonempty license_summary creates no formal source.
    assert owner.execute('SELECT count(*) FROM aip_license_source_issuance').fetchone()[0] == issuance_count
    owner.execute("""INSERT INTO bundle_installation(org_id,project_id,installation_pk,
        installation_id,display_name,current_revision,etag_version,created_by)
        VALUES('org-org','dev-project',%s,%s,'test-only',1,1,'test-only')""", (uuid4(), installation))
    owner.execute("""INSERT INTO aip_agent_registry_receipt(org_id,project_id,receipt_id,
        operation,idempotency_key,request_hash,resource_ref,result_ref,status,created_by,created_at)
        VALUES('org-org','dev-project',%s,'b82.test-only',%s,%s,'{}','{}','applied','test-only',NOW())""", (receipt, suffix, 'b'*64))
    owner.execute("""INSERT INTO aip_capability_binding(org_id,project_id,binding_id,
        capability_ref,secret_ref,health,network_policy_revision,quota_policy_revision,
        timeout_ms,max_concurrency,status)
        VALUES('org-org','dev-project',%s,'{}','vault://test-only','unknown','1','1',100,1,'provisioning')""", (binding,))
    owner.execute("""INSERT INTO aip_license_source_issuance(org_id,project_id,issuance_id,
        bundle_id,revision,content_hash,installation_id,installation_etag,receipt_id,
        owner_authorization_ref,policy_ref,issued_at,expires_at)
        VALUES('org-org','dev-project',%s,%s,1,%s,%s,1,%s,
        '{"test":"owner-fixture"}','{"test":"policy-fixture"}',NOW(),NOW()+INTERVAL '1 hour')""",
        (issuance,bundle,'a'*64,installation,receipt))
    owner.execute("""INSERT INTO aip_license_source_head(org_id,project_id,bundle_id,
        revision,content_hash,issuance_id,epoch)
        VALUES('org-org','dev-project',%s,1,%s,%s,0)""", (bundle,'a'*64,issuance))
    owner.execute("""INSERT INTO aip_binding_evaluation_proof(org_id,project_id,proof_id,
        binding_id,binding_version,installation_id,installation_etag,receipt_id,
        legacy_dependency_hash,facts_hash,facts,checked_at,valid_until)
        VALUES('org-org','dev-project',%s,%s,1,%s,1,%s,%s,%s,
        '{"Provider":{},"Model":{},"Policy":{},"Route":{},"Eval":{},"Health":{},"Capacity":{},"Price":{}}',
        NOW(),NOW()+INTERVAL '1 hour')""", (suffix,binding,installation,receipt,'c'*64,'d'*64))
    return bundle, issuance


@pytest.mark.parametrize('table', TABLES)
def test_runtime_can_read_only_its_tenant_and_cannot_write(owner, source, table):
    owner.execute('SET LOCAL ROLE aos_runtime')
    owner.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
    bundle,_=source
    column='binding_id' if table=='aip_binding_evaluation_proof' else 'bundle_id'
    identifier=bundle[:-6]+'binding' if column=='binding_id' else bundle
    query = sql.SQL('SELECT count(*) FROM {} WHERE {}=%s').format(sql.Identifier(table),sql.Identifier(column))
    assert owner.execute(query,(identifier,)).fetchone()[0] == 1
    for permission in ('INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER'):
        assert not owner.execute('SELECT has_table_privilege(current_user,%s,%s)', (table,permission)).fetchone()[0]
    with pytest.raises(psycopg.errors.InsufficientPrivilege), owner.transaction():
        owner.execute(sql.SQL('INSERT INTO {} SELECT * FROM {} LIMIT 0').format(sql.Identifier(table),sql.Identifier(table)))
    owner.execute("SELECT set_config('aos.org_id','dev-org',true)")
    assert owner.execute(query,(identifier,)).fetchone()[0] == 0
    owner.execute("SELECT set_config('aos.org_id','',true)")
    assert owner.execute(query,(identifier,)).fetchone()[0] == 0


def test_exact_source_and_same_tenant_links_are_enforced(owner, source):
    bundle, issuance = source
    with pytest.raises(psycopg.errors.ForeignKeyViolation), owner.transaction():
        owner.execute("UPDATE aip_license_source_head SET content_hash=%s", ('e'*64,))
    with pytest.raises(psycopg.errors.ForeignKeyViolation), owner.transaction():
        owner.execute("UPDATE aip_license_source_head SET org_id='dev-org'")
    with pytest.raises(psycopg.errors.CheckViolation), owner.transaction():
        owner.execute('UPDATE aip_license_source_head SET epoch=-1')
    assert owner.execute('SELECT epoch FROM aip_license_source_head WHERE bundle_id=%s', (bundle,)).fetchone()[0] == 0


@pytest.mark.parametrize('table', ('aip_license_source_issuance','aip_binding_evaluation_proof'))
@pytest.mark.parametrize('operation', ('UPDATE','DELETE','TRUNCATE'))
def test_immutable_history_rejects_even_maintenance_mutation(owner, source, table, operation):
    before=owner.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
    statement = {'UPDATE':'UPDATE {} SET project_id=project_id',
                 'DELETE':'DELETE FROM {}', 'TRUNCATE':'TRUNCATE {} CASCADE'}[operation]
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState, match='AIP6_REGISTRY_APPEND_ONLY'), owner.transaction():
        owner.execute(sql.SQL(statement).format(sql.Identifier(table)))
    assert owner.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] == before


def test_missing_dimension_and_invalid_validity_rejected(owner, source):
    # Constraints are structural only: canonical source semantics are future command work.
    for change in ("facts='{}'::jsonb", 'valid_until=checked_at'):
        with pytest.raises(psycopg.errors.CheckViolation), owner.transaction():
            # INSERT avoids UPDATE immutable guard and preserves existing proof.
            columns = owner.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='aip_binding_evaluation_proof' ORDER BY ordinal_position").fetchall()
            expressions = [sql.Identifier(c[0]) for c in columns]
            key, value = change.split('=',1)
            expressions[[c[0] for c in columns].index('proof_id')] = sql.Literal(uuid4().hex)
            expressions[[c[0] for c in columns].index(key)] = sql.SQL(value)
            owner.execute(sql.SQL('INSERT INTO aip_binding_evaluation_proof SELECT {} FROM aip_binding_evaluation_proof LIMIT 1').format(sql.SQL(',').join(expressions)))


@pytest.mark.parametrize('column,value', [('content_hash','e'*64), ('revision',2),
                                       ('org_id','dev-org'), ('installation_id',uuid4()),
                                       ('receipt_id','b82.nonexistent')])
def test_issuance_cannot_reference_wrong_exact_source_or_parent(owner, source, column, value):
    columns = owner.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='aip_license_source_issuance' ORDER BY ordinal_position").fetchall()
    expressions = [sql.Identifier(c[0]) for c in columns]
    expressions[[c[0] for c in columns].index('issuance_id')] = sql.Literal(uuid4().hex)
    expressions[[c[0] for c in columns].index(column)] = sql.Literal(value)
    with pytest.raises(psycopg.errors.ForeignKeyViolation), owner.transaction():
        owner.execute(sql.SQL('INSERT INTO aip_license_source_issuance SELECT {} FROM aip_license_source_issuance LIMIT 1').format(sql.SQL(',').join(expressions)))
