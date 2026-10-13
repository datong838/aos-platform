"""Selected preparation retains the original owner without dispatching unrelated work."""
import asyncio
from uuid import UUID
import pytest
from test_live_installation_scheduler import dependencies,descriptor,SCOPE
from aos_api.extension_runtime.live_installation_scheduler import LiveInstallationScheduler
from aos_api.extension_runtime.pending_preparation_directory import PendingPreparationDescriptor
from aos_api.extension_runtime.runtime_host import RuntimeHost,RuntimeTenantAssignment
from aos_api.tenant_scope import TenantScope


def test_selected_retains_only_native_selected_owner_for_followup(monkeypatch):
 calls=[];directory,factory,owners=dependencies(monkeypatch,((descriptor(1),descriptor(2)),()),calls)
 async def run():
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  assignment=RuntimeTenantAssignment(scope=SCOPE,lifecycle=scheduler)
  host=RuntimeHost(assignments=lambda:(assignment,))
  assert not host.has_current_preparation_assignment(SCOPE,kind='runtime-verify',installation_id=UUID(int=2))
  first=await scheduler.run_selected_once(UUID(int=2))
  assert [i.int for i,_ in first.deliveries]==[2]
  original=scheduler.find_owner(UUID(int=2));assert original is owners[UUID(int=2)]
  assert host.has_current_preparation_assignment(SCOPE,kind='runtime-verify',installation_id=UUID(int=2))
  assert not host.has_current_preparation_assignment(SCOPE,kind='runtime-verify',installation_id=UUID(int=1))
  second=await scheduler.run_selected_once(UUID(int=2))
  assert [i.int for i,_ in second.deliveries]==[2] and scheduler.find_owner(UUID(int=2)) is original
  assert scheduler.find_owner(UUID(int=1)) is None
  await scheduler.stop()
 asyncio.run(run());assert calls==[('create',2),('run',2),('run',2),('stop',2)]


def test_selected_does_not_dispatch_an_existing_unselected_owner(monkeypatch):
 calls=[];directory,factory,_=dependencies(monkeypatch,((descriptor(1),descriptor(2)),()),calls)
 async def run():
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  await scheduler.run_once();calls.clear()
  await scheduler.run_selected_once(UUID(int=2));assert calls==[('run',2)]
  await scheduler.stop()
 asyncio.run(run());assert calls==[('run',2),('stop',1),('stop',2)]


def test_missing_target_has_no_fabricated_descriptor_or_owner(monkeypatch):
 calls=[];directory,factory,_=dependencies(monkeypatch,((descriptor(1),),),calls)
 async def run():
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  result=await scheduler.run_selected_once(UUID(int=9));assert result.deliveries==() and scheduler.owners==()
  await scheduler.stop()
 asyncio.run(run());assert calls==[]


@pytest.mark.parametrize('target',[None,'00000000-0000-0000-0000-000000000002',2])
def test_selected_rejects_non_uuid_before_directory_read(monkeypatch,target):
 calls=[];directory,factory,_=dependencies(monkeypatch,(),calls)
 async def run():
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  with pytest.raises(TypeError,match='UUID'):await scheduler.run_selected_once(target)
  await scheduler.stop()
 asyncio.run(run());assert calls==[]


@pytest.mark.parametrize('page',[(descriptor(2),descriptor(2)),(PendingPreparationDescriptor(TenantScope('dev-org','dev-project'),UUID(int=2)),)])
def test_selected_rejects_duplicate_or_cross_scope_native_page(monkeypatch,page):
 calls=[];directory,factory,_=dependencies(monkeypatch,(page,),calls)
 async def run():
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  with pytest.raises((TypeError,ValueError)):await scheduler.run_selected_once(UUID(int=2))
  with pytest.raises((TypeError,ValueError)):await scheduler.stop()
 asyncio.run(run());assert calls==[]


def test_selected_and_legacy_share_one_tick_and_stop_awaits_owned_work(monkeypatch):
 calls=[]
 async def run():
  entered,release=asyncio.Event(),asyncio.Event()
  directory,factory,_=dependencies(monkeypatch,((descriptor(2),),),calls,block=(2,entered,release))
  scheduler=LiveInstallationScheduler(directory=directory,factory=factory)
  request=asyncio.create_task(scheduler.run_selected_once(UUID(int=2)));await entered.wait()
  with pytest.raises(RuntimeError,match='already in progress'):await scheduler.run_once()
  with pytest.raises(RuntimeError,match='already in progress'):await scheduler.run_selected_once(UUID(int=2))
  request.cancel()
  with pytest.raises(asyncio.CancelledError):await request
  closing=asyncio.create_task(scheduler.stop());await asyncio.sleep(0)
  assert not closing.done() and ('stop',2) not in calls
  release.set();await closing
  with pytest.raises(RuntimeError,match='closing'):await scheduler.run_selected_once(UUID(int=2))
 asyncio.run(run());assert calls==[('create',2),('run',2),('stop',2)]
