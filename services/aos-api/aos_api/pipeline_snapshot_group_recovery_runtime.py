"""Resume only original saved input through the original Completion and Store."""
from contextlib import contextmanager
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import _ref_identity
from aos_api.pipeline_snapshot_group_completion import PipelineSnapshotGroupCompletion
from aos_api.pipeline_snapshot_group_recovery_authority import SnapshotGroupRecoveryAuthority
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
from aos_api.pipeline_snapshot_schedule_claim import PipelineSnapshotScheduleClaimOwner
from aos_api.pipeline_snapshot_schedule_definition import PipelineSnapshotScheduleDefinitionOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.tenant_scope import TenantScope


class PipelineSnapshotGroupRecoveryRuntime:
    def __init__(self,*,claims,store,connect,eng):
        if type(claims) is not PipelineSourceClaimOwner or claims._recovery is not None:
            raise TypeError('original ordinary source claim Owner required')
        if type(store) is not EcomConsistencyStore or not callable(connect):
            raise TypeError('original Store and independent connection factory required')
        self._controls,self._store,self._connect,self._eng=claims._controls,store,connect,eng
        self._claims=PipelineSnapshotScheduleClaimOwner(controls=self._controls)
        self._definitions=PipelineSnapshotScheduleDefinitionOwner(controls=self._controls,installation_store=PostgresInstallationStore())

    @contextmanager
    def _transaction(self,scope):
        if type(scope) is not TenantScope:raise TypeError('exact recovery runtime tenant required')
        with self._connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise IngressJournalConflict('RECOVERY_REQUIRES_INDEPENDENT_TRANSACTION')
            with conn.transaction():
                apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
                yield conn

    def resume_saved(self,*,scope,actor,recovery_ref,deadline=None,cancel_event=None):
        active=dict(deadline=deadline,cancel_event=cancel_event)
        _check_active(**active)
        ref=PipelineExactRef.model_validate(recovery_ref)
        group_id=_ref_identity(ref,'SnapshotGroupRecoveryRevision','snapshot-recovery-')
        wire=ref.model_dump(mode='json',by_alias=True,exclude_none=True)
        with self._transaction(scope) as conn:
            receipt=read_recovery_receipt(conn,scope=scope,group_id=group_id)
            if receipt is None:raise LookupError('original saved recovery receipt unavailable')
            if receipt['ref']!=wire:raise ValueError('recovery receipt is not current')
            identifier,_=self._claims._definition_ref(receipt['body']['currentDefinitionRef'])
            definition=self._definitions.read(conn,scope=scope,definition_id=identifier)
            if definition is None or definition['ref']!=receipt['body']['currentDefinitionRef']:
                raise ValueError('recovery definition is not current')
            original=self._claims.read(conn,scope=scope,group_id=group_id)
            if original is None:raise LookupError('original snapshot run claim unavailable')
            runs={m['scheduleId']:m['runId'] for m in original['members']}
            saved=self._definitions._saved_bindings(conn,scope,definition['body'])
            if {b.schedule_id for b in saved}!=set(runs):raise ValueError('recovery original schedule members differ')
            bindings=tuple((b.control_ref,runs[b.schedule_id]) for b in saved)
            authority=SnapshotGroupRecoveryAuthority(definitions=self._definitions,claims=self._claims,ref=ref)
            claims=PipelineSourceClaimOwner(controls=self._controls,recovery=authority,recovery_bindings=bindings)
            completion=PipelineSnapshotGroupCompletion(claims=claims,store=self._store,connect=self._connect,eng=self._eng)
            authority.run_current(conn,scope=scope,actor=actor,bindings=bindings,
                execute=lambda _:completion._route_with_recovery(completion._rows(conn,scope,bindings)))
            _check_active(**active)
        # No ScheduleClaim, source reservation or preparation. A completed
        # metadata transaction must return before original Store recovery starts.
        _check_active(**active)
        result=completion.complete(scope=scope,group_id=group_id,actor=actor,bindings=bindings,
            policy_ref=receipt['body']['policyRef'],**active)
        return dict(result,mode='saved-input-only',recovery_ref=wire,input_replayed=True,
            original_definition_ref=receipt['body']['originalDefinitionRef'],current_definition_ref=receipt['body']['currentDefinitionRef'])
