from __future__ import annotations

from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb
import pytest

from test_lifecycle_pg import database, pytestmark, seed
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _digest
from aos_api.extension_runtime.pending_preparation_directory import (
    PostgresPendingPreparationDirectory,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _connect(database):
    _, _, schema = database

    @contextmanager
    def connect():
        with psycopg.connect(
            host="127.0.0.1",
            port=18432,
            user="postgres",
            dbname="postgres",
            autocommit=True,
            row_factory=dict_row,
        ) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("SET SESSION AUTHORIZATION aos_runtime")
            yield conn

    return connect


def _append_delivery(conn, operation):
    event = uuid4()
    payload = {"operationId": str(operation)}
    conn.execute(
        """INSERT INTO extension_runtime_event
             (org_id,project_id,operation_id,sequence,event_id,type,payload,payload_hash)
             VALUES('org-org','dev-project',%s,1,%s,'operation-accepted',%s,%s)""",
        (operation, event, Jsonb(payload), _digest(payload)),
    )
    conn.execute(
        """INSERT INTO extension_runtime_outbox
             (org_id,project_id,event_id,consumer_id)
             VALUES('org-org','dev-project',%s,'runtime-reconciler')""",
        (event,),
    )
    return event


def test_reads_only_undelivered_pending_apply_for_exact_tenant(database):
    conn, _, schema = database
    first, operation = seed(conn)
    event = _append_delivery(conn, operation)
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
    conn.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO aos_runtime").format(
            sql.Identifier(schema)
        )
    )
    directory = PostgresPendingPreparationDirectory(
        connect=_connect(database), scope=SCOPE
    )
    assert tuple(item.installation_id for item in directory.read_descriptors()) == (first,)
    assert PostgresPendingPreparationDirectory(
        connect=_connect(database), scope=TenantScope("dev-org", "dev-project")
    ).read_descriptors() == ()
    conn.execute(
        "UPDATE extension_runtime_outbox SET delivered_at=clock_timestamp() WHERE event_id=%s",
        (event,),
    )
    assert directory.read_descriptors() == ()


def test_non_apply_delivery_is_not_a_creation_descriptor(database):
    conn, _, schema = database
    _, operation = seed(conn)
    _append_delivery(conn, operation)
    conn.execute(
        "UPDATE extension_runtime_operation SET kind='runtime-verify' WHERE operation_id=%s",
        (operation,),
    )
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(sql.Identifier(schema)))
    conn.execute(
        sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO aos_runtime").format(
            sql.Identifier(schema)
        )
    )
    assert PostgresPendingPreparationDirectory(
        connect=_connect(database), scope=SCOPE
    ).read_descriptors() == ()


def test_rejects_privileged_role_and_non_idle_connection(database):
    _, _, schema = database

    @contextmanager
    def privileged():
        with psycopg.connect(
            host="127.0.0.1", port=18432, user="postgres", dbname="postgres",
            autocommit=True, row_factory=dict_row,
        ) as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            yield conn

    with pytest.raises(RuntimeConflict, match="adopted runtime role"):
        PostgresPendingPreparationDirectory(
            connect=privileged, scope=SCOPE
        ).read_descriptors()

    class Dirty:
        class Info:
            transaction_status = TransactionStatus.INTRANS

        info = Info()

    @contextmanager
    def dirty():
        yield Dirty()

    with pytest.raises(RuntimeConflict, match="independent idle"):
        PostgresPendingPreparationDirectory(
            connect=dirty, scope=SCOPE
        ).read_descriptors()
