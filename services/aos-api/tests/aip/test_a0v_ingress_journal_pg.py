import importlib.util
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4
import pytest
from psycopg import errors
from test_aip_budget_reservation_pg import database, runtime_connection, ROOT
from aos_api.tenant_scope import TenantScope

pytestmark = pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='isolated PG opt-in')


def test_ingress_command_survives_connections_and_rejects_replacement(database):
    from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
    from aos_api.ec_ot_writer import _normalize_rows, _build_sync_scope, _build_batch_command
    database.owner.execute('CREATE TABLE data_source_configuration_revision(org_id text,project_id text,source_id text,revision_id uuid,PRIMARY KEY(org_id,project_id,source_id,revision_id))')
    revision = uuid4()
    database.owner.execute("INSERT INTO data_source_configuration_revision VALUES('org-org','dev-project','source',%s)", (revision,))
    spec = importlib.util.spec_from_file_location('ingress_migration', ROOT/'alembic/versions/a0v_005_ingress_command_journal.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=database.owner.execute)
    migration.upgrade(); migration.downgrade(); migration.upgrade()
    scope = TenantScope('org-org', 'dev-project')
    sync = _build_sync_scope(scope, SimpleNamespace(id='p01'))
    objects, links = _normalize_rows([{'ot':'Shop','source_pk':'1','source_updated_at':datetime.now(timezone.utc),
        'properties':{'name':'fixture','status':'active','currency':'CNY','timezone':'Asia/Shanghai'}}], sync)
    command = _build_batch_command(sync_scope=sync, objects=objects, links=links, pipeline_id='p01',store=SimpleNamespace(get_checkpoint=lambda _:None))
    journal = IngressJournal(storage_schema=database.schema)
    factory = runtime_connection(database)
    args = dict(run_id='run',pipeline_id='p01',source_id='source',source_revision=str(revision),pipeline_hash='a'*64,command=command)
    with factory(scope) as conn:
        first = journal.save(conn, scope, **args)
    with factory(scope) as conn:
        assert journal.read(conn, scope, 'run') == first
        assert journal.save(conn, scope, **args) == first
        with pytest.raises(IngressJournalConflict):
            journal.save(conn, scope, **dict(args,pipeline_hash='b'*64))
    with factory(TenantScope('dev-org','dev-project')) as conn:
        assert journal.read(conn, scope, 'run') is None
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        database.owner.execute('DELETE FROM ecommerce_ingress_command')
    with pytest.raises(errors.RaiseException), database.owner.transaction():
        migration.downgrade()
