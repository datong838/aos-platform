"""Read actual analysis bindings and publication lineage within current roles."""
from copy import deepcopy
from uuid import UUID
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_skill_binding_readiness_service import AipSkillBindingReadinessService
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_analysis_skill_set import AnalysisSkillBindingSet
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisSkillSetReader:
    def __init__(self, roles):
        if type(roles) is not AnalysisCompilationRoleReader:
            raise TypeError('current configured role reader required')
        self._roles = roles

    def run_current(self, conn, *, scope, selection_ref, actor, domain_profile,
                    compiler_profile, stage_ref, binding_ids, execute):
        if (not isinstance(binding_ids, (list, tuple)) or not 1 <= len(binding_ids) <= 128
                or any(type(value) is not str or not value or value != value.strip() for value in binding_ids)
                or len(set(binding_ids)) != len(binding_ids) or not callable(execute)):
            raise ValueError('explicit unique bounded skill binding IDs required')
        selected = tuple(sorted(binding_ids))

        def current(roles):
            factory = TransactionBoundConnectFactory(HostTransaction(conn), scope)
            registry = AipSkillRegistry(factory)
            readiness = AipSkillBindingReadinessService(connect_factory=factory)
            plan = roles['responsibilityPlan']
            assignees = {slot['assignee']['resourceId'] for slot in plan['slots']
                         if slot['assignee']['kind'] == 'agent_instance'}
            plan_ref = ExactRevisionRef(resourceType='ResponsibilityPlanRevision',
                resourceId=plan['planId'], revision=plan['revision'], contentHash=plan['contentHash'])
            installation = roles['currentInstallation']

            def read():
                now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                bindings = [registry.get_binding(scope, value) for value in selected]
                if tuple(item.binding_id for item in bindings) != selected:
                    raise ValueError('selected binding identity differs')
                payload = dict(schemaVersion='aos.ecommerce.analysis-skill-binding-set/v1',
                    tenant=dict(orgId=scope.org_id, projectId=scope.project_id), **installation,
                    responsibilityPlanRef=plan_ref.model_dump(mode='json', by_alias=True),
                    bindings=[item.model_dump(mode='json', by_alias=True) for item in bindings])
                exact_set = AnalysisSkillBindingSet.model_validate(dict(payload, contentHash=canonical_sha256(payload)))
                exact_set.validate_current(scope=scope, installation_id=UUID(installation['installationId']),
                    generation=UUID(installation['generation']), execution_epoch=installation['executionEpoch'],
                    responsibility_ref=plan_ref, bindings=bindings, now=now)
                skills, publications = [], []
                for binding in bindings:
                    if binding.instance_id not in assignees:
                        raise ValueError('skill binding is outside configured responsibilities')
                    evaluation = readiness.evaluate(scope, binding, evaluated_at=now)
                    if (evaluation.readiness.value != 'available' or evaluation.reasons
                            or evaluation.dependency_snapshot_hash != binding.dependency_snapshot_hash):
                        raise ValueError('current skill dependencies are unavailable or drifted')
                    skill = registry.get_skill(binding.skill.asset_id, binding.skill.revision).model_dump(mode='json', by_alias=True)
                    if (skill['skillId'] != binding.skill.asset_id or skill['revision'] != binding.skill.revision
                            or skill['contentHash'] != binding.skill.content_hash or skill['lifecycle'] != 'published'
                            or skill['publicationTenant'] != payload['tenant']):
                        raise ValueError('exact skill publication differs')
                    logic = skill.get('logicRevisionRef') or {}
                    if logic.get('assetType') != 'LogicRevision':
                        raise ValueError('published skill has no exact Logic revision')
                    rows = conn.execute('''SELECT publication_id,graph_hash FROM aip_logic_publication
                        WHERE org_id=%s AND project_id=%s AND graph_id=%s AND graph_revision=%s''',
                        (*scope.key, logic['assetId'], logic['revision'])).fetchall()
                    if len(rows) != 1 or rows[0]['graph_hash'] != logic['contentHash']:
                        raise ValueError('exact Logic publication missing or drifted')
                    skills.append(skill)
                    publications.append(dict(logicRef=logic, publicationId=rows[0]['publication_id']))
                return dict(skillBindingSet=exact_set.model_dump(mode='json', by_alias=True),
                    skillBindingSetRef=exact_set.exact_ref.model_dump(mode='json', by_alias=True),
                    skills=skills, logicPublications=publications)

            before = read()
            result = execute(dict(deepcopy(roles), **deepcopy(before)))
            _reject_deferred(result)
            if canonical_sha256(read()) != canonical_sha256(before):
                raise ValueError('current analysis skill dependencies changed during callback')
            return result

        return self._roles.run_with_stage(conn, scope=scope, selection_ref=selection_ref, actor=actor,
            domain_profile=domain_profile, compiler_profile=compiler_profile, stage_ref=stage_ref, execute=current)
