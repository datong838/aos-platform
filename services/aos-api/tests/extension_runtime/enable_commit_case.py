"""Negative enable transactions before the live owner performs its real commit."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest


def exercise_enable_rejections(worker, scope, plan, request):
    from aos_api.extension_runtime.enable_commit import commit_enabled
    from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
    from aos_api.asset_registry.errors import AssetRegistryError

    cases=('cas','generation','preparation','permission','conditions','configuration',
           'stale_health','future_health','released','binding','pointer','deadline','rollback',
           'final_health','final_resource','resource_pointer','lock_pointer','async_permission')
    for case in cases:
        with pytest.raises((ValueError, LookupError, PermissionError, AssetRegistryError)):
            with worker._connection(scope) as c:
                args=dict(installation_store=worker.store,revalidator=worker.revalidator,
                    check_current_permission=worker.enable_permission,check_current_conditions=worker.conditions,
                    **scope,**request,preparation_operation_id=plan.operation_id,generation=plan.generation,
                    health_checked_at=datetime.now(timezone.utc))
                if case=='cas':args['expected_revision']=0
                if case=='generation':args['generation']=uuid4()
                if case=='preparation':args['preparation_operation_id']=uuid4()
                if case=='permission':args['check_current_permission']=lambda **k:False
                if case=='conditions':args['check_current_conditions']=lambda **k:None
                if case=='configuration':args['authorize']=lambda *a,**k:False
                if case=='stale_health':args['health_checked_at']-=timedelta(seconds=5)
                if case=='future_health':args['health_checked_at']+=timedelta(seconds=5)
                if case=='released':c.execute("UPDATE extension_runtime_resource_lease SET cleanup_state='released',observed_release=true")
                if case=='binding':c.execute('UPDATE extension_runtime_binding SET revision=revision+1')
                if case=='pointer':c.execute('UPDATE extension_runtime_binding SET config_ref=NULL')
                if case=='deadline':c.execute("UPDATE extension_runtime_operation SET deadline=clock_timestamp()-interval '1 second' WHERE operation_id=%s",(request['operation_id'],))
                if case=='resource_pointer':c.execute("UPDATE extension_runtime_binding SET resource_handle_ref='{}'::jsonb")
                if case=='lock_pointer':c.execute("UPDATE extension_runtime_binding SET package_lock_ref='{}'::jsonb")
                if case=='async_permission':
                    async def deferred(**k):return True
                    args['check_current_permission']=deferred
                if case in ('final_health','final_resource'):
                    count=0
                    original=args['authorize']
                    def crossing(db,**context):
                        nonlocal count
                        result=original(db,**context)
                        count+=1
                        if count==2:
                            db.execute('SELECT pg_sleep(%s)',(3.05 if case=='final_health' else .6,))
                        return result
                    if case=='final_resource':
                        c.execute("UPDATE extension_runtime_resource_lease SET expires_at=clock_timestamp()+interval '500 milliseconds'")
                    args['authorize']=crossing
                commit_enabled(c,**args)
                if case=='rollback':raise RuntimeConflict('isolated post-commit rollback')
        with worker._connection(scope) as c:
            assert c.execute('SELECT enabled,operation_fence,observed_state FROM extension_runtime_binding').fetchone()=={
                'enabled':False,'operation_fence':True,'observed_state':'unknown'}
            assert c.execute("SELECT count(*) AS n FROM extension_runtime_event WHERE type='enabled_committed'").fetchone()['n']==0
