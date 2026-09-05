"""Atomic verification negative cases on real isolated tables; explicit host seam."""
from datetime import datetime, timezone, timedelta
import uuid

import pytest

from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, RuntimeOperationStore
from aos_api.asset_registry.errors import AssetRegistryError


def run_verification_case(connect,store,validator,service,action,scope,applied,preparation,generation,case):
    from aos_api.extension_runtime.verification_commit import commit_verified
    requested = service.request_preparation(**{**action,'kind':'runtime-verify',
        'idempotency_key':'verify-test','if_match':f'"{applied.etag_version}"'})
    operation = requested.response_json['operationId']
    now = datetime.now(timezone.utc)
    if case=='locked_unrelated':
        with connect() as conn:
            unrelated=RuntimeOperationStore().accept(conn,**scope,installation_id=applied.installation_id,
                kind='runtime-verify',idempotency_key='adversarial-unrelated-reference',requested_by='test-actor',
                expected_installation_etag=applied.etag_version,deadline=now+timedelta(minutes=1)).operation_id
    def conditions(**kwargs):
        if case == 'late_conditions':
            kwargs['conn'].execute("SELECT pg_sleep(0.1)")
            kwargs['conn'].execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second' WHERE operation_id=%s", (operation,))
        return case != 'conditions'
    def execute():
        with connect() as conn:
            if case=='locked_unrelated':conn.execute("SET LOCAL statement_timeout='100ms'")
            if case == 'released':
                conn.execute("UPDATE extension_runtime_resource_lease SET observed_release=true,cleanup_state='released'")
            result = commit_verified(conn,installation_store=store,revalidator=validator,
                check_current_permission=lambda **kwargs: case != 'permission',
                check_current_conditions=conditions,**scope,operation_id=operation,
                expected_revision=0 if case=='cas' else requested.response_json['revision'],
                preparation_operation_id=unrelated if case=='locked_unrelated' else uuid.uuid4() if case=='wrong_preparation' else preparation,
                generation=uuid.uuid4() if case=='generation' else generation,
                health_checked_at=now-timedelta(seconds=5) if case=='stale_health' else now+timedelta(seconds=5) if case=='future_health' else datetime.now(timezone.utc))
            if case=='rollback':raise RuntimeConflict('post-append rollback')
            return result
    if case=='valid':
        verified = execute()
        assert verified.state == 'active'
        assert verified.active_revision == verified.current_revision
        with pytest.raises((RuntimeConflict,AssetRegistryError)):execute()
    elif case=='locked_unrelated':
        with connect() as locker:
            locker.execute('SELECT operation_id FROM extension_runtime_operation WHERE operation_id=%s FOR UPDATE',(unrelated,))
            with pytest.raises(LookupError):execute()
    else:
        with pytest.raises((RuntimeConflict,LookupError)):execute()
    observed = store.get_installation(**scope,installation_id=applied.installation_id)
    assert observed.state == ('active' if case=='valid' else 'applied')
    with connect() as conn:
        rows = conn.execute('SELECT enabled,operation_fence,observed_state,installation_revision FROM extension_runtime_binding').fetchall()
        assert rows == ([{'enabled':False,'operation_fence':True,'observed_state':'ready',
            'installation_revision':observed.current_revision}] if case=='valid' else [])
        status=conn.execute('SELECT phase,status FROM extension_runtime_operation WHERE operation_id=%s',(operation,)).fetchone()
        assert status==({'phase':'succeeded','status':'succeeded'} if case=='valid' else {'phase':'accepted','status':'accepted'})
