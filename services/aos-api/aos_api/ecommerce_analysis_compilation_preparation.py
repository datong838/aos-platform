"""Current event Context -> canonical Plan/Saga, without runtime authorization."""
from copy import deepcopy

from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompileSaga, BusinessInvestigationCompilationReceiptStore
from aos_api.aip_business_investigation_compiler import BusinessInvestigationProfileCompiler
from aos_api.aip_logic_publication_store import LogicPublicationStore
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_responsibility_template_authority import resolve_responsibility_template
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.ecommerce_analysis_compilation_binding import build_analysis_compilation_binding
from aos_api.ecommerce_analysis_context_preparation import AnalysisContextPreparation
from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisCompilationPreparation:
    def __init__(self, context):
        if type(context) is not AnalysisContextPreparation:
            raise TypeError('exact current event Context preparation required')
        self.context = context

    def run_current(self, conn, *, claimed, run_ref, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('synchronous compilation callback required')
        analysis = self.context.analysis
        scope, actor = analysis.scope, analysis.source.actor
        factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
        contracts = AipProductionContractStore(factory,
            responsibility_template_resolver=resolve_responsibility_template,
            stage_template_source_resolver=resolve_stage_template_source)
        cases, runs = BusinessInvestigationCaseStore(factory), BusinessInvestigationRunStore(factory)
        receipts = BusinessInvestigationCompilationReceiptStore(factory)

        def compile_current(prepared):
            run = runs.get_verified(scope, run_ref.resource_id)
            case = cases.get(scope, run.authority.case_ref.resource_id)
            binding = build_analysis_compilation_binding(scope=scope, case=case, run=run,
                domain_profile=domain_profile, blueprint=blueprint, prepared=prepared)
            request = binding.request
            resolver = _CompilationExactResolver(conn, scope, factory, contracts, binding, prepared, case, run)
            saga = BusinessInvestigationCompileSaga(BusinessInvestigationProfileCompiler(contracts, resolver), receipts)
            written = saga.execute(scope, actor, run.authority.trigger_key, run, request)
            receipt = written.authority
            plan = conn.execute('''SELECT * FROM aip_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s''',
                (*scope.key, receipt.plan_ref.resource_id)).fetchone()
            if (plan is None or plan['task_id'] != request.task_id
                    or plan['revision'] != receipt.plan_ref.revision or plan['content_hash'] != receipt.plan_ref.content_hash
                    or not plan['risk'].get('productionContract', {}).get('productionStartGateRequired')):
                raise ValueError('compiled Plan lineage or start gate differs')
            output = dict(deepcopy(prepared),
                compilationBinding=binding.model_dump(mode='json', by_alias=True),
                compilationReceipt=receipt.model_dump(mode='json', by_alias=True),
                compilationRef=receipt.exact_ref.model_dump(mode='json', by_alias=True))
            result = execute(output)
            _reject_deferred(result)
            for _label, ref in BusinessInvestigationProfileCompiler._input_refs(request):
                if not resolver(scope, ref):
                    raise ValueError('compilation input changed during callback')
            if receipts.get_for_run(scope, run_ref) != receipt:
                raise ValueError('compilation Receipt changed during callback')
            current_plan = conn.execute('''SELECT * FROM aip_plan_revision
                WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s''',
                (*scope.key, receipt.plan_ref.resource_id)).fetchone()
            if current_plan != plan:
                raise ValueError('compiled Plan changed during callback')
            return result
        return self.context.run_current(conn, claimed=claimed, run_ref=run_ref,
            domain_profile=domain_profile, blueprint=blueprint, execute=compile_current)


class _CompilationExactResolver:
    """Only the current owner callback's references can reach canonical reads."""
    def __init__(self, conn, scope, factory, contracts, binding, prepared, case, run):
        self.conn, self.scope, self.factory, self.contracts = conn, scope, factory, contracts
        self.binding, self.prepared, self.case, self.run = binding, deepcopy(prepared), case, run
        self.allowed = {tuple(ref.model_dump().values()) for _, ref in
                        BusinessInvestigationProfileCompiler._input_refs(binding.request)}

    def __call__(self, scope, ref):
        if (scope != self.scope or type(ref) is not ExactRevisionRef
                or tuple(ref.model_dump().values()) not in self.allowed):
            return False
        request, p, store = self.binding.request, self.prepared, self.contracts
        kind = ref.resource_type
        if kind == 'BusinessInvestigationCaseRevision':
            case = BusinessInvestigationCaseStore(self.factory).get(scope, ref.resource_id)
            return case == self.case and case.calculated_content_hash() == case.content_hash
        if kind == 'BusinessInvestigationRun':
            return BusinessInvestigationRunStore(self.factory).get_verified(scope, ref.resource_id) == self.run
        if kind == 'TaskBriefRevision':
            brief = store.get_brief(scope, ref.resource_id, conn=self.conn)
            return (brief.task_id == request.task_id and brief.revision == ref.revision
                and brief.content_hash == ref.content_hash and brief.lifecycle.value == 'frozen'
                and brief.spec == request.task_brief_spec.model_dump(mode='json', by_alias=True)
                and canonical_hash(dict(briefType=brief.brief_type, schemaRef=brief.schema_ref.model_dump(mode='json', by_alias=True),
                    spec=brief.spec)) == ref.content_hash)
        if kind == 'InvestigationProfileRevision':
            if ref == request.profile.exact_ref:
                return request.profile.calculated_content_hash() == ref.content_hash
            return ref == request.task_brief_spec.domain_profile_ref and resolve_stage_template_source(scope, ref)
        if kind == 'SkillBindingSetRevision':
            # Derived set has no independent database head. Its original current
            # binding reader surrounds this entire callback and rechecks on exit.
            return AnalysisSkillBindingSet.model_validate(p['skillBindingSet']).exact_ref == ref
        if kind == 'SkillTemplateRevision':
            skill = AipSkillRegistry(self.factory).get_skill(ref.resource_id, ref.revision)
            expected = next(item for item in p['skills'] if item['skillId'] == ref.resource_id)
            logic = skill.logic_revision_ref
            return (skill.model_dump(mode='json', by_alias=True) == expected and logic is not None
                and self._logic_verified(scope, ExactRevisionRef(resourceType='LogicRevision',
                    resourceId=logic.asset_id, revision=logic.revision, contentHash=logic.content_hash)))
        if kind == 'LogicRevision':
            return self._logic_verified(scope, ref)
        readers = {
            'StageTemplateRevision': (store.get_stage_template, 'stageTemplate'),
            'ResponsibilityPlanRevision': (store.get_responsibility_plan, 'responsibilityPlan'),
            'ProductionContextRevision': (store.get_production_context, 'productionContext'),
        }
        if kind not in readers:
            return False
        reader, key = readers[kind]
        current = reader(scope, ref.resource_id, conn=self.conn)
        return current.model_dump(mode='json', by_alias=True) == p[key]

    def _logic_verified(self, scope, ref):
        rows = self.conn.execute('''SELECT publication_id FROM aip_logic_publication
            WHERE org_id=%s AND project_id=%s AND graph_id=%s AND graph_revision=%s''',
            (*scope.key, ref.resource_id, ref.revision)).fetchall()
        if len(rows) != 1:
            return False
        publication = LogicPublicationStore(self.factory).get(*scope.key, ref.resource_id, rows[0]['publication_id'])
        return publication.graph_hash == ref.content_hash
