"""Internal async stage-review command service; no public route."""

from contextlib import contextmanager
from copy import deepcopy
import inspect

from aos_api.ecommerce_analyst_stage_review_composite_authority import StageReviewCompositeAuthorityReader
from aos_api.ecommerce_analyst_stage_review_coordinator import AsyncStageReviewCommandCoordinator
from aos_api.ecommerce_analyst_stage_review_database_phases import StageReviewDatabasePhases
from aos_api.ecommerce_analyst_stage_review_owner_binding import StageReviewDecisionOwnerBinding
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class AsyncAnalystStageReviewCommandService:
    def __init__(self,connect_factory,*,invoke_installed_once,markings,
            installed_snapshot_in_transaction=None):
        if not callable(connect_factory):raise TypeError('explicit scoped connection factory required')
        if not callable(invoke_installed_once) or not inspect.iscoroutinefunction(invoke_installed_once):
            raise TypeError('async installed stage review invoker required')
        if installed_snapshot_in_transaction is not None and (
                not callable(installed_snapshot_in_transaction)
                or inspect.iscoroutinefunction(installed_snapshot_in_transaction)):
            raise TypeError('synchronous installed snapshot reader required')
        self.connect,self.invoke=connect_factory,invoke_installed_once
        self.installed_snapshot=installed_snapshot_in_transaction
        self.reader=StageReviewCompositeAuthorityReader(markings)

    async def decide(self,scope,item,*,actor,key,expected_version):
        if type(scope) is not TenantScope:raise TypeError('stage review requires TenantScope')
        command={'scope':{'orgId':scope.org_id,'projectId':scope.project_id},
            'item':item.model_dump(mode='json',by_alias=True),'actor':actor,'key':key,
            'expectedVersion':expected_version}
        binding=StageReviewDecisionOwnerBinding(scope,read_authority=self.reader)
        with self.connect(scope) as conn:
            replay=binding.read_replay_in_transaction(HostTransaction(conn),command)
        if replay is not None:return replay
        @contextmanager
        def transaction_factory(_command):
            with self.connect(scope) as conn:yield HostTransaction(conn)
        phases=StageReviewDatabasePhases(transaction_factory=transaction_factory,
            prepare_in_transaction=self._prepare(binding),
            load_current_snapshot=self._current(binding),
            publish_in_transaction=binding.publish_in_transaction)
        coordinator=AsyncStageReviewCommandCoordinator(prepare=phases.prepare,
            port=InstalledGrowthStageReviewPort(self.invoke),commit=phases.commit)
        return await coordinator.execute(command)

    def _prepare(self,binding):
        if self.installed_snapshot is None:return binding.prepare_in_transaction
        def prepare(transaction,command):
            snapshot,exchanges=binding.prepare_in_transaction(transaction,command)
            return self._seal_installed(transaction,snapshot),exchanges
        return prepare

    def _current(self,binding):
        if self.installed_snapshot is None:return binding.load_current_snapshot
        def current(transaction,command):
            return self._seal_installed(transaction,binding.load_current_snapshot(transaction,command))
        return current

    def _seal_installed(self,transaction,snapshot):
        if type(snapshot) is not dict or not snapshot:
            raise TypeError('stage review authority snapshot required')
        installed=self.installed_snapshot(transaction)
        if type(installed) is not dict or not installed:
            raise TypeError('installed runtime snapshot required')
        if 'installedRuntime' in snapshot:
            raise ValueError('installed runtime snapshot key is reserved')
        return {**deepcopy(snapshot),'installedRuntime':deepcopy(installed)}


def build_current_installed_analyst_stage_review_service(connect_factory,*,scope,
        installation_id,generation,installation_store,live_directory,markings):
    from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
    invoker=CurrentInstalledPackageInvoker(scope=scope,installation_id=installation_id,
        generation=generation,package_id='solution.ecommerce.growth',markings=markings,
        connect_factory=connect_factory,installation_store=installation_store,
        live_directory=live_directory)
    return AsyncAnalystStageReviewCommandService(connect_factory,
        invoke_installed_once=invoker.__call__,markings=markings,
        installed_snapshot_in_transaction=invoker.read_current_in_transaction)


__all__=['AsyncAnalystStageReviewCommandService',
    'build_current_installed_analyst_stage_review_service']
