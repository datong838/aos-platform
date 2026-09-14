"""Current bootstrap reviewer eligibility; never grants execution or memberships."""
from aos_api.aip_action_policy import ACTION_APPROVAL_ROLES
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.openfga import openfga_api_url, user_key, marking_key
from aos_api.tenant_scope import TenantScope


def require_current_bootstrap_review_identity(*, transaction, scope, actor, maker, action_snapshot, checker):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope or type(checker) is not bool:
        raise TypeError('exact bootstrap transaction, tenant and review operation required')
    if openfga_api_url():
        raise PermissionError('current remote bootstrap review adapter required')
    for identity in (actor, maker):
        if type(identity) is not str or not identity or identity != identity.strip() or not identity.isprintable():
            raise PermissionError('current bootstrap identity invalid')
    if (checker and actor == maker) or (not checker and actor != maker):
        raise PermissionError('bootstrap maker and reviewer must remain distinct')
    current = transaction.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                                  "current_setting('aos.project_id',true) AS project_id").fetchone()
    if current is None or (current['org_id'], current['project_id']) != scope.key:
        raise PermissionError('current bootstrap transaction tenant differs')
    if not isinstance(action_snapshot, dict) or action_snapshot.get('id') != 'ecommerce_analysis_bootstrap':
        raise ValueError('exact bootstrap action required')
    row = transaction.execute('''SELECT id,name,object_type,parameters,required_markings,submission_criteria
        FROM meta_action_type WHERE id=%s FOR SHARE''', (action_snapshot['id'],)).fetchone()
    if row is None or action_snapshot_from_row(row) != action_snapshot:
        raise ValueError('current bootstrap action snapshot differs')
    markings = action_snapshot['requiredMarkings']
    if type(markings) is not list or any(type(label) is not str or not label or label != label.strip() for label in markings):
        raise ValueError('current bootstrap action markings invalid')
    roles = {}
    for identity in sorted({actor, maker}):
        rows = transaction.execute('''SELECT role FROM meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''', (*scope.key, identity)).fetchall()
        if len(rows) != 1 or not isinstance(rows[0]['role'], str):
            raise PermissionError('current bootstrap membership unavailable')
        roles[identity] = rows[0]['role']
        if checker and identity == actor and roles[identity].lower() not in ACTION_APPROVAL_ROLES:
            raise PermissionError('current bootstrap reviewer role denied')
        for label in sorted(set(markings)):
            grants = transaction.execute('''SELECT object_key FROM authz_tuple
                WHERE org_id=%s AND project_id=%s AND user_key=%s
                AND relation='bearer' AND object_key=%s FOR SHARE''',
                (*scope.key, user_key(identity), marking_key(label))).fetchall()
            if len(grants) != 1:
                raise PermissionError('current bootstrap action marking denied')
    return (roles[actor],)
