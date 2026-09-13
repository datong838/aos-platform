"""Current configured analysis responsibility; no new grants or plan writes."""
from copy import deepcopy
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileRevision
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.extension_runtime.configuration_store import read_configuration
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.tenant_scope import TenantScope


class AnalysisCompilationRoleReader:
    def __init__(self,source_owner):
        if type(source_owner) is not PipelineSourceSelectionOwner:
            raise TypeError('exact current source Owner required')
        self._owner=source_owner

    def run_current(self,conn,*,scope,selection_ref,actor,domain_profile,compiler_profile,execute):
        if type(scope) is not TenantScope or type(domain_profile) is not EcommerceInvestigationProfileRevision or not callable(execute):
            raise TypeError('exact analysis intent and scoped callback required')
        domain=EcommerceInvestigationProfileRevision.model_validate(domain_profile.model_dump(mode='json',by_alias=True))
        if type(compiler_profile) is not str or not 1<=len(compiler_profile)<=80 or compiler_profile!=compiler_profile.strip():
            raise ValueError('exact compiler profile required')
        required={cap for stage in domain.stages for cap in stage.required_capability_ids}
        def current(draft,_mapping):
            if (draft.org_id,draft.project_id)!=scope.key:
                raise ValueError('analysis source tenant differs')
            def read():
                document=read_configuration(conn,org_id=scope.org_id,project_id=scope.project_id,
                    installation_id=draft.installation_ref.installation_id,generation=draft.generation,
                    actor=actor,ref=draft.configuration_ref,authorize=self._owner._authorization)
                store=AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),scope))
                selected=[]
                for ref in document.roleRefs:
                    plan=store.get_responsibility_plan(scope,ref.id,ref.revision,conn=conn).model_dump(mode='json',by_alias=True)
                    if plan['profile']!=compiler_profile:continue
                    if (plan['planId']!=ref.id or plan['revision']!=ref.revision
                            or 'sha256:'+plan['contentHash']!=ref.hash):
                        raise ValueError('configured responsibility reference differs')
                    selected.append(plan)
                if len(selected)!=1:
                    raise ValueError('analysis responsibility must be uniquely configured')
                plan=selected[0]
                capabilities={cap for slot in plan['slots'] for cap in slot['requiredCapabilityIds']}
                if (plan['lifecycle']!='frozen' or plan['readiness']!='ready' or plan['coverage']!='complete'
                        or not required.issubset(capabilities)):
                    raise ValueError('current analysis responsibility is not ready')
                return dict(configuration=document.model_dump(mode='json'),responsibilityPlan=plan,
                            domainProfileRef=domain.exact_ref.model_dump(mode='json',by_alias=True))
            before=read();fingerprint=canonical_sha256(before)
            result=execute(deepcopy(before))
            _reject_deferred(result)
            if canonical_sha256(read())!=fingerprint:
                raise ValueError('analysis configuration changed during callback')
            return result
        return self._owner.run_current_snapshot(conn,scope=scope,ref=selection_ref,actor=actor,execute=current)
