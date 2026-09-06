from contextlib import contextmanager
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
import pytest
from test_lifecycle_pg import database,pytestmark
from test_configuration_store_pg import configuration_case
from test_configuration_begin_pg import accepted_configuration


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
