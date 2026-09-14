"""Derive startup Eval contracts from the current selected skill publication."""
from copy import deepcopy

from aos_api.aip_agent_registry_contracts import SkillTemplateRevision
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_eval_runner import AipEvalRunner
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import CreateEvalContractRequest, ExactRevisionRef
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.asset_registry.canonical_json import canonical_json
from aos_api.ecommerce_analysis_compilation_selection import AnalysisCompilationSelectionReader
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisStartupEvalPreparation:
    def __init__(self, selection):
        if type(selection) is not AnalysisCompilationSelectionReader:
            raise TypeError('exact current compilation selection reader required')
        self.selection = selection

    def run_current(self, conn, *, scope, selection_ref, actor, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('current startup Eval callback required')
        blueprint = validate_analysis_compilation_blueprint(domain_profile,blueprint)
        first = blueprint['stageSkills'][0]
        factory = TransactionBoundConnectFactory(HostTransaction(conn),scope)
        store = AipProductionContractStore(factory)

        def current(dependencies):
            choices = [s for s in dependencies['skills'] if s['skillId']==first['skillId']]
            if len(choices)!=1:
                raise ValueError('startup Eval requires one selected first-stage skill')
            skill = SkillTemplateRevision.model_validate(choices[0])
            body = self._request(conn,scope,skill,factory)
            digest = canonical_hash(body.model_dump(mode='json',by_alias=True))
            key = 'analysis-startup-eval-' + digest
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                         (canonical_json([*scope.key,key]).decode('utf-8'),))
            def matches():
                return conn.execute('''SELECT h.contract_id FROM aip_eval_contract_head h
                    JOIN aip_eval_contract_revision r ON r.org_id=h.org_id AND r.project_id=h.project_id
                      AND r.contract_id=h.contract_id AND r.revision=h.current_revision
                    WHERE h.org_id=%s AND h.project_id=%s AND r.content_hash=%s AND r.lifecycle='frozen'
                    ORDER BY h.contract_id LIMIT 2''',(*scope.key,digest)).fetchall()
            rows = matches()
            if len(rows)>1:
                raise ValueError('startup Eval contract selection is ambiguous')
            contract = (store.get_eval_contract(scope,rows[0]['contract_id'],conn=conn) if rows
                        else store.create_eval_contract(scope,actor,key+'-create',body))
            contract = store.get_eval_contract(scope,contract.contract_id,conn=conn)
            if contract.content_hash!=digest:
                raise ValueError('startup Eval contract intent drifted')
            if contract.lifecycle.value=='draft':
                contract = store.freeze_eval_contract(scope,actor,contract.contract_id,contract.version,key+'-freeze')
            if (contract.lifecycle.value!='frozen' or contract.readiness.value!='ready' or contract.blockers
                    or CreateEvalContractRequest(**{k:getattr(contract,k) for k in CreateEvalContractRequest.model_fields})!=body):
                raise ValueError('startup Eval contract is not currently ready')
            ref = ExactRevisionRef(resourceType='EvalContractRevision',resourceId=contract.contract_id,
                revision=contract.revision,contentHash=contract.content_hash)
            result = execute(dict(deepcopy(dependencies),
                startupEval=contract.model_dump(mode='json',by_alias=True),
                startupEvalRef=ref.model_dump(mode='json',by_alias=True)))
            _reject_deferred(result)
            if (self._request(conn,scope,skill,factory)!=body
                    or store.get_eval_contract(scope,contract.contract_id,conn=conn)!=contract
                    or matches()!=[{'contract_id':contract.contract_id}]):
                raise ValueError('startup Eval dependencies changed during callback')
            return result
        return self.selection.run_current(conn,scope=scope,selection_ref=selection_ref,actor=actor,
            domain_profile=domain_profile,blueprint=blueprint,execute=current)

    @staticmethod
    def _request(conn,scope,skill,factory):
        if (skill.lifecycle.value!='published' or skill.publication_tenant is None
                or (skill.publication_tenant.org_id,skill.publication_tenant.project_id)!=scope.key):
            raise ValueError('startup Eval selected skill publication differs')
        row = conn.execute('''SELECT * FROM aip_release_gate_decision
            WHERE org_id=%s AND project_id=%s AND decision_id=%s''',
            (*scope.key,skill.release_gate_ref.asset_id)).fetchone()
        event = conn.execute('''SELECT * FROM aip_publication_event
            WHERE org_id=%s AND project_id=%s AND publication_id=%s
            ORDER BY occurred_at DESC,event_id DESC LIMIT 1''',
            (*scope.key,skill.publication_ref.revision)).fetchone()
        if row is None or event is None:
            raise ValueError('startup Eval publication authority missing')
        gate = AipReleasePublicationService._gate_from_row(scope,row)
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        parent = skill.parent_ref
        if (gate.status.value!='passed' or not gate.decided_at<=now<gate.expires_at
                or event['occurred_at']>now or gate.decision_hash!=skill.release_gate_ref.content_hash
                or gate.target.asset_type!=AssetType.SKILL_TEMPLATE
                or (gate.target.asset_id,int(gate.target.revision),gate.target.content_hash)
                    !=(parent.asset_id,parent.revision,parent.content_hash)
                or event['event_type']!='published' or event['event_id']!=skill.publication_ref.resource_id
                or event['release_gate_decision_id']!=gate.decision_id
                or AssetRevisionRef.model_validate(event['target_ref'])!=gate.target):
            raise ValueError('startup Eval publication lineage invalid or expired')
        AipReleasePublicationService._verify_gate_evidence(conn,scope,gate)
        report = AipEvalRunner(factory).get_report(scope,gate.eval_report.artifact_id,int(gate.eval_report.revision))
        run_row = conn.execute('SELECT * FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND run_id=%s',
                              (*scope.key,gate.eval_run_id)).fetchone()
        if run_row is None:
            raise ValueError('startup Eval original evaluation run missing')
        AipReleasePublicationService._verify_run(report,run_row)
        return CreateEvalContractRequest(
            suiteRef=ExactRevisionRef(resourceType='EvalSuiteRevision',resourceId=gate.suite_ref.asset_id,
                revision=int(gate.suite_ref.revision),contentHash=gate.suite_ref.content_hash),
            publicationRef=ExactRevisionRef(resourceType='PublicationEvent',resourceId=event['event_id'],
                revision=1,contentHash=canonical_hash(AipProductionContractStore._publication_snapshot(event))),
            releaseGateRef=ExactRevisionRef(resourceType='ReleaseGateDecision',resourceId=gate.decision_id,
                revision=1,contentHash=gate.decision_hash),
            artifactSchemaRef=ResourceRef(resourceType='Schema',resourceId='SkillPublicationContract.'+skill.skill_id.removeprefix('ecommerce.skill.'),
                revision='1',authority='aip-contract'),
            severityThresholds={'critical':1.0,'required':1.0},
            gatePolicy={'requiredPassRate':1.0,'requiredCases':report.total,'evidenceKind':'isolated_skill_contract'},
            returnMapping={'pass':'publish','fail':'block'},overridePolicy={'allowed':False})
