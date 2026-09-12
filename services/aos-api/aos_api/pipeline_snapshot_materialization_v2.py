"""Declared product snapshot values, preserving source time and state."""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re

from aos_api.pipeline_snapshot_materialization import SnapshotMapping


@dataclass(frozen=True)
class SnapshotMappingV2:
    base: SnapshotMapping
    conversions: tuple[tuple[str, str], ...]
    source_time: tuple[str, str]
    tombstone: tuple[str, int, int]
    status_field: str
    status_target: str
    statuses: tuple[tuple[int, str], ...]
    non_negative: tuple[str, ...]

    @property
    def read_spec(self): return self.base.read_spec
    @property
    def platform(self): return self.base.platform
    @property
    def shop_id(self): return self.base.shop_id
    @property
    def source_timezone(self): return self.base.source_timezone


def compile_v2(mapping, read_spec):
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
    try:
        value=deepcopy(mapping)
        config=value['snapshot_materialization']
        base_keys={'schema_version','platform','shop_key','source_timezone','property_defaults'}
        if (type(config) is not dict or set(config)!=base_keys|{'source_updated_at','tombstone','status'}
                or config['schema_version']!='aos.snapshot-materialization/v2'
                or value.get('links') or 'soft_delete' in value or 'incremental_cursor' in value):
            raise ValueError('unsupported snapshot declaration')
        if any(str(key).casefold() in {'status','status_raw','is_deleted'} for key in config['property_defaults']):
            raise ValueError('state cannot come from a constant default')
        clock,deleted,status=[config[key] for key in ('source_updated_at','tombstone','status')]
        if (type(clock) is not dict or set(clock)!={'primary','fallback'}
                or type(deleted) is not dict or set(deleted)!={'field','live_value','deleted_value'}
                or type(status) is not dict or set(status)!={'field','values','property_target'}):
            raise ValueError('explicit state and time required')
        fields=value['field_mappings']
        from aos_api.pipeline_source_selection import _identifier
        target=_identifier(status['property_target'])
        reserved={str(f['target']).casefold() for f in fields}|{str(k).casefold() for k in config['property_defaults']}
        if target.casefold() in reserved: raise ValueError('state property overwrites mapped field')
        kinds={f['source']:f['type'] for f in fields}
        validation=value['validation']
        if type(validation) is not dict: raise ValueError('explicit validation required')
        non_negative=validation.pop('non_negative',[])
        if (type(non_negative) is not list or any(type(name) is not str or kinds.get(name) not in ('int','decimal') for name in non_negative)
                or len(set(non_negative))!=len(non_negative)):
            raise ValueError('selected unique numeric constraints required')
        if any(kinds.get(clock[k])!='timestamp' for k in ('primary','fallback')):
            raise ValueError('selected source timestamp required')
        if kinds.get(deleted['field'])!='int' or kinds.get(status['field'])!='int':
            raise ValueError('selected integer state required')
        live,removed=deleted['live_value'],deleted['deleted_value']
        if type(live) is not int or type(removed) is not int or live==removed:
            raise ValueError('distinct explicit delete values required')
        values=status['values']
        if type(values) is not dict or not 1<=len(values)<=32:
            raise ValueError('bounded state map required')
        states=[]
        for key,raw in values.items():
            if (type(key) is not str or not 1<=len(key)<=11 or str(int(key))!=key
                    or type(raw) is not str or raw=='DELETED' or re.fullmatch(r'[A-Z][A-Z0-9_]{0,39}',raw) is None):
                raise ValueError('canonical state mapping required')
            states.append((int(key),raw))
        conversions=[]
        for field in fields:
            if field['type'] in ('decimal','text'):
                if field['source'] in dict(read_spec.filters) or field['source']==read_spec.primary_key:
                    raise ValueError('converted fields cannot define source scope or primary key')
                conversions.append((field['source'],field['type']))
                field['type']='string'
        value['snapshot_materialization']={key:config[key] for key in base_keys}
        value['snapshot_materialization']['schema_version']='aos.snapshot-materialization/v1'
        base=compile_snapshot_mapping(value,read_spec)
        return SnapshotMappingV2(base,tuple(conversions),(clock['primary'],clock['fallback']),
            (deleted['field'],live,removed),status['field'],target,tuple(sorted(states)),tuple(non_negative))
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        raise ValueError('SNAPSHOT_MAPPING_INVALID') from None


def _decimal(value):
    if type(value) not in (Decimal,int): raise ValueError('exact decimal required')
    if type(value) is int and value.bit_length()>127: raise ValueError('bounded integer required')
    number=Decimal(value)
    if not number.is_finite(): raise ValueError('finite decimal required')
    digits=number.as_tuple()
    if len(digits.digits)>38 or digits.exponent < -18 or number.adjusted()>=38:
        raise ValueError('bounded decimal required')
    rendered=format(number,'f')
    if len(rendered)>80: raise ValueError('bounded decimal required')
    return rendered


def materialize_v2(rows,mapping,*,observed_at):
    from aos_api.pipeline_snapshot_materialization import materialize_snapshot
    try:
        if type(mapping) is not SnapshotMappingV2 or type(rows) is not list or len(rows)>1000:
            raise ValueError('bounded v2 snapshot required')
        converted=[]
        for source in rows:
            if type(source) is not dict: raise ValueError('exact source row required')
            row=dict(source)
            for field,kind in mapping.conversions:
                if kind=='decimal': row[field]=_decimal(source[field])
                elif type(source[field]) is not str or len(source[field])>262144:
                    raise ValueError('bounded text required')
            converted.append(row)
        result=materialize_snapshot(converted,mapping.base,observed_at=observed_at)
        states=dict(mapping.statuses)
        for source,output in zip(rows,result):
            if any(source[field]<0 for field in mapping.non_negative):
                raise ValueError('nonnegative source value required')
            primary,fallback=mapping.source_time
            stamp=source[primary] if source[primary]!=0 else source[fallback]
            if type(stamp) is not int or stamp<=0: raise ValueError('source timestamp absent')
            at=datetime.fromtimestamp(stamp,tz=timezone.utc)
            if at>observed_at: raise ValueError('source timestamp is in the future')
            field,live,removed=mapping.tombstone
            if source[field] not in (live,removed): raise ValueError('unknown delete value')
            if source[mapping.status_field] not in states: raise ValueError('unknown state value')
            is_deleted=source[field]==removed
            raw_status='DELETED' if is_deleted else states[source[mapping.status_field]]
            output.update(source_updated_at=at,is_deleted=is_deleted,
                status_raw=raw_status)
            output['properties'][mapping.status_target]=raw_status
        return result
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,OSError):
        raise ValueError('SNAPSHOT_MATERIALIZATION_INVALID') from None
