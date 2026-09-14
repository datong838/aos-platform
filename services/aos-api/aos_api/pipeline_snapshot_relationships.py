"""Bounded declarative relationship assessment; no persistence or readiness grant."""
from dataclasses import dataclass
from datetime import datetime,timezone
import re
from aos_api.ec_ingress_journal import _digest
from aos_api.pipeline_source_selection import _identifier


@dataclass(frozen=True)
class RelationshipRule:
    link_type: str
    row_type: str
    parent_type: str
    reference_property: str
    direction: str
    encoding: str
    allow_unset: bool


@dataclass(frozen=True)
class SnapshotRelationshipPolicy:
    object_types: tuple[str,...]
    rules: tuple[RelationshipRule,...]
    content_hash: str


@dataclass(frozen=True)
class SnapshotRelationshipAssessment:
    policy_hash: str
    candidate_links: tuple[dict,...]
    counts: dict[str,dict[str,int]]


def compile_relationship_policy(document):
    if (type(document) is not dict or set(document)!={'schemaVersion','objectTypes','rules'}
            or document['schemaVersion']!='aos.snapshot-relationships/v1'):
        raise ValueError('exact relationship policy required')
    types=document['objectTypes'];rules=document['rules']
    if type(types) is not list or not 1<=len(types)<=12 or type(rules) is not list or not 1<=len(rules)<=32:
        raise ValueError('bounded explicit types and rules required')
    types=tuple(_identifier(ot) for ot in types)
    if len({ot.casefold() for ot in types})!=len(types):raise ValueError('unique object types required')
    compiled=[];names=set()
    for rule in rules:
        if type(rule) is not dict or set(rule)!={'linkType','rowType','parentType','referenceProperty','direction','encoding','allowUnset'}:
            raise ValueError('exact relationship rule required')
        name=rule['linkType']
        if type(name) is not str or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}\.[A-Za-z_][A-Za-z0-9_]{0,63}',name) or name.casefold() in names:
            raise ValueError('unique canonical link type required')
        names.add(name.casefold())
        row_type=_identifier(rule['rowType']);parent_type=_identifier(rule['parentType']);prop=_identifier(rule['referenceProperty'])
        if (row_type not in types or parent_type not in types or type(rule['allowUnset']) is not bool
                or rule['direction'] not in ('row-to-parent','parent-to-row')
                or rule['encoding'] not in ('positive-id','csv-positive-id','wrapped-csv-positive-id')):
            raise ValueError('explicit relationship semantics required')
        source_type=row_type if rule['direction']=='row-to-parent' else parent_type
        if name.split('.')[0]!=source_type:raise ValueError('link direction and namespace differ')
        compiled.append(RelationshipRule(name,row_type,parent_type,prop,rule['direction'],rule['encoding'],rule['allowUnset']))
    return SnapshotRelationshipPolicy(types,tuple(compiled),'sha256:'+_digest(document))


def _key(value):
    if type(value) is int and 0<value<=9223372036854775807:return str(value)
    if type(value) is str and re.fullmatch(r'[1-9][0-9]{0,18}',value) and int(value)<=9223372036854775807:return value
    raise ValueError('canonical positive key required')


def _keys(value,encoding):
    if encoding=='positive-id':return (_key(value),)
    if type(value) is not str or not 1<=len(value)<=4096:raise ValueError('bounded reference list required')
    if encoding=='wrapped-csv-positive-id':
        if not value.startswith(',') or not value.endswith(','):raise ValueError('exact wrapped reference list required')
        value=value[1:-1]
    parts=value.split(',')
    if not 1<=len(parts)<=32:raise ValueError('bounded reference count required')
    keys=tuple(_key(item) for item in parts)
    if len(set(keys))!=len(keys):raise ValueError('duplicate reference required rejection')
    return keys


def assess_snapshot_relationships(outputs,policy,*,observed_at):
    """Caller supplies one verified cohort and retains original current authority.

    Missing and deleted endpoints stay visible in counts. Candidate links never
    imply previous links should be deleted, nor that data readiness is complete.
    """
    if (type(policy) is not SnapshotRelationshipPolicy or type(outputs) is not dict
            or set(outputs)!=set(policy.object_types) or type(observed_at) is not datetime
            or observed_at.utcoffset() is None):
        raise ValueError('exact policy, complete cohort and aware observation required')
    if type(policy.object_types) is not tuple or type(policy.rules) is not tuple or any(type(r) is not RelationshipRule for r in policy.rules):
        raise ValueError('exact immutable relationship rules required')
    document={'schemaVersion':'aos.snapshot-relationships/v1','objectTypes':list(policy.object_types),'rules':[
        dict(linkType=r.link_type,rowType=r.row_type,parentType=r.parent_type,referenceProperty=r.reference_property,
            direction=r.direction,encoding=r.encoding,allowUnset=r.allow_unset) for r in policy.rules]}
    if compile_relationship_policy(document)!=policy:raise ValueError('compiled relationship policy differs')
    observed_at=observed_at.astimezone(timezone.utc)
    indexed={}
    for ot,rows in outputs.items():
        if type(rows) is not list or len(rows)>=1000:raise ValueError('bounded complete object list required')
        index={}
        for row in rows:
            if (type(row) is not dict or row.get('ot')!=ot or 'link_type' in row
                    or type(row.get('properties')) is not dict or type(row.get('is_deleted')) is not bool):
                raise ValueError('canonical object required')
            key=_key(row.get('source_pk'))
            if key in index:raise ValueError('unique object key required')
            index[key]=row
        indexed[ot]=index
    links=[];counts={};identities=set()
    for rule in policy.rules:
        current=dict(rows=len(outputs[rule.row_type]),matched=0,missingReference=0,invalidReference=0,
            missingParent=0,deletedEndpoint=0,allowedUnset=0)
        for row in outputs[rule.row_type]:
            value=row['properties'].get(rule.reference_property)
            if value is None:current['missingReference']+=1;continue
            if type(value) in (int,str) and value in (0,'0','') and rule.allow_unset:
                current['allowedUnset']+=1;continue
            try:keys=_keys(value,rule.encoding)
            except ValueError:current['invalidReference']+=1;continue
            for key in keys:
                parent=indexed[rule.parent_type].get(key)
                if parent is None:current['missingParent']+=1;continue
                if row['is_deleted'] or parent['is_deleted']:current['deletedEndpoint']+=1;continue
                left,right=(row,parent) if rule.direction=='row-to-parent' else (parent,row)
                identity=(rule.link_type,_key(left['source_pk']),_key(right['source_pk']))
                if identity in identities:raise ValueError('duplicate candidate relationship')
                identities.add(identity)
                if len(identities)>24000:raise ValueError('candidate relationship limit exceeded')
                links.append(dict(link_type=rule.link_type,source_type=left['ot'],source_pk=identity[1],
                    target_type=right['ot'],target_source_pk=identity[2],source_updated_at=observed_at,
                    source_timezone='+00:00',is_deleted=False,properties={'sourceModificationTimeKnown':False,'sourceUpdatedAtBasis':'observation'}))
                current['matched']+=1
        counts[rule.link_type]=current
    return SnapshotRelationshipAssessment(policy.content_hash,tuple(links),counts)
