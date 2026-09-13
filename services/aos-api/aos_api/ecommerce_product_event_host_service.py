"""Event policy save under current source, Case, method and exact approval."""
from copy import deepcopy

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, _validate_schedule_approval_rows
from aos_api.ecommerce_product_event_guard import ProductEventPolicyGuard
from aos_api.ecommerce_product_event_qualified_owner import ProductEventQualifiedOwner
from aos_api.ecommerce_product_event_approval import require_current_event_approval
from aos_api.tenant_scope import TenantScope
from aos_api.ecommerce_product_event_store import ProductEventPolicyStore


def _parse(command, scope):
    keys = {'idempotencyKey', 'expectedPolicyRevision', 'expectedCaseVersion',
            'policy', 'caseAuthority', 'approvalRef'}
    if type(command) is not dict or set(command) != keys:
        raise ValueError('event save command envelope invalid')
    value = deepcopy(command)
    key = value['idempotencyKey']
    if type(key) is not str or not 1 <= len(key) <= 200 or key != key.strip():
        raise ValueError('event save key invalid')
    for name, minimum in (('expectedPolicyRevision', 0), ('expectedCaseVersion', 1)):
        if type(value[name]) is not int or not minimum <= value[name] < 2**63 - 1:
            raise ValueError('event save expected version invalid')
    if any(type(value[name]) is not dict for name in ('policy', 'caseAuthority', 'approvalRef')):
        raise ValueError('event save requires strict JSON objects')
    if type(scope) is not TenantScope:
        raise TypeError('trusted Host scope required')
    for name in ('policy','caseAuthority'):
        if 'tenant' in value[name]:raise ValueError('wire cannot supply tenant')
        value[name]['tenant']=dict(orgId=scope.org_id,projectId=scope.project_id)
        if value[name].get('contentHash') != canonical_hash({k:v for k,v in value[name].items() if k!='contentHash'},prefixed=True):
            raise ValueError('event wire authority digest differs')
    if value['policy'].get('schemaVersion')!='aos.ecommerce.product-event-schedule-policy/v1':
        raise ValueError('event wire schema invalid')
    approval = InvestigationExactRef.model_validate(value['approvalRef'])
    if (approval.resource_type != 'ActionApprovalEvent'
            or type(value['approvalRef'].get('revision')) is not int or approval.receipt_id is not None):
        raise ValueError('event save exact approval required')
    return value, approval


def _request_hash(command):
    return canonical_hash({'policy': command['policy'], 'case': command['caseAuthority']}, prefixed=True)


def _response(command, replayed):
    policy = command['policy']
    return dict(receiptRef=dict(resourceType='SchedulePolicyRevision',resourceId=policy['schedulePolicyId'],
        revision=policy['revision'],contentHash=policy['contentHash']),authority=deepcopy(policy),
        caseAuthority=deepcopy(command['caseAuthority']),approvalRef=deepcopy(command['approvalRef']),replayed=replayed)


