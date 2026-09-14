"""Strict installed-policy syntax; never a SourceReadiness decision."""
from dataclasses import dataclass
import re

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_snapshot_fact_quality import FactQualityPolicy
from aos_api.pipeline_snapshot_relationship_quality import SnapshotRelationshipQualityPolicy
from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES


@dataclass(frozen=True)
class SnapshotReadinessPolicy:
    field_policy_hash: str
    relationship_quality_policy_hash: str
    purpose_code: str
    freshness_mode: str
    reconciliation_mode: str
    query_binding_id: str
    sources: tuple[tuple[str, str], ...]
    content_hash: str


def compile_snapshot_readiness_policy(document, *, field_policy, quality_policy):
    if type(field_policy) is not FactQualityPolicy or type(quality_policy) is not SnapshotRelationshipQualityPolicy:
        raise TypeError('original compiled field and relationship quality policies required')
    keys={'schemaVersion','fieldPolicyHash','relationshipQualityPolicyHash','purposeCode',
          'freshnessMode','reconciliationMode','queryBindingId','sources'}
    if (type(document) is not dict or set(document)!=keys
            or document['schemaVersion']!='aos.snapshot-readiness-policy/v1'
            or document['fieldPolicyHash']!=field_policy.content_hash
            or document['relationshipQualityPolicyHash']!=quality_policy.content_hash
            or field_policy.quality_policy_hash!=quality_policy.content_hash
            or document['purposeCode']!='initial_store_analysis'
            or field_policy.purpose_code!=document['purposeCode']
            or not any(p.purpose_code==document['purposeCode'] for p in quality_policy.purposes)
            or document['freshnessMode']!='requirement-oldest-observation'
            or document['reconciliationMode']!='current-original-base-and-derived'):
        raise ValueError('exact snapshot readiness policy bindings required')
    binding=document['queryBindingId']
    if type(binding) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}',binding) is None:
        raise ValueError('canonical bounded query binding identity required')
    expected=tuple((s.pipeline_id,s.object_type) for s in CANONICAL_QYH_SOURCES)
    sources=document['sources']
    if (type(sources) is not list or len(sources)!=len(expected)
            or any(type(s) is not dict or set(s)!={'pipelineId','objectType'} for s in sources)
            or tuple((s['pipelineId'],s['objectType']) for s in sources)!=expected):
        raise ValueError('ordered complete original P01-P12 source set required')
    facts=tuple(name for name,_ in field_policy.facts)
    if len(facts)!=len(expected) or set(facts)!={name for _,name in expected}:
        raise ValueError('original quality policy must cover every source exactly once')
    return SnapshotReadinessPolicy(field_policy.content_hash,quality_policy.content_hash,document['purposeCode'],
        document['freshnessMode'],document['reconciliationMode'],binding,expected,'sha256:'+_digest(document))
