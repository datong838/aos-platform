"""Verify existing Skill gate evidence with the original reader, readonly."""
import importlib.util
import json
from collections import Counter

spec = importlib.util.spec_from_file_location('qyh_detail', __file__.replace('read_skill_proof.py','audit.py'))
detail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(detail)
from aos_api.aip_release_publication_service import AipReleasePublicationService, AipReleasePublicationError


def observe():
    registry = detail.AipSkillRegistry(detail.connection)
    source = json.loads((detail.OUT/'current.json').read_text())
    records = []
    for item in source['rows']:
        binding = registry.get_binding(detail.SCOPE, item['bindingId'])
        with detail.connection(detail.SCOPE) as conn:
            row = conn.execute('SELECT * FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s',
                (*detail.SCOPE.key, binding.dependencies.eval_gate_ref.asset_id)).fetchone()
            assert row is not None
            gate = AipReleasePublicationService._gate_from_row(detail.SCOPE, row)
            try:
                AipReleasePublicationService._verify_gate_evidence(conn, detail.SCOPE, gate)
            except AipReleasePublicationError as error:
                outcome = {'errorType': type(error).__name__, 'reason': str(error)}
            else:
                outcome = {'verified': True}
        records.append({'slotId': item['slotId'], 'bindingId': item['bindingId'], 'originalEvidenceOutcome': outcome})
    return records


if __name__ == '__main__':
    output = detail.OUT/'skill-proof.json'
    assert not output.exists(), 'Existing result cannot be overwritten'
    first, second = observe(), observe()
    assert first == second
    result = {'twoIndependentViewsEqual': True, 'databaseWrites':0, 'rows':first,
        'reasons':dict(Counter(str(r['originalEvidenceOutcome']) for r in first))}
    with output.open('x') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({'bindings':len(first),'outcomes':result['reasons']}))
