"""Internal async stage-review command service; no public route."""

from contextlib import contextmanager
import inspect

from aos_api.ecommerce_analyst_stage_review_composite_authority import StageReviewCompositeAuthorityReader
from aos_api.ecommerce_analyst_stage_review_coordinator import AsyncStageReviewCommandCoordinator
from aos_api.ecommerce_analyst_stage_review_database_phases import StageReviewDatabasePhases
from aos_api.ecommerce_analyst_stage_review_owner_binding import StageReviewDecisionOwnerBinding
from aos_api.ecommerce_analyst_stage_review_package_port import InstalledGrowthStageReviewPort
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class AsyncAnalystStageReviewCommandService:
    def __init__(self,connect_factory,*,invoke_installed_once,markings):
        if not callable(connect_factory):raise TypeError('explicit scoped connection factory required')
        if not callable(invoke_installed_once) or not inspect.iscoroutinefunction(invoke_installed_once):
            raise TypeError('async installed stage review invoker required')
        self.connect,self.invoke=connect_factory,invoke_installed_once
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
            prepare_in_transaction=binding.prepare_in_transaction,
            load_current_snapshot=binding.load_current_snapshot,
            publish_in_transaction=binding.publish_in_transaction)
        coordinator=AsyncStageReviewCommandCoordinator(prepare=phases.prepare,
            port=InstalledGrowthStageReviewPort(self.invoke),commit=phases.commit)
        return await coordinator.execute(command)


__all__=['AsyncAnalystStageReviewCommandService']
