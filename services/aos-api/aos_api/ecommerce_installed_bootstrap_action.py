"""Immutable installed internal action metadata; never business execution authority."""
from copy import deepcopy
from uuid import UUID

from aos_api.aip_budget_reservation_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


class InstalledBootstrapActionCatalog:
    def __init__(self, transaction, scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('exact Host transaction and scope required')
        self.tx, self.scope = transaction, scope
        identity = transaction.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if identity is None or (identity['role'], identity['org_id'], identity['project_id']) != ('aos_runtime', *scope.key):
            raise PermissionError('current installed action runtime scope required')

    def install(self, receipt):
        ref = receipt['receiptRef']
        if ref['resourceType'] != 'EventPolicyControlReceipt':
            raise ValueError('event admission receipt required')
        self.tx.execute('SELECT public.install_bootstrap_action_a0v_061(%s)', (UUID(ref['resourceId']),)).fetchone()

    def read_current(self, *, installation_id, generation, execution_epoch):
        row = self.tx.execute('''SELECT * FROM ecommerce_installed_bootstrap_action
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s AND execution_epoch=%s''',
            (*self.scope.key, installation_id, generation, execution_epoch)).fetchone()
        return self._snapshot(row)

    def _snapshot(self, row):
        if row is None:
            raise ValueError('installed bootstrap action unavailable')
        payload = row['payload']
        if (canonical_hash(payload, prefixed=True) != row['content_hash']
                or payload.get('tenant') != dict(orgId=self.scope.org_id, projectId=self.scope.project_id)
                or payload.get('entryId') != str(row['entry_id'])
                or payload.get('installationId') != str(row['installation_id'])
                or payload.get('generation') != str(row['generation'])
                or payload.get('executionEpoch') != row['execution_epoch']
                or payload.get('businessExecutionAuthorized') is not False
                or payload.get('externalEffectAuthorized') is not False):
            raise ValueError('installed bootstrap action content drift')
        runtime = self.tx.execute('''SELECT * FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s''',
            (*self.scope.key, row['installation_id'], row['generation'])).fetchone()
        if (runtime is None or not runtime['enabled'] or runtime['operation_fence']
                or runtime['execution_epoch'] != row['execution_epoch']
                or runtime['desired_state'] != 'enabled' or runtime['observed_state'] != 'ready'
                or runtime['config_ref'] != payload['configRef']):
            raise ValueError('installed bootstrap action runtime drift')
        receipt = self.tx.execute('''SELECT * FROM ecommerce_product_event_control_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s''',
            (*self.scope.key, row['control_receipt_id'])).fetchone()
        if (receipt is None or canonical_hash(receipt['authority'], prefixed=True) != receipt['content_hash']
                or payload['controlReceiptRef'] != dict(resourceType='EventPolicyControlReceipt',
                    resourceId=str(receipt['receipt_id']), revision=receipt['binding_revision'], contentHash=receipt['content_hash'])):
            raise ValueError('installed bootstrap action admission drift')
        snapshot = deepcopy(payload['definition'])
        snapshot['installedActionRef'] = dict(resourceType='InstalledActionTypeRevision',
            resourceId=str(row['entry_id']), revision=1, contentHash=row['content_hash'])
        snapshot['revisionHash'] = canonical_hash(snapshot)
        return snapshot

    def verify_snapshot(self, snapshot):
        ref = snapshot.get('installedActionRef', {})
        if ref.get('resourceType') != 'InstalledActionTypeRevision' or ref.get('revision') != 1:
            raise ValueError('exact installed action reference required')
        row = self.tx.execute('''SELECT * FROM ecommerce_installed_bootstrap_action
            WHERE org_id=%s AND project_id=%s AND entry_id=%s''',
            (*self.scope.key, UUID(ref['resourceId']))).fetchone()
        if self._snapshot(row) != snapshot:
            raise ValueError('current installed bootstrap action snapshot differs')
