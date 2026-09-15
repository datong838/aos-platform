"""Freeze real publication contracts; no business-quality or runtime claims."""
import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from a0v_formal_text_model_renewal import database_connect
from a0v_firstchain_contract_materialize import require_target
from a0v_formal_text_model import SCOPE
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_production_contracts import CreateEvalContractRequest, ExactRevisionRef
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash

ACTOR = 'a0v-firstchain-eval-contracts'


def require_lineage(skill, gate, event, now):
    parent = skill.parent_ref
    if (skill.lifecycle.value != 'published' or parent is None
            or skill.publication_tenant is None
            or (skill.publication_tenant.org_id, skill.publication_tenant.project_id) != SCOPE.key
            or gate.status.value != 'passed' or not gate.decided_at <= now < gate.expires_at
            or gate.target.asset_type != AssetType.SKILL_TEMPLATE
            or gate.decision_hash != skill.release_gate_ref.content_hash
            or (gate.target.asset_id, int(gate.target.revision), gate.target.content_hash)
               != (parent.asset_id, parent.revision, parent.content_hash)
            or event['event_id'] != skill.publication_ref.resource_id
            or event['publication_id'] != skill.publication_ref.revision
            or event['release_gate_decision_id'] != gate.decision_id
            or AssetRevisionRef.model_validate(event['target_ref']) != gate.target
            or event['event_type'] != 'published'):
        raise ValueError('FIRSTCHAIN_EVAL_PUBLICATION_LINEAGE_INVALID')


def run(database, apply=False, logic_ids=('D01','D02','D03')):
    connect = database_connect(database)
    return materialize(connect, database=database, validate_target=lambda c: require_target(c, database),
        apply=apply, logic_ids=logic_ids)


def materialize(connect, *, database, validate_target, apply=False, logic_ids=('D01','D02','D03'), skill_revision=2):
    if tuple(logic_ids) not in {('D01','D02','D03'),('S01','P01','C06','A02','G06')}:
        raise ValueError('EXACT_CONTRACT_SKILL_SET_REQUIRED')
    if skill_revision not in (2, 3):
        raise ValueError('EXACT_CONTRACT_SKILL_REVISION_REQUIRED')
    validate_target(connect)
    store = AipProductionContractStore(connect)
    skills = AipSkillRegistry(connect)
    results = []
    for logic_id in logic_ids:
        validate_target(connect)
        skill = skills.get_skill('ecommerce.skill.'+logic_id, skill_revision)
        with connect(SCOPE) as conn:
            row = conn.execute('SELECT * FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*SCOPE.key, skill.release_gate_ref.asset_id)).fetchone()
            event = conn.execute('SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND publication_id=%s ORDER BY occurred_at DESC,event_id DESC LIMIT 1',
                (*SCOPE.key, skill.publication_ref.revision)).fetchone()
            if row is None or event is None:
                raise ValueError('FIRSTCHAIN_EVAL_AUTHORITY_MISSING')
            gate = AipReleasePublicationService._gate_from_row(SCOPE, row)
            require_lineage(skill, gate, event, datetime.now(UTC))
            AipReleasePublicationService._verify_gate_evidence(conn, SCOPE, gate)
            event_hash = canonical_hash(store._publication_snapshot(event))
            from aos_api.aip_eval_runner import AipEvalRunner
            report = AipEvalRunner(connect).get_report(SCOPE, gate.eval_report.artifact_id, int(gate.eval_report.revision))
        body = CreateEvalContractRequest(
            suite_ref=ExactRevisionRef(resource_type='EvalSuiteRevision', resource_id=gate.suite_ref.asset_id,
                revision=int(gate.suite_ref.revision), content_hash=gate.suite_ref.content_hash),
            publication_ref=ExactRevisionRef(resource_type='PublicationEvent', resource_id=event['event_id'],
                revision=1, content_hash=event_hash),
            release_gate_ref=ExactRevisionRef(resource_type='ReleaseGateDecision', resource_id=gate.decision_id,
                revision=1, content_hash=gate.decision_hash),
            artifact_schema_ref=ResourceRef(resource_type='Schema', resource_id='SkillPublicationContract.'+logic_id,
                revision='1', authority='aip-contract'),
            severity_thresholds={'critical': 1.0, 'required': 1.0},
            gate_policy={'requiredPassRate': 1.0, 'requiredCases': report.total, 'evidenceKind': 'isolated_skill_contract'},
            return_mapping={'pass': 'publish', 'fail': 'block'}, override_policy={'allowed': False})
        if not apply:
            results.append({'skillId': skill.skill_id, 'status': 'ready_to_freeze'})
            continue
        key = 'a0v-eval-contract-'+skill.content_hash[:32]
        contract = store.create_eval_contract(SCOPE, ACTOR, key, body)
        contract = store.get_eval_contract(SCOPE, contract.contract_id)
        if contract.lifecycle.value == 'draft':
            contract = store.freeze_eval_contract(SCOPE, ACTOR, contract.contract_id, contract.version, key+'-freeze')
        if contract.lifecycle.value != 'frozen':
            raise ValueError('FIRSTCHAIN_EVAL_CONTRACT_NOT_FROZEN')
        results.append({'skillId': skill.skill_id, 'contractId': contract.contract_id,
            'revision': contract.revision, 'contentHash': contract.content_hash, 'lifecycle': contract.lifecycle.value})
    return {'database': database, 'contracts': results, 'providerCalls': 0, 'businessRuns': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--database-name', required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.database_name, args.apply)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(result, ensure_ascii=False))
