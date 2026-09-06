from datetime import datetime, timedelta, timezone

import pytest

from test_lifecycle_pg import database, pytestmark
from test_configuration_target_pg import case
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore


def disable_case(conn):
    args=case(conn)
    config=args.pop('configuration_target')
    args.update(kind='disable',binding_target={key:config[key] for key in ('generation','bindingRevision')})
    return args


def test_disable_target_freezes_identity_without_requiring_configuration(database):
    from aos_api.extension_runtime.disable_request import load_disable_target
    conn,_,_=database
    args=disable_case(conn)
    args['deadline']=datetime.now(timezone(timedelta(hours=8)))-timedelta(seconds=1)
    # Expired forward deadline must not prevent conservative disable acceptance.
    with conn.transaction():
        accepted=RuntimeOperationStore().accept(conn,**args)
        target=load_disable_target(conn,org_id=args['org_id'],project_id=args['project_id'],operation_id=accepted.operation_id)
        assert target.model_dump(mode='json')==args['binding_target']
        assert RuntimeOperationStore().accept(conn,**args).replayed
    args['binding_target']['bindingRevision']=2
    with pytest.raises(ValueError):
        with conn.transaction():RuntimeOperationStore().accept(conn,**args)


@pytest.mark.parametrize('failure',['cas','scope','generation','kind','extra','bool'])
def test_disable_target_rejects_identity_drift(database,failure):
    conn,_,_=database
    args=disable_case(conn)
    if failure=='cas':args['binding_target']['bindingRevision']=2
    if failure=='scope':args['org_id']='dev-org'
    if failure=='generation':args['binding_target']['generation']='00000000-0000-0000-0000-000000000001'
    if failure=='kind':args['kind']='enable'
    if failure=='extra':args['binding_target']['enabled']=False
    if failure=='bool':args['binding_target']['bindingRevision']=True
    with pytest.raises((ValueError,LookupError,PermissionError)):
        with conn.transaction():RuntimeOperationStore().accept(conn,**args)


def test_targetless_disable_has_no_recoverable_target(database):
    from aos_api.extension_runtime.disable_request import load_disable_target
    conn,_,_=database
    args=disable_case(conn);args.pop('binding_target')
    with conn.transaction():
        accepted=RuntimeOperationStore().accept(conn,**args)
        with pytest.raises(ValueError):
            load_disable_target(conn,org_id=args['org_id'],project_id=args['project_id'],operation_id=accepted.operation_id)
