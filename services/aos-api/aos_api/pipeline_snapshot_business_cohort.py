"""Declarative as-observed business membership; unknowns retain their denominator.

This pure selector neither authenticates rows nor issues quality/fact evidence.
The calling Owner must bind policies, original cohort, purpose and time window.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import re

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_source_selection import _identifier
from aos_api.pipeline_snapshot_relationships import SnapshotRelationshipPolicy, assess_snapshot_relationships, _key


@dataclass(frozen=True)
class StatusSelection:
    property_name: str
    known: tuple[str, ...]
    accepted: tuple[str, ...]


@dataclass(frozen=True)
class BusinessCohortRule:
    object_type: str
    basis: str
    status_filter: StatusSelection | None
    time_property: str | None = None
    parent_type: str | None = None
    reference_property: str | None = None


@dataclass(frozen=True)
class BusinessCohortPolicy:
    relationship_policy_hash: str
    purpose_code: str
    rules: tuple[BusinessCohortRule, ...]
    content_hash: str


@dataclass(frozen=True)
class ObjectBusinessCohort:
    included_keys: tuple[str, ...]
    unknown: tuple[tuple[str, tuple[str, ...]], ...]
    excluded: tuple[tuple[str, str], ...]

    @property
    def eligible_count(self):
        return len(self.included_keys)+len(self.unknown)

    @property
    def observed_count(self):
        return self.eligible_count+len(self.excluded)


@dataclass(frozen=True)
class BusinessCohortSelection:
    policy_hash: str
    cohorts: dict[str, ObjectBusinessCohort]


def _status(document):
    if document is None:
        return None
    if type(document) is not dict or set(document) != {'property','known','accepted'}:
        raise ValueError('explicit status selection required')
    field=_identifier(document['property'])
    known,accepted=document['known'],document['accepted']
    for values in (known,accepted):
        if (type(values) is not list or not 1<=len(values)<=64
            or any(type(v) is not str or re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}',v) is None for v in values)
            or len(set(values))!=len(values)):
            raise ValueError('bounded unique status names required')
    if not set(accepted)<=set(known):
        raise ValueError('accepted statuses must be known')
    return StatusSelection(field,tuple(known),tuple(accepted))


def compile_business_cohort_policy(document, *, relationship_policy):
    if (type(relationship_policy) is not SnapshotRelationshipPolicy or type(document) is not dict
        or set(document)!={'schemaVersion','relationshipPolicyHash','purposeCode','windowBoundary','rules'}
        or document['schemaVersion']!='aos.snapshot-business-cohort/v1'
        or document['relationshipPolicyHash']!=relationship_policy.content_hash
        or document['windowBoundary']!='start-inclusive-end-exclusive'
        or type(document['purposeCode']) is not str
        or re.fullmatch(r'[a-z][a-z0-9_]{1,119}',document['purposeCode']) is None):
        raise ValueError('exact bound business cohort policy required')
    rules=document['rules'];expected=set(relationship_policy.object_types)
    if type(rules) is not list or len(rules)!=len(expected):
        raise ValueError('complete object cohort rules required')
    compiled=[];seen=set()
    for rule in rules:
        if type(rule) is not dict or rule.get('basis') not in ('snapshot','own-time','parent-time'):
            raise ValueError('explicit membership basis required')
        basis=rule['basis'];keys={'objectType','basis','statusFilter'}
        if basis!='snapshot':keys.add('timeProperty')
        if basis=='parent-time':keys.update(('parentType','referenceProperty'))
        if set(rule)!=keys:
            raise ValueError('exact cohort rule fields required')
        ot=_identifier(rule['objectType'])
        if ot not in expected or ot in seen:
            raise ValueError('unique known cohort type required')
        seen.add(ot)
        parent=_identifier(rule['parentType']) if basis=='parent-time' else None
        if parent is not None and parent not in expected:
            raise ValueError('parent must belong to the original cohort')
        reference=_identifier(rule['referenceProperty']) if basis=='parent-time' else None
        if parent is not None and not any(r.row_type==ot and r.parent_type==parent
                and r.reference_property==reference and r.encoding=='positive-id' for r in relationship_policy.rules):
            raise ValueError('parent time must use an explicit original relationship')
        compiled.append(BusinessCohortRule(ot,basis,_status(rule['statusFilter']),
            _identifier(rule['timeProperty']) if basis!='snapshot' else None,parent,
            reference))
    return BusinessCohortPolicy(relationship_policy.content_hash,document['purposeCode'],
        tuple(compiled),'sha256:'+_digest(document))


def _document(policy):
    if (type(policy) is not BusinessCohortPolicy or type(policy.rules) is not tuple
        or any(type(r) is not BusinessCohortRule or (r.status_filter is not None and type(r.status_filter) is not StatusSelection) for r in policy.rules)):
        raise ValueError('exact compiled business cohort policy required')
    rules=[]
    for rule in policy.rules:
        status=rule.status_filter
        value=dict(objectType=rule.object_type,basis=rule.basis,statusFilter=None if status is None else
            dict(property=status.property_name,known=list(status.known),accepted=list(status.accepted)))
        if rule.basis!='snapshot':value['timeProperty']=rule.time_property
        if rule.basis=='parent-time':value.update(parentType=rule.parent_type,referenceProperty=rule.reference_property)
        rules.append(value)
    return dict(schemaVersion='aos.snapshot-business-cohort/v1',relationshipPolicyHash=policy.relationship_policy_hash,
        purposeCode=policy.purpose_code,windowBoundary='start-inclusive-end-exclusive',rules=rules)


def _time(value, observed_at):
    if type(value) is not str:
        return None
    try:
        parsed=datetime.fromisoformat(value)
        if parsed.utcoffset() is None or not datetime(1970,1,1,tzinfo=timezone.utc)<parsed<=observed_at:
            return None
        return parsed
    except (ValueError,OverflowError):
        return None


def select_business_cohort(outputs, relationship_policy, policy, *, window_start, window_end, observed_at):
    if (any(type(v) is not datetime or v.utcoffset() is None for v in (window_start,window_end,observed_at))
        or not window_start<window_end<=observed_at):
        raise ValueError('aware ordered business window and observation required')
    assess_snapshot_relationships(outputs,relationship_policy,observed_at=observed_at)
    if compile_business_cohort_policy(_document(policy),relationship_policy=relationship_policy)!=policy:
        raise ValueError('compiled cohort policy differs')
    indexes={ot:{_key(row['source_pk']):row for row in rows} for ot,rows in outputs.items()}
    cohorts={}
    for rule in policy.rules:
        included=[];unknown=[];excluded=[]
        for row in outputs[rule.object_type]:
            key=_key(row['source_pk']);reasons=[]
            if row['is_deleted']:
                excluded.append((key,'deleted'));continue
            status=rule.status_filter
            if status is not None:
                value=row['properties'].get(status.property_name)
                if type(value) is not str or value not in status.known:
                    reasons.append('unknown-status')
                elif value not in status.accepted:
                    excluded.append((key,'status-outside'));continue
            dated=row
            if rule.basis=='parent-time':
                value=row['properties'].get(rule.reference_property)
                try:parent_key=_key(value)
                except ValueError:
                    unknown.append((key,tuple(reasons+['invalid-parent-reference'])));continue
                dated=indexes[rule.parent_type].get(parent_key)
                if dated is None:
                    unknown.append((key,tuple(reasons+['missing-parent'])));continue
                if dated['is_deleted']:
                    excluded.append((key,'parent-deleted'));continue
            if rule.basis!='snapshot':
                at=_time(dated['properties'].get(rule.time_property),observed_at)
                if at is None:
                    reasons.append('unknown-business-time')
                elif not window_start<=at<window_end:
                    excluded.append((key,'time-outside'));continue
            if reasons:unknown.append((key,tuple(reasons)))
            else:included.append(key)
        cohorts[rule.object_type]=ObjectBusinessCohort(tuple(included),tuple(unknown),tuple(excluded))
    return BusinessCohortSelection(policy.content_hash,cohorts)
