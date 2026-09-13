"""Transaction-bound control audit transport, never an enable authority."""
from copy import deepcopy
from uuid import NAMESPACE_URL, uuid5
from psycopg.types.json import Jsonb
from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.tenant_scope import TenantScope
from aos_api.automation_occurrence_store import AutomationOccurrenceStore


def _hash(value):
    return canonical_hash(value,prefixed=True)


class ProductEventControlReceiptStore:
    def __init__(self,transaction,scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact Host transaction and scope required')
        self._transaction,self._scope=transaction,scope

    def put(self,command,*,actor):
        checked=ProductEventControlCommand.model_validate(command)
        command=checked.model_dump(by_alias=True,mode='json')
        if type(actor) is not str or not 1<=len(actor)<=240 or actor!=actor.strip() or not actor.isprintable():
            raise ValueError('canonical control actor required')
        tx,scope=self._transaction,self._scope
        identity=tx.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if identity is None or (identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key):
            raise ValueError('current runtime scope required')
        AutomationOccurrenceStore._lock_policy(tx,scope,checked.policy_ref.resource_id)
        # Policy, then original command key, then binding: the future CAS Owner
        # must acquire the same policy lock before mutating its binding.
        tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            (_hash({'scope':list(scope.key),'controlKey':checked.idempotency_key}),))
        request_hash=_hash(command)
        row=tx.execute('SELECT * FROM ecommerce_product_event_control_receipt '
            'WHERE org_id=%s AND project_id=%s AND idempotency_key=%s',(*scope.key,checked.idempotency_key)).fetchone()
        replayed=row is not None
        if row is None:
            binding=tx.execute('SELECT to_jsonb(b) AS authority FROM automation_schedule_binding b '
                'WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s FOR UPDATE',
                (*scope.key,checked.policy_ref.resource_id,checked.policy_ref.revision)).fetchone()
            binding=None if binding is None else binding['authority']
            if (binding is None or binding['policy_hash']!=checked.policy_ref.content_hash
                    or binding['revision']!=checked.expected_binding_revision+1 or binding['cadence']!='event'
                    or binding['enabled'] is not (checked.intent=='enable')
                    or (checked.intent=='enable' and binding['approved'] is not True)):
                raise ValueError('control binding result differs')
            authority=dict(schemaVersion='aos.ecommerce.product-event-control-receipt/v1',
                actor=actor,command=command,binding=binding)
            receipt_id=uuid5(NAMESPACE_URL,_hash({'scope':list(scope.key),'controlKey':checked.idempotency_key}))
            row=tx.execute('''INSERT INTO ecommerce_product_event_control_receipt(
                org_id,project_id,idempotency_key,receipt_id,request_hash,policy_id,policy_revision,
                binding_revision,actor,command,authority,content_hash)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *''',
                (*scope.key,checked.idempotency_key,receipt_id,request_hash,checked.policy_ref.resource_id,
                 checked.policy_ref.revision,binding['revision'],actor,Jsonb(command),Jsonb(authority),_hash(authority))).fetchone()
        if (row is None or row['request_hash']!=request_hash or _hash(row['command'])!=request_hash
                or _hash(row['authority'])!=row['content_hash']):
            raise ValueError('event control receipt conflict')
        authority=row['authority']
        binding=authority.get('binding')
        if (set(authority)!={'schemaVersion','actor','command','binding'}
                or authority['schemaVersion']!='aos.ecommerce.product-event-control-receipt/v1'
                or authority['actor']!=row['actor'] or _hash(authority['command'])!=request_hash
                or type(binding) is not dict or binding.get('revision')!=row['binding_revision']
                or binding.get('policy_id')!=checked.policy_ref.resource_id
                or binding.get('policy_revision')!=checked.policy_ref.revision
                or binding.get('policy_hash')!=checked.policy_ref.content_hash
                or (binding.get('org_id'),binding.get('project_id'))!=scope.key):
            raise ValueError('event control receipt authority conflict')
        return dict(receiptRef=dict(resourceType='EventPolicyControlReceipt',resourceId=str(row['receipt_id']),
            revision=row['binding_revision'],contentHash=row['content_hash']),authority=deepcopy(row['authority']),replayed=replayed)
