"""Policy-selected public facts from complete inputs; no source/effect authority."""
from dataclasses import dataclass
import json

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_snapshot_relationships import _key
from aos_api.pipeline_snapshot_business_cohort import select_business_cohort
from aos_api.pipeline_snapshot_fact_quality import FactQualityPolicy,measure_fact_quality,_valid


@dataclass(frozen=True)
class BusinessFactPolicy:
    field_policy_hash: str
    purpose_code: str
    facts: tuple
    content_hash: str


def compile_business_fact_policy(document,*,field_policy):
    if (type(field_policy) is not FactQualityPolicy or type(document) is not dict
        or set(document)!={'schemaVersion','fieldPolicyHash','purposeCode','facts'}
        or document['schemaVersion']!='aos.snapshot-business-facts/v1'
        or document['fieldPolicyHash']!=field_policy.content_hash or document['purposeCode']!=field_policy.purpose_code):
        raise ValueError('exact bound business fact policy required')
    allowed={ot:{field.property_name:field for field in fields} for ot,fields in field_policy.facts}
    facts=document['facts']
    if type(facts) is not list or len(facts)!=len(allowed):raise ValueError('complete fact content policy required')
    compiled=[];seen=set()
    for fact in facts:
        if type(fact) is not dict or set(fact)!={'objectType','mode','fields'}:
            raise ValueError('exact fact content fields required')
        ot=fact['objectType'];mode=fact['mode'];fields=fact['fields']
        if (type(ot) is not str or ot not in allowed or ot in seen or mode not in ('records','group-counts')
            or type(fields) is not list or not 1<=len(fields)<=16
            or any(type(f) is not str or f not in allowed[ot] for f in fields) or len(set(fields))!=len(fields)):
            raise ValueError('bounded explicit public fields required')
        if mode=='group-counts' and any(allowed[ot][f].kind not in ('enum','boolean','nonnegative-integer','positive-integer') for f in fields):
            raise ValueError('grouping free text or non-discrete fields is forbidden')
        seen.add(ot);compiled.append((ot,mode,tuple(fields)))
    return BusinessFactPolicy(field_policy.content_hash,field_policy.purpose_code,tuple(compiled),'sha256:'+_digest(document))


def _document(policy):
    if type(policy) is not BusinessFactPolicy:raise ValueError('compiled business fact policy required')
    return dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash=policy.field_policy_hash,purposeCode=policy.purpose_code,
        facts=[dict(objectType=ot,mode=mode,fields=list(fields)) for ot,mode,fields in policy.facts])


def build_business_facts(outputs,relationship_policy,cohort_policy,quality_policy,field_policy,policy,*,window_start,window_end,observed_at):
    # Original validators verify the complete inputs and all bound policies.
    measured=measure_fact_quality(outputs,relationship_policy,cohort_policy,quality_policy,field_policy,
        window_start=window_start,window_end=window_end,observed_at=observed_at)
    selection=select_business_cohort(outputs,relationship_policy,cohort_policy,
        window_start=window_start,window_end=window_end,observed_at=observed_at)
    if compile_business_fact_policy(_document(policy),field_policy=field_policy)!=policy:
        raise ValueError('compiled business fact policy differs')
    definitions={ot:{field.property_name:field for field in fields} for ot,fields in field_policy.facts}
    facts={}
    for ot,mode,fields in policy.facts:
        cohort=selection.cohorts[ot];unknown=dict(cohort.unknown)
        included=set(cohort.included_keys);eligible=included|set(unknown)
        current=measured['facts'][ot]
        value=dict(mode=mode,counts=dict(**current['counts'],unknownRows=current['unknownRows']),
            fieldIssues=dict(current['fieldIssues']),relationshipIssues=dict(current['relationshipIssues']),
            exclusionReasons={reason:sum(r==reason for _,r in cohort.excluded) for reason in sorted({r for _,r in cohort.excluded})})
        selected=sorted((r for r in outputs[ot] if _key(r['source_pk']) in eligible),key=lambda r:_key(r['source_pk']))
        if len(selected)>1000:raise ValueError('business facts exceed complete record limit; truncation forbidden')
        if mode=='records':
            records=[]
            for source in selected:
                key=_key(source['source_pk']);properties=source['properties'];invalid=[];values={}
                for name in fields:
                    valid=_valid(properties.get(name),definitions[ot][name],observed_at)
                    values[name]=properties.get(name) if valid else None
                    if not valid:invalid.append(name)
                records.append(dict(sourceKeyHash='sha256:'+_digest([ot,key]),membership='unknown' if key in unknown else 'known',
                    membershipIssues=list(unknown.get(key,())),values=values,invalidFields=invalid))
            value['records']=records
        else:
            groups={}
            for name in fields:
                buckets={'known':{},'unknown':{}};invalid={'known':0,'unknown':0}
                for source in selected:
                    membership='unknown' if _key(source['source_pk']) in unknown else 'known'
                    raw=source['properties'].get(name)
                    if not _valid(raw,definitions[ot][name],observed_at):invalid[membership]+=1;continue
                    key=json.dumps(raw,ensure_ascii=False,allow_nan=False)
                    buckets[membership][key]=buckets[membership].get(key,0)+1
                    if len(buckets[membership])>256:raise ValueError('business group limit exceeded; truncation forbidden')
                groups[name]={membership:[dict(value=json.loads(key),count=count) for key,count in sorted(values.items())]
                    for membership,values in buckets.items()}
                groups[name].update(invalidKnown=invalid['known'],invalidUnknown=invalid['unknown'])
            value['groups']=groups
        facts[ot]=value
    result=dict(schemaVersion='aos.snapshot-business-fact-content/v1',policyHash=policy.content_hash,
        purposeCode=policy.purpose_code,timeWindow=dict(startAt=window_start.isoformat(),endAt=window_end.isoformat()),
        observedAt=observed_at.isoformat(),facts=facts,factIds=[],
        limitations=['Selected public as-observed content; no sales, profit or causal inference',
            'Source key hashes are locators, not anonymization or domain authority',
            'Source authentication and current permission must be supplied by the original Owner'])
    if len(json.dumps(result,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())>2_000_000:
        raise ValueError('business facts exceed complete payload limit; truncation forbidden')
    return result
