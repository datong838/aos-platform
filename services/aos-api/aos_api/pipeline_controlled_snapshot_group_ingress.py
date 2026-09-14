"""Commit group claims before one read and atomic original input preparation."""
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ec_ingress_journal import IngressJournalConflict,_digest
from aos_api.ec_ingress_recovery import _bound_parent,_check_active
from aos_api.ec_ot_writer import _normalize_rows,_build_batch_command
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import SyncScope
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner
from aos_api.pipeline_selected_snapshot_group import read_selected_snapshot_group
from aos_api.pipeline_snapshot_materialization import materialize_snapshot
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class PreparedControlledSnapshotGroup:
    parents: tuple[dict,...]
    rows_read: int
    replayed: bool
    manifest_hash: str


class ControlledSnapshotGroupIngress:
    def __init__(self,*,claims,store,connect):
        if type(claims) is not PipelineSourceClaimOwner or type(store) is not EcomConsistencyStore or not callable(connect):
            raise TypeError('exact original Owners and trusted connection required')
        self._claims,self._store,self._connect=claims,store,connect
        self._groups=PipelineSnapshotGroupClaimOwner(claims=claims)

    @contextmanager
    def _transaction(self,scope):
        with self._connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise IngressJournalConflict('GROUP_CLAIM_REQUIRES_INDEPENDENT_TRANSACTION')
            with conn.transaction():
                apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
                yield conn

    def prepare(self,*,scope,group_id,actor,bindings,deadline=None,cancel_event=None):
        """Input preparation only. Unknown claim/read outcomes never reissue a read."""
        args=dict(scope=scope,group_id=group_id,actor=actor,bindings=bindings)
        _check_active(deadline,cancel_event)
        with self._transaction(scope) as conn:
            reservation=self._groups.reserve(conn,**args)
        _check_active(deadline,cancel_event)
        with self._transaction(scope) as conn:
            def prepare_input(group):
                if self._groups.read_current(conn,**args)!=reservation.record:
                    raise IngressJournalConflict('GROUP_CLAIM_BINDING_DRIFT')
                runs={ref.resource_id:run for ref,run in bindings}
                members=tuple((runs[ref.resource_id],draft,mapping,ControlledIngressJournal(
                    claims=self._claims,scope=scope,run_id=runs[ref.resource_id],control_ref=ref,actor=actor))
                    for ref,draft,mapping in group.members)
                _check_active(deadline,cancel_event)
                table=sql.Identifier(self._claims._journal.schema,'pipeline_snapshot_group_input')
                with conn.cursor(row_factory=dict_row) as cursor:
                    saved=cursor.execute(sql.SQL('SELECT request_hash,manifest_hash,manifest FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(table),(*scope.key,UUID(group_id))).fetchone()
                if saved is not None:
                    if (saved['request_hash']!=reservation.record.request_hash
                            or saved['manifest_hash']!='sha256:'+_digest(saved['manifest'])
                            or set(saved['manifest'])!={'members'}
                            or type(saved['manifest']['members']) is not list
                            or len(saved['manifest']['members'])!=len(members)):
                        raise IngressJournalConflict('GROUP_INPUT_MANIFEST_DRIFT')
                    parents=[]
                    for leaf,(run,_,_,journal) in zip(saved['manifest']['members'],members):
                        parent=_bound_parent(conn,scope,run,journal)
                        if leaf['runId']!=run or leaf['envelopeHash']!=_digest(parent):
                            raise IngressJournalConflict('GROUP_INPUT_MEMBER_DRIFT')
                        parents.append(parent)
                    return PreparedControlledSnapshotGroup(tuple(parents),0,True,saved['manifest_hash'])
                if reservation.created is not True:
                    raise IngressJournalConflict('GROUP_OUTCOME_UNCONFIRMED')
                if any(journal.read(conn,scope,run) is not None for run,_,_,journal in members):
                    raise IngressJournalConflict('GROUP_REQUIRES_NEW_ORIGINAL_INPUTS')
                result=read_selected_snapshot_group(transaction=HostTransaction(conn),scope=scope,group=group)
                if (result.source_configuration_ref!=group.members[0][1].source_configuration_ref
                        or set(result.rows_by_table)!={mapping.read_spec.table for _,_,mapping,_ in members}):
                    raise IngressJournalConflict('GROUP_SOURCE_READ_BINDING_DRIFT')
                _check_active(deadline,cancel_event)
                parents=[];leaves=[]
                for run,draft,mapping,journal in members:
                    rows=result.rows_by_table[mapping.read_spec.table]
                    output=materialize_snapshot(rows,mapping,observed_at=result.completed_at)
                    bound=dict(run_id=run,pipeline_id=draft.pipeline_id,source_id=draft.source_id,
                        source_revision=draft.source_configuration_ref.resource_id.removeprefix('source-config-'),pipeline_hash=draft.graph_hash)
                    if output:
                        sync=SyncScope(org_id=scope.org_id,workspace_id=scope.project_id,platform=mapping.platform,
                            shop_or_marketplace_id=mapping.shop_id,stream=draft.pipeline_id)
                        objects,links=_normalize_rows(output,sync)
                        command=_build_batch_command(sync_scope=sync,objects=objects,links=links,pipeline_id=draft.pipeline_id,store=self._store)
                        parent=journal.save_for_running_schedule(conn,scope,**bound,command=command,output_rows=output)
                    else:parent=journal.save_empty_for_running_schedule(conn,scope,**bound)
                    parents.append(parent)
                    leaves.append(dict(runId=run,envelopeHash=_digest(parent),rowsHash=observed_rows_hash(rows),rowCount=len(rows)))
                    _check_active(deadline,cancel_event)
                manifest={'members':leaves};manifest_hash='sha256:'+_digest(manifest)
                conn.execute(sql.SQL('''INSERT INTO {} (org_id,project_id,group_id,request_hash,
                    read_started_at,read_completed_at,snapshot_basis,manifest_hash,manifest)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)''').format(table),
                    (*scope.key,UUID(group_id),reservation.record.request_hash,result.started_at,result.completed_at,
                     'innodb-repeatable-read',manifest_hash,Jsonb(manifest)))
                _check_active(deadline,cancel_event)
                return PreparedControlledSnapshotGroup(tuple(parents),sum(leaf['rowCount'] for leaf in leaves),False,manifest_hash)
            prepared=self._groups._groups.run_current(conn,scope=scope,refs=tuple(ref for ref,_ in bindings),actor=actor,execute=prepare_input)
            _check_active(deadline,cancel_event)
        return prepared
