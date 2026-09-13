"""Revalidate current internal reviewers when consuming a cutover approval."""
from psycopg import sql
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, APPROVE_INSTALLATION_OPERATION
from aos_api.asset_registry.errors import AssetRegistryError
from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverBlocked
from aos_api.ecommerce_growth_cutover_action_binding import internal_cutover_binding_hash
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict


def require_current_cutover_approval(*, conn, scope, proposal, approval_id, checked_at, schema):
    from aos_api.ecommerce_growth_cutover_proposal_gate import require_internal_cutover_binding
    policy = proposal['policy_snapshot']
    minimum = policy.get('minimumApprovals')
    if (proposal['risk_level'] not in {'R2','R3'} or policy.get('floor') != 'R2'
            or policy.get('makerChecker') is not True or policy.get('executionAllowed') is not True
            or policy.get('draftOnly') is not False or type(minimum) is not int
            or minimum < (2 if proposal['risk_level'] == 'R3' else 1)
            or canonical_hash(policy) != proposal['approval_policy_hash']
            or proposal['task_id'] is not None or proposal['run_id'] is not None
            or proposal['impact_preview_id'] is not None):
        raise EcommerceGrowthCutoverBlocked('current executable internal review policy required')
    try:
        binding = internal_cutover_binding_hash(scope=scope,
            action_snapshot=proposal['action_type_snapshot'], payload=proposal['payload'])
        if binding != proposal['action_binding_hash']:
            raise ValueError('internal binding differs')
        events = conn.execute(sql.SQL('''SELECT approval_event_id,actor_id,expires_at,
                proposal_hash,action_binding_hash FROM {}.aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved'
            ORDER BY created_at,approval_event_id''').format(sql.Identifier(schema)),
            (*scope.key, proposal['proposal_id'])).fetchall()
        actors = set()
        for event in events:
            if (event['actor_id'] == proposal['created_by'] or event['actor_id'] in actors
                    or event['expires_at'] is None or event['expires_at'] <= checked_at
                    or event['proposal_hash'] != proposal['proposal_hash']
                    or event['action_binding_hash'] != binding):
                raise ValueError('current independent approval differs')
            actors.add(event['actor_id'])
        if len(actors) < minimum or approval_id not in {event['approval_event_id'] for event in events}:
            raise ValueError('current independent approval count insufficient')
        conn.execute('SET LOCAL ROLE aos_runtime')
        for actor, operation in [(proposal['created_by'], APPLY_INSTALLATION_OPERATION),
                                 *((event['actor_id'], APPROVE_INSTALLATION_OPERATION) for event in events)]:
            current_binding, _ = require_internal_cutover_binding(conn=conn, scope=scope,
                actor=actor, action_snapshot=proposal['action_type_snapshot'], payload=proposal['payload'],
                operation=operation)
            if current_binding != binding:
                raise ValueError('current internal binding differs')
        conn.execute('SET LOCAL ROLE aos_extension_maintainer')
    except (ValueError, TypeError, AssetRegistryError, RuntimeConflict) as exc:
        # The owning cutover transaction rolls back, including any local role change.
        raise EcommerceGrowthCutoverBlocked('current internal approval authority unavailable') from exc
