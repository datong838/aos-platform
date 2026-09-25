"""Installation lock and post-callback window checks in isolated PG only."""

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
from aos_api import pipeline_snapshot_group_owner as group_module


def test_installation_row_lock_spans_original_input_callback(prepared_case, database):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    _, _, schema = database
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    query = sql.SQL('SELECT installation_id FROM {} WHERE org_id=%s AND project_id=%s '
                    'AND installation_id=%s FOR UPDATE NOWAIT').format(
                        sql.Identifier(schema, 'bundle_installation'))
    installation = []

    def other_connection():
        return psycopg.connect(host=conn.info.host, port=conn.info.port,
            user=conn.info.user, dbname=conn.info.dbname, autocommit=True)

    def consume(current):
        identity = current.group.members[0][1].installation_ref.installation_id
        installation.append(identity)
        with other_connection() as other:
            with pytest.raises(psycopg.errors.LockNotAvailable), other.transaction():
                other.execute(query, (*args['scope'].key, identity))
        return current

    with conn.transaction():
        current = owner.run_current(conn, **args, execute=consume)
    assert len(current.parents) == 2 and state['calls'] == 1
    with other_connection() as other, other.transaction():
        assert other.execute(query, (*args['scope'].key, installation[0])).fetchone() is not None


def test_post_callback_group_window_expiry_rejects_without_new_source(prepared_case, monkeypatch):
    executor, conn, args, state = prepared_case
    executor.prepare(**args)
    owner = PipelineSnapshotGroupInputOwner(claims=executor._claims)
    original_now = group_module._now
    changed = [None]
    monkeypatch.setattr(group_module, '_now',
        lambda db: changed[0] if changed[0] is not None else original_now(db))

    def consume(current):
        changed[0] = current.group.expires_at
        return current

    with pytest.raises(PermissionError, match='window is not current'), conn.transaction():
        owner.run_current(conn, **args, execute=consume)
    assert state['calls'] == 1
