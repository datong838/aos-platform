"""Binding CAS transport. Only a current authorization Owner may invoke it."""
from aos_api.automation_occurrence_store import AutomationOccurrenceStore, ScheduleBinding
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_control_contracts import ProductEventControlCommand
from aos_api.ecommerce_product_event_control_receipt import ProductEventControlReceiptStore
from aos_api.tenant_scope import TenantScope


class ProductEventBindingControlStore:
    def __init__(self,transaction,scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact Host transaction and scope required')
        self._transaction,self._scope=transaction,scope
        self._receipts=ProductEventControlReceiptStore(transaction,scope)

    def apply(self,command,*,actor,binding=None):
        """Caller must roll back its transaction on any failure, including receipt failure."""
        checked=ProductEventControlCommand.model_validate(command)
        original=self._receipts.find(checked,actor=actor)
        if original is not None:
            return original
        tx,scope=self._transaction,self._scope
        ref=checked.policy_ref
        row=tx.execute('SELECT * FROM automation_schedule_binding '
            'WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s FOR UPDATE',
            (*scope.key,ref.resource_id,ref.revision)).fetchone()
        revision=0 if row is None else row['revision']
        if revision!=checked.expected_binding_revision or revision>=2**63-1:
            raise ValueError('event control binding revision conflict')
        if row is not None and (row['policy_hash']!=ref.content_hash or row['cadence']!='event'):
            raise ValueError('event control binding authority differs')
        if checked.intent=='enable':
            if (type(binding) is not ScheduleBinding or binding.cadence!='event'
                    or type(binding.policy_revision) is not int or type(binding.execution_epoch) is not int
                    or binding.approved is not True or binding.enabled is not True
                    or (binding.policy_id,binding.policy_revision,binding.policy_hash)!=
                       (ref.resource_id,ref.revision,ref.content_hash)):
                raise ValueError('current Owner event binding required')
            # The enclosing Host Owner holds dispatch authority locks. The runtime
            # role deliberately has no direct UPDATE privilege on this table.
            dispatch=tx.execute('SELECT handler_kind,installation_id,generation,execution_epoch '
                'FROM extension_operation_dispatch_binding '
                'WHERE org_id=%s AND project_id=%s AND operation_id=%s',
                (*scope.key,binding.operation_id)).fetchone()
            if dispatch is None or tuple(dispatch[key] for key in
                    ('handler_kind','installation_id','generation','execution_epoch'))!=\
                    ('extension',binding.installation_id,binding.generation,binding.execution_epoch):
                raise ValueError('event control dispatch drifted')
            immutable=('policy_id','policy_revision','policy_hash','operation_id','installation_id',
                       'generation','execution_epoch','cadence','effective_from','effective_until')
            if row is not None and any(row[key]!=getattr(binding,key) for key in immutable):
                raise ValueError('event control binding identity drifted')
            if row is None:
                AutomationOccurrenceStore(TransactionBoundConnectFactory(tx,scope)).put_binding(scope,binding)
        elif row is None:
            raise ValueError('event control binding unavailable')
        if row is not None:
            changed=tx.execute('''UPDATE automation_schedule_binding
                SET enabled=%s,approved=CASE WHEN %s THEN true ELSE approved END,revision=revision+1
                WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s AND revision=%s
                RETURNING revision''',(checked.intent=='enable',checked.intent=='enable',*scope.key,
                    ref.resource_id,ref.revision,checked.expected_binding_revision)).fetchone()
            if changed is None:
                raise ValueError('event control binding revision conflict')
        return self._receipts.put(checked,actor=actor)
