"""Typed current business contents, not a hydration or fulfillment shortcut."""
from copy import deepcopy
from datetime import datetime
from psycopg import sql
from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_quality_evidence import QualityEvidenceStore
from aos_api.ecommerce_analysis_snapshot_source_evidence import _digest,_subject
from aos_api.ecommerce_analysis_snapshot_quality_evidence import AnalysisSnapshotQualityEvidence
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_business_facts import compile_business_fact_policy,build_business_facts

SCHEMA='aos.analysis-snapshot-business-evidence/v1'
TYPE='analysis-snapshot-business-facts'
PREFIX='evidence-analysis-snapshot-business-'
KEYS={'schemaVersion','tenant','actor','selection','requirementRef','content','factIds','qualityReasons','observedAt','freshnessAt','createdAt'}


def _json(ref):return ref.model_dump(mode='json',by_alias=True,exclude_none=True)


class AnalysisSnapshotBusinessEvidence:
    def __init__(self,source):
        self.quality=AnalysisSnapshotQualityEvidence(source)
        self.source=source;self.scope=source.analysis.scope;self._schema=source._schema

    def _during(self,conn,*,evidence_ref,query_ref,quality_ref,policy_ref,execute):
        evidence=InvestigationExactRef.model_validate(evidence_ref);query=InvestigationExactRef.model_validate(query_ref)
        quality=InvestigationExactRef.model_validate(quality_ref);policy_ref=PipelineExactRef.model_validate(policy_ref)
        def consume(body,snapshot):
            tx=HostTransaction(conn);value=self.quality._value(tx,body,snapshot,evidence,query)
            store=QualityEvidenceStore(tx,self.scope)
            if store.read_exact(quality)!=value:raise ValueError('current exact snapshot quality required')
            current=self.quality._assess_current(tx,value)
            selection=body['selection'];fields_owner=self.source._fields
            relation,cohort_quality,cohort,fields=fields_owner._load_policies(conn,snapshot,
                cohort_ref=selection['cohortPolicyRef'],field_ref=selection['fieldPolicyRef'])
            original=snapshot.quality.assessment.input
            policies=fields_owner._business._snapshot._quality._assessments._policies
            def load():
                return compile_business_fact_policy(policies._load_exported_document(conn,self.scope,original.group,policy_ref,
                    resource_type='SnapshotBusinessFactPolicy'),field_policy=fields)
            policy=load()
            outputs={mapping.read_spec.object_type:parent['outputRows'] for (_,_,mapping),parent in zip(original.group.members,original.parents)}
            content=build_business_facts(outputs,relation,cohort,cohort_quality,fields,policy,
                window_start=value.requirement.time_window.start_at,window_end=value.requirement.time_window.end_at,observed_at=original.read_completed_at)
            covered=[]
            if 'POPULATION_BELOW_MINIMUM' not in current.reasons:
                for fact in value.measurement.facts:
                    if fact.eligible_count and not any(reason.endswith(':'+fact.fact_id) for reason in current.reasons):
                        covered.append(fact.fact_id)
            result=dict(schemaVersion=SCHEMA,tenant=deepcopy(body['tenant']),actor=body['actor'],
                selection=dict(evidenceRef=_json(evidence),queryRef=_json(query),qualityRef=_json(quality),policyRef=_json(policy_ref)),
                requirementRef=_subject(body),content=content,factIds=sorted(covered),qualityReasons=list(current.reasons),
                observedAt=original.read_completed_at.isoformat(),freshnessAt=original.read_started_at.isoformat(),
                createdAt=value.measurement.measured_at.isoformat())
            digest=_digest(result)
            outcome=execute(result)
            if _digest(result)!=digest:raise ValueError('business content changed during consumption')
            if load()!=policy or store.read_exact(quality)!=value:raise ValueError('business dependencies changed during consumption')
            self.quality._assess_current(tx,value)
            return outcome
        return self.source._run_current(conn,evidence_ref=evidence,execute=consume)

    def put_current(self,conn,*,evidence_ref,query_ref,quality_ref,policy_ref):
        return self._during(conn,evidence_ref=evidence_ref,query_ref=query_ref,quality_ref=quality_ref,policy_ref=policy_ref,
            execute=lambda body:self._persist(conn,body))

    def read_current(self,conn,*,reference):
        return self.run_current(conn,reference=reference,execute=lambda body:deepcopy(body))

    def run_current(self,conn,*,reference,execute):
        if not callable(execute):raise TypeError('synchronous business evidence consumer required')
        with conn.transaction():
            body=self._record(conn,reference);selection=body['selection']
            def consume(current):
                if current!=body or self._record(conn,reference)!=body:raise ValueError('business evidence differs from current sources')
                result=execute(current)
                if self._record(conn,reference)!=body:raise ValueError('business Evidence changed during consumption')
                return result
            return self._during(conn,evidence_ref=selection['evidenceRef'],query_ref=selection['queryRef'],
                quality_ref=selection['qualityRef'],policy_ref=selection['policyRef'],execute=consume)

    def _persist(self,conn,body):
        digest=_digest(body)[7:]
        reference=InvestigationExactRef(resource_type='Evidence',resource_id=PREFIX+digest,revision=1,content_hash='sha256:'+digest)
        conn.execute(sql.SQL('''INSERT INTO {}(org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
            observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,'{{}}'::jsonb,%s,%s,%s)
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING''').format(sql.Identifier(self._schema,'aip_evidence')),
            (*self.scope.key,reference.resource_id,TYPE,Jsonb(body['requirementRef']),TYPE,body['selection']['evidenceRef']['resourceId'],
                datetime.fromisoformat(body['observedAt']),datetime.fromisoformat(body['freshnessAt']),digest,Jsonb(body),body['actor'],
                datetime.fromisoformat(body['createdAt'])))
        if self._record(conn,reference)!=body:raise ValueError('business evidence persistence differs')
        return reference

    def _record(self,conn,reference):
        ref=InvestigationExactRef.model_validate(reference)
        if (ref.resource_type!='Evidence' or type(ref.revision) is not int or ref.revision!=1 or ref.receipt_id is not None
            or ref.resource_id!=PREFIX+ref.content_hash[7:]):raise ValueError('exact business evidence reference required')
        row=conn.execute(sql.SQL('''SELECT e.*,EXISTS(SELECT 1 FROM {} r WHERE r.org_id=e.org_id AND r.project_id=e.project_id
            AND r.evidence_id=e.evidence_id AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM {} e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s''').format(
                sql.Identifier(self._schema,'aip_evidence_revoke_event'),sql.Identifier(self._schema,'aip_evidence')),
            (*self.scope.key,ref.resource_id)).fetchone()
        if row is None:raise LookupError('business evidence unavailable')
        if row['revoked']:raise ValueError('business evidence revoked')
        body=row['payload']
        if (type(body) is not dict or set(body)!=KEYS or body['schemaVersion']!=SCHEMA
            or body['tenant']!=dict(orgId=self.scope.org_id,projectId=self.scope.project_id)
            or body['actor']!=self.source.analysis.source.actor or _digest(body)!=ref.content_hash):
            raise ValueError('business evidence content differs')
        expected=dict(org_id=self.scope.org_id,project_id=self.scope.project_id,evidence_id=ref.resource_id,run_id=None,
            evidence_type=TYPE,subject_ref=body['requirementRef'],source_type=TYPE,source_ref=body['selection']['evidenceRef']['resourceId'],
            observed_at=datetime.fromisoformat(body['observedAt']),freshness_at=datetime.fromisoformat(body['freshnessAt']),
            content_hash=ref.content_hash[7:],redaction={},created_by=body['actor'],created_at=datetime.fromisoformat(body['createdAt']))
        if any(row.get(key)!=value for key,value in expected.items()):raise ValueError('business evidence columns differ')
        return body