class ProductEventSchedulePutHostService:
    """Unregistered until current runtime composition supplies its real actor."""
    executor_identity = 'ecommerce-growth-event-schedule-host'

    def __init__(self, source_owner, *, actor):
        if type(actor) is not str or not 1 <= len(actor) <= 240 or actor != actor.strip() or not actor.isprintable():
            raise ValueError('trusted Host actor required')
        if type(source_owner) is not ProductEventQualifiedOwner:
            raise TypeError('qualified current event source Owner required')
        self._guard = ProductEventPolicyGuard(source_owner)
        self._actor = actor

    def _check(self, transaction, scope, command, approval):
        policy, case = command['policy'], command['caseAuthority']
        store = ProductEventPolicyStore(transaction, scope)
        original = store.find_receipt(command['idempotencyKey'], _request_hash(command))
        AutomationOccurrenceStore._lock_policy(transaction, scope, policy['schedulePolicyId'])
        transaction.execute('SELECT ecommerce_product_event_lock_a0v_041(%s,%s,%s)',
            (case.get('caseId'),policy['schedulePolicyId'],approval.resource_id))
        current = transaction.execute(
            'SELECT r.authority_data FROM ecommerce_investigation_case_head h '
            'JOIN ecommerce_investigation_case_revision r USING(org_id,project_id,case_id) '
            'WHERE h.org_id=%s AND h.project_id=%s AND h.case_id=%s '
            'AND r.revision=h.current_revision',
            (*scope.key, case.get('caseId')),
        ).fetchone()
        if current is None:
            raise ValueError('current event Case unavailable')
        current = current['authority_data']
        if (current.get('lifecycle') != 'ACTIVE'
                or current.get('contentHash') != canonical_hash({k:v for k,v in current.items() if k!='contentHash'},prefixed=True)):
            raise ValueError('current event Case invalid')
        selection = EcommerceInvestigationProfileCatalog().read(current['analysisType'])
        if selection is None:
            raise ValueError('current event method unavailable')
        profile, investigation_scope = selection
        profile_ref = profile.exact_ref.model_dump(by_alias=True,mode='json')
        scope_ref = investigation_scope.exact_ref.model_dump(by_alias=True,mode='json')
        if (policy.get('methodRef') != profile_ref or current.get('investigationProfileRef') != profile_ref
                or current.get('scopeRef') != scope_ref):
            raise ValueError('current event Case or method drifted')
        bound = store.get_current_binding(policy['schedulePolicyId'])
        if bound is not None and bound['caseAuthority'] != current:
            raise ValueError('current event binding Case differs')
        if original is None:
            expected_ref = dict(resourceType='BusinessInvestigationCaseRevision',resourceId=current['caseId'],
                revision=current['revision'],contentHash=current['contentHash'],receiptId=None)
            if (current['version'] != command['expectedCaseVersion']
                    or policy.get('caseRef') != expected_ref
                    or (0 if bound is None else bound['policy']['revision']) != command['expectedPolicyRevision']):
                raise ValueError('current event Case or policy version differs')
        now = transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        event = transaction.execute(
            'SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,actor_id,reason,'
            'expires_at,created_at,action_binding_hash FROM aip_action_approval_event '
            'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*scope.key,approval.resource_id),
        ).fetchone()
        proposal = transaction.execute(
            'SELECT proposal_id,action_type_id,payload,proposal_hash,status,action_binding_hash,version,expires_at '
            'FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
            (*scope.key,event['proposal_id']),
        ).fetchone() if event is not None else None
        _validate_schedule_approval_rows(event,proposal,approval,checked_at=now,case_id=case['caseId'],
            policy_id=policy['schedulePolicyId'],policy_hash=canonical_hash(policy,prefixed=True),
            expected_policy_revision=command['expectedPolicyRevision'],expected_case_version=command['expectedCaseVersion'])
        if (event['created_at'] > now or proposal is None or proposal['version'] != approval.revision
                or proposal['expires_at'] is None or proposal['expires_at'] <= now):
            raise ValueError('event approval is not current')
        require_current_event_approval(transaction=transaction,scope=scope,case_id=case['caseId'],
            policy_id=policy['schedulePolicyId'],approval_ref=approval,executor=self._actor)

    def revalidate(self, *, transaction, scope, dispatch, command):
        command,approval = _parse(command,scope)
        self._guard.run_policy(transaction=transaction,scope=scope,policy=command['policy'],
            dispatch=dispatch,actor=self._actor,execute=lambda:self._check(transaction,scope,command,approval))

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        command,approval = _parse(command,scope)
        def save():
            self._check(transaction,scope,command,approval)
            result = ProductEventPolicyStore(transaction,scope).put(
                idempotency_key=command['idempotencyKey'],expected_policy_revision=command['expectedPolicyRevision'],
                expected_case_version=command['expectedCaseVersion'],policy=command['policy'],case=command['caseAuthority'])
            if not result['replayed']:
                AutomationOccurrenceStore(TransactionBoundConnectFactory(transaction,scope)).disable_policy_bindings(
                    scope,command['policy']['schedulePolicyId'],keep_revision=None)
            self._check(transaction,scope,command,approval)
            return _response(command,result['replayed'])
        return self._guard.run_policy(transaction=transaction,scope=scope,policy=command['policy'],
            dispatch=dispatch_ref,actor=self._actor,execute=save)

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        command,_approval = _parse(command,scope)
        saved = ProductEventPolicyStore(transaction,scope).find_receipt(command['idempotencyKey'],_request_hash(command))
        if (saved is None or type(receipt) is not dict or type(receipt.get('replayed')) is not bool
                or saved['policy_authority'] != command['policy'] or saved['case_authority'] != command['caseAuthority']):
            return {}
        expected = _response(command,receipt['replayed'])
        return expected if receipt == expected else {}
