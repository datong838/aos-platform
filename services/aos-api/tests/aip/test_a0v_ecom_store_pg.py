"""Isolated real PostgreSQL consistency owner; no public schema writes."""
import os
from datetime import timedelta
from types import SimpleNamespace
import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine
from test_aip_budget_reservation_pg import database,PG
from aos_api.ecom_consistency_store import EcomConsistencyStore,metadata
from aos_api.ecom_core_models import EcomConsistencyError
from test_ec_ingress_input import prepared
from aos_api.ec_ot_writer import prepare_derived_commands_for_batch,_build_batch_command

pytestmark=pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST')!='1',reason='isolated PG opt-in')


@pytest.fixture
def pg_store(database):
    engine=create_engine('postgresql+psycopg://',creator=lambda:psycopg.connect(**PG,options=f'-c search_path={database.schema}'))
    try:
        metadata.create_all(engine)
        database.owner.execute('CREATE SEQUENCE projection_input_revision_seq')
        database.owner.execute(sql.SQL('GRANT USAGE ON SCHEMA {} TO aos_runtime').format(sql.Identifier(database.schema)))
        for name in metadata.tables:
            database.owner.execute(sql.SQL('GRANT SELECT,INSERT,UPDATE,DELETE ON {} TO aos_runtime').format(sql.Identifier(name)))
            database.owner.execute(sql.SQL('ALTER TABLE {} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(name)))
            database.owner.execute(sql.SQL('ALTER TABLE {} FORCE ROW LEVEL SECURITY').format(sql.Identifier(name)))
            database.owner.execute(sql.SQL("CREATE POLICY tenant_scope ON {} TO aos_runtime USING(org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true)) WITH CHECK(org_id=current_setting('aos.org_id',true) AND workspace_id=current_setting('aos.project_id',true))").format(sql.Identifier(name)))
        database.owner.execute(sql.SQL('GRANT USAGE ON ALL SEQUENCES IN SCHEMA {} TO aos_runtime').format(sql.Identifier(database.schema)))
        yield EcomConsistencyStore(engine)
    finally:
        engine.dispose()


def test_pg_guard_rejects_changed_base_without_derived_effect(pg_store,database):
    scope,pipeline,row,base,_=prepared()
    eng=SimpleNamespace(ecom_consistency_store=pg_store)
    pg_store.apply_batch(base)
    command=prepare_derived_commands_for_batch(eng,scope,pipeline,base,[row])[0]
    # The original precheck completed, then another base transaction committed.
    assert pg_store.read_committed_batch_revision(base)>0
    newer=base.objects[0].model_copy(update={'source_updated_at':base.objects[0].source_updated_at+timedelta(seconds=1)})
    updated=_build_batch_command(sync_scope=base.scope,objects=[newer],links=[],pipeline_id=pipeline.id,store=pg_store)
    pg_store.apply_batch(updated)
    with pytest.raises(EcomConsistencyError,match='expected base payload'):
        pg_store.update_derived_metrics(command,expected_base=base.objects[0])
    assert pg_store.read_committed_derived(command) is None
    assert database.owner.execute("SELECT count(*) AS n FROM projection_outbox WHERE change_kind='derived_upsert'").fetchone()['n']==0
    assert pg_store.update_derived_metrics(command,expected_base=newer).updated
    assert pg_store.update_derived_metrics(command,expected_base=newer).replayed
    assert database.owner.execute('SELECT count(*) AS n FROM ecom_derived_receipt').fetchone()['n']==1
    canary=command.model_copy(update={'identity':command.identity.model_copy(update={'org_id':'dev-org'})})
    assert pg_store.read_committed_derived(canary) is None
