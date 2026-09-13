import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from aos_api.ecommerce_product_event_worker import ProductEventConsumptionWorker
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
from test_live_job_directory import _job


def setup(monkeypatch,*,fail=False):
    import aos_api.ecommerce_product_event_worker as module
    directory=LivePreparedJobDirectory();directory.register(_job())
    factory=object.__new__(PipelineControlServiceFactory)
    worker=ProductEventConsumptionWorker(factory,directory)
    async def no_dispatch(target):return False
    monkeypatch.setattr(worker,'_dispatch',no_dispatch)
    discovered=[];called=[]
    def candidates(target,after):
        discovered.append(after)
        return tuple(dict(policyId='policy',runId=str(n),actor='actor',controlRef={}) for n in range(5)) if after is None else ()
    monkeypatch.setattr(worker,'_discover',candidates)
    monkeypatch.setattr(worker,'_markings',lambda scope,actor:('internal',))
    @contextmanager
    def store():yield object()
    monkeypatch.setattr(module,'_authoritative_store',store)
    def build(self,scope,**kwargs):
        called.append(kwargs)
        async def consume(policy):
            assert policy=='policy'
            if fail:raise ValueError('denied')
            return (SimpleNamespace(replayed=False),)
        return SimpleNamespace(consume=consume)
    monkeypatch.setattr(PipelineControlServiceFactory,'build_event_consumer',build)
    return worker,directory,discovered,called


def test_bounded_tick_and_empty_page_wrap(monkeypatch):
    worker,_,discovered,calls=setup(monkeypatch)
    first=asyncio.run(worker.tick());second=asyncio.run(worker.tick());third=asyncio.run(worker.tick())
    assert discovered==[None,('policy','4'),None]
    assert first['occurrences']==third['occurrences']==5 and second['candidates']==0
    assert len(calls)==10 and all(c['markings']==('internal',) for c in calls)


def test_failure_does_not_starve_later_candidates(monkeypatch):
    worker,_,discovered,calls=setup(monkeypatch,fail=True)
    result=asyncio.run(worker.tick())
    assert result['failed']==5 and len(calls)==5
    asyncio.run(worker.tick());assert discovered[-1]==('policy','4')


def test_no_live_targets_does_no_work(monkeypatch):
    worker,directory,_,calls=setup(monkeypatch)
    for scope,installation,generation in directory.current_targets():directory.unregister(directory.resolve(scope=scope,installation_id=installation,generation=generation))
    assert asyncio.run(worker.tick())['candidates']==0 and calls==[]


def test_stopped_or_failed_host_never_ticks(monkeypatch):
    worker,_,_,calls=setup(monkeypatch)
    async def run():
        stop=asyncio.Event();stop.set()
        await worker.serve(stop,host_ready=lambda:True)
        await worker.serve(asyncio.Event(),host_ready=lambda:False)
    asyncio.run(run());assert calls==[]


def test_cancellation_is_not_swallowed(monkeypatch):
    worker,_,_,_=setup(monkeypatch)
    def build(*args,**kwargs):
        async def consume(policy):raise asyncio.CancelledError()
        return SimpleNamespace(consume=consume)
    monkeypatch.setattr(PipelineControlServiceFactory,'build_event_consumer',build)
    with pytest.raises(asyncio.CancelledError):asyncio.run(worker.tick())


def test_target_rotation_visits_more_than_one_tick_limit(monkeypatch):
    worker,directory,_,_=setup(monkeypatch)
    for _ in range(4):directory.register(_job())
    seen=[]
    monkeypatch.setattr(worker,'_discover',lambda target,after:seen.append(target) or ())
    asyncio.run(worker.tick());asyncio.run(worker.tick())
    assert len(seen)==8 and len(set(seen))==5


def test_worker_is_owned_by_application_lifecycle(monkeypatch):
    from test_runtime_startup_composition import _quiet_startup
    from aos_api import main
    import aos_api.asset_registry.control_wiring as wiring
    import aos_api.ecommerce_product_event_worker as module
    _quiet_startup(monkeypatch)
    monkeypatch.setattr(wiring,'build_runtime_control_plane',lambda **kw:object())
    async def run():
        entered=asyncio.Event();stopped=asyncio.Event()
        class Host:
            async def serve(self,stop):await stop.wait()
        class Worker:
            async def serve(self,stop,*,host_ready):
                assert host_ready();entered.set()
                try:await stop.wait()
                finally:stopped.set()
        monkeypatch.setattr(wiring,'build_production_runtime_host_selection',lambda **kw:SimpleNamespace(host=Host(),status='ACTIVE',error_code=None))
        monkeypatch.setattr(module,'build_product_event_worker',lambda plane:Worker())
        async with main.lifespan(main.app):
            await asyncio.wait_for(entered.wait(),timeout=1)
            assert {t.get_name() for t in main.app.state.runtime_background_tasks}=={'extension-runtime-host','product-event-consumption'}
        assert stopped.is_set() and main.app.state.runtime_background_tasks==[]
    asyncio.run(run())


def test_empty_discovery_still_checks_persisted_analysis_tasks(monkeypatch):
    worker,directory,_,_=setup(monkeypatch)
    monkeypatch.setattr(worker,'_discover',lambda *args:())
    calls=[]
    async def dispatch(target):calls.append(target);return True
    monkeypatch.setattr(worker,'_dispatch',dispatch)
    result=asyncio.run(worker.tick())
    assert result['candidates']==0 and result['analysesAccepted']==1
    assert calls==list(directory.current_targets())


def test_worker_dispatches_exact_event_with_original_route(monkeypatch):
    import aos_api.ecommerce_product_event_worker as module
    worker,directory,_,_=setup(monkeypatch)
    target=directory.current_targets()[0];claimed=object();calls=[]
    monkeypatch.setattr(worker,'_origin',lambda scope,claim:{'runId':'original','actor':'controller','controlRef':{'exact':1}})
    def build(self,scope,**kwargs):
        calls.append(kwargs)
        async def handle(claim):
            assert claim is claimed
            return {'resourceId':'receipt'}
        return SimpleNamespace(handle=handle)
    monkeypatch.setattr(PipelineControlServiceFactory,'build_event_analysis',build)
    async def dispatch(scope,**kwargs):
        assert kwargs['target'].trigger_source=='event'
        assert kwargs['target'].installation_id==target[1] and kwargs['target'].generation==target[2]
        assert kwargs['store']._connect_factory is module.connect_serializable
        assert kwargs['owner']==worker._claim_owner
        assert await kwargs['handler'](claimed)=={'resourceId':'receipt'}
        return True
    monkeypatch.setattr(module,'dispatch_one_occurrence_async',dispatch)
    assert asyncio.run(ProductEventConsumptionWorker._dispatch(worker,target))
    assert calls[0]['run_id']=='original' and calls[0]['actor']=='controller'


def test_analysis_dispatch_cancellation_propagates(monkeypatch):
    worker,_,_,_=setup(monkeypatch)
    monkeypatch.setattr(worker,'_discover',lambda *args:())
    async def cancel(target):raise asyncio.CancelledError()
    monkeypatch.setattr(worker,'_dispatch',cancel)
    with pytest.raises(asyncio.CancelledError):asyncio.run(worker.tick())
