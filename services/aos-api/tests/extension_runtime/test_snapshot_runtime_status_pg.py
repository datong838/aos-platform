import psycopg
import pytest
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict

pytest_plugins=('test_snapshot_schedule_runtime_pg',)


def test_runtime_status_is_current_authorized_read_only(runtime_case):
    runtime,args,state,api,common,enabled,database=runtime_case
    status=api.read_runtime_status(**common)
    assert status['definitionRef']==enabled['ref'] and status['configurationState']=='enabled'
    assert status['executionAuthorized'] is False and status['originalGroups']==[]
    assert (status['orgId'],status['projectId'])==args['scope'].key
    with runtime._transaction(args['scope']) as conn:
        assert conn.execute('SELECT count(*) AS n FROM meta_schedule_run').fetchone()['n']==0
    with psycopg.connect(database) as admin:
        admin.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
            (*args['scope'].key,common['actor']))
    with pytest.raises(RuntimeConflict,match='membership'):api.read_runtime_status(**common)
    assert state['calls']==0


def test_pending_group_is_reported_without_creating_input(runtime_case):
    runtime,args,state,api,common,enabled,_=runtime_case
    with runtime._transaction(args['scope']) as conn:
        bindings=runtime._definitions._saved_bindings(conn,args['scope'],enabled['body'])
        runtime._claims.claim(conn,**args,bindings=bindings)
    result=api.read_runtime_status(**common)
    assert result['routingStatus']=='original_group_pending'
    assert result['originalGroups']==[dict(groupId=args['group_id'],recoveryRef=None)]
    assert state['calls']==0
