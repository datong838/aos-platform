"""Event-schema storage transport. Caller owns authorization and transaction."""
from copy import deepcopy
import re

from psycopg.types.json import Jsonb

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

_SCHEMA = 'aos.ecommerce.product-event-schedule-policy/v1'


def _digest(value):
    return canonical_hash(value, prefixed=True)


def _key(value):
    if type(value) is not str or not 1 <= len(value) <= 200 or value.strip() != value:
        raise ValueError('event storage key invalid')


class ProductEventPolicyStore:
    """Does not commit, open connections, enable policies, or claim approval."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact Host transaction and tenant scope required')
        self._transaction = transaction
        self._scope = scope

    def _current_scope(self):
        row = self._transaction.execute(
            "SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id"
        ).fetchone()
        if (row is None or row['role'] != 'aos_runtime'
                or (row['org_id'], row['project_id']) != self._scope.key):
            raise ValueError('event storage current tenant or runtime role invalid')

    def _authority(self, value, *, policy=False):
        if type(value) is not dict:
            raise ValueError('event storage authority must be JSON object')
        if value.get('tenant') != {'orgId': self._scope.org_id, 'projectId': self._scope.project_id}:
            raise ValueError('event storage authority tenant mismatch')
        if policy and value.get('schemaVersion') != _SCHEMA:
            raise ValueError('event storage does not accept timed or unknown policy schema')
        if value.get('contentHash') != _digest({k: v for k, v in value.items() if k != 'contentHash'}):
            raise ValueError('event storage authority digest mismatch')
        return deepcopy(value)

    def get(self, policy_id):
        _key(policy_id)
        self._current_scope()
        row = self._transaction.execute(
            'SELECT authority_data FROM ecommerce_investigation_schedule_policy_head '
            'WHERE org_id=%s AND project_id=%s AND schedule_policy_id=%s',
            (*self._scope.key, policy_id),
        ).fetchone()
        if row is None:
            return None
        result = self._authority(row['authority_data'], policy=True)
        if result.get('schedulePolicyId') != policy_id:
            raise ValueError('event storage returned another policy')
        return result

    def get_current_binding(self, policy_id):
        """Current read only; callers still need locked execution authority."""
        _key(policy_id)
        self._current_scope()
        row = self._transaction.execute(
            """SELECT h.current_revision,h.content_hash,h.authority_data,
                r.content_hash AS history_hash,r.authority_data AS history_authority,
                ch.case_id,ch.current_revision AS case_revision,ch.version AS case_version,
                ch.lifecycle AS case_lifecycle,c.content_hash AS case_hash,c.authority_data AS case_authority
                FROM ecommerce_investigation_schedule_policy_head h
                LEFT JOIN ecommerce_investigation_schedule_policy_revision r
                  ON (r.org_id,r.project_id,r.schedule_policy_id,r.revision)=
                     (h.org_id,h.project_id,h.schedule_policy_id,h.current_revision)
                LEFT JOIN ecommerce_investigation_case_head ch
                  ON (ch.org_id,ch.project_id,ch.case_id)=(h.org_id,h.project_id,h.case_id)
                LEFT JOIN ecommerce_investigation_case_revision c
                  ON (c.org_id,c.project_id,c.case_id,c.revision)=
                     (ch.org_id,ch.project_id,ch.case_id,ch.current_revision)
                WHERE h.org_id=%s AND h.project_id=%s AND h.schedule_policy_id=%s""",
            (*self._scope.key, policy_id),
        ).fetchone()
        if row is None:
            return None
        try:
            policy = self._authority(row['authority_data'], policy=True)
            case = self._authority(row['case_authority'])
            expected_ref = dict(resourceType='SchedulePolicyRevision',resourceId=policy_id,
                revision=row['current_revision'],contentHash=row['content_hash'],receiptId=None)
            if (policy.get('schedulePolicyId') != policy_id
                    or type(policy.get('revision')) is not int or policy['revision'] != row['current_revision']
                    or policy['contentHash'] != row['content_hash'] or row['history_hash'] != row['content_hash']
                    or _digest(row['history_authority']) != _digest(policy)
                    or case.get('schemaVersion') != 'aos.ecommerce.business-investigation-case/v1'
                    or type(policy['caseRef'].get('revision')) is not int
                    or row['case_revision'] <= policy['caseRef']['revision']
                    or case.get('caseId') != row['case_id'] or policy['caseRef']['resourceId'] != row['case_id']
                    or type(case.get('revision')) is not int or case['revision'] != row['case_revision']
                    or type(case.get('version')) is not int or case['version'] != row['case_version']
                    or row['case_revision'] != row['case_version']
                    or case['contentHash'] != row['case_hash']
                    or case.get('lifecycle') != 'ACTIVE' or row['case_lifecycle'] != 'ACTIVE'
                    or _digest(case.get('schedulePolicyRef')) != _digest(expected_ref)
                    or _digest(case.get('investigationProfileRef')) != _digest(policy.get('methodRef'))):
                raise ValueError('authority drift')
        except (ValueError, TypeError, KeyError) as exc:
            raise ValueError('current event binding authority differs') from exc
        return dict(policy=policy,caseAuthority=case)

    def find_receipt(self, idempotency_key, request_hash):
        _key(idempotency_key)
        if type(request_hash) is not str or re.fullmatch(r'sha256:[0-9a-f]{64}', request_hash) is None:
            raise ValueError('event storage request digest invalid')
        self._current_scope()
        row = self._transaction.execute(
            'SELECT policy_authority,case_authority,expected_policy_revision,expected_case_version,request_hash '
            'FROM ecommerce_investigation_schedule_policy_command_receipt '
            "WHERE org_id=%s AND project_id=%s AND operation='business_investigation_schedule_policy.put' "
            'AND idempotency_key=%s',
            (*self._scope.key, idempotency_key),
        ).fetchone()
        if row is None:
            return None
        policy = self._authority(row['policy_authority'], policy=True)
        case = self._authority(row['case_authority'])
        if (row['request_hash'] != request_hash or _digest({'policy': policy, 'case': case}) != request_hash
                or policy.get('revision') != row['expected_policy_revision'] + 1
                or case.get('revision') != row['expected_case_version'] + 1):
            raise ValueError('event storage original Receipt conflict')
        return dict(row, policy_authority=policy, case_authority=case)

    def put(self, *, idempotency_key, expected_policy_revision, expected_case_version, policy, case):
        _key(idempotency_key)
        policy = self._authority(policy, policy=True)
        case = self._authority(case)
        for value, minimum in ((expected_policy_revision, 0), (expected_case_version, 1)):
            if type(value) is not int or not minimum <= value < 2**63 - 1:
                raise ValueError('event storage expected version invalid')
        self._current_scope()
        request_hash = _digest({'policy': policy, 'case': case})
        row = self._transaction.execute(
            'SELECT policy_authority,case_authority,replayed '
            'FROM ecommerce_product_event_policy_put_a0v_040(%s,%s,%s,%s,%s,%s)',
            (idempotency_key, expected_policy_revision, expected_case_version,
             request_hash, Jsonb(policy), Jsonb(case)),
        ).fetchone()
        if (row is None or row['policy_authority'] != policy or row['case_authority'] != case
                or type(row['replayed']) is not bool):
            raise ValueError('event storage write response mismatch')
        receipt = self.find_receipt(idempotency_key, request_hash)
        if (receipt is None or receipt['policy_authority'] != policy or receipt['case_authority'] != case
                or receipt['expected_policy_revision'] != expected_policy_revision
                or receipt['expected_case_version'] != expected_case_version):
            raise ValueError('event storage persisted Receipt mismatch')
        return deepcopy(dict(row))
