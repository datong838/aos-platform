"""Observe only the bound generation after a preparation reset."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
from uuid import uuid4

import pytest
from test_lifecycle_pg import database,seed,pytestmark
from test_resource_recovery_pg import setup,SCOPE
from aos_api.extension_runtime.reconciler import ResourceJournal
from aos_api.extension_runtime.resource_recovery import ExpiredResourceRecovery

spec=importlib.util.spec_from_file_location('continuity_probe',Path(__file__).resolve().parents[4]/'scripts/a0v_ecommerce_continuity_observe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)


@pytest.mark.parametrize('case',['current','ambiguous','no-binding','tenant'])
def test_observation_selects_exact_binding_not_historical_apply(database,case):
    conn,intent,connect=setup(database)
    installation,operation=conn.execute('SELECT installation_id,operation_id FROM extension_runtime_operation').fetchone()
    _,old=seed(conn)
    conn.execute("UPDATE extension_runtime_operation SET installation_id=%s,idempotency_key='historical' WHERE operation_id=%s",(installation,old))
    with conn.transaction():
        ResourceJournal().prepare(conn,**SCOPE,operation_id=old,
            generation=conn.execute('SELECT generation FROM extension_runtime_binding').fetchone()[0] if case=='ambiguous' else uuid4(),package_id='historical',
            package_hash='sha256:'+'a'*64,engine_context='colima-aos-extension',expires_at=datetime.now(timezone.utc)+timedelta(minutes=1))
    if case=='no-binding':conn.execute('DELETE FROM extension_runtime_binding')
    worker=ExpiredResourceRecovery(connect=connect,driver=SimpleNamespace(context='colima-aos-extension'))
    scope={**SCOPE,'org_id':'dev-org'} if case=='tenant' else SCOPE
    with worker._idle() as db:
        with worker._transaction(db,scope):
            if case!='current':
                with pytest.raises(ValueError,match='exact current preparation required'):
                    probe.current_preparation(db,installation,**scope)
            else:
                row=probe.current_preparation(db,installation,**scope)
                assert row['operation_id']==operation and row['operation_id']!=old
