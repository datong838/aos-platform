"""Internal template preparation within an already authorized analysis Host transaction."""
from copy import deepcopy
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateStageTemplateRequest, ExactRevisionRef
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.asset_registry.canonical_json import canonical_sha256, canonical_json
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisTemplatePreparation:
    def __init__(self, roles):
        if type(roles) is not AnalysisCompilationRoleReader:
            raise TypeError('current configured role reader required')
        self._roles = roles

    def run_current(self, conn, *, scope, selection_ref, actor, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('scoped preparation callback required')
        blueprint = validate_analysis_compilation_blueprint(domain_profile, blueprint)
        body = CreateStageTemplateRequest.model_validate(blueprint['stageTemplateRequest'])
        digest = canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:')
        key = 'analysis-template-' + digest

        def current(_roles):
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (canonical_json([*scope.key,key]).decode('utf-8'),))
            store = AipProductionContractStore(TransactionBoundConnectFactory(HostTransaction(conn),scope),
                stage_template_source_resolver=resolve_stage_template_source)
            def matches():
                return conn.execute('''SELECT h.template_id FROM aip_stage_template_head h
                    JOIN aip_stage_template_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                    AND r.template_id=h.template_id AND r.revision=h.current_revision
                    WHERE h.org_id=%s AND h.project_id=%s AND r.profile=%s AND r.content_hash=%s
                    AND r.lifecycle='frozen' ORDER BY h.template_id LIMIT 2''',
                    (*scope.key,body.profile,digest)).fetchall()
            rows = matches()
            if len(rows)>1:
                raise ValueError('analysis template preparation is ambiguous')
            if rows:
                template_id = rows[0]['template_id']
            else:
                created = store.create_stage_template(scope,actor,key+'-create',body)
                template_id = created.template_id
            stage = store.get_stage_template(scope,template_id,conn=conn)
            if stage.content_hash != digest:
                raise ValueError('prepared template head differs')
            if stage.lifecycle.value == 'draft':
                stage = store.freeze_stage_template(scope,actor,stage.template_id,stage.version,key+'-freeze')
            if stage.lifecycle.value != 'frozen' or stage.readiness.value != 'ready' or stage.blockers:
                raise ValueError('prepared template is not frozen and ready')
            stage_ref = ExactRevisionRef(resourceType='StageTemplateRevision',resourceId=stage.template_id,
                revision=stage.revision,contentHash=stage.content_hash)
            result = execute(dict(stageTemplateRef=stage_ref.model_dump(mode='json',by_alias=True),
                                  compilationBlueprint=deepcopy(blueprint)))
            _reject_deferred(result)
            after = store.get_stage_template(scope,stage.template_id,conn=conn)
            if (after.model_dump(mode='json',by_alias=True)!=stage.model_dump(mode='json',by_alias=True)
                    or matches()!=[{'template_id':stage.template_id}]):
                raise ValueError('prepared template changed during callback')
            return result

        return self._roles.run_current(conn,scope=scope,selection_ref=selection_ref,actor=actor,
            domain_profile=domain_profile,compiler_profile=blueprint['compilerProfile'],execute=current)
