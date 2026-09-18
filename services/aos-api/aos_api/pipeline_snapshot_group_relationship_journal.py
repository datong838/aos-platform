"""Immutable relationship preparation from an in-transaction current assessment."""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_snapshot_group_assessment_owner import (
    CurrentSnapshotGroupAssessment,CurrentSnapshotGroupAssessmentMaterial,
    PipelineSnapshotGroupAssessmentOwner,assessment_payload,
)
from aos_api.pipeline_snapshot_relationships import SnapshotRelationshipAssessment
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

    def prepare_or_materialize(self,conn,**args):
        """Return a replay, or immutable recovery material for lock-free assessment."""
        _require_transaction(conn)
        if self._assessments._inputs._claims._recovery is None:
            return self.prepare(conn,**args)
        current=self._assessments.materialize_current(conn,**args)
        saved=self._load(conn,current.input.claim.scope,UUID(current.input.claim.group_id))
        return current if saved is None else self._preparation(self._restore(current,saved),saved,False)

    def prepare_assessed_current(self,conn,current,**args):
        """Persist an outside assessment only after exact current material revalidation."""
        _require_transaction(conn)
        if (self._assessments._inputs._claims._recovery is None
                or type(current) is not CurrentSnapshotGroupAssessment):
            raise TypeError('saved recovery assessment required')
        reloaded=self._assessments.materialize_current(conn,**args)
        if (reloaded.input!=current.input or reloaded.policy_ref!=current.policy_ref
                or reloaded.policy.content_hash!=current.assessment.policy_hash):
            raise IngressJournalConflict('RELATIONSHIP_ASSESSMENT_MATERIAL_CHANGED')
        if observed_rows_hash([assessment_payload(current)])!=current.content_hash:
            raise IngressJournalConflict('RELATIONSHIP_ASSESSMENT_CHANGED')
        return self._consume(conn,current,create=True)

    def read_current(self,conn,**args):
        return self._operate(conn,args,create=False)

    def read_completed_current(self,conn,**args):
        return self._operate(conn,args,create=False,completed_read=True)

    def run_current(self,conn,*,execute,**args):
        return self._run_current(conn,args,execute=execute,completed_read=False)

    def run_completed_current(self,conn,*,execute,**args):
        return self._run_current(conn,args,execute=execute,completed_read=True)

    def _load(self,conn,scope,group_id):
        table=sql.Identifier(self._schema,'pipeline_snapshot_group_relationship')
        with conn.cursor(row_factory=dict_row) as cursor:
            return cursor.execute(sql.SQL('SELECT input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment FROM {} WHERE org_id=%s AND project_id=%s AND group_id=%s').format(table),(*scope.key,group_id)).fetchone()

    @staticmethod
    def _restore(material,saved):
        try:
            payload=saved['assessment']
            links=tuple(dict(link,source_updated_at=datetime.fromisoformat(link['source_updated_at']))
                        for link in payload['candidateLinks'])
            assessment=SnapshotRelationshipAssessment(payload['policyHash'],links,payload['counts'])
            current=CurrentSnapshotGroupAssessment(material.input,material.policy_ref,assessment,saved['assessment_hash'])
        except (KeyError,TypeError,ValueError) as error:
            raise IngressJournalConflict('RELATIONSHIP_PREPARATION_DRIFT') from error
        if (saved['input_manifest_hash']!=material.input.manifest_hash
                or saved['policy_ref']!=material.policy_ref.model_dump(mode='json',by_alias=True)
                or saved['policy_hash']!=material.policy.content_hash
                or assessment_payload(current)!=payload
                or observed_rows_hash([payload])!=saved['assessment_hash']):
            raise IngressJournalConflict('RELATIONSHIP_PREPARATION_DRIFT')
        return current

    def _run_current(self,conn,args,*,execute,completed_read):
        if not callable(execute):raise TypeError('synchronous assessment consumer required')
        if self._assessments._inputs._claims._recovery is None:
            read=self._assessments.run_completed_current if completed_read else self._assessments.run_current
            return read(conn,**args,execute=execute)
        material=self._assessments.materialize_current(conn,**args,completed_read=completed_read)
        saved=self._load(conn,material.input.claim.scope,UUID(material.input.claim.group_id))
        if saved is None:raise LookupError('relationship preparation required')
        current=self._restore(material,saved)
        result=execute(current);_reject_deferred(result)
        if self._assessments.materialize_current(conn,**args,completed_read=completed_read)!=material:
            raise IngressJournalConflict('GROUP_INPUT_CHANGED_DURING_CONSUMPTION')
        if self._restore(material,self._load(conn,material.input.claim.scope,
                UUID(material.input.claim.group_id)))!=current:
            raise IngressJournalConflict('RELATIONSHIP_PREPARATION_DRIFT')
        return result

    @staticmethod
    def _preparation(current,saved,created):
        return SnapshotRelationshipPreparation(current.content_hash,saved['assessment'],created)

    def _consume(self,conn,current,*,create):
        payload=assessment_payload(current);digest=current.content_hash
        if observed_rows_hash([payload])!=digest:raise IngressJournalConflict('RELATIONSHIP_ASSESSMENT_HASH_DRIFT')
        scope=current.input.claim.scope;group_id=UUID(current.input.claim.group_id)
        saved=self._load(conn,scope,group_id)
        if saved is not None:
            restored=self._restore(CurrentSnapshotGroupAssessmentMaterial(
                current.input,current.policy_ref,
                self._assessments._policies._load(conn,scope,current.input.group,current.policy_ref)),saved)
            if restored!=current:raise IngressJournalConflict('RELATIONSHIP_PREPARATION_DRIFT')
            return self._preparation(restored,saved,False)
        if not create:raise LookupError('relationship preparation required')
        table=sql.Identifier(self._schema,'pipeline_snapshot_group_relationship')
        with conn.cursor(row_factory=dict_row) as cursor:
            cursor.execute(sql.SQL('INSERT INTO {} (org_id,project_id,group_id,input_manifest_hash,policy_ref,policy_hash,assessment_hash,assessment) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)').format(table),
                (*scope.key,group_id,current.input.manifest_hash,Jsonb(payload['policyRef']),current.assessment.policy_hash,digest,Jsonb(payload)))
        return SnapshotRelationshipPreparation(digest,payload,True)

    def _operate(self,conn,args,*,create,completed_read=False):
        if completed_read and create:raise ValueError('completed input cannot prepare relationships')
        def consume(current):
            return self._consume(conn,current,create=create)
        return self._run_current(conn,args,execute=consume,completed_read=completed_read)
