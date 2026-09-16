"""Tenant-bound approval services using the existing production runtime identity."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable

from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.pipeline_runtime_control_contracts import PipelineRuntimeControlDraft, PipelineSourceSelectionDraft
from aos_api.pipeline_runtime_control_owner import PipelineRuntimeControlOwner
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class PipelineControlServices:
    scope: TenantScope
    selections: PipelineSourceSelectionOwner
    controls: PipelineRuntimeControlOwner
    claims: PipelineSourceClaimOwner | None = None

    def _approve(self,*,draft,actor,idempotency_key,previous_ref,selection):
        kind=PipelineSourceSelectionDraft if selection else PipelineRuntimeControlDraft
        draft=kind.model_validate(draft)
        if self.scope.key!=(draft.org_id,draft.project_id):
            raise PermissionError('pipeline approval tenant differs')
        scope=dict(org_id=self.scope.org_id,project_id=self.scope.project_id)
        with consumer_connection(runtime_worker_connection,scope) as conn:
            require_runtime_role(conn,**scope,protected_tables=(
                'public.pipeline_source_selection_revision','public.pipeline_runtime_control_revision'))
            owner=self.selections if selection else self.controls
            return owner.append(conn,draft=draft,actor=actor,idempotency_key=idempotency_key,previous_ref=previous_ref)

    def approve_selection(self,*,draft,actor,idempotency_key,previous_ref=None):
        return self._approve(draft=draft,actor=actor,idempotency_key=idempotency_key,previous_ref=previous_ref,selection=True)

    def approve_control(self,*,draft,actor,idempotency_key,previous_ref=None):
        return self._approve(draft=draft,actor=actor,idempotency_key=idempotency_key,previous_ref=previous_ref,selection=False)

    def bind_schedule(self,*,pipeline_id,schedule_id,control_ref,actor,idempotency_key,previous_ref=None):
        owner=PipelineScheduleControlOwner(controls=self.controls)
        scope=dict(org_id=self.scope.org_id,project_id=self.scope.project_id)
        with consumer_connection(runtime_worker_connection,scope) as conn:
            require_runtime_role(conn,**scope,protected_tables=(
                'public.pipeline_schedule_control_binding','public.pipeline_runtime_control_revision'))
            return owner.bind(conn,scope=self.scope,schedule_id=schedule_id,control_ref=control_ref,
                actor=actor,idempotency_key=idempotency_key,previous_ref=previous_ref,expected_pipeline_id=pipeline_id).ref


@dataclass(frozen=True)
class PipelineControlServiceFactory:
    installation_store: PostgresInstallationStore
    policy: ReleasePolicy
    allowlist_roots: dict[str,Path]
    event_dispatch_connect: Callable | None = None

    def __post_init__(self):
        if type(self.installation_store) is not PostgresInstallationStore or type(self.policy) is not ReleasePolicy:
            raise TypeError('exact production pipeline dependencies required')
        if type(self.allowlist_roots) is not dict or any(type(key) is not str or not isinstance(value,Path) for key,value in self.allowlist_roots.items()):
            raise TypeError('server-owned asset roots required')
        if self.event_dispatch_connect is not None and not callable(self.event_dispatch_connect):
            raise TypeError('explicit event dispatch identity connector required')
        object.__setattr__(self,'allowlist_roots',MappingProxyType(dict(self.allowlist_roots)))

    def _source_dependencies(self,scope):
        if type(scope) is not TenantScope:raise TypeError('exact pipeline tenant required')
        # Invalid roots fail here without taking unrelated lifecycle controls down.
        loader=ManifestLoader(self.allowlist_roots,trust_roots=self.policy._trust_roots)
        artifacts=CurrentRuntimeReleaseArtifacts(connect=runtime_worker_connection,scope=scope,loader=loader)
        selections=PipelineSourceSelectionOwner(installation_store=self.installation_store,
            artifacts=artifacts,release_policy=self.policy)
        return selections,artifacts

    def build(self,scope):
        selections,_artifacts=self._source_dependencies(scope)
        controls=PipelineRuntimeControlOwner(selections=selections)
        return PipelineControlServices(scope,selections,controls,PipelineSourceClaimOwner(controls=controls))

    def build_snapshot_schedule(self,scope,*,source_controls=True):
        from aos_api.pipeline_snapshot_schedule_service import PipelineSnapshotScheduleService
        if type(source_controls) is not bool:raise TypeError('explicit source control mode required')
        controls=None
        if source_controls:
            selections,_artifacts=self._source_dependencies(scope)
            controls=PipelineRuntimeControlOwner(selections=selections)
        return PipelineSnapshotScheduleService(scope=scope,controls=controls,installation_store=self.installation_store)

    def build_snapshot_worker(self,scope,*,store):
        from aos_api.ecom_consistency_store import EcomConsistencyStore
        from aos_api.phase5_pipeline_engine import get_engine
        from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime
        from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
        from aos_api.pipeline_snapshot_schedule_worker import PipelineSnapshotScheduleWorker
        if type(store) is not EcomConsistencyStore:raise TypeError('original snapshot Store required')
        services=self.build(scope)
        dependencies=dict(claims=services.claims,store=store,connect=runtime_worker_connection,eng=get_engine())
        return PipelineSnapshotScheduleWorker(scope=scope,runtime=PipelineSnapshotScheduleRuntime(**dependencies),
            recovery=PipelineSnapshotGroupRecoveryRuntime(**dependencies))

    def build_event_dispatch_lifecycle(self,scope):
        from aos_api.ecommerce_event_control_dispatch_lifecycle import EventControlDispatchLifecycle
        if self.event_dispatch_connect is None:
            raise PermissionError('protected event dispatch identity is not configured')
        _,artifacts=self._source_dependencies(scope)
        return EventControlDispatchLifecycle(connect=self.event_dispatch_connect,
            installation_store=self.installation_store,artifacts=artifacts,release_policy=self.policy)

    def build_event_owner(self,scope):
        from aos_api.ecommerce_product_event_qualified_owner import ProductEventQualifiedOwner
        selections,artifacts=self._source_dependencies(scope)
        return ProductEventQualifiedOwner(selections=selections,installation_store=self.installation_store,
            artifacts=artifacts,release_policy=self.policy)

    def build_event_control_owner(self,scope):
        from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
        selections,artifacts=self._source_dependencies(scope)
        return ProductEventControlQualifiedOwner(selections=selections,installation_store=self.installation_store,
            artifacts=artifacts,release_policy=self.policy)

    def build_event_consumer(self,scope,*,actor,run_id,control_ref,installation_id,generation,
                             live_directory,markings,store):
        """Build saved-input consumption only; construction performs no source call."""
        from aos_api.ecommerce_product_event_consumer import ProductEventConsumptionService
        from aos_api.ecommerce_product_event_control_qualified_owner import ProductEventControlQualifiedOwner
        from aos_api.ecommerce_product_event_reader import ProductEventCandidateReader
        from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
        from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
        from aos_api.ecommerce_growth_runtime_connection import connect_serializable
        selections,artifacts=self._source_dependencies(scope)
        owner=ProductEventControlQualifiedOwner(selections=selections,installation_store=self.installation_store,
            artifacts=artifacts,release_policy=self.policy)
        claims=PipelineSourceClaimOwner(controls=PipelineRuntimeControlOwner(selections=selections))
        journal=ControlledIngressJournal(claims=claims,scope=scope,run_id=run_id,control_ref=control_ref,
            actor=actor,completed_read=True)
        reader=ProductEventCandidateReader(selections,journal=journal,store=store)
        invoker=CurrentInstalledPackageInvoker(scope=scope,installation_id=installation_id,generation=generation,
            package_id='domain.ecommerce.core',markings=markings,connect_factory=connect_serializable,
            installation_store=self.installation_store,live_directory=live_directory)
        return ProductEventConsumptionService(scope=scope,actor=actor,owner=owner,reader=reader,invoker=invoker)

    def build_event_analysis(self,scope,*,actor,run_id,control_ref,installation_id,generation,
                             live_directory,markings,store):
        from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
        from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
        from aos_api.ecommerce_growth_runtime_connection import connect_serializable
        source=self.build_event_consumer(scope,actor=actor,run_id=run_id,control_ref=control_ref,
            installation_id=installation_id,generation=generation,live_directory=live_directory,
            markings=markings,store=store)
        growth=CurrentInstalledPackageInvoker(scope=scope,installation_id=installation_id,generation=generation,
            package_id='solution.ecommerce.growth',markings=markings,connect_factory=connect_serializable,
            installation_store=self.installation_store,live_directory=live_directory)
        return ProductEventAnalysisService(source_context=source,invoker=growth)

    def build_scheduled_analysis(self,scope,*,actor,run_id,control_ref,installation_id,generation,
                                 live_directory,markings,store):
        """Build the same sealed analysis bootstrap with a schedule-only phase owner."""
        from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
        from aos_api.ecommerce_scheduled_analysis_service import ScheduledBaselinePhaseOwner
        from aos_api.extension_runtime.installed_package_invoker import CurrentInstalledPackageInvoker
        from aos_api.ecommerce_growth_runtime_connection import connect_serializable
        source=self.build_event_consumer(scope,actor=actor,run_id=run_id,control_ref=control_ref,
            installation_id=installation_id,generation=generation,live_directory=live_directory,
            markings=markings,store=store)
        growth=CurrentInstalledPackageInvoker(scope=scope,installation_id=installation_id,generation=generation,
            package_id='solution.ecommerce.growth',markings=markings,connect_factory=connect_serializable,
            installation_store=self.installation_store,live_directory=live_directory)
        return ProductEventAnalysisService(source_context=source,invoker=growth,
            phase_owner=ScheduledBaselinePhaseOwner())

    def build_analysis_snapshot_coordinator(self,scope,*,route,live_directory,markings,store):
        """Build the one fixed coordinator from a server-resolved original route."""
        from aos_api.ecommerce_analysis_data_requirement_route import AnalysisDataRequirementRoute
        from aos_api.ecommerce_analysis_snapshot_coordinator import AnalysisSnapshotCoordinator
        from aos_api.ecom_consistency_store import EcomConsistencyStore
        from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory
        from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
        from aos_api.phase5_pipeline_engine import get_engine
        from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
        if (type(route) is not AnalysisDataRequirementRoute
                or type(live_directory) is not LivePreparedJobDirectory
                or type(store) is not EcomConsistencyStore):
            raise TypeError('exact lifecycle snapshot coordinator inputs required')
        analysis=self.build_event_analysis(scope,actor=route.actor,run_id=route.source_run_id,
            control_ref=route.source_control_ref,installation_id=route.installation_id,
            generation=route.generation,live_directory=live_directory,markings=markings,store=store)
        claims=analysis.source.reader._journal._claims
        completion=PipelineSnapshotGroupCompletion(claims=claims,store=store,
            connect=runtime_worker_connection,eng=get_engine())
        return AnalysisSnapshotCoordinator(analysis=analysis,completion=completion,store=store)
