"""Correlate event policy with the current source inside its Owner transaction."""
import json
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.ecommerce_product_event_qualified_owner import ProductEventQualifiedOwner
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2
from aos_api.tenant_scope import TenantScope


class ProductEventPolicyGuard:
    def __init__(self, owner):
        if type(owner) not in (PipelineSourceSelectionOwner, ProductEventQualifiedOwner):
            raise TypeError('current source Owner required')
        self._owner = owner

    def run_policy(self, *, transaction, scope, policy, dispatch, actor, execute):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope or type(policy) is not dict:
            raise TypeError('trusted Host transaction, scope and policy required')
        ref = PipelineExactRef.model_validate(policy['sourceSelectionRef'])
        def current(draft, mapping):
            source = draft.model_dump(by_alias=True,mode='json')
            values = {key:source[key] for key in ('orgId','projectId','installationRef','generation',
                'executionEpoch','configurationRef','sourceConfigurationRef')}
            values.update(policyId=policy['schedulePolicyId'],sourceSelectionRef=policy['sourceSelectionRef'],
                platform=policy['platform'],shopOrMarketplaceId=policy['shopId'],objectTypes=policy['objectTypes'],
                methodVersion='aos.product-source-event/v1',effectiveFrom=policy['effectiveFrom'],
                effectiveUntil=policy['effectiveUntil'],maxSourceAgeSeconds=policy['maxSourceAgeSeconds'],
                recoveryWindowSeconds=policy['recoveryWindowSeconds'])
            context = ProductEventPolicyDraft.model_validate_json(json.dumps(values))
            self._correlate(scope,context,policy,dispatch)
            return self._during_current(transaction,context,draft,mapping,actor,execute)
        return transaction.run_current_source_snapshot(self._owner,scope=scope,ref=ref,actor=actor,execute=current)

    @staticmethod
    def _correlate(scope, context, policy, dispatch):
        context.validate_policy(policy)
        if (scope.key != (context.org_id, context.project_id)
                or str(dispatch.installation_id) != context.installation_ref.installation_id
                or str(dispatch.generation) != context.generation
                or type(dispatch.execution_epoch) is not int
                or dispatch.execution_epoch != context.execution_epoch):
            raise ValueError('event context differs from current Host dispatch')

    @staticmethod
    def _during_current(transaction,context,draft,mapping,actor,execute):
        if not callable(execute):raise TypeError('synchronous Host callback required')
        if type(mapping) not in (SnapshotMapping, SnapshotMappingV2):
            raise TypeError('compiled current source mapping required')
        context.validate_selection(SourceSelectionRecord(context.source_selection_ref,draft,mapping.read_spec,actor,None))
        if (mapping.platform,mapping.shop_id)!=(context.platform,context.shop_or_marketplace_id):
            raise PermissionError('event policy source differs from current mapping')
        def check_time():
            row=transaction.execute('SELECT clock_timestamp() AS now').fetchone()
            if row is None or not context.effective_from<=row['now']<context.effective_until:
                raise PermissionError('event policy window is not current')
        check_time()
        result=execute()
        _reject_deferred(result)
        check_time()
        return result

    def run(self, *, transaction, scope, context, policy, dispatch, actor, execute):
        """Trusted Host callback only. This is not a package-callable permission."""
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope or not callable(execute):
            raise TypeError('current Host transaction, scope and synchronous callback required')
        context = ProductEventPolicyDraft.model_validate(context)
        self._correlate(scope,context,policy,dispatch)
        return transaction.run_current_source_snapshot(self._owner, scope=scope,
            ref=context.source_selection_ref, actor=actor,
            execute=lambda draft,mapping:self._during_current(transaction,context,draft,mapping,actor,execute))
