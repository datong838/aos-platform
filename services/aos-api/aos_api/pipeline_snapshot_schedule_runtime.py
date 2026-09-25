"""Trusted whole-group execution using original claims, input and completion Owners."""
from contextlib import contextmanager

from psycopg.pq import TransactionStatus
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_controlled_snapshot_group_ingress import ControlledSnapshotGroupIngress
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.host_lease import OptInHostLease


class PipelineSnapshotScheduleRuntime:
    def __init__(self,*,claims,store,connect,eng,host_lease=None):
        if type(claims) is not PipelineSourceClaimOwner or type(store) is not EcomConsistencyStore or not callable(connect):
            raise TypeError('original snapshot runtime dependencies required')
        if host_lease is not None and type(host_lease) is not OptInHostLease:
            raise TypeError('exact snapshot Schedule Host lease required')
        self._connect=connect
        self._host_lease=host_lease
        self._claims=PipelineSnapshotScheduleClaimOwner(controls=claims._controls)
        self._definitions=PipelineSnapshotScheduleDefinitionOwner(
            controls=claims._controls,installation_store=PostgresInstallationStore())
        self._ingress=ControlledSnapshotGroupIngress(claims=claims,store=store,connect=connect)
        self._completion=PipelineSnapshotGroupCompletion(claims=claims,store=store,connect=connect,eng=eng)

    @contextmanager
    def _transaction(self,scope):
        if type(scope) is not TenantScope:raise TypeError('exact snapshot runtime tenant required')
        with self._connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise IngressJournalConflict('SCHEDULE_GROUP_REQUIRES_INDEPENDENT_TRANSACTION')
            with conn.transaction():
                apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
                if self._host_lease is not None:
                    self._host_lease.fence_in_transaction(
                        conn,dict(org_id=scope.org_id,project_id=scope.project_id))
                yield conn

    def execute(self,*,scope,definition_ref,group_id,actor,scheduled_for,trigger,deadline=None,cancel_event=None):
        active=dict(deadline=deadline,cancel_event=cancel_event)
        _check_active(**active)
        identifier,wire=self._claims._definition_ref(definition_ref)
        with self._transaction(scope) as conn:
            definition=self._definitions.read(conn,scope=scope,definition_id=identifier)
            if definition is None:raise LookupError('snapshot definition unavailable')
            if definition['ref']!=wire or definition['body']['state']!='enabled':
                raise ValueError('snapshot definition is not current enabled authority')
            bindings=self._definitions._saved_bindings(conn,scope,definition['body'])
            receipt=self._claims.claim(conn,scope=scope,group_id=group_id,actor=actor,
                scheduled_for=scheduled_for,trigger=trigger,bindings=bindings,definition_ref=wire)
            _check_active(**active)
        # The whole claim transaction and connection have confirmed COMMIT.
        _check_active(**active)
        original=tuple((PipelineExactRef.model_validate(m['controlRef']),m['runId']) for m in receipt['members'])
        args=dict(scope=scope,group_id=group_id,actor=actor,bindings=original)
        with self._transaction(scope) as conn:
            route=self._completion._route(self._completion._rows(conn,scope,original))
        _check_active(**active)
        prepared=None
        if route=='running':
            # Existing source claim without original input remains unknown.
            # This call never retries a source read on an unknown outcome.
            prepared=self._ingress.prepare(**args,**active)
        result=self._completion.complete(**args,policy_ref=definition['body']['policyRef'],**active)
        return dict(result,definition_ref=wire,schedule_claim_hash=canonical_sha256(receipt),
            input_replayed=prepared.replayed if prepared is not None else True)
