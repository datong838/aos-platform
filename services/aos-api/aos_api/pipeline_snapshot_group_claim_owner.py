"""Atomic original source claims for one immutable current snapshot group."""
from dataclasses import dataclass
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.ec_ingress_journal import _digest,IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_owner import PipelineSnapshotGroupOwner
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner,SourceClaimRecord,_text
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True)
class SnapshotGroupClaimRecord:
    scope: TenantScope
    group_id: str
    actor: str
    request_hash: str
    members: tuple[SourceClaimRecord,...]


@dataclass(frozen=True)
class SnapshotGroupClaimReservation:
    record: SnapshotGroupClaimRecord
    created: bool


class PipelineSnapshotGroupClaimOwner:
    def __init__(self,*,claims):
        if type(claims) is not PipelineSourceClaimOwner:raise TypeError('exact source claim Owner required')
        self._claims=claims
        self._groups=PipelineSnapshotGroupOwner(controls=claims._controls)
        self._schema=claims._journal.schema

    def reserve(self,conn,*,scope,group_id,actor,bindings):
        """No commit or source read. Only a confirmed outer COMMIT persists this claim."""
        _require_transaction(conn)
        with conn.transaction():
            return self._operate(conn,scope,group_id,actor,bindings,create=True)

    def read_current(self,conn,*,scope,group_id,actor,bindings):
        return self._operate(conn,scope,group_id,actor,bindings,create=False).record

    def read_completed_current(self,conn,*,scope,group_id,actor,bindings):
        """All original members completed; current authorization remains required."""
        return self._operate(conn,scope,group_id,actor,bindings,create=False,completed_read=True).record

    def _operate(self,conn,scope,group_id,actor,bindings,*,create,completed_read=False):
        if completed_read and create:raise ValueError('completed group cannot reserve source calls')
        if type(scope) is not TenantScope or type(group_id) is not str or str(UUID(group_id))!=group_id:
            raise ValueError('canonical snapshot group identity required')
        actor=_text(actor,240)
        if type(bindings) is not tuple or not 1<=len(bindings)<=12:raise ValueError('bounded group run bindings required')
        normalized=[]
        for item in bindings:
            if type(item) is not tuple or len(item)!=2:raise ValueError('exact control/run pair required')
            normalized.append((PipelineExactRef.model_validate(item[0]),_text(item[1],200)))
        if len({run for _,run in normalized})!=len(normalized):raise ValueError('unique group runs required')
        self._claims._guard_group(conn,scope=scope,group_id=group_id,actor=actor,bindings=tuple(normalized))
        refs=tuple(ref for ref,_ in normalized);runs={ref.resource_id:run for ref,run in normalized}
        def current(group):
            members=[{'runId':runs[ref.resource_id],'controlRef':ref.model_dump(mode='json',by_alias=True),
                'draft':draft.model_dump(mode='json',by_alias=True)} for ref,draft,_ in group.members]
            body={'schemaVersion':'aos.snapshot-group-claim/v1','orgId':scope.org_id,'projectId':scope.project_id,
                'groupId':group_id,'actor':actor,'members':members}
            request_hash='sha256:'+_digest(body)
            with conn.cursor(row_factory=dict_row) as cursor:
                existing=cursor.execute(sql.SQL('SELECT actor,request_hash,member_count,binding FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(
                    sql.Identifier(self._schema,'pipeline_snapshot_group_claim')),(*scope.key,UUID(group_id))).fetchone()
                records=[]
                if existing is not None:
                    if (existing['actor']!=actor or existing['request_hash']!=request_hash or existing['binding']!=body
                            or 'sha256:'+_digest(existing['binding'])!=existing['request_hash'] or existing['member_count']!=len(members)):
                        raise IngressJournalConflict('SNAPSHOT_GROUP_BINDING_DIFFERS')
                    saved=cursor.execute(sql.SQL('SELECT ordinal,run_id FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s ORDER BY ordinal').format(
                        sql.Identifier(self._schema,'pipeline_snapshot_group_member')),(*scope.key,UUID(group_id))).fetchall()
                    if [(row['ordinal'],row['run_id']) for row in saved]!=[(i+1,item['runId']) for i,item in enumerate(members)]:
                        raise IngressJournalConflict('SNAPSHOT_GROUP_MEMBERS_DIFFER')
                    for ref,_,_ in group.members:
                        read=self._claims.read_completed_current if completed_read else self._claims.read_current
                        records.append(read(conn,scope=scope,run_id=runs[ref.resource_id],control_ref=ref,actor=actor))
                    return SnapshotGroupClaimReservation(SnapshotGroupClaimRecord(scope,group_id,actor,request_hash,tuple(records)),False)
                if not create:raise LookupError('snapshot group claim unavailable')
                for ref,_,_ in group.members:
                    result=self._claims.reserve(conn,scope=scope,run_id=runs[ref.resource_id],control_ref=ref,actor=actor)
                    if result.created is not True:raise IngressJournalConflict('SNAPSHOT_GROUP_REQUIRES_NEW_SOURCE_CLAIMS')
                    records.append(result.record)
                cursor.execute(sql.SQL('INSERT INTO {}(org_id,project_id,group_id,actor,request_hash,member_count,binding) VALUES(%s,%s,%s,%s,%s,%s,%s)').format(
                    sql.Identifier(self._schema,'pipeline_snapshot_group_claim')),(*scope.key,UUID(group_id),actor,request_hash,len(members),Jsonb(body)))
                for ordinal,item in enumerate(members,1):
                    cursor.execute(sql.SQL('INSERT INTO {}(org_id,project_id,group_id,ordinal,run_id) VALUES(%s,%s,%s,%s,%s)').format(
                        sql.Identifier(self._schema,'pipeline_snapshot_group_member')),(*scope.key,UUID(group_id),ordinal,item['runId']))
                return SnapshotGroupClaimReservation(SnapshotGroupClaimRecord(scope,group_id,actor,request_hash,tuple(records)),True)
        return self._groups.run_current(conn,scope=scope,refs=refs,actor=actor,execute=current)
