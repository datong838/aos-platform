"""Exact dependency predicates; no evaluation/health writes or model calls."""
import importlib.util
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qyh_readonly', ROOT / '.evidence/qyh-source-mainline-gates-20261012/audit.py')
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, ModelRuntimeStoreError, evaluation_candidate_ref
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore, AipEvalGateDependencyBlocked

OUT = Path(__file__).parent
SCOPE = previous.SCOPE
connection = previous.connection


def gate_view(conn, ref):
    if ref is None:
        return {'present': False, 'referencePresent': False}
    row = conn.execute("""SELECT status,decision_hash,invalidated_by,
      decided_at<=clock_timestamp() AS started,
      expires_at<=clock_timestamp() AS expired
      FROM aip_release_gate_decision WHERE org_id=%s AND project_id=%s AND decision_id=%s""",
      (*SCOPE.key, ref.asset_id)).fetchone()
    if row is None:
        return {'present': False, 'referencePresent': True}
    return {'present': True, 'status': row['status'],
            'hashMatches': row['decision_hash'] == ref.content_hash,
            'started': row['started'], 'expired': row['expired'],
            'invalidated': row['invalidated_by'] is not None}


def observe():
    contracts = AipProductionContractStore(connection)
    context = contracts.get_production_context(SCOPE, 'ctx-daeec3f5a06049a08783')
    plan = contracts.get_responsibility_plan(SCOPE, context.responsibility_plan_ref.resource_id, context.responsibility_plan_ref.revision)
    registry, models, evals = AipSkillRegistry(connection), AipModelRuntimeStore(connection), AipEvalAuthorityStore(connection)
    records = []
    for slot in plan.slots:
        for binding in registry.list_bindings(SCOPE, instance_id=slot.assignee.resource_id):
            refs = binding.dependencies
            item = {'slotId': slot.slot_id, 'bindingId': binding.binding_id, 'bindingStatus': binding.status}
            with connection(SCOPE) as conn:
                item['skillGate'] = gate_view(conn, refs.eval_gate_ref)
                capabilities = conn.execute("""SELECT binding_id,status,operational_readiness,
                    dependency_snapshot_hash IS NOT NULL AS snapshot_present,
                    readiness_expires_at<=clock_timestamp() AS expired,
                    readiness_expires_at IS NOT NULL AS expiry_present
                    FROM aip_capability_binding WHERE org_id=%s AND project_id=%s
                    AND binding_id=ANY(%s) ORDER BY binding_id""",
                    (*SCOPE.key, binding.capability_binding_ids)).fetchall()
                item['capabilities'] = capabilities
            if refs.model_route_ref is None or refs.runtime_policy_ref is None:
                item['routePolicy'] = {'referencesPresent': False}
            else:
                try:
                    route = models.get_route(SCOPE, refs.model_route_ref.asset_id, refs.model_route_ref.revision)
                    policy = models.get_policy(SCOPE, refs.runtime_policy_ref.asset_id, refs.runtime_policy_ref.revision)
                except ModelRuntimeStoreError as error:
                    item['routePolicy'] = {'errorType': type(error).__name__}
                else:
                    item['routePolicy'] = {'referencesPresent': True,
                        'routeHashMatches': route.content_hash == refs.model_route_ref.content_hash,
                        'routeLifecycle': route.lifecycle.value,
                        'routePolicyMatches': route.runtime_policy_ref == refs.runtime_policy_ref,
                        'policyHashMatches': policy.content_hash == refs.runtime_policy_ref.content_hash,
                        'policyLifecycle': policy.lifecycle.value, 'killSwitch': policy.kill_switch_enabled}
                    with connection(SCOPE) as conn:
                        item['routeGate'] = gate_view(conn, route.eval_gate_ref)
                    try:
                        evals.require_exact_passed(SCOPE, route.eval_gate_ref,
                            expected_target=evaluation_candidate_ref(route), now=datetime.now(timezone.utc))
                    except AipEvalGateDependencyBlocked as error:
                        item['originalRouteGateRejection'] = str(error)
                    else:
                        item['originalRouteGateRejection'] = None
            records.append(item)
    return records


if __name__ == '__main__':
    assert not (OUT / 'current.json').exists(), 'Reconcile an existing result; do not overwrite'
    first, second = observe(), observe()
    assert first == second
    result = {'twoIndependentViewsEqual': True, 'originalReadOnlyFactories': True,
        'databaseWrites': 0, 'modelCalls': 0, 'rows': first,
        'summary': {'bindings': len(first),
            'skillGateExpired': sum(r['skillGate'].get('expired') is True for r in first),
            'skillGateStatus': dict(Counter(r['skillGate'].get('status','missing') for r in first)),
            'routeGateExpired': sum(r.get('routeGate',{}).get('expired') is True for r in first),
            'routeGateStatus': dict(Counter(r.get('routeGate',{}).get('status','missing') for r in first)),
            'routeRejections': dict(Counter(str(r.get('originalRouteGateRejection')) for r in first)),
            'expiredCapabilityOccurrences': sum(c['expired'] is True for r in first for c in r['capabilities'])},
        'realWorkbenchRestoreOrApprovalAccepted': False}
    with (OUT / 'current.json').open('x') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result['summary']))
