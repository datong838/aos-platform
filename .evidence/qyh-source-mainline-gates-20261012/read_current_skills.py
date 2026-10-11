"""Original readiness inspection only; never save a refreshed snapshot."""
import json
from datetime import datetime, timezone

from audit import OUT, SCOPE, connection
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_skill_registry import AipSkillRegistry


def observe():
    contracts = AipProductionContractStore(connection)
    context = contracts.get_production_context(SCOPE, 'ctx-daeec3f5a06049a08783')
    plan = contracts.get_responsibility_plan(SCOPE, context.responsibility_plan_ref.resource_id, context.responsibility_plan_ref.revision)
    registry = AipSkillRegistry(connection)
    rows = []
    for slot in plan.slots:
        bindings = registry.list_bindings(SCOPE, instance_id=slot.assignee.resource_id)
        for binding in bindings:
            current = registry.inspect_binding_readiness(SCOPE, binding, evaluated_at=datetime.now(timezone.utc))
            rows.append({'slotId': slot.slot_id, 'bindingId': binding.binding_id,
                         'bindingStatus': binding.status,
                         'currentReadiness': current.readiness.value,
                         'currentReasons': current.reasons})
    return rows


if __name__ == '__main__':
    path = OUT / 'skill-current-readiness.json'
    assert not path.exists(), 'Existing observation must not be overwritten'
    before, after = observe(), observe()
    assert before == after
    result = {'originalInspectorUsed': True, 'readOnlyConnectionsOnly': True,
              'evaluationsPersisted': 0, 'twoIndependentViewsEqual': True,
              'bindings': before, 'distinctReasons': sorted({r for item in before for r in item['currentReasons']})}
    with path.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'bindingCount': len(before), 'currentReasons': result['distinctReasons'], 'writes': 0}))
