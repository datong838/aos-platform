"""Current query Binding observation; no activation or Provider permission."""
from dataclasses import dataclass,asdict
from datetime import datetime
import re
from types import SimpleNamespace

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_binding_readiness_service import AipBindingReadinessService,PostgresBindingDependencyAuthority
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_production_contract_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,ContentGenerateHostService
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.source_readiness_contracts import ExactResourceRef
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class CurrentAnalysisQueryBinding:
    binding_ref: ExactResourceRef
    capability_ref: VersionedAssetRef
    binding_snapshot_hash: str
    checked_at: datetime
    expires_at: datetime


class AnalysisQueryBinding:
    def __init__(self,scope):
        if type(scope) is not TenantScope:raise TypeError('original tenant scope required')
        self.scope=scope

    def _read(self,tx,binding_id):
        scope=tx.execute("SELECT current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project").fetchone()
        if scope is None or (scope['org'],scope['project'])!=self.scope.key:
            raise PermissionError('query binding transaction tenant differs')
        now=tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        row=tx.execute('SELECT * FROM aip_capability_binding WHERE org_id=%s AND project_id=%s AND binding_id=%s FOR SHARE',
                       (*self.scope.key,binding_id)).fetchone()
        if row is None:raise ValueError('query binding unavailable')
        binding=AipCapabilityBindingService._from_row(self.scope,row)
        if (binding.binding_id!=binding_id or binding.capability.asset_type!='CapabilityRevision'
                or binding.capability.asset_id!='strategy.plan' or binding.status!='active'
                or binding.health.value!='healthy' or binding.operational_readiness.value!='available'
                or binding.readiness_reasons or type(binding.version) is not int or binding.version<1
                or binding.last_evaluated_at is None or binding.readiness_expires_at is None
                or binding.observed_at is None or not binding.created_at<=binding.observed_at<=now
                or not binding.last_evaluated_at<=now<binding.readiness_expires_at or binding.updated_at>now
                or binding.dependency_snapshot_hash!=AipBindingReadinessService.snapshot_hash(binding.capability,binding.dependencies)):
            raise ValueError('query binding current health or exact dependency snapshot differs')
        factory=TransactionBoundConnectFactory(tx,self.scope)
        authority=PostgresBindingDependencyAuthority(factory)
        model_store=AipModelRuntimeStore(factory)
        service=AipBindingReadinessService(authority=authority,model_store=model_store)
        assessed=service.evaluate_capability(self.scope,binding.capability,binding.dependencies,evaluated_at=now)
        if (assessed.readiness.value!='available' or assessed.reasons
                or assessed.dependency_snapshot_hash!=binding.dependency_snapshot_hash
                or assessed.dependencies!=binding.dependencies or assessed.expires_at<=now):
            raise ValueError('query binding dependencies are not currently available')
        capability=authority.capability(binding.capability)
        if capability is None:raise ValueError('query capability unavailable')
        required=SimpleNamespace(required_data_refs=[VersionedAssetRef.model_validate(r) for r in capability['required_data_refs']],
            required_tool_refs=[VersionedAssetRef.model_validate(r) for r in capability['required_tool_refs']])
        ContentGenerateHostService._binding_dependency_authority(tx,self.scope,required,binding.dependencies,row,checked_at=now)
        reference=ExactResourceRef(resource_type='CapabilityBinding',resource_id=binding_id,revision=str(binding.version),
            content_hash=binding.dependency_snapshot_hash,authority='postgres:aip_capability_binding')
        return CurrentAnalysisQueryBinding(reference,binding.capability,canonical_hash(binding.model_dump(mode='json',by_alias=True)),
                                          now,min(binding.readiness_expires_at,assessed.expires_at))

    def run_current(self,conn,*,binding_id,execute):
        if type(binding_id) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}',binding_id) is None:
            raise ValueError('canonical query binding identity required')
        if not callable(execute):raise TypeError('synchronous query binding consumer required')
        with conn.transaction():
            tx=HostTransaction(conn)
            current=self._read(tx,binding_id);digest=canonical_hash(asdict(current))
            result=execute(current)
            _reject_deferred(result)
            after=self._read(tx,binding_id)
            if (canonical_hash(asdict(current))!=digest or after.binding_snapshot_hash!=current.binding_snapshot_hash
                    or after.checked_at>=current.expires_at):
                raise ValueError('query binding changed during consumption')
            return result
