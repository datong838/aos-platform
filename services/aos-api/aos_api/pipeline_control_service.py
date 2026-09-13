"""Tenant-bound approval services using the existing production runtime identity."""
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

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

    def __post_init__(self):
        if type(self.installation_store) is not PostgresInstallationStore or type(self.policy) is not ReleasePolicy:
            raise TypeError('exact production pipeline dependencies required')
        if type(self.allowlist_roots) is not dict or any(type(key) is not str or not isinstance(value,Path) for key,value in self.allowlist_roots.items()):
            raise TypeError('server-owned asset roots required')
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
