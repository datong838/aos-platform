"""Currently applicable snapshot quality in the original Evidence store."""
from dataclasses import dataclass

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_quality import SnapshotQueryQualityMeasurement,ResolvedPopulationPolicy,QualityAssessment,evaluate_quality
from aos_api.data_requirement_quality_evidence import QualityEvidenceInput,QualityEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_analysis_snapshot_fact_query import AnalysisSnapshotFactQuery,_definition
from aos_api.ecommerce_analysis_snapshot_source_evidence import AnalysisSnapshotSourceEvidence,_subject
from aos_api.ecommerce_growth_host_ports import HostTransaction

_POPULATION=dict(identity='snapshot-single-current-shop',revision='1',rule='at-most-one-shop-source-pk-equals-compiled-shop;live-row-only')


def _population_policy():
    return ResolvedPopulationPolicy(version=dict(identity=_POPULATION['identity'],revision='1',
        content_hash='sha256:'+canonical_hash(_POPULATION)),grain='store',population_unit='shop')


@dataclass(frozen=True)
class CurrentSnapshotQuality:
    value: QualityEvidenceInput
    assessment: QualityAssessment


class AnalysisSnapshotQualityEvidence:
    def __init__(self,source):
        if type(source) is not AnalysisSnapshotSourceEvidence:raise TypeError('original complete source Owner required')
        self.source=source
        self.query=AnalysisSnapshotFactQuery(source)
        self.scope=source.analysis.scope

    def _value(self,tx,body,snapshot,evidence,query_ref):
        result=self.query._read(tx,body,evidence,query_ref)
        req=DataRequirementRevisionRecord.model_validate(body['fieldContext']['requirement'])
        if req.grain!='store' or req.purpose_code!='initial_store_analysis':
            raise ValueError('snapshot shop quality applicability differs')
        original=snapshot.quality.assessment.input
        shops=[(mapping,parent['outputRows']) for (_,_,mapping),parent in zip(original.group.members,original.parents)
            if mapping.read_spec.object_type=='Shop']
        if len(shops)!=1:raise ValueError('one original Shop source required')
        mapping,rows=shops[0]
        if len(rows)>1 or any(row['source_pk']!=mapping.shop_id for row in rows):
            raise ValueError('Shop population differs from compiled source scope')
        population=sum(not row['is_deleted'] for row in rows)
        counts=body['fieldContext']['measurement']
        shop=counts['facts']['Shop']
        if shop['counts']['eligibleCount']!=population or shop['unknownRows']:
            raise ValueError('Shop cohort cannot be reinterpreted as population')
        policy=_population_policy()
        definition=_definition()
        measurement=SnapshotQueryQualityMeasurement(tenant=req.tenant,requirement_ref=_subject(body),
            channel_ref=req.channel_ref,entity_ref=req.entity_ref,time_window=req.time_window,cutoff_at=req.cutoff_at,
            grain=req.grain,source_refs=[evidence],query_result_ref=query_ref,
            query_version=dict(identity=definition.metric_id,revision=str(definition.revision),content_hash='sha256:'+definition.content_hash),
            rule_version=dict(identity='installed-snapshot-fact-quality',revision='1',content_hash=counts['fieldPolicyHash']),
            population_policy_version=policy.version,population_unit=policy.population_unit,distinct_population_count=population,
            source_observed_at=original.read_started_at,measured_at=result.created_at,
            facts=[dict(factId=name,**value['counts']) for name,value in sorted(counts['facts'].items())])
        value=QualityEvidenceInput(requirement=req,measurement=measurement,population_policy=policy,
            evaluated_at=result.created_at,actor=body['actor'],run_id=None)
        self._assess_current(tx,value)
        return value

    def _assess_current(self,tx,value):
        now=tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        assessment=evaluate_quality(self.scope,value.requirement,value.measurement,evaluated_at=now,population_policy=value.population_policy)
        if now>=assessment.freshness_expires_at:raise ValueError('snapshot quality source expired')
        return assessment

    def put_current(self,conn,*,evidence_ref,query_ref):
        evidence=InvestigationExactRef.model_validate(evidence_ref);query_ref=InvestigationExactRef.model_validate(query_ref)
        def consume(body,snapshot):
            tx=HostTransaction(conn);value=self._value(tx,body,snapshot,evidence,query_ref)
            store=QualityEvidenceStore(tx,self.scope)
            ref=store.put(value)
            if store.read_exact(ref)!=value:raise ValueError('quality Evidence changed during persistence')
            self._assess_current(tx,value)
            return ref
        return self.source._run_current(conn,evidence_ref=evidence,execute=consume)

    def read_current(self,conn,*,quality_ref,evidence_ref,query_ref):
        evidence=InvestigationExactRef.model_validate(evidence_ref);query_ref=InvestigationExactRef.model_validate(query_ref)
        quality_ref=InvestigationExactRef.model_validate(quality_ref)
        def consume(body,snapshot):
            tx=HostTransaction(conn);expected=self._value(tx,body,snapshot,evidence,query_ref)
            value=QualityEvidenceStore(tx,self.scope).read_exact(quality_ref)
            if value is None:raise LookupError('snapshot quality Evidence unavailable')
            if value!=expected:raise ValueError('snapshot quality differs from current source and fixed query')
            return CurrentSnapshotQuality(value,self._assess_current(tx,value))
        return self.source._run_current(conn,evidence_ref=evidence,execute=consume)
