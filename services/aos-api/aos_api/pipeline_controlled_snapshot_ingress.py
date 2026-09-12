"""Commit one source claim before one selected read and immutable input preparation."""
from contextlib import contextmanager
from dataclasses import dataclass

from psycopg.pq import TransactionStatus

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _bound_parent, _check_active
from aos_api.ec_ot_writer import _normalize_rows, _build_batch_command
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import SyncScope
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.pipeline_selected_snapshot import read_selected_snapshot
from aos_api.pipeline_snapshot_materialization import materialize_snapshot
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner


@dataclass(frozen=True)
class PreparedControlledSnapshot:
    parent: dict
    rows_read: int
    replayed: bool


class ControlledSnapshotIngress:
    def __init__(self, *, claims, store, connect):
        if type(claims) is not PipelineSourceClaimOwner or type(store) is not EcomConsistencyStore or not callable(connect):
            raise TypeError('exact claim and consistency Owners with trusted connection required')
        self._claims,self._store,self._connect=claims,store,connect

    @contextmanager
    def _transaction(self, scope):
        with self._connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise IngressJournalConflict('SOURCE_CLAIM_REQUIRES_INDEPENDENT_TRANSACTION')
            with conn.transaction():
                apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
                yield conn

    def prepare(self, *, scope, run_id, control_ref, actor, deadline=None, cancel_event=None):
        """Return committed input, never an object receipt or completed run.

        No exception here authorizes a new run/key or another source call. If a
        claim commit acknowledgement is lost, retrying this exact run can only
        find original input or report an unconfirmed outcome.
        """
        journal=ControlledIngressJournal(claims=self._claims,scope=scope,run_id=run_id,control_ref=control_ref,actor=actor)
        args=dict(scope=scope,run_id=run_id,control_ref=control_ref,actor=actor)
        current=dict(scope=scope,ref=control_ref,actor=actor)
        _check_active(deadline,cancel_event)
        with self._transaction(scope) as conn:
            def reserve(draft,mapping):
                _check_active(deadline,cancel_event)
                return self._claims.reserve(conn,**args)
            reservation=self._claims._controls.run_current_snapshot(conn,**current,execute=reserve)
        # Both transaction and connection exited normally: the claim is durable.
        _check_active(deadline,cancel_event)
        with self._transaction(scope) as conn:
            def prepare_input(draft,mapping):
                record=self._claims.read_current(conn,**args)
                if record!=reservation.record:
                    raise IngressJournalConflict('SOURCE_CLAIM_BINDING_DRIFT')
                _check_active(deadline,cancel_event)
                if journal.read(conn,scope,run_id) is not None:
                    return PreparedControlledSnapshot(_bound_parent(conn,scope,run_id,journal),0,True)
                if reservation.created is not True:
                    raise IngressJournalConflict('SOURCE_OUTCOME_UNCONFIRMED')
                body=draft.model_dump(exclude={'schema_version','source_selection_ref'})
                selection=PipelineSourceSelectionDraft.model_validate(body)
                result=read_selected_snapshot(transaction=HostTransaction(conn),scope=scope,draft=selection,read_spec=mapping.read_spec)
                if result.source_configuration_ref!=draft.source_configuration_ref:
                    raise IngressJournalConflict('INGRESS_SOURCE_READ_VERSION_DRIFT')
                _check_active(deadline,cancel_event)
                output=materialize_snapshot(result.rows,mapping,observed_at=result.completed_at)
                bound=dict(run_id=run_id,pipeline_id=draft.pipeline_id,source_id=draft.source_id,
                    source_revision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),pipeline_hash=draft.graph_hash)
                if output:
                    sync=SyncScope(org_id=scope.org_id,workspace_id=scope.project_id,platform=mapping.platform,
                        shop_or_marketplace_id=mapping.shop_id,stream=draft.pipeline_id)
                    objects,links=_normalize_rows(output,sync)
                    command=_build_batch_command(sync_scope=sync,objects=objects,links=links,pipeline_id=draft.pipeline_id,store=self._store)
                    parent=journal.save_for_running_schedule(conn,scope,**bound,command=command,output_rows=output)
                else:
                    parent=journal.save_empty_for_running_schedule(conn,scope,**bound)
                _check_active(deadline,cancel_event)
                return PreparedControlledSnapshot(parent,len(result.rows),False)
            prepared=self._claims._controls.run_current_snapshot(conn,**current,execute=prepare_input)
        return prepared
