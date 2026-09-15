"""Current review eligibility and Case/Policy provenance in the AIP transaction."""
from aos_api.aip_action_policy import ACTION_APPROVAL_ROLES
from aos_api.asset_registry.control_policy import require_target_markings
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_event_action_binding import internal_event_binding_hash
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.openfga import openfga_api_url,user_key,marking_key


def require_internal_event_binding(*,conn,scope,actor,action_snapshot,payload,checker):
    _require_transaction(conn)
    if type(actor) is not str or not actor or actor!=actor.strip() or not actor.isprintable():
        raise PermissionError('current event reviewer identity required')
    if openfga_api_url():raise PermissionError('current remote event review adapter required')
    binding=internal_event_binding_hash(scope=scope,action_snapshot=action_snapshot,payload=payload)
    row=conn.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria FROM meta_action_type WHERE id=%s FOR SHARE',(action_snapshot['id'],)).fetchone()
    if row is None or action_snapshot_from_row(row)!=action_snapshot:raise ValueError('current event action differs')
    members=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE',(*scope.key,actor)).fetchall()
    allowed=ACTION_APPROVAL_ROLES if checker else frozenset(('owner','admin'))
    if len(members)!=1 or members[0]['role'].lower() not in allowed:raise PermissionError('current event membership denied')
    labels=action_snapshot['requiredMarkings'];granted=[]
    if any(type(label) is not str or not label.strip() for label in labels):raise ValueError('event action markings invalid')
    for label in sorted(set(labels)):
        rows=conn.execute("SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s AND user_key=%s AND relation='bearer' AND object_key=%s FOR SHARE",(*scope.key,user_key(actor),marking_key(label))).fetchall()
        if len(rows)==1:granted.append(label)
    require_target_markings(principal_markings=granted,target_markings=labels)
    conn.execute('SELECT ecommerce_product_event_proposal_lock_a0v_057(%s,%s)',(payload['caseId'],payload['schedulePolicyId']))
    row=conn.execute('''SELECT r.authority_data FROM ecommerce_investigation_case_head h
        JOIN ecommerce_investigation_case_revision r USING(org_id,project_id,case_id)
        WHERE h.org_id=%s AND h.project_id=%s AND h.case_id=%s AND r.revision=h.current_revision''',(*scope.key,payload['caseId'])).fetchone()
    if row is None:raise ValueError('current event Case missing')
    case=BusinessInvestigationCaseRevision.model_validate(row['authority_data'])
    if case.content_hash!=case.calculated_content_hash() or case.case_id!=payload['caseId'] or case.tenant.org_id!=scope.org_id or case.tenant.project_id!=scope.project_id:
        raise ValueError('current event Case integrity differs')
    action=action_snapshot['id']
    recovery=(action=='ecommerce_growth_event_control' and payload['controlIntent']['intent']=='disable'
        or action=='ecommerce_growth_event_dispatch' and payload['dispatchIntent']['phase']!='expand')
    if not recovery and case.lifecycle.value!='ACTIVE':raise ValueError('active event Case required')
    if action=='ecommerce_growth_schedule_put' and case.version!=payload['expectedCaseVersion']:
        raise ValueError('current event Case version differs')
    policy=conn.execute('SELECT current_revision,content_hash,case_id FROM ecommerce_investigation_schedule_policy_head WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s',(*scope.key,payload['schedulePolicyId'])).fetchone()
    if action=='ecommerce_growth_schedule_put':
        if (0 if policy is None else policy['current_revision'])!=payload['expectedPolicyRevision']:
            raise ValueError('current event Policy version differs')
    elif policy is None or policy['case_id']!=case.case_id:raise ValueError('current event Policy Case differs')
    if action=='ecommerce_growth_event_control':
        ref=payload['controlIntent']['policyRef']
        if ref['revision']!=policy['current_revision'] or ref['contentHash']!=policy['content_hash']:
            raise ValueError('current event Policy ref differs')
    return binding,(members[0]['role'],)
