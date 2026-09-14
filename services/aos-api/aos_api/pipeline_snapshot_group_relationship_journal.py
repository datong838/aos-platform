"""Immutable relationship preparation from an in-transaction current assessment."""
from dataclasses import dataclass
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.pipeline_snapshot_group_assessment_owner import PipelineSnapshotGroupAssessmentOwner,assessment_payload
from aos_api.source_read_observation import observed_rows_hash


@dataclass(frozen=True)
class SnapshotRelationshipPreparation:
    assessment_hash: str
    payload: dict
    created: bool


class PipelineSnapshotGroupRelationshipJournal:
    def __init__(self,*,claims):
        self._assessments=PipelineSnapshotGroupAssessmentOwner(claims=claims)
        self._schema=claims._journal.schema

    def prepare(self,conn,**args):
        _require_transaction(conn)
        with conn.transaction():return self._operate(conn,args,create=True)

    def read_current(self,conn,**args):
        return self._operate(conn,args,create=False)

    def _operate(self,conn,args,*,create):
        def consume(current):
            payload=assessment_payload(current);digest=current.content_hash
            if observed_rows_hash([payload])!=digest:raise IngressJournalConflict('RELATIONSHIP_ASSESSMENT_HASH_DRIFT')
            scope=current.input.claim.scope;group_id=UUID(current.input.claim.group_id)
            table=sql.Identifier(self._schema,'pipeline_snapshot_group_relationship')
            with conn.cursor(row_factory=dict_row) as cursor:
                saved=cursor.execute(sql.SQL('SELECT input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(table),(*scope.key,group_id)).fetchone()
                if saved is not None:
                    if (saved['input_manifest_hash']!=current.input.manifest_hash or saved['policy_ref']!=payload['policyRef']
                            or saved['policy_hash']!=current.assessment.policy_hash or saved['assessment_hash']!=digest
                            or saved['assessment']!=payload or observed_rows_hash([saved['assessment']])!=digest):
                        raise IngressJournalConflict('RELATIONSHIP_PREPARATION_DRIFT')
                    return SnapshotRelationshipPreparation(digest,saved['assessment'],False)
                if not create:raise LookupError('relationship preparation required')
                cursor.execute(sql.SQL('INSERT INTO {} (org_id,project_id,group_id,input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)').format(table),
                    (*scope.key,group_id,current.input.manifest_hash,Jsonb(payload['policyRef']),current.assessment.policy_hash,digest,Jsonb(payload)))
            return SnapshotRelationshipPreparation(digest,payload,True)
        return self._assessments.run_current(conn,**args,execute=consume)
