import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from test_lifecycle_pg import database,pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_begin_pg import accepted_configuration

from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
from aos_api.extension_runtime.generation_attempts import (
    ExpiredSignedReadAttemptRecovery,
    GenerationDrainReader,
    PostgresRuntimeAttemptStore,
)
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.runtime_host import RuntimeHost, RuntimeTenantAssignment
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('case',['success','pending','ack_failure','other_kind','tenant','deferred'])
def test_configuration_consumer_commits_fence_before_drain(database,accepted_configuration,case):
    from aos_api.extension_runtime.configuration_consumer import ConfigurationConsumer
    conn,args=accepted_configuration
    schema=database[2]
    @contextmanager
    def connect():
        with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',autocommit=True,row_factory=dict_row) as c:
            c.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            c.execute('SET SESSION AUTHORIZATION aos_runtime')
            yield c
    calls=[]
    def drained(c,**kwargs):
        # Independent observer must see the committed fence before drain runs.
        assert conn.execute('SELECT operation_fence,enabled,execution_epoch FROM extension_runtime_binding').fetchone()==(True,False,2)
        calls.append(kwargs)
        return case!='pending'
    consumer=ConfigurationConsumer(connect=connect,authorize=args['authorize'],check_drained=drained)
    scope={k:args[k] for k in ('org_id','project_id')}
    if case=='other_kind':conn.execute("UPDATE extension_runtime_operation SET kind='disable'")
    if case=='tenant':scope['org_id']='dev-org'
    if case=='deferred':conn.execute("UPDATE extension_runtime_operation SET status='running',phase='validating'")
    original=consumer.outbox.ack
    if case=='ack_failure':
        def failed(c,**kw):original(c,**kw);raise RuntimeError('named ACK rollback')
        consumer.outbox.ack=failed
    if case in ('pending','ack_failure'):
        with pytest.raises((ValueError,RuntimeError)):consumer.run_once(**scope)
        assert conn.execute('SELECT operation_fence,execution_epoch FROM extension_runtime_binding').fetchone()==(True,2)
        conn.execute("UPDATE extension_runtime_outbox SET claim_until=clock_timestamp()-interval '1 second' WHERE claim_until IS NOT NULL")
        consumer.outbox.ack=original
        consumer.check_drained=lambda *a,**kw:True
        result=consumer.run_once(**scope)
        assert result.operation_status=='succeeded'
        assert conn.execute('SELECT execution_epoch FROM extension_runtime_binding').fetchone()==(2,)
    else:
        result=consumer.run_once(**scope)
        if case in ('other_kind','tenant'):assert result is None and not calls
        elif case=='deferred':assert result.delivery_status=='deferred' and not calls
        else:assert result.operation_status=='succeeded' and len(calls)==1


