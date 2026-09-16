"""Consume complete original group input only while original current controls hold."""
from dataclasses import dataclass
from datetime import datetime
import re
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from aos_api.ec_ingress_journal import _digest,IngressJournalConflict
from aos_api.ec_ingress_recovery import _bound_parent
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_claim_owner import PipelineSnapshotGroupClaimOwner,SnapshotGroupClaimRecord
from aos_api.pipeline_snapshot_group_owner import CurrentSnapshotGroup
from aos_api.pipeline_source_selection_owner import _now
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef


@dataclass(frozen=True)
class CurrentSnapshotGroupInput:
    group: CurrentSnapshotGroup
    claim: SnapshotGroupClaimRecord
    manifest_hash: str
    manifest: dict
    read_started_at: datetime
    read_completed_at: datetime
    parents: tuple[dict,...]
    recovery_ref: PipelineExactRef | None = None


class PipelineSnapshotGroupInputOwner:
    def __init__(self,*,claims):
        self._groups=PipelineSnapshotGroupClaimOwner(claims=claims)
        self._claims=claims

    def run_current(self,conn,*,scope,group_id,actor,bindings,execute):
        return self._run(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,execute=execute,completed_read=False)

    def run_completed_current(self,conn,*,scope,group_id,actor,bindings,execute):
        return self._run(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,execute=execute,completed_read=True)

    def _run(self,conn,*,scope,group_id,actor,bindings,execute,completed_read):
        if not callable(execute):raise TypeError('synchronous consumer required')
        if self._claims._recovery is not None:
            return self._run_recovery(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,
                execute=execute,completed_read=completed_read)
        args=dict(scope=scope,group_id=group_id,actor=actor,bindings=bindings)
        def consume(group):
            current=self._load(conn,group,args,completed_read=completed_read)
            result=execute(current);_reject_deferred(result)
            if self._load(conn,group,args,completed_read=completed_read)!=current:raise IngressJournalConflict('GROUP_INPUT_CHANGED_DURING_CONSUMPTION')
            return result
        return self._groups._groups.run_current(conn,scope=scope,refs=tuple(ref for ref,_ in bindings),actor=actor,execute=consume)

    def _run_recovery(self,conn,*,scope,group_id,actor,bindings,execute,completed_read):
        authority=self._claims._recovery
        if group_id!=authority._group_id:raise PermissionError('fixed recovery group differs')
        def consume(current):
            facts=current.facts;group=current.execution.group
            by_control={PipelineExactRef.model_validate(ref).resource_id:run for ref,run in bindings}
            def load():
                read=self._claims.read_completed_current if completed_read else self._claims.read_saved_current
                records=tuple(read(conn,scope=scope,run_id=by_control[ref.resource_id],control_ref=ref,actor=actor)
                    for ref,_,_ in group.members)
                claim=SnapshotGroupClaimRecord(scope,group_id,actor,facts.source_claim_hash,records)
                return CurrentSnapshotGroupInput(group,claim,facts.manifest_hash,facts.manifest,
                    facts.read_started_at,facts.read_completed_at,facts.parents,authority._ref)
            source=load()
            result=execute(source);_reject_deferred(result)
            if load()!=source:raise IngressJournalConflict('GROUP_RECOVERY_INPUT_CHANGED_DURING_CONSUMPTION')
            return result
        return authority.run_current(conn,scope=scope,actor=actor,bindings=bindings,execute=consume)

    def _load(self,conn,group,args,*,completed_read=False):
        scope=args['scope']
        read=self._groups.read_completed_current if completed_read else self._groups.read_current
        claim=read(conn,**args)
        with conn.cursor(row_factory=dict_row) as cursor:
            saved=cursor.execute(sql.SQL('SELECT request_hash,manifest_hash,manifest,read_started_at,read_completed_at,snapshot_basis FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(
                sql.Identifier(self._claims._journal.schema,'pipeline_snapshot_group_input')),(*scope.key,UUID(args['group_id']))).fetchone()
        if saved is None:raise IngressJournalConflict('GROUP_ORIGINAL_INPUT_REQUIRED')
        manifest=saved['manifest'];started=saved['read_started_at'];completed=saved['read_completed_at']
        if (saved['request_hash']!=claim.request_hash or type(manifest) is not dict or set(manifest)!={'members'}
                or saved['manifest_hash']!='sha256:'+_digest(manifest) or type(manifest['members']) is not list
                or len(manifest['members'])!=len(group.members) or saved['snapshot_basis']!='innodb-repeatable-read'
                or not group.not_before<=started<=completed<group.expires_at or completed>_now(conn)):
            raise IngressJournalConflict('GROUP_ORIGINAL_INPUT_BINDING_DRIFT')
        parents=[]
        for leaf,(ref,draft,mapping),member in zip(manifest['members'],group.members,claim.members):
            if (type(leaf) is not dict or set(leaf)!={'runId','envelopeHash','rowsHash','rowCount'}
                    or leaf['runId']!=member.run_id or type(leaf['rowCount']) is not int or not 0<=leaf['rowCount']<group.row_limit
                    or type(leaf['rowsHash']) is not str or re.fullmatch(r'sha256:[0-9a-f]{64}',leaf['rowsHash']) is None):
                raise IngressJournalConflict('GROUP_ORIGINAL_MEMBER_DRIFT')
            journal=ControlledIngressJournal(claims=self._claims,scope=scope,run_id=member.run_id,control_ref=ref,actor=args['actor'],completed_read=completed_read)
            parent=_bound_parent(conn,scope,member.run_id,journal)
            rows=parent.get('outputRows')
            if (leaf['envelopeHash']!=_digest(parent) or type(rows) is not list or len(rows)!=leaf['rowCount']
                    or any(type(row) is not dict or row.get('ot')!=mapping.read_spec.object_type or 'link_type' in row for row in rows)):
                raise IngressJournalConflict('GROUP_ORIGINAL_OBJECT_INPUT_DRIFT')
            parents.append(parent)
        return CurrentSnapshotGroupInput(group,claim,saved['manifest_hash'],manifest,started,completed,tuple(parents))
