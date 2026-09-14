"""Task-scoped startup Context inside the original event and configured-role owners."""
from copy import deepcopy
from datetime import datetime

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, ExactRevisionRef, FreezeProductionContextRequest
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_analysis_startup_eval import AnalysisStartupEvalPreparation
from aos_api.ecommerce_analysis_startup_evidence import AnalysisStartupEvidenceService
from aos_api.ecommerce_analysis_task_preparation import prepare_analysis_task
from aos_api.ecommerce_analysis_template_preparation import AnalysisTemplatePreparation
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef


class AnalysisContextPreparation:
    def __init__(self, analysis):
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('exact current event analysis service required')
        self.analysis = analysis
        roles = AnalysisCompilationRoleReader(analysis.source.control._owner._source)
        self.templates = AnalysisTemplatePreparation(roles)
        self.evaluation = AnalysisStartupEvalPreparation(AnalysisCompilationSelectionReader(roles))
        self.evidence = AnalysisStartupEvidenceService(analysis)

    def run_current(self, conn, *, claimed, run_ref, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('synchronous startup Context callback required')
        blueprint = validate_analysis_compilation_blueprint(domain_profile,blueprint)
        scope,actor = self.analysis.scope,self.analysis.source.actor
        tx = HostTransaction(conn)
        factory = TransactionBoundConnectFactory(tx,scope)
        store = AipProductionContractStore(factory)

        def current(snapshot, request, _dispatch):
            selection_ref = PipelineExactRef.model_validate(snapshot['source']['policy']['sourceSelectionRef'])
            self.templates.run_current(conn,scope=scope,selection_ref=selection_ref,actor=actor,
                domain_profile=domain_profile,blueprint=blueprint,execute=lambda prepared:prepared)
            case = BusinessInvestigationCaseRevision.model_validate(snapshot['source']['case'])
            run = BusinessInvestigationRunStore(factory).get_verified(scope,run_ref.resource_id)
            # No AIP task is prepared for a substituted business Run.
            if (run_ref.resource_type,run_ref.resource_id,run_ref.revision,run_ref.content_hash)!= (
                    'BusinessInvestigationRun',run.authority.run_id,run.authority.version,run.authority.content_hash):
                raise ValueError('startup Context Run exact reference differs')
            prepared = prepare_analysis_task(tx,scope=scope,actor=actor,case=case,run=run,domain_profile=domain_profile)
            evidence = self.evidence.record(conn,claimed=claimed,run_ref=run_ref,domain_profile=domain_profile,blueprint=blueprint)
            brief_ref = ExactRevisionRef.model_validate(prepared['taskBriefRef'])
            evidence_ref = ExactRevisionRef(resourceType='Evidence',resourceId=evidence.resource_id,
                revision=evidence.revision,contentHash=evidence.content_hash.removeprefix('sha256:'))
            bundle_request = BuildEvidenceBundleRequest(briefRef=brief_ref,
                subjectRefs=[ResourceRef(resourceType='BusinessInvestigationRun',resourceId=run.authority.run_id,
                    revision=str(run.authority.version),authority='aos.ecommerce.business-investigation')],
                cutoffAt=datetime.fromisoformat(request['cutoffAt']),itemRefs=[evidence_ref],
                requiredFactIds=blueprint['startupContextPolicy']['requiredFactIds'],marking=['internal','analysis-startup'],
                licenseSummary={'allowedPurposes':['analysis-start'],'businessFactCoverage':'not-evaluated'})
            key = 'analysis-context-' + canonical_sha256([*scope.key,run.authority.run_id]).removeprefix('sha256:')

            def with_eval(dependencies):
                plan = dependencies['responsibilityPlan']
                if (plan['profile']!=blueprint['compilerProfile'] or plan['lifecycle']!='frozen'
                        or plan['readiness']!='ready' or plan['coverage']!='complete' or plan['blockers']):
                    raise ValueError('startup Context configured responsibilities unavailable')
                role_ref = ExactRevisionRef(resourceType='ResponsibilityPlanRevision',resourceId=plan['planId'],
                    revision=plan['revision'],contentHash=plan['contentHash'])
                bundle = store.build_evidence_bundle(scope,actor,key+'-bundle',bundle_request)
                bundle = store.get_evidence_bundle(scope,bundle.bundle_id,bundle.revision,conn=conn)
                if (bundle.brief_ref!=brief_ref or bundle.item_refs!=[evidence_ref]
                        or bundle.coverage.value!='complete' or bundle.freshness.value!='fresh'
                        or bundle.revoked or bundle.missing or bundle.conflicts or bundle.uncertainties):
                    raise ValueError('startup Context evidence bundle unavailable')
                bundle_ref = ExactRevisionRef(resourceType='EvidenceBundleRevision',resourceId=bundle.bundle_id,
                    revision=bundle.revision,contentHash=bundle.content_hash)
                context = store.freeze_production_context(scope,actor,key+'-freeze',FreezeProductionContextRequest(
                    taskId=prepared['task']['id'],briefRef=brief_ref,evidenceBundleRef=bundle_ref,
                    evalContractRef=ExactRevisionRef.model_validate(dependencies['startupEvalRef']),
                    responsibilityPlanRef=role_ref,profile=blueprint['compilerProfile']))
                context_ref = ExactRevisionRef(resourceType='ProductionContextRevision',resourceId=context.context_id,
                    revision=context.revision,contentHash=context.content_hash)
                result = execute(dict(deepcopy(dependencies),**deepcopy(prepared),
                    startupEvidenceRef=evidence_ref.model_dump(mode='json',by_alias=True),
                    startupBundleRequest=bundle_request.model_dump(mode='json',by_alias=True),
                    startupBundle=bundle.model_dump(mode='json',by_alias=True),
                    startupBundleRef=bundle_ref.model_dump(mode='json',by_alias=True),
                    productionContext=context.model_dump(mode='json',by_alias=True),
                    productionContextRef=context_ref.model_dump(mode='json',by_alias=True)))
                _reject_deferred(result)
                if (self.evidence.record(conn,claimed=claimed,run_ref=run_ref,domain_profile=domain_profile,blueprint=blueprint)!=evidence
                        or store.get_evidence_bundle(scope,bundle.bundle_id,bundle.revision,conn=conn)!=bundle
                        or store.get_production_context(scope,context.context_id,context.revision,conn=conn)!=context):
                    raise ValueError('startup Context dependencies changed during callback')
                return result
            return self.evaluation.run_current(conn,scope=scope,
                selection_ref=selection_ref,
                actor=actor,domain_profile=domain_profile,blueprint=blueprint,execute=with_eval)
        return self.analysis._phase(conn,claimed,current)
