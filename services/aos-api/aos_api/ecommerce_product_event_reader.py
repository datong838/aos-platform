"""Current-source candidate metadata. No policy approval, payload export or ACK."""
from psycopg.rows import dict_row

from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2
from aos_api.tenant_scope import TenantScope


def _read_candidates(conn, policy, limit):
    """Internal SQL primitive; only call inside the current source Owner callback."""
    policy = ProductEventPolicyDraft.model_validate(policy)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('event candidate limit must be 1 to 100')
    with conn.cursor(row_factory=dict_row) as cursor:
        return tuple(cursor.execute('''SELECT e.outbox_id,e.input_revision,e.event_key,e.payload_hash,
            e.authority_tx_id,e.object_type,e.external_id,e.change_kind,e.created_at,
            e.payload->'record'->>'source_updated_at' AS source_updated_at
            FROM projection_outbox e
            WHERE e.org_id=%s AND e.project_id=%s AND e.workspace_id=%s
              AND e.platform=%s AND e.shop_or_marketplace_id=%s
              AND e.object_type=ANY(%s) AND e.event_source='authoritative_store'
              AND e.change_kind IN ('objects_written','objects_tombstoned')
              AND e.created_at>=%s AND e.created_at<%s
              AND NOT EXISTS (SELECT 1 FROM automation_occurrence o
                WHERE o.org_id=e.org_id AND o.project_id=e.project_id
                  AND o.policy_id=%s AND o.source_event_id=e.event_key)
            ORDER BY e.input_revision,e.outbox_id LIMIT %s''',
            (policy.org_id,policy.project_id,policy.project_id,policy.platform,policy.shop_or_marketplace_id,
             list(policy.object_types),policy.effective_from,policy.effective_until,policy.policy_id,limit)).fetchall())


class ProductEventCandidateReader:
    def __init__(self, selection_owner):
        if type(selection_owner) is not PipelineSourceSelectionOwner:
            raise TypeError('current source selection Owner required')
        self._owner = selection_owner

    def read(self, conn, *, policy, actor):
        policy = ProductEventPolicyDraft.model_validate(policy)
        scope = TenantScope(policy.org_id,policy.project_id)

        def current(draft, mapping):
            if type(mapping) not in (SnapshotMapping,SnapshotMappingV2):
                raise TypeError('compiled current mapping required')
            policy.validate_selection(SourceSelectionRecord(policy.source_selection_ref,draft,
                mapping.read_spec,actor,None))
            if (mapping.platform,mapping.shop_id) != (policy.platform,policy.shop_or_marketplace_id):
                raise PermissionError('event source scope differs from current mapping')
            return _read_candidates(conn,policy,min(100,draft.row_limit))

        return self._owner.run_current_snapshot(conn,scope=scope,ref=policy.source_selection_ref,
            actor=actor,execute=current)
