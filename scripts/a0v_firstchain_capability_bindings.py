"""Derive first-chain binding inputs from live exact authorities, without writes."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
from a0v_formal_text_model import SCOPE
from a0v_firstchain_contract_materialize import require_target
from a0v_firstchain_internal_license import AUTHORITY, require_internal_skills
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_agent_registry_contracts import (
    CapabilityBindingRequest, CreateCapabilityBindingRequest, OperationalBindingDependencies,
)
from aos_api.aip_model_runtime_contracts import VersionedAssetRef
from aos_api.aip_binding_readiness_service import AipBindingReadinessService, PostgresBindingDependencyAuthority
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_skill_registry import AipSkillRegistry


def exact(kind, asset_id, revision, content_hash):
    return VersionedAssetRef(asset_type=kind, asset_id=asset_id, revision=revision, content_hash=content_hash)


def require_license(row, skills):
    expected = {(s.skill_id, str(s.revision)) for s in skills}
    subjects = row['subject_refs']
    summary = row['license_summary']
    if (row['lifecycle'] != 'frozen' or row['coverage'] != 'complete'
            or not isinstance(summary, dict) or summary.get('authorizationRef') != AUTHORITY
            or summary.get('sourceLicense') != 'internal'
            or summary.get('commercialLicenseAsserted') is not False
            or summary.get('externalPublicationAuthorized') is not False
            or not isinstance(subjects, list) or len(subjects) != len(expected)
            or any(s.get('resourceType') != 'SkillTemplate' for s in subjects)
            or {(s.get('resourceId'), s.get('revision')) for s in subjects} != expected):
        raise ValueError('FIRSTCHAIN_LICENSE_SCOPE_INVALID')


def require_contract(row, skill):
    gate = row['release_gate_ref']
    schema = row['artifact_schema_ref']
    if (row['lifecycle'] != 'frozen'
            or gate.get('resourceType') != 'ReleaseGateDecision'
            or gate.get('resourceId') != skill.release_gate_ref.asset_id
            or gate.get('contentHash') != skill.release_gate_ref.content_hash
            or schema.get('resourceId') != 'SkillPublicationContract.'+skill.skill_id.rsplit('.',1)[1]
            or row['gate_policy'].get('evidenceKind') != 'isolated_skill_contract'):
        raise ValueError('FIRSTCHAIN_EVAL_CONTRACT_LINEAGE_INVALID')


def binding_namespace(skill_revision):
    if skill_revision not in (2, 3):
        raise ValueError('EXACT_BINDING_SKILL_REVISION_REQUIRED')
    return 'a0v-firstchain-' if skill_revision == 2 else 'a0v-model-successor-r3-'


def prepare(database, logic_ids=('D01','D02','D03')):
    connect = database_connect(database)
    return prepare_material(connect, validate_target=lambda c: require_target(c, database), logic_ids=logic_ids)


def prepare_material(connect, *, validate_target, logic_ids=('D01','D02','D03'), skill_revision=2):
    prefix = binding_namespace(skill_revision)
    validate_target(connect)
    registry = AipSkillRegistry(connect)
    skills = [registry.get_skill('ecommerce.skill.'+logic, skill_revision) for logic in logic_ids]
    require_internal_skills(skills,logic_ids,skill_revision=skill_revision)
    models = AipModelRuntimeStore(connect)
    route = models.get_route(SCOPE, 'a0v-ecommerce-text-readonly-v1')
    if len(route.candidates) != 1:
        raise ValueError('FIRSTCHAIN_EXACT_TEXT_ROUTE_REQUIRED')
    model_ref = route.candidates[0].model
    model = models.get_model(SCOPE, model_ref.asset_id, model_ref.revision)
    if model.content_hash != model_ref.content_hash:
        raise ValueError('FIRSTCHAIN_MODEL_HASH_DRIFT')
    provider = models.get_provider(SCOPE, model.provider.asset_id, model.provider.revision)
    policy = models.get_policy(SCOPE, route.runtime_policy_ref.asset_id, route.runtime_policy_ref.revision)
    if provider.content_hash != model.provider.content_hash or policy.content_hash != route.runtime_policy_ref.content_hash:
        raise ValueError('FIRSTCHAIN_PROVIDER_POLICY_HASH_DRIFT')
    readiness = AipBindingReadinessService(authority=PostgresBindingDependencyAuthority(connect), model_store=models)
    with connect(SCOPE) as conn:
        bundles = conn.execute("SELECT * FROM aip_evidence_bundle_revision WHERE org_id=%s AND project_id=%s AND lifecycle='frozen' AND license_summary->>'authorizationRef'=%s", (*SCOPE.key,AUTHORITY)).fetchall()
        valid_bundles = []
        expected_subjects={(skill.skill_id,str(skill.revision)) for skill in skills}
        for row in bundles:
            if {(ref.get('resourceId'),ref.get('revision')) for ref in row['subject_refs']} != expected_subjects:
                continue
            require_license(row, skills)
            valid_bundles.append(row)
        if len(valid_bundles) != 1:
            raise ValueError('FIRSTCHAIN_UNIQUE_LICENSE_REQUIRED')
        license_row = valid_bundles[0]
        contracts = conn.execute("SELECT * FROM aip_eval_contract_revision WHERE org_id=%s AND project_id=%s AND lifecycle='frozen'", SCOPE.key).fetchall()
        prepared = []
        for skill in skills:
            matches = [row for row in contracts if row['release_gate_ref'].get('resourceId') == skill.release_gate_ref.asset_id]
            if len(matches) != 1:
                raise ValueError('FIRSTCHAIN_UNIQUE_EVAL_CONTRACT_REQUIRED')
            contract = matches[0]
            require_contract(contract, skill)
            deps = OperationalBindingDependencies(provider_ref=model.provider,
                model_route_ref=exact('ModelRouteRevision',route.route_id,route.revision,route.content_hash),
                runtime_policy_ref=route.runtime_policy_ref, eval_gate_ref=route.eval_gate_ref,
                eval_contract_ref=exact('EvalContractRevision',contract['contract_id'],contract['revision'],contract['content_hash']),
                license_evidence_refs=[ResourceRef(resource_type='EvidenceBundleRevision',resource_id=license_row['bundle_id'],revision=str(license_row['revision']),authority='aip-production')],
                budget_policy_ref=policy.budget_policy_ref)
            for capability_id in skill.required_capabilities:
                rows = conn.execute("SELECT capability_id,revision,content_hash,lifecycle FROM aip_capability_revision WHERE capability_id=%s ORDER BY revision DESC LIMIT 1",(capability_id,)).fetchall()
                if len(rows)!=1 or rows[0]['lifecycle']!='published':
                    raise ValueError('FIRSTCHAIN_PUBLISHED_CAPABILITY_REQUIRED')
                cap=rows[0]
                ref=exact('CapabilityRevision',cap['capability_id'],cap['revision'],cap['content_hash'])
                request=CreateCapabilityBindingRequest(binding_id=prefix+skill.skill_id.rsplit('.',1)[1].lower()+'-'+capability_id,
                    binding=CapabilityBindingRequest(capability=ref,secret_ref=provider.secret_ref,
                        network_policy_revision=policy.network_policy_ref.asset_id+'@'+str(policy.network_policy_ref.revision),
                        quota_policy_revision=policy.quota_policy_ref.asset_id+'@'+str(policy.quota_policy_ref.revision),
                        timeout_ms=policy.deadline_ms,max_concurrency=1))
                result=readiness.evaluate_capability(SCOPE,ref,deps,evaluated_at=datetime.now(UTC))
                prepared.append((skill.skill_id,request,deps,result))
    return connect, readiness, prepared


def run(database):
    _,_,items=prepare(database)
    return {'database':database,'writes':0,'providerCalls':0,'bindings':[
        {'skillId':skill,'bindingId':request.binding_id,'capability':request.binding.capability.model_dump(mode='json',by_alias=True),
         'readiness':result.readiness.value,'reasons':result.reasons,'dependencies':deps.model_dump(mode='json',by_alias=True)}
        for skill,request,deps,result in items]}


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database-name',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.database_name)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
