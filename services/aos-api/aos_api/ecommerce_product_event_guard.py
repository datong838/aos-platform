"""Correlate event policy with the current source inside its Owner transaction."""
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2
from aos_api.tenant_scope import TenantScope


class ProductEventPolicyGuard:
    def __init__(self, owner):
        if type(owner) is not PipelineSourceSelectionOwner:
            raise TypeError('current source Owner required')
        self._owner = owner

    def run(self, *, transaction, scope, context, policy, dispatch, actor, execute):
        """Trusted Host callback only. This is not a package-callable permission."""
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope or not callable(execute):
            raise TypeError('current Host transaction, scope and synchronous callback required')
        context = ProductEventPolicyDraft.model_validate(context)
        context.validate_policy(policy)
        if (scope.key != (context.org_id, context.project_id)
                or str(dispatch.installation_id) != context.installation_ref.installation_id
                or str(dispatch.generation) != context.generation
                or type(dispatch.execution_epoch) is not int
                or dispatch.execution_epoch != context.execution_epoch):
            raise ValueError('event context differs from current Host dispatch')

        def check_time():
            row = transaction.execute('SELECT clock_timestamp() AS now').fetchone()
            if row is None or not context.effective_from <= row['now'] < context.effective_until:
                raise PermissionError('event policy window is not current')

        def current(draft, mapping):
            if type(mapping) not in (SnapshotMapping, SnapshotMappingV2):
                raise TypeError('compiled current source mapping required')
            context.validate_selection(SourceSelectionRecord(context.source_selection_ref, draft,
                mapping.read_spec, actor, None))
            if (mapping.platform, mapping.shop_id) != (context.platform, context.shop_or_marketplace_id):
                raise PermissionError('event policy source differs from current mapping')
            check_time()
            result = execute()
            _reject_deferred(result)
            check_time()
            return result

        return transaction.run_current_source_snapshot(self._owner, scope=scope,
            ref=context.source_selection_ref, actor=actor, execute=current)
