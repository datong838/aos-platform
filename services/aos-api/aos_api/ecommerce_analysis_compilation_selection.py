"""Resolve an installed blueprint against current configured dependencies only."""
from copy import deepcopy
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ecommerce_analysis_compilation_roles import AnalysisCompilationRoleReader
from aos_api.ecommerce_analysis_skill_reader import AnalysisSkillSetReader
from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisCompilationSelectionReader:
    def __init__(self, roles):
        if type(roles) is not AnalysisCompilationRoleReader:
            raise TypeError('current configured responsibility reader required')
        self._roles = roles

    def run_current(self, conn, *, scope, selection_ref, actor, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('scoped compilation callback required')
        blueprint = validate_analysis_compilation_blueprint(domain_profile, blueprint)
        expected_hash = canonical_sha256(blueprint['stageTemplateRequest']).removeprefix('sha256:')
        expected_skills = {item['skillId']:item['canonicalLogicId'] for item in blueprint['stageSkills']}

        def current(roles):
            assignees = sorted({slot['assignee']['resourceId'] for slot in roles['responsibilityPlan']['slots']
                                if slot['assignee']['kind'] == 'agent_instance'})
            def select():
                stages = conn.execute('''SELECT h.template_id,r.revision,r.content_hash
                    FROM aip_stage_template_head h JOIN aip_stage_template_revision r
                      ON r.org_id=h.org_id AND r.project_id=h.project_id AND r.template_id=h.template_id
                      AND r.revision=h.current_revision
                    WHERE h.org_id=%s AND h.project_id=%s AND r.profile=%s
                      AND r.content_hash=%s AND r.lifecycle='frozen'
                    ORDER BY h.template_id LIMIT 2''',
                    (*scope.key,blueprint['compilerProfile'],expected_hash)).fetchall()
                if len(stages) != 1:
                    raise ValueError('compilation blueprint must resolve one current frozen template')
                stage = ExactRevisionRef(resourceType='StageTemplateRevision',resourceId=stages[0]['template_id'],
                    revision=stages[0]['revision'],contentHash=stages[0]['content_hash'])
                bindings = conn.execute('''SELECT binding_id,skill_id FROM aip_skill_binding
                    WHERE org_id=%s AND project_id=%s AND instance_id=ANY(%s)
                      AND skill_id=ANY(%s) AND status='active'
                    ORDER BY skill_id,binding_id LIMIT 129''',
                    (*scope.key,assignees,sorted(expected_skills))).fetchall()
                by_skill = {}
                for row in bindings:
                    if row['skill_id'] not in expected_skills or row['skill_id'] in by_skill:
                        raise ValueError('compilation skill binding selection is ambiguous')
                    by_skill[row['skill_id']] = row['binding_id']
                if set(by_skill) != set(expected_skills):
                    raise ValueError('compilation skill binding selection is incomplete')
                return dict(stageRef=stage.model_dump(mode='json',by_alias=True),bindings=by_skill)

            before = select()
            def consume(dependencies):
                skills = dependencies['skills']
                if (len(skills) != len(expected_skills) or {item['skillId'] for item in skills} != set(expected_skills)
                        or any((item.get('logicRevisionRef') or {}).get('assetId') != expected_skills[item['skillId']]
                               for item in skills)):
                    raise ValueError('published skill Logic lineage differs from installed blueprint')
                result = execute(dict(deepcopy(dependencies),compilationBlueprint=deepcopy(blueprint)))
                _reject_deferred(result)
                if canonical_sha256(select()) != canonical_sha256(before):
                    raise ValueError('compilation dependency selection changed during callback')
                return result

            return AnalysisSkillSetReader(self._roles).run_current(conn,scope=scope,selection_ref=selection_ref,
                actor=actor,domain_profile=domain_profile,compiler_profile=blueprint['compilerProfile'],
                stage_ref=ExactRevisionRef.model_validate(before['stageRef']),
                binding_ids=sorted(before['bindings'].values()),execute=consume)

        return self._roles.run_current(conn,scope=scope,selection_ref=selection_ref,actor=actor,
            domain_profile=domain_profile,compiler_profile=blueprint['compilerProfile'],execute=current)
