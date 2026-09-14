"""Current Store projection proofs for complete saved groups; never a write grant."""
from dataclasses import dataclass, asdict
from psycopg import sql

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import read_saved_projection_evidence
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner, CurrentSnapshotGroupInput


@dataclass(frozen=True)
class CurrentSnapshotGroupProjection:
    input: CurrentSnapshotGroupInput
    payload: dict
    content_hash: str


class PipelineSnapshotGroupProjectionOwner:
    def __init__(self, *, claims, store):
        if type(store) is not EcomConsistencyStore:
            raise TypeError('original canonical Store required')
        self._inputs=PipelineSnapshotGroupInputOwner(claims=claims)
        self._claims,self._store=claims,store

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
