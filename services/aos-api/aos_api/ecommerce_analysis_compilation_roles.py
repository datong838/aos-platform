"""Current configured analysis responsibility; no new grants or plan writes."""
from copy import deepcopy
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_template_authority import resolve_responsibility_template
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
        if compiler_profile != domain.responsibility_template_code:
            raise ValueError('compiler responsibility profile differs from domain template')
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
                template = ExactRevisionRef.model_validate(plan['templateRef'])
                if (template.resource_type != 'ResponsibilityTemplateRevision'
                        or template.resource_id != domain.responsibility_template_code
                        or not resolve_responsibility_template(scope, template)):
                    raise ValueError('domain responsibility template differs or is unavailable')
                # L1 analysis intent IDs are resolved by the Logic/Skill compiler;
                # responsibility slots cover concrete operational capabilities.
                if (plan['lifecycle']!='frozen' or plan['readiness']!='ready' or plan['coverage']!='complete'):
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

    def run_with_stage(self, conn, *, scope, selection_ref, actor, domain_profile,
                       compiler_profile, stage_ref, execute):
        """Read a specified current template inside the configured-role boundary.

        The caller must obtain stage_ref from its governed compilation selection.
        This reader neither selects an arbitrary tenant template nor grants execution.
        """
        from aos_api.aip_production_contract_store import canonical_hash
        from aos_api.aip_stage_template_authority import resolve_stage_template_source

        if type(stage_ref) is not ExactRevisionRef or not callable(execute):
            raise TypeError('exact stage reference and scoped callback required')
        ref = ExactRevisionRef.model_validate(stage_ref.model_dump(mode='json', by_alias=True))
        if ref.resource_type != 'StageTemplateRevision':
            raise ValueError('stage reference type differs')
        domain = EcommerceInvestigationProfileRevision.model_validate(
            domain_profile.model_dump(mode='json', by_alias=True))
        source = ExactRevisionRef(resourceType=domain.exact_ref.resource_type,
            resourceId=domain.profile_id, revision=domain.revision,
            contentHash=domain.content_hash.removeprefix('sha256:'))

        def current(roles):
            store = AipProductionContractStore(
                TransactionBoundConnectFactory(HostTransaction(conn), scope),
                stage_template_source_resolver=resolve_stage_template_source)
            slot_ids = {slot['slotId'] for slot in roles['responsibilityPlan']['slots']}

            def read():
                # Read the head, not a superseded frozen revision selected by the caller.
                stage = store.get_stage_template(scope, ref.resource_id, conn=conn).model_dump(
                    mode='json', by_alias=True)
                if (stage['tenant'] != dict(orgId=scope.org_id, projectId=scope.project_id)
                        or stage['templateId'] != ref.resource_id or stage['revision'] != ref.revision
                        or stage['contentHash'] != ref.content_hash
                        or stage['lifecycle'] != 'frozen' or stage['readiness'] != 'ready'):
                    raise ValueError('current stage template is unavailable or differs')
                if (stage['profile'] != domain.profile_type
                        or ExactRevisionRef.model_validate(stage['sourceBundleRef']) != source
                        or not resolve_stage_template_source(scope, source)):
                    raise ValueError('stage source differs from current domain intent')
                body = {key: stage[key] for key in ('profile', 'sourceBundleRef', 'stages')}
                if canonical_hash(body) != ref.content_hash:
                    raise ValueError('stage template body hash differs')
                if tuple(item['stageId'] for item in stage['stages']) != tuple(
                        item.stage_id for item in domain.stages):
                    raise ValueError('analysis stage order differs')
                if any(not set(item['requiredSlotIds']).issubset(slot_ids) for item in stage['stages']):
                    raise ValueError('stage responsibility slots are not configured')
                return stage

            before = read()
            result = execute(dict(deepcopy(roles), stageTemplate=deepcopy(before)))
            _reject_deferred(result)
            if canonical_sha256(read()) != canonical_sha256(before):
                raise ValueError('stage template changed during callback')
            return result

        return self.run_current(conn, scope=scope, selection_ref=selection_ref, actor=actor,
            domain_profile=domain, compiler_profile=compiler_profile, execute=current)
