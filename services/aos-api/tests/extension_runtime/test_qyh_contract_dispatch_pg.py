"""Real original Brief/Receipt transactions under the fixed Contract identity."""
import os
import secrets
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
import pytest

from aos_api.aip_bi_plan_issuer_connection import BIIssuerDatabaseConfig
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import AipProductionContractStore, ProductionContractIdempotencyConflict, ProductionContractNotFound
from aos_api.aip_production_contracts import CreateBriefRequest, ReviseBriefRequest
from aos_api.aip_source_issuer_connection import SourceIssuerDatabaseConfig, connect_source_issuer_write
from aos_api.aip_task_models import CreateTaskRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import get_dsn, connect_read_only
from aos_api.tenant_scope import TenantScope

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated full-schema PG opt-in required')
SCOPE=TenantScope('org-org','dev-project')
ROLE='aos_contract_source_issuer'


def test_original_brief_uses_fixed_contract_identity_and_retains_transactions(tmp_path):
    db=conninfo_to_dict(get_dsn())
    assert db['host']=='127.0.0.1' and int(db['port'])==18432
    assert db['dbname'].startswith('aos_test_') and db['dbname'].endswith('_ti4_test')
    identity_dir=tmp_path/'identity';identity_dir.mkdir(mode=0o700)
    credential=identity_dir/'contract.pgpass'
    credential.write_text(f"127.0.0.1:18432:{db['dbname']}:{ROLE}:{secrets.token_hex(24)}\n")
    credential.chmod(0o600)
    config=SourceIssuerDatabaseConfig('contract',BIIssuerDatabaseConfig('127.0.0.1',18432,db['dbname'],credential))
    tables={'aip_task':'SELECT','aip_task_brief_head':'SELECT,INSERT,UPDATE','aip_task_brief_revision':'SELECT,INSERT','aip_production_contract_receipt':'SELECT,INSERT'}
    token=uuid4().hex[:12]
    with psycopg.connect(get_dsn(),autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(ROLE)))
        try:
            for table,grants in tables.items():
                admin.execute(sql.SQL('GRANT {} ON {} TO {}').format(sql.SQL(grants),sql.Identifier(table),sql.Identifier(ROLE)))
                admin.execute(sql.SQL("CREATE POLICY {} ON {} TO {} USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))").format(sql.Identifier(token+'_'+table),sql.Identifier(table),sql.Identifier(ROLE)))
            task=AipTaskStore().create_task(SCOPE,'test',token,CreateTaskRequest(title='Isolated Contract dispatch'))
            connections=[]
            @contextmanager
            def contract(scope):
                with connect_source_issuer_write(config,scope) as conn:
                    assert conn.execute('SELECT session_user AS login').fetchone()['login']==ROLE
                    connections.append(scope.key)
                    yield conn
            def plan_forbidden(scope):
                raise AssertionError('Contract used Plan identity')
            store=AipProductionContractStore(connect_factory=connect_read_only,plan_connect_factory=plan_forbidden,contract_connect_factory=contract)
            body=CreateBriefRequest(task_id=task.id,brief_type='ecommerce.analysis',schema_ref=ResourceRef(resource_type='Schema',resource_id='ecommerce.analysis',revision='1',authority='aip'),spec={'goal':'original contract transaction'})
            created=store.create_brief(SCOPE,'test',token+'-create',body)
            assert store.create_brief(SCOPE,'test',token+'-create',body).brief_id==created.brief_id
            with pytest.raises(ProductionContractIdempotencyConflict):
                store.create_brief(SCOPE,'test',token+'-create',body.model_copy(update={'spec':{'goal':'drift'}}))
            revised=store.revise_brief(SCOPE,'test',created.brief_id,token+'-revise',ReviseBriefRequest(**body.model_dump(exclude={'task_id'}),expected_version=created.version))
            frozen=store.freeze_brief(SCOPE,'test',created.brief_id,revised.version,token+'-freeze')
            assert frozen.lifecycle.value=='frozen' and frozen.revision==3
            before=admin.execute('SELECT count(*) FROM aip_task_brief_head').fetchone()[0]
            admin.execute(sql.SQL("CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.idempotency_key={} THEN RAISE EXCEPTION 'CONTRACT_FORCED_ROLLBACK'; END IF; RETURN NEW; END $$").format(sql.Identifier(token+'_guard'),sql.Literal(token+'-rollback')))
            admin.execute(sql.SQL('CREATE TRIGGER {} BEFORE INSERT ON aip_production_contract_receipt FOR EACH ROW EXECUTE FUNCTION {}()').format(sql.Identifier(token+'_guard'),sql.Identifier(token+'_guard')))
            with pytest.raises(psycopg.Error,match='CONTRACT_FORCED_ROLLBACK'):
                store.create_brief(SCOPE,'test',token+'-rollback',body)
            assert admin.execute('SELECT count(*) FROM aip_task_brief_head').fetchone()[0]==before
            assert admin.execute('SELECT count(*) FROM aip_production_contract_receipt WHERE idempotency_key=%s',(token+'-rollback',)).fetchone()[0]==0
            with pytest.raises(ProductionContractNotFound):
                store.get_brief(TenantScope('dev-org','dev-project'),created.brief_id)
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connect_source_issuer_write(config,SCOPE) as conn:
                    conn.execute("INSERT INTO aip_production_contract_receipt(org_id,project_id,operation,idempotency_key,request_hash,result_ref,created_by) VALUES(%s,%s,'task_brief.create',%s,%s,'{}','test')",('dev-org','dev-project',token+'-forged','a'*64))
            assert len(connections)==6
            assert admin.execute('SELECT count(*) FROM aip_production_contract_receipt WHERE idempotency_key=ANY(%s)',([token+'-create',token+'-revise',token+'-freeze'],)).fetchone()[0]==3
        finally:
            admin.execute(sql.SQL('DROP TRIGGER IF EXISTS {} ON aip_production_contract_receipt').format(sql.Identifier(token+'_guard')))
            admin.execute(sql.SQL('DROP FUNCTION IF EXISTS {}()').format(sql.Identifier(token+'_guard')))
            for table in tables:
                admin.execute(sql.SQL('DROP POLICY IF EXISTS {} ON {}').format(sql.Identifier(token+'_'+table),sql.Identifier(table)))
            admin.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(ROLE)))
            admin.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE)))
