from datetime import datetime, timedelta, timezone

import pytest

from test_lifecycle_pg import database, pytestmark, seed
from test_configuration_target_pg import case
from aos_api.extension_runtime.lifecycle_store import RuntimeOperationStore


def test_enable_target_is_exact_and_readable(database):
    from aos_api.extension_runtime.configuration_request import load_enable_target,load_configure_target
    conn,_,_=database
    args=case(conn);args['kind']='enable'
    args['deadline']=datetime.now(timezone(timedelta(hours=8)))+timedelta(minutes=1)
    with conn.transaction():
        accepted=RuntimeOperationStore().accept(conn,**args)
        scope=dict(org_id=args['org_id'],project_id=args['project_id'],operation_id=accepted.operation_id)
        assert load_enable_target(conn,**scope).model_dump(mode='json')==args['configuration_target']
        with pytest.raises(ValueError):load_configure_target(conn,**scope)
    with conn.transaction():assert RuntimeOperationStore().accept(conn,**args).replayed
    args['configuration_target']['configRef']['hash']='sha256:'+'b'*64
    with pytest.raises(ValueError):
        with conn.transaction():RuntimeOperationStore().accept(conn,**args)


def test_legacy_targetless_enable_cannot_be_recovered(database):
    from aos_api.extension_runtime.configuration_request import load_enable_target
    conn,_,_=database
    args=case(conn);args['kind']='enable';args.pop('configuration_target')
    with conn.transaction():
        operation=RuntimeOperationStore().accept(conn,**args)
        with pytest.raises(ValueError):load_enable_target(conn,org_id=args['org_id'],project_id=args['project_id'],operation_id=operation.operation_id)


@pytest.mark.parametrize('failure',['binding','scope','missing_binding'])
def test_enable_target_validation(database,failure):
    conn,_,_=database
    args=case(conn);args['kind']='enable'
    if failure=='binding':args['configuration_target']['bindingRevision']=2
    elif failure=='scope':args['org_id']='dev-org'
    else:
        from uuid import uuid4
        args['configuration_target']['generation']=str(uuid4())
    with pytest.raises((ValueError,LookupError,PermissionError)):
        with conn.transaction():RuntimeOperationStore().accept(conn,**args)
