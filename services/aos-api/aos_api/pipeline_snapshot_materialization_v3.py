"""Explicit observation-version snapshots without fabricated source modification time."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import timezone
import re

from aos_api.pipeline_snapshot_materialization import SnapshotMapping
from aos_api.pipeline_snapshot_materialization_v2 import _decimal
from aos_api.pipeline_source_selection import _identifier

_RESERVED={'updatedat','observedat','updatedatsourcetimezone','observedatsourcetimezone',
           'sourceupdatedatbasis','sourcemodificationtimeknown','sourcemodifiedat'}


@dataclass(frozen=True)
class SnapshotMappingV3:
    base: SnapshotMapping
    conversions: tuple[tuple[str,str],...]
    non_negative: tuple[str,...]
    status_field: str
    status_target: str
    statuses: tuple[tuple[int,str],...]
    hierarchy: tuple[str,int] | None = None

    @property
    def read_spec(self):return self.base.read_spec
    @property
    def platform(self):return self.base.platform
    @property
    def shop_id(self):return self.base.shop_id
    @property
    def source_timezone(self):return self.base.source_timezone


def compile_v3(mapping,read_spec):
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
    try:
        value=deepcopy(mapping);config=value['snapshot_materialization']
        base_keys={'schema_version','platform','shop_key','source_timezone','property_defaults'}
        if (type(config) is not dict or set(config)!=base_keys|{'time_basis','deletion_basis','status'}
                or config['schema_version']!='aos.snapshot-materialization/v3'
                or config['time_basis']!='observation' or config['deletion_basis']!='row-presence-only'
                or value.get('links') or 'soft_delete' in value or 'incremental_cursor' in value):
            raise ValueError('explicit observation-only snapshot required')
        fields=value['field_mappings'];defaults=config['property_defaults']
        targets={_identifier(f['target']).casefold() for f in fields}|{_identifier(k).casefold() for k in defaults}
        if targets&_RESERVED:raise ValueError('observation metadata cannot be overwritten')
        status=config['status']
        if type(status) is not dict or set(status)!={'field','property_target','values'}:
            raise ValueError('explicit source state required')
        target=_identifier(status['property_target'])
        if target.casefold() in targets|_RESERVED:raise ValueError('state target collision')
        kinds={f['source']:f['type'] for f in fields}
        hierarchy=None
        if 'hierarchy' in value['validation']:
            rule=value['validation'].pop('hierarchy')
            if (type(rule) is not dict or set(rule)!={'parent_field','root_value'}
                    or type(rule['root_value']) is not int
                    or kinds.get(rule['parent_field'])!='int'
                    or kinds.get(read_spec.primary_key)!='int'):
                raise ValueError('selected integer hierarchy required')
            hierarchy=(_identifier(rule['parent_field']),rule['root_value'])
        if kinds.get(status['field'])!='int':raise ValueError('selected integer state required')
        states=status['values']
        if type(states) is not dict or not 1<=len(states)<=32:raise ValueError('bounded states required')
        parsed=[]
        for key,raw in states.items():
            if (type(key) is not str or not 1<=len(key)<=11 or str(int(key))!=key
                    or type(raw) is not str or raw=='DELETED' or re.fullmatch(r'[A-Z][A-Z0-9_]{0,39}',raw) is None):
                raise ValueError('canonical nondelete state required')
            parsed.append((int(key),raw))
        constraints=value['validation'].pop('non_negative',[])
        if (type(constraints) is not list or len(set(constraints))!=len(constraints)
                or any(kinds.get(name) not in ('int','decimal') for name in constraints)):
            raise ValueError('selected numeric constraint required')
        conversions=[]
        for field in fields:
            if field['type'] in ('decimal','text'):
                if field['source'] in dict(read_spec.filters) or field['source']==read_spec.primary_key:
                    raise ValueError('converted identity or scope not supported')
                conversions.append((field['source'],field['type']));field['type']='string'
        value['snapshot_materialization']={key:config[key] for key in base_keys}
        value['snapshot_materialization']['schema_version']='aos.snapshot-materialization/v1'
        base=compile_snapshot_mapping(value,read_spec)
        return SnapshotMappingV3(base,tuple(conversions),tuple(constraints),status['field'],target,tuple(sorted(parsed)),hierarchy)
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise ValueError('SNAPSHOT_MAPPING_INVALID') from None


def materialize_v3(rows,mapping,*,observed_at):
    from aos_api.pipeline_snapshot_materialization import materialize_snapshot
    try:
        if type(mapping) is not SnapshotMappingV3 or type(rows) is not list or len(rows)>1000:
            raise ValueError('bounded observation snapshot required')
        converted=[]
        for source in rows:
            if type(source) is not dict:raise ValueError('source row required')
            row=dict(source)
            for field,kind in mapping.conversions:
                if kind=='decimal':row[field]=_decimal(source[field])
                elif type(source[field]) is not str or len(source[field])>262144:
                    raise ValueError('bounded text required')
            converted.append(row)
        output=materialize_snapshot(converted,mapping.base,observed_at=observed_at)
        if mapping.hierarchy is not None:
            parent_field,root=mapping.hierarchy
            parents={row[mapping.read_spec.primary_key]:row[parent_field] for row in rows}
            if root in parents or any(parent!=root and parent not in parents for parent in parents.values()):
                raise ValueError('hierarchy root collision or missing parent')
            verified=set()
            for node in parents:
                trail=set()
                while node!=root and node not in verified:
                    if node in trail:raise ValueError('hierarchy cycle')
                    trail.add(node)
                    node=parents[node]
                verified.update(trail)
        observed=observed_at.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
        states=dict(mapping.statuses)
        for source,item in zip(rows,output):
            if any(source[field]<0 for field in mapping.non_negative):raise ValueError('negative source value')
            if type(source[mapping.status_field]) is not int or source[mapping.status_field] not in states:
                raise ValueError('unknown source state')
            status=states[source[mapping.status_field]]
            item['status_raw']=status
            item['properties'].update(updatedAt=observed,observedAt=observed,
                sourceUpdatedAtBasis='observation',sourceModificationTimeKnown=False)
            item['properties'][mapping.status_target]=status
        return output
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError):
        raise ValueError('SNAPSHOT_MATERIALIZATION_INVALID') from None
