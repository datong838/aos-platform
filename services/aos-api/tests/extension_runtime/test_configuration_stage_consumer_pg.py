"""Atomic Host staging with real AIP sources and isolated permission fixture."""
import pytest
import psycopg

from test_lifecycle_pg import database, pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_stage_schema_pg import stage, insert, TABLE
from current_configuration_sources_case import install_current_configuration_sources
from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
from aos_api.extension_runtime.configuration_stage_consumer import process_one_configuration_stage


@pytest.fixture
def consumer(stage, database):
    conn, args, body = stage
    _, _, schema = database
    _, refs = install_current_configuration_sources(conn, schema)
    body.update(roleRefs=[r.model_dump(mode='json') for r in refs['configuration'].roleRefs],
                policyRef=refs['policy'].model_dump(mode='json'))
    def permission(db, *, org_id, project_id, actor, **context):
        return db.execute('SELECT actor FROM test_configuration_actors WHERE org_id=%s AND project_id=%s AND actor=%s FOR SHARE',
                          (org_id, project_id, actor)).fetchone() is not None
    authorize = build_current_configuration_authorization(permission=permission)
    conn.execute('RESET ROLE')
    identity = insert(stage)
    conn.execute('SET ROLE aos_runtime')
    return conn, authorize, identity


def process(consumer):
    conn, authorize, _ = consumer
    return process_one_configuration_stage(conn, org_id='org-org', project_id='dev-project', authorize=authorize)


def test_success_commits_one_configuration_and_terminal_result(consumer):
    conn, _, identity = consumer
    with conn.transaction(): result = process(consumer)
    assert result['requestId'] == str(identity) and result['state'] == 'succeeded'
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 1
    assert conn.execute(f'SELECT state,result_json FROM {TABLE}').fetchone() == ('succeeded', result['result'])
    with conn.transaction(): assert process(consumer) is None
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 1


def test_outer_transaction_failure_rolls_back_record_and_result_then_reclaims(consumer):
    conn, _, _ = consumer
    with pytest.raises(RuntimeError):
        with conn.transaction():
            assert process(consumer)['state'] == 'succeeded'
            raise RuntimeError('simulated connection owner failure before commit')
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 0
    assert conn.execute(f'SELECT state FROM {TABLE}').fetchone()[0] == 'requested'
    with conn.transaction(): assert process(consumer)['state'] == 'succeeded'
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 1


@pytest.mark.parametrize('mutation', (
    'DELETE FROM test_configuration_actors',
    'UPDATE aip_runtime_policy_head SET current_revision=2',
    'UPDATE aip_responsibility_plan_head SET current_revision=2',
    'UPDATE bundle_installation SET etag_version=2',
    'UPDATE extension_runtime_binding SET revision=2',
))
def test_current_authority_or_target_rejection_has_no_configuration(consumer, mutation):
    conn, _, _ = consumer
    conn.execute('RESET ROLE'); conn.execute(mutation); conn.execute('SET ROLE aos_runtime')
    with conn.transaction(): result = process(consumer)
    assert result['state'] == 'rejected' and result['result'] is None
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 0


def test_database_result_write_failure_is_not_swallowed_or_partially_committed(consumer):
    conn, _, _ = consumer
    conn.execute('RESET ROLE')
    conn.execute("""CREATE FUNCTION test_reject_stage_result() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'isolated result persistence failure'; END; $$""")
    conn.execute(f'CREATE TRIGGER test_result_failure BEFORE UPDATE ON {TABLE} FOR EACH ROW EXECUTE FUNCTION test_reject_stage_result()')
    conn.execute('SET ROLE aos_runtime')
    with pytest.raises(psycopg.Error):
        with conn.transaction(): process(consumer)
    assert conn.execute('SELECT count(*) FROM extension_runtime_configuration').fetchone()[0] == 0
    assert conn.execute(f'SELECT state FROM {TABLE}').fetchone()[0] == 'requested'
