"""Deterministic joint field/reference counts; not a quality authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_source_selection import _identifier
from aos_api.pipeline_snapshot_relationships import _key
from aos_api.pipeline_snapshot_relationship_quality import measure_relationship_quality, reference_row_issues
from aos_api.pipeline_snapshot_business_cohort import select_business_cohort

KINDS = {'nonblank-string','positive-id','positive-integer','nonnegative-integer','nonnegative-number','boolean','timestamp','enum'}


@dataclass(frozen=True)
class FactField:
    property_name: str
    kind: str
    values: tuple = ()


@dataclass(frozen=True)
class FactQualityPolicy:
    cohort_policy_hash: str
    quality_policy_hash: str
    purpose_code: str
    facts: tuple
    content_hash: str


def compile_fact_quality_policy(document, *, relationship_policy, cohort_policy, quality_policy):
    if (type(document) is not dict
        or set(document) != {'schemaVersion','cohortPolicyHash','relationshipQualityPolicyHash','purposeCode','facts'}
        or document['schemaVersion'] != 'aos.snapshot-fact-quality/v1'
        or document['cohortPolicyHash'] != cohort_policy.content_hash
        or document['relationshipQualityPolicyHash'] != quality_policy.content_hash
        or cohort_policy.relationship_policy_hash != relationship_policy.content_hash
        or quality_policy.relationship_policy_hash != relationship_policy.content_hash
        or document['purposeCode'] != cohort_policy.purpose_code
        or not any(p.purpose_code == document['purposeCode'] for p in quality_policy.purposes)):
        raise ValueError('exact fact quality policy bindings required')
    facts = document['facts']; expected = set(relationship_policy.object_types)
    if type(facts) is not list or len(facts) != len(expected):
        raise ValueError('complete fact policies required')
    compiled=[];seen=set()
    for fact in facts:
        if type(fact) is not dict or set(fact) != {'objectType','fields'}:
            raise ValueError('exact fact fields required')
        ot = _identifier(fact['objectType']); fields = fact['fields']
        if ot not in expected or ot in seen or type(fields) is not list or not 1 <= len(fields) <= 32:
            raise ValueError('unique fact and nonempty bounded fields required')
        seen.add(ot); names=set(); rules=[]
        for field in fields:
            if type(field) is not dict or type(field.get('kind')) is not str or field['kind'] not in KINDS:
                raise ValueError('fixed field predicate required')
            kind=field['kind']
            if set(field) != ({'property','kind','values'} if kind == 'enum' else {'property','kind'}):
                raise ValueError('exact field predicate shape required')
            name=_identifier(field['property'])
            if name in names:raise ValueError('unique field required')
            names.add(name); values=field.get('values',[])
            if kind == 'enum' and (type(values) is not list or not 1 <= len(values) <= 64
                or any(type(v) not in (str,int) or (type(v) is str and (not v.strip() or len(v)>200)) for v in values)
                or len(set((type(v),v) for v in values)) != len(values)):
                raise ValueError('bounded canonical enum values required')
            rules.append(FactField(name,kind,tuple(values)))
        compiled.append((ot,tuple(rules)))
    return FactQualityPolicy(cohort_policy.content_hash,quality_policy.content_hash,document['purposeCode'],
        tuple(compiled),'sha256:'+_digest(document))


def _valid(value, field, observed_at):
    if field.kind == 'nonblank-string': return type(value) is str and bool(value.strip()) and len(value)<=4096
    if field.kind == 'positive-id':
        try: _key(value); return True
        except ValueError: return False
    if field.kind == 'nonnegative-integer': return type(value) is int and 0<=value<=9_223_372_036_854_775_807
    if field.kind == 'positive-integer': return type(value) is int and 0<value<=9_223_372_036_854_775_807
    if field.kind == 'nonnegative-number':
        return type(value) in (int,float) and 0<=value<=9_223_372_036_854_775_807 and math.isfinite(value)
    if field.kind == 'boolean': return type(value) is bool
    if field.kind == 'enum': return any(type(value) is type(v) and value==v for v in field.values)
    if field.kind == 'timestamp':
        if type(value) is not str:return False
        try: timestamp=datetime.fromisoformat(value)
        except ValueError:return False
        return timestamp.utcoffset() is not None and datetime(1970,1,1,tzinfo=timezone.utc)<timestamp<=observed_at
    return False


def measure_fact_quality(outputs, relationship_policy, cohort_policy, quality_policy, field_policy, *, window_start, window_end, observed_at):
    measure_relationship_quality(outputs,relationship_policy,quality_policy,observed_at=observed_at)
    cohort=select_business_cohort(outputs,relationship_policy,cohort_policy,
        window_start=window_start,window_end=window_end,observed_at=observed_at)
    if type(field_policy) is not FactQualityPolicy:raise ValueError('compiled field policy required')
    document=dict(schemaVersion='aos.snapshot-fact-quality/v1',cohortPolicyHash=field_policy.cohort_policy_hash,
        relationshipQualityPolicyHash=field_policy.quality_policy_hash,purposeCode=field_policy.purpose_code,
        facts=[dict(objectType=ot,fields=[dict(property=f.property_name,kind=f.kind,
            **({'values':list(f.values)} if f.kind=='enum' else {})) for f in fields]) for ot,fields in field_policy.facts])
    if compile_fact_quality_policy(document,relationship_policy=relationship_policy,
        cohort_policy=cohort_policy,quality_policy=quality_policy) != field_policy:
        raise ValueError('compiled fact policy differs')
    purpose=next(p for p in quality_policy.purposes if p.purpose_code==field_policy.purpose_code)
    required={name for name,kind in purpose.rules if kind=='required'}
    indexed={ot:{_key(row['source_pk']):row for row in rows} for ot,rows in outputs.items()}
    facts={}
    for ot,fields in field_policy.facts:
        selected=cohort.cohorts[ot]; unknown=dict(selected.unknown)
        field_issues={f.property_name:0 for f in fields}
        rules=[rule for rule in relationship_policy.rules if rule.row_type==ot]
        relationship_issues={rule.link_type:0 for rule in rules};valid=0
        for key in (*selected.included_keys,*unknown):
            row=indexed[ot][key];bad=key in unknown
            for field in fields:
                invalid=not _valid(row['properties'].get(field.property_name),field,observed_at)
                field_issues[field.property_name]+=int(invalid);bad=bad or invalid
            for rule in rules:
                invalid=bool(reference_row_issues(row,rule,indexed))
                relationship_issues[rule.link_type]+=int(invalid)
                bad=bad or (invalid and rule.link_type in required)
            valid+=int(not bad)
        facts[ot]=dict(counts=dict(observedCount=selected.observed_count,eligibleCount=selected.eligible_count,
            validCount=valid,excludedCount=len(selected.excluded),duplicateCount=0),
            unknownRows=len(unknown),fieldIssues=field_issues,relationshipIssues=relationship_issues)
    return dict(fieldPolicyHash=field_policy.content_hash,cohortPolicyHash=cohort_policy.content_hash,
        relationshipQualityPolicyHash=quality_policy.content_hash,purposeCode=field_policy.purpose_code,facts=facts)
