"""Purpose-specific row coverage over a verified cohort; no readiness authority.

The caller must bind both policies and rows to their original current Owners.
Counts describe reference coverage only, not temporal or business fact quality.
"""
from dataclasses import dataclass
import re

from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_snapshot_relationships import (
    SnapshotRelationshipPolicy, assess_snapshot_relationships, _key, _keys,
)


@dataclass(frozen=True)
class RelationshipQualityPurpose:
    purpose_code: str
    rules: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SnapshotRelationshipQualityPolicy:
    relationship_policy_hash: str
    purposes: tuple[RelationshipQualityPurpose, ...]
    content_hash: str


@dataclass(frozen=True)
class SnapshotRelationshipQualityMeasurement:
    relationship_policy_hash: str
    quality_policy_hash: str
    counts: dict[str, dict[str, int]]
    purposes: dict[str, dict[str, tuple[str, ...]]]


def compile_relationship_quality_policy(document, *, relationship_policy):
    if (type(relationship_policy) is not SnapshotRelationshipPolicy or type(document) is not dict
        or set(document) != {'schemaVersion', 'relationshipPolicyHash', 'purposes'}
        or document['schemaVersion'] != 'aos.snapshot-relationship-quality/v1'
        or document['relationshipPolicyHash'] != relationship_policy.content_hash):
        raise ValueError('exact relationship quality policy binding required')
    purposes = document['purposes']
    if type(purposes) is not list or not 1 <= len(purposes) <= 16:
        raise ValueError('bounded explicit purposes required')
    names = set()
    expected = {rule.link_type for rule in relationship_policy.rules}
    compiled = []
    for purpose in purposes:
        if type(purpose) is not dict or set(purpose) != {'purposeCode', 'rules'}:
            raise ValueError('exact purpose required')
        code, rules = purpose['purposeCode'], purpose['rules']
        if (type(code) is not str or not re.fullmatch(r'[a-z][a-z0-9_]{1,119}', code)
            or code in names or type(rules) is not list or len(rules) != len(expected)):
            raise ValueError('unique purpose and complete rules required')
        names.add(code)
        items = []
        for rule in rules:
            if (type(rule) is not dict or set(rule) != {'linkType', 'requirement'}
                or type(rule['linkType']) is not str or rule['linkType'] not in expected
                or rule['requirement'] not in ('required', 'disclose')):
                raise ValueError('explicit known relationship requirement required')
            items.append((rule['linkType'], rule['requirement']))
        if len({name for name, _ in items}) != len(expected) or not any(v == 'required' for _, v in items):
            raise ValueError('complete unique rules and a required relationship required')
        compiled.append(RelationshipQualityPurpose(code, tuple(items)))
    return SnapshotRelationshipQualityPolicy(relationship_policy.content_hash, tuple(compiled),
        'sha256:' + _digest(document))


def measure_relationship_quality(outputs, relationship_policy, quality_policy, *, observed_at):
    # Retain original full-cohort, key, duplication, size and policy hash checks.
    assess_snapshot_relationships(outputs, relationship_policy, observed_at=observed_at)
    if (type(quality_policy) is not SnapshotRelationshipQualityPolicy
        or type(quality_policy.purposes) is not tuple
        or any(type(p) is not RelationshipQualityPurpose or type(p.rules) is not tuple
               or any(type(r) is not tuple or len(r) != 2 for r in p.rules) for p in quality_policy.purposes)):
        raise ValueError('exact compiled quality policy required')
    document = dict(schemaVersion='aos.snapshot-relationship-quality/v1',
        relationshipPolicyHash=quality_policy.relationship_policy_hash,
        purposes=[dict(purposeCode=p.purpose_code,
            rules=[dict(linkType=name, requirement=value) for name, value in p.rules])
            for p in quality_policy.purposes])
    if compile_relationship_quality_policy(document, relationship_policy=relationship_policy) != quality_policy:
        raise ValueError('compiled quality policy differs')
    indexed = {ot: {_key(row['source_pk']): row for row in rows} for ot, rows in outputs.items()}
    counts = {}
    for rule in relationship_policy.rules:
        rows = outputs[rule.row_type]
        active = [row for row in rows if not row['is_deleted']]
        count = dict(observedRows=len(rows), excludedRows=len(rows)-len(active), eligibleRows=len(active),
            completeRows=0, allowedUnsetRows=0, incompleteRows=0, missingReferenceRows=0,
            invalidReferenceRows=0, missingParentRows=0, deletedParentRows=0)
        for row in active:
            value = row['properties'].get(rule.reference_property)
            if value is None:
                count['missingReferenceRows'] += 1
                count['incompleteRows'] += 1
                continue
            if rule.allow_unset and type(value) in (int, str) and value in (0, '0', ''):
                count['allowedUnsetRows'] += 1
                continue
            try:
                keys = _keys(value, rule.encoding)
            except ValueError:
                count['invalidReferenceRows'] += 1
                count['incompleteRows'] += 1
                continue
            parents = [indexed[rule.parent_type].get(key) for key in keys]
            missing = any(parent is None for parent in parents)
            deleted = any(parent is not None and parent['is_deleted'] for parent in parents)
            count['missingParentRows'] += int(missing)
            count['deletedParentRows'] += int(deleted)
            count['incompleteRows'] += int(missing or deleted)
            count['completeRows'] += int(not (missing or deleted))
        counts[rule.link_type] = count
    purposes = {}
    for purpose in quality_policy.purposes:
        purposes[purpose.purpose_code] = dict(
            requiredIncomplete=tuple(name for name, kind in purpose.rules
                if kind == 'required' and counts[name]['incompleteRows']),
            disclosedIncomplete=tuple(name for name, kind in purpose.rules
                if kind == 'disclose' and counts[name]['incompleteRows']),
            emptyRules=tuple(name for name, _ in purpose.rules if not counts[name]['eligibleRows']))
    return SnapshotRelationshipQualityMeasurement(relationship_policy.content_hash,
        quality_policy.content_hash, counts, purposes)
