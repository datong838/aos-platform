"""Read-only cross-session lock probes for the original group consumption path."""

import psycopg
from psycopg import sql
import pytest

from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner


def test_schedule_and_run_locks_span_original_input_callback(prepared_case, database):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    run_id = args['bindings'][0][1]
    schedule_id = conn.execute('SELECT schedule_id FROM meta_schedule_run WHERE id=%s',
                               (run_id,)).fetchone()['schedule_id']
    _, _, schema = database
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    probes = (
        (sql.Identifier(schema, 'meta_schedule'), schedule_id),
        (sql.Identifier(schema, 'meta_schedule_run'), run_id),
    )

    def other_connection():
        return psycopg.connect(host=conn.info.host, port=conn.info.port,
            user=conn.info.user, dbname=conn.info.dbname, autocommit=True)

    def lock_query(table):
        return sql.SQL('SELECT id FROM {} WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE NOWAIT').format(table)

    def consume(current):
        assert len(current.parents) == 2
        with other_connection() as other:
            for table, identity in probes:
                with pytest.raises(psycopg.errors.LockNotAvailable), other.transaction():
                    other.execute(lock_query(table), (*args['scope'].key, identity))
        return current

    with conn.transaction():
        current = owner.run_current(conn, **args, execute=consume)
    assert len(current.parents) == 2 and state['calls'] == 1
    with other_connection() as other:
        for table, identity in probes:
            with other.transaction():
                assert other.execute(lock_query(table), (*args['scope'].key, identity)).fetchone() is not None
