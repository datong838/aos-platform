"""Complete snapshot provenance in canonical Evidence, requiring current revalidation."""
from copy import deepcopy
from datetime import datetime
import json
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_fact_quality_context import AnalysisFactQualityContext
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_projection_owner import PipelineSnapshotGroupProjectionOwner

SCHEMA='aos.analysis-snapshot-source-evidence/v1'
TYPE='analysis-snapshot-fact-source'
PREFIX='evidence-analysis-snapshot-source-'
CALL_REFS={'receipt_ref':'receiptRef','policy_ref':'relationshipPolicyRef','quality_ref':'qualityPolicyRef',
    'cohort_ref':'cohortPolicyRef','field_ref':'fieldPolicyRef'}
BODY_KEYS={'schemaVersion','tenant','actor','selection','fieldContext','inputManifest','members','projection','purpose','factIds'}


def _digest(body):
    if len(json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())>2_000_000:
        raise ValueError('complete source evidence exceeds size limit; truncation forbidden')
    return canonical_sha256(body)


def _subject(body):
    requirement=body['fieldContext']['requirement']
    ref=InvestigationExactRef(resource_type='DataRequirementRevision',resource_id=requirement['requirementId'],
        revision=requirement['revision'],content_hash=requirement['contentHash'])
    return ref.model_dump(mode='json',by_alias=True,exclude_none=True)


class AnalysisSnapshotSourceEvidence:
    def __init__(self, analysis, *, store):
        self._fields=AnalysisFactQualityContext(analysis)
        self.analysis=analysis
        self._claims=analysis.source.reader._journal._claims
        self._projections=PipelineSnapshotGroupProjectionOwner(claims=self._claims,store=store)
        self._schema=self._claims._journal.schema

    def _bound(self, conn, *, execute, **refs):
        if set(refs)!=set(CALL_REFS):raise ValueError('exact original provenance selection required')
        def consume_fields(fields,snapshot):
            source=snapshot.quality.assessment.input
            bindings=tuple((ref,parent['runId']) for (ref,_,_),parent in zip(source.group.members,source.parents))
            def consume_projection(projection):
                if (projection.input.manifest_hash!=source.manifest_hash
                    or projection.input.claim.request_hash!=source.claim.request_hash
                    or projection.input.read_started_at!=source.read_started_at
                    or projection.input.read_completed_at!=source.read_completed_at):
                    raise ValueError('field and current projection sources differ')
                selection={label:(deepcopy(value) if name=='receipt_ref' else
                    PipelineExactRef.model_validate(value).model_dump(mode='json',by_alias=True))
                    for name,label in CALL_REFS.items() for value in [refs[name]]}
                body=dict(schemaVersion=SCHEMA,tenant=dict(orgId=self.analysis.scope.org_id,projectId=self.analysis.scope.project_id),
                    actor=self.analysis.source.actor,selection=selection,fieldContext=deepcopy(fields),
                    inputManifest=deepcopy(source.manifest),
                    members=[dict(controlRef=ref.model_dump(mode='json',by_alias=True),
                        control=draft.model_dump(mode='json',by_alias=True)) for ref,draft,_ in source.group.members],
                    projection=deepcopy(projection.payload),purpose='complete-snapshot-source-provenance-only',factIds=[])
                digest=_digest(body)
                result=execute(body)
                _reject_deferred(result)
                if _digest(body)!=digest:raise ValueError('source evidence changed during consumption')
                return result
            return self._projections.run_current(conn,scope=self.analysis.scope,group_id=source.claim.group_id,
                actor=self.analysis.source.actor,bindings=bindings,execute=consume_projection)
        return self._fields._run(conn,**refs,execute=consume_fields)

    def capture_current(self, conn, **refs):
        with conn.transaction():
            return self._bound(conn,**refs,execute=lambda body:self._persist(conn,body))

    def run_current(self, conn, *, evidence_ref, execute):
        if not callable(execute):raise TypeError('synchronous source evidence consumer required')
        with conn.transaction():
            saved=self._record(conn,evidence_ref)
            refs={name:saved['selection'][label] for name,label in CALL_REFS.items()}
            def consume(body):
                if body!=saved:raise ValueError('persisted source evidence differs from current original sources')
                result=execute(body)
                _reject_deferred(result)
                if self._record(conn,evidence_ref)!=saved:raise ValueError('source evidence changed')
                return result
            return self._bound(conn,**refs,execute=consume)

    def _persist(self, conn, body):
        digest=_digest(body)[7:]
        ref=InvestigationExactRef(resource_type='Evidence',resource_id=PREFIX+digest,revision=1,content_hash='sha256:'+digest)
        scope=self.analysis.scope;projection=body['projection']
        conn.execute(sql.SQL('''INSERT INTO {}(org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,
            source_type,source_ref,observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,'{{}}'::jsonb,%s,%s,clock_timestamp())
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING''').format(sql.Identifier(self._schema,'aip_evidence')),
            (*scope.key,ref.resource_id,TYPE,Jsonb(_subject(body)),TYPE,projection['groupId'],
                datetime.fromisoformat(projection['readCompletedAt']),datetime.fromisoformat(projection['readStartedAt']),
                digest,Jsonb(body),body['actor']))
        if self._record(conn,ref)!=body:raise ValueError('source evidence persistence drifted')
        return ref

    def _record(self, conn, reference):
        ref=InvestigationExactRef.model_validate(reference)
        if (ref.resource_type!='Evidence' or type(ref.revision) is not int or ref.revision!=1 or ref.receipt_id is not None
            or ref.resource_id!=PREFIX+ref.content_hash[7:]):raise ValueError('exact complete source evidence reference required')
        row=conn.execute(sql.SQL('''SELECT e.*,EXISTS(SELECT 1 FROM {} r WHERE r.org_id=e.org_id
            AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM {} e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s''').format(
                sql.Identifier(self._schema,'aip_evidence_revoke_event'),sql.Identifier(self._schema,'aip_evidence')),
            (*self.analysis.scope.key,ref.resource_id)).fetchone()
        if row is None:raise LookupError('source evidence unavailable')
        if row['revoked']:raise ValueError('source evidence revoked')
        body=row['payload']
        if (type(body) is not dict or set(body)!=BODY_KEYS or body['schemaVersion']!=SCHEMA
            or body['purpose']!='complete-snapshot-source-provenance-only' or body['factIds']!=[]
            or body['tenant']!=dict(orgId=self.analysis.scope.org_id,projectId=self.analysis.scope.project_id)
            or body['actor']!=self.analysis.source.actor or type(body['selection']) is not dict
            or set(body['selection'])!=set(CALL_REFS.values()) or _digest(body)!=ref.content_hash):
            raise ValueError('source evidence body or digest drifted')
        projection=body['projection'];observed=datetime.fromisoformat(projection['readCompletedAt'])
        started=datetime.fromisoformat(projection['readStartedAt'])
        expected=dict(org_id=self.analysis.scope.org_id,project_id=self.analysis.scope.project_id,evidence_id=ref.resource_id,
            run_id=None,evidence_type=TYPE,subject_ref=_subject(body),source_type=TYPE,source_ref=projection['groupId'],
            observed_at=observed,freshness_at=started,content_hash=ref.content_hash[7:],redaction={},created_by=body['actor'])
        recorded=row['created_at']
        if (any(row.get(k)!=v for k,v in expected.items()) or type(recorded) is not datetime
            or recorded.utcoffset() is None or recorded<observed):raise ValueError('source evidence columns drifted')
        return body
