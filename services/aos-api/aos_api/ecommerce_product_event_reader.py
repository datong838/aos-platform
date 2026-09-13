"""Current-source candidate metadata. No policy approval, payload export or ACK."""
import hashlib
import json
from psycopg.rows import dict_row
from aos_api.extension_runtime.runtime_gate import _reject_deferred

from aos_api.ecommerce_product_event_policy import ProductEventPolicyDraft
from aos_api.pipeline_source_selection_owner import PipelineSourceSelectionOwner
from aos_api.pipeline_source_selection_store import SourceSelectionRecord
from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2
from aos_api.tenant_scope import TenantScope
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.ecom_consistency_store import EcomConsistencyStore, ProjectionEventEvidence
from aos_api.ec_ingress_recovery import _bound_parent
from aos_api.ecom_core_models import BatchCommand, DerivedMetricCommand


def _read_candidates(conn, policy, limit, evidence):
    """Internal SQL primitive; only call inside the current source Owner callback."""
    policy = ProductEventPolicyDraft.model_validate(policy)
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('event candidate limit must be 1 to 100')
    if type(evidence) is not tuple or len(evidence)>10000 or any(type(item) is not ProjectionEventEvidence for item in evidence):
        raise ValueError('bounded original batch evidence required')
    refs = {item.event_key:item for item in evidence}
    if len(refs)!=len(evidence):raise ValueError('ambiguous original batch evidence')
    if not refs:return ()
    with conn.cursor(row_factory=dict_row) as cursor:
        rows = tuple(cursor.execute('''SELECT e.outbox_id,e.input_revision,e.event_key,e.payload_hash,
            e.authority_tx_id,e.object_type,e.external_id,e.change_kind,e.created_at,e.payload,
            e.payload->'record'->>'source_updated_at' AS source_updated_at
            FROM projection_outbox e
            WHERE e.org_id=%s AND e.project_id=%s AND e.workspace_id=%s
              AND e.platform=%s AND e.shop_or_marketplace_id=%s
              AND e.object_type=ANY(%s) AND e.event_source='authoritative_store'
              AND e.change_kind IN ('objects_written','objects_tombstoned')
              AND e.created_at>=%s AND e.created_at<%s
              AND e.event_key=ANY(%s)
              AND NOT EXISTS (SELECT 1 FROM automation_occurrence o
                WHERE o.org_id=e.org_id AND o.project_id=e.project_id
                  AND o.policy_id=%s AND o.source_event_id=e.event_key)
            ORDER BY e.input_revision,e.outbox_id LIMIT %s''',
            (policy.org_id,policy.project_id,policy.project_id,policy.platform,policy.shop_or_marketplace_id,
             list(policy.object_types),policy.effective_from,policy.effective_until,list(refs),policy.policy_id,limit)).fetchall())
    for row in rows:
        ref=refs[row['event_key']]
        if (row['payload_hash'],row['input_revision'])!=(ref.payload_hash,ref.input_revision):
            raise ValueError('original batch event evidence differs')
        payload = row.pop('payload')
        try:
            if type(payload) is not dict:
                raise ValueError('payload must be an object')
            encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                 separators=(',', ':'), allow_nan=False).encode('utf-8')
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ValueError('original batch payload integrity differs') from None
        if hashlib.sha256(encoded).hexdigest() != ref.payload_hash:
            raise ValueError('original batch payload integrity differs')
    return rows


class ProductEventCandidateReader:
    def __init__(self, selection_owner, *, journal, store):
        if (type(selection_owner) is not PipelineSourceSelectionOwner
                or type(journal) is not ControlledIngressJournal or type(store) is not EcomConsistencyStore):
            raise TypeError('current source and original ingress Owners required')
        self._owner = selection_owner
        self._journal,self._store=journal,store

    def read(self, conn, *, policy, actor, run_id):
        return self.run_candidates(conn, policy=policy, actor=actor, run_id=run_id,
                                   execute=lambda rows: rows)

    def run_candidates(self, conn, *, policy, actor, run_id, execute):
        """Trusted synchronous callback under the original current-source Owner.

        The caller retains transaction ownership. This supplies metadata, not
        permission to enable a policy or consume an unauthenticated source.
        """
        if not callable(execute):
            raise TypeError('synchronous candidate consumer required')
        policy = ProductEventPolicyDraft.model_validate(policy)
        def consume(rows):
            result = execute(rows)
            _reject_deferred(result)
            return result
        scope = TenantScope(policy.org_id,policy.project_id)

        def current(draft, mapping):
            if type(mapping) not in (SnapshotMapping,SnapshotMappingV2):
                raise TypeError('compiled current mapping required')
            policy.validate_selection(SourceSelectionRecord(policy.source_selection_ref,draft,
                mapping.read_spec,actor,None))
            if (mapping.platform,mapping.shop_id) != (policy.platform,policy.shop_or_marketplace_id):
                raise PermissionError('event source scope differs from current mapping')
            self._journal.lock_run(conn,scope,run_id)
            parent=_bound_parent(conn,scope,run_id,self._journal)
            if (parent['pipelineId'],parent['sourceId'],parent['sourceRevision'],parent['pipelineHash']) != (
                    draft.pipeline_id,draft.source_id,
                    draft.source_configuration_ref.resource_id.removeprefix('source-config-'),draft.graph_hash):
                raise PermissionError('original ingress does not match selected source')
            saved=self._journal.read_derived(conn,scope,run_id)
            if saved is None:raise ValueError('complete original derived preparation required')
            if parent.get('kind')=='empty_observation_v1':return consume(())
            evidence=self._store.read_batch_projection_evidence(BatchCommand.model_validate(parent['command']),
                [DerivedMetricCommand.model_validate(raw) for raw in saved['commands']])
            return consume(_read_candidates(conn,policy,min(100,draft.row_limit),evidence))

        return self._owner.run_current_snapshot(conn,scope=scope,ref=policy.source_selection_ref,
            actor=actor,execute=current)