def test_rebuilt_host_recovers_expired_read_then_acknowledges_configuration(
    database, accepted_configuration
):
    """A process exit cannot strand a fenced configure operation forever."""
    conn, args = accepted_configuration
    schema = database[2]
    scope = {key: args[key] for key in ("org_id", "project_id")}

    # This migration is the durable-attempt authority consumed by the runtime
    # host.  Load it into the same isolated schema as the accepted configure.
    conn.execute("RESET ROLE")
    path = (
        Path(__file__).resolve().parents[2]
        / "alembic/versions/ar1_004_runtime_execution_attempt.py"
    )
    spec = importlib.util.spec_from_file_location("configuration_attempt_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = SimpleNamespace(execute=conn.execute)
    migration.upgrade()
    conn.execute("SET ROLE aos_runtime")

    binding = conn.execute(
        "SELECT installation_id,generation FROM extension_runtime_binding"
    ).fetchone()
    installation, generation = binding
    conn.execute(
        """UPDATE extension_runtime_binding
              SET desired_state='enabled',observed_state='ready',enabled=true,
                  operation_fence=false,
                  config_ref=(SELECT payload->'configurationTarget'->'configRef'
                                FROM extension_runtime_event
                               WHERE operation_id=%s AND sequence=1)""",
        (args["operation_id"],),
    )
    with conn.transaction():
        attempt = PostgresRuntimeAttemptStore().begin(
            conn,
            **scope,
            installation_id=installation,
            generation=generation,
            execution_epoch=1,
            operation_kind="signed_read",
            operation_key="products.read",
            idempotency_key="process-a-read",
            request_hash="sha256:" + "c" * 64,
            owner_token="process-a-owner-" + "x" * 32,
            lease_until=datetime.now(timezone.utc) + timedelta(milliseconds=150),
        )

    @contextmanager
    def connect():
        with psycopg.connect(
            host="127.0.0.1",
            port=18432,
            user="postgres",
            dbname="postgres",
            autocommit=True,
            row_factory=dict_row,
        ) as runtime:
            runtime.execute("SET SESSION AUTHORIZATION aos_runtime")
            runtime.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            runtime.execute(
                "SELECT set_config('aos.org_id','org-org',false),"
                "set_config('aos.project_id','dev-project',false)"
            )
            yield runtime

    def rebuilt_host():
        assignment = RuntimeTenantAssignment(
            scope=TenantScope(**scope),
            attempt_recovery=ExpiredSignedReadAttemptRecovery(connect=connect),
            consumers=(
                ConfigurationConsumer(
                    connect=connect,
                    authorize=args["authorize"],
                    check_drained=GenerationDrainReader(),
                ),
            ),
        )
        return RuntimeHost(assignments=lambda: (assignment,))

    # Process B sees the live lease, commits the fence, and refuses to finish.
    with pytest.raises(RuntimeConflict, match="undrained"):
        asyncio.run(rebuilt_host().run_once())
    assert conn.execute(
        "SELECT state FROM extension_runtime_execution_attempt WHERE attempt_id=%s",
        (attempt.attempt_id,),
    ).fetchone() == ("running",)
    assert conn.execute(
        "SELECT status,phase FROM extension_runtime_operation WHERE operation_id=%s",
        (args["operation_id"],),
    ).fetchone() == ("running", "fencing")

    # Simulate the configured claim lease expiring after process B exits.  A
    # newly built host must recover the read before delivering configure.
    conn.execute("SELECT pg_sleep(.18)")
    conn.execute(
        """UPDATE extension_runtime_outbox
              SET claim_until=clock_timestamp()-interval '1 second'
                WHERE event_id IN (
                        SELECT event_id FROM extension_runtime_event
                         WHERE operation_id=%s AND sequence=1
                      )
              AND delivered_at IS NULL""",
        (args["operation_id"],),
    )
    tick = asyncio.run(rebuilt_host().run_once())
    assert tick.tenants[0].recovered_attempts == (attempt.attempt_id,)
    assert tick.tenants[0].deliveries[0].operation_status == "succeeded"
    assert tick.tenants[0].deliveries[0].delivery_status == "acknowledged"
    assert conn.execute(
        "SELECT state FROM extension_runtime_execution_attempt WHERE attempt_id=%s",
        (attempt.attempt_id,),
    ).fetchone() == ("abandoned",)
    assert conn.execute(
        "SELECT type,state FROM extension_runtime_execution_attempt_event "
        "WHERE attempt_id=%s ORDER BY sequence",
        (attempt.attempt_id,),
    ).fetchall() == [
        ("attempt_accepted", "running"),
        ("attempt_abandoned", "abandoned"),
    ]
    assert conn.execute(
        "SELECT status,phase FROM extension_runtime_operation WHERE operation_id=%s",
        (args["operation_id"],),
    ).fetchone() == ("succeeded", "succeeded")
    assert conn.execute(
        "SELECT delivered_at IS NOT NULL,claim_until IS NULL "
        "FROM extension_runtime_outbox WHERE event_id IN ("
        "SELECT event_id FROM extension_runtime_event "
        "WHERE operation_id=%s AND sequence=1)",
        (args["operation_id"],),
    ).fetchone() == (True, True)
    assert conn.execute(
        "SELECT count(*) FROM extension_runtime_outbox b "
        "JOIN extension_runtime_event e USING(org_id,project_id,event_id) "
        "WHERE e.operation_id=%s AND e.sequence>1 "
        "AND b.delivered_at IS NULL AND b.claim_until IS NOT NULL",
        (args["operation_id"],),
    ).fetchone() == (0,)
