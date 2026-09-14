"""Current Store projection proofs for complete saved groups; never a write grant."""
from dataclasses import dataclass, asdict
from psycopg import sql

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import read_saved_projection_evidence
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.ecom_core_models import BatchCommand
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner, CurrentSnapshotGroupInput


@dataclass(frozen=True)
class CurrentSnapshotGroupProjection:
    input: CurrentSnapshotGroupInput
    payload: dict
    content_hash: str


@dataclass(frozen=True)
class CurrentSnapshotGroupBaseCounts:
    projection: CurrentSnapshotGroupProjection
    payload: dict
    content_hash: str


def _base_counts(projection):
    members=[]
    for (_,draft,mapping),parent in zip(projection.input.group.members,projection.input.parents):
        rows=parent['outputRows']
        if any(type(row.get('is_deleted')) is not bool for row in rows):
            raise IngressJournalConflict('GROUP_BASE_DELETION_COUNT_UNKNOWN')
        deleted=sum(row['is_deleted'] for row in rows)
        if parent.get('kind')=='empty_observation_v1':
            if rows:raise IngressJournalConflict('GROUP_EMPTY_BASE_COUNT_DIFFERS')
            objects=[]
        else:
            command=BatchCommand.model_validate(parent['command'])
            objects=command.objects
            identities={(obj.object_type,obj.identity.scoped_key()) for obj in objects}
            if (len(objects)!=len(rows) or len(identities)!=len(objects)
                    or any(obj.object_type!=mapping.read_spec.object_type for obj in objects)
                    or sum(obj.is_deleted for obj in objects)!=deleted):
                raise IngressJournalConflict('GROUP_BASE_IDENTITY_COUNT_DIFFERS')
        members.append(dict(pipelineId=draft.pipeline_id,runId=parent['runId'],objectType=mapping.read_spec.object_type,
            sourceTotal=len(rows),sourceActive=len(rows)-deleted,sourceDeleted=deleted,projectedBaseTotal=len(objects)))
    return dict(schemaVersion='aos.snapshot-group-current-base-counts/v1',tenant=projection.payload['tenant'].copy(),
        groupId=projection.input.claim.group_id,projectionHash=projection.content_hash,members=members)


class PipelineSnapshotGroupProjectionOwner:
    def __init__(self, *, claims, store):
        if type(store) is not EcomConsistencyStore:
            raise TypeError('original canonical Store required')
        self._inputs=PipelineSnapshotGroupInputOwner(claims=claims)
        self._claims,self._store=claims,store

    def run_current_base_counts(self,conn,*,scope,group_id,actor,bindings,execute):
        """Count verified base identities; retain the existing projection payload."""
        if not callable(execute):raise TypeError('synchronous base count consumer required')
        def consume(projection):
            payload=_base_counts(projection);digest=canonical_sha256(payload)
            current=CurrentSnapshotGroupBaseCounts(projection,payload,digest)
            result=execute(current)
            _reject_deferred(result)
            if canonical_sha256(payload)!=digest or canonical_sha256(_base_counts(projection))!=digest:
                raise IngressJournalConflict('GROUP_BASE_COUNTS_CHANGED')
            return result
        return self.run_current(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,execute=consume)

    def run_current(self, conn, *, scope, group_id, actor, bindings, execute):
        if not callable(execute):raise TypeError('synchronous projection proof consumer required')
        def consume(source):
            def read():
                members=[]
                for (ref,_,mapping),parent in zip(source.group.members,source.parents):
                    run_id=parent['runId']
                    journal=ControlledIngressJournal(claims=self._claims,scope=scope,run_id=run_id,
                        control_ref=ref,actor=actor,completed_read=True)
                    events=read_saved_projection_evidence(conn,scope,run_id,journal=journal,store=self._store)
                    if any(not event.projected for event in events):
                        raise IngressJournalConflict('GROUP_CURRENT_PROJECTION_PENDING')
                    row=conn.execute(sql.SQL('SELECT payload_hash FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s').format(
                        sql.Identifier(self._claims._journal.schema,'ecommerce_ingress_dataset_receipt')),(*scope.key,run_id)).fetchone()
                    if row is None:raise IngressJournalConflict('GROUP_DATASET_RECEIPT_REQUIRED')
                    members.append(dict(runId=run_id,objectType=mapping.read_spec.object_type,
                        controlRef=ref.model_dump(mode='json',by_alias=True),datasetReceiptHash=row['payload_hash'],
                        events=[asdict(event) for event in sorted(events,key=lambda e:e.event_key)]))
                return dict(schemaVersion='aos.snapshot-group-current-projection/v1',
                    tenant=dict(orgId=scope.org_id,projectId=scope.project_id),groupId=source.claim.group_id,
                    inputManifestHash=source.manifest_hash,claimHash=source.claim.request_hash,
                    readStartedAt=source.read_started_at.isoformat(),readCompletedAt=source.read_completed_at.isoformat(),members=members)
            payload=read();digest=canonical_sha256(payload)
            current=CurrentSnapshotGroupProjection(source,payload,digest)
            result=execute(current)
            _reject_deferred(result)
            if canonical_sha256(payload)!=digest or canonical_sha256(read())!=digest:
                raise IngressJournalConflict('GROUP_CURRENT_PROJECTION_CHANGED')
            return result
        return self._inputs.run_completed_current(conn,scope=scope,group_id=group_id,actor=actor,bindings=bindings,execute=consume)
