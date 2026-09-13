"""Current AIP review eligibility for an internal event-policy save."""
from aos_api.aip_action_policy import ACTION_APPROVAL_ROLES, classify_action_risk
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.openfga import openfga_api_url, user_key, marking_key
from aos_api.tenant_scope import TenantScope

_HASH_FIELDS=('approval_event_id','proposal_id','proposal_version','proposal_hash','decision',
    'actor_id','reason','expires_at','created_at','action_binding_hash')


def require_current_event_approval(*,transaction,scope,case_id,policy_id,approval_ref,executor):
    """No role grants; all current checks stay in the owning Host transaction."""
    return _require_current_event_approval(transaction=transaction,scope=scope,case_id=case_id,
        policy_id=policy_id,approval_ref=approval_ref,executor=executor,
        action_type='ecommerce_growth_schedule_put',expected_payload=None)


def _require_current_event_approval(*,transaction,scope,case_id,policy_id,approval_ref,executor,
                                    action_type,expected_payload):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('current Host transaction and scope required')
    if openfga_api_url():
        raise PermissionError('current remote review authority adapter required')
    transaction.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',
        (case_id,policy_id,approval_ref.resource_id))
    proposal=transaction.execute('''SELECT p.* FROM aip_action_proposal p
        JOIN aip_action_approval_event a ON a.org_id=p.org_id AND a.project_id=p.project_id AND a.proposal_id=p.proposal_id
        WHERE p.org_id=%s AND p.project_id=%s AND a.approval_event_id=%s''',
        (*scope.key,approval_ref.resource_id)).fetchone()
    now=transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (proposal is None or proposal['status']!='approved' or proposal['expires_at']<=now
            or proposal['action_type_id']!=action_type
            or proposal['payload'].get('caseId')!=case_id or proposal['payload'].get('schedulePolicyId')!=policy_id
            or not proposal['action_binding_hash']):
        raise ValueError('current executable event proposal required')
    if expected_payload is not None and canonical_hash(proposal['payload'])!=canonical_hash(expected_payload):
        raise ValueError('current event control intent differs')
    row=transaction.execute('''SELECT id,name,object_type,parameters,required_markings,submission_criteria
        FROM meta_action_type WHERE id=%s FOR SHARE''',(proposal['action_type_id'],)).fetchone()
    if row is None or action_snapshot_from_row(row)!=proposal['action_type_snapshot']:
        raise ValueError('current event action snapshot differs')
    risk=classify_action_risk(proposal['action_type_id'],proposal['action_type_snapshot'],
        proposal['payload'],ActionRiskLevel(proposal['risk_level']))
    expected=dict(floor=risk.floor.value,reasons=list(risk.reasons),**risk.approval_policy)
    if (risk.level.value!=proposal['risk_level'] or proposal['policy_snapshot']!=expected
            or proposal['approval_policy_hash']!=canonical_hash(expected)
            or expected['executionAllowed'] is not True or expected['draftOnly'] is not False
            or expected['makerChecker'] is not True):
        raise ValueError('current event approval policy differs')
    events=transaction.execute('''SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
        actor_id,reason,expires_at,created_at,action_binding_hash,approval_policy_hash
        FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s
        AND decision='approved' ORDER BY approval_event_id''',(*scope.key,proposal['proposal_id'])).fetchall()
    locked_ids=[event['approval_event_id'] for event in events]
    for event in events:
        transaction.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',
            (case_id,policy_id,event['approval_event_id']))
    events=transaction.execute("""SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
        actor_id,reason,expires_at,created_at,action_binding_hash,approval_policy_hash
        FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s
        AND decision='approved' ORDER BY approval_event_id""",(*scope.key,proposal['proposal_id'])).fetchall()
    if [event['approval_event_id'] for event in events]!=locked_ids:
        raise ValueError('approval set changed during locking')
    valid=[event for event in events if event['expires_at'] is not None and event['created_at']<=now<event['expires_at']]
    actors=[event['actor_id'] for event in valid]
    chosen=[event for event in valid if event['approval_event_id']==approval_ref.resource_id]
    if (len(actors)<expected['minimumApprovals'] or len(actors)!=len(set(actors))
            or proposal['created_by'] in actors or executor in actors or len(chosen)!=1
            or canonical_hash({key:chosen[0][key] for key in _HASH_FIELDS},prefixed=True)!=approval_ref.content_hash
            or chosen[0]['proposal_version']!=approval_ref.revision):
        raise ValueError('current independent approval quorum required')
    if any(event['proposal_hash']!=proposal['proposal_hash'] or event['proposal_version']!=proposal['version']
           or event['action_binding_hash']!=proposal['action_binding_hash']
           or event['approval_policy_hash']!=proposal['approval_policy_hash'] for event in valid):
        raise ValueError('current approval set binding differs')
    markings=proposal['action_type_snapshot']['requiredMarkings']
    if type(markings) is not list or any(type(label) is not str or not label.strip() for label in markings):
        raise ValueError('current action markings invalid')
    for actor in sorted(set([proposal['created_by'],executor,*actors])):
        if type(actor) is not str or not actor or actor!=actor.strip() or not actor.isprintable():
            raise PermissionError('current review identity invalid')
        members=transaction.execute('''SELECT role FROM meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''',(*scope.key,actor)).fetchall()
        if len(members)!=1 or (actor in actors and members[0]['role'].lower() not in ACTION_APPROVAL_ROLES):
            raise PermissionError('current review membership denied')
        for label in sorted(set(markings)):
            grants=transaction.execute('''SELECT object_key FROM authz_tuple WHERE org_id=%s AND project_id=%s
                AND user_key=%s AND relation='bearer' AND object_key=%s FOR SHARE''',
                (*scope.key,user_key(actor),marking_key(label))).fetchall()
            if len(grants)!=1:raise PermissionError('current action marking denied')
    ended=transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if proposal['expires_at']<=ended or any(event['expires_at']<=ended for event in valid):
        raise ValueError('approval elapsed during current eligibility checks')
