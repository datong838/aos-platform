"""Pure declared snapshot mapping; callers retain asset and execution authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import re
from string import Formatter

from aos_api.pipeline_source_selection import MappingReadSpec, _identifier
from aos_api.ec_source_adapter import _parse_site_filter


@dataclass(frozen=True)
class SnapshotMapping:
    read_spec: MappingReadSpec
    fields: tuple[tuple[str, str, str], ...]
    required: tuple[str, ...]
    identity_parts: tuple[tuple[str, str | None], ...]
    platform: str
    shop_key: str
    shop_id: str
    source_timezone: str
    defaults: tuple[tuple[str, str | int | float | bool], ...]


def compile_snapshot_mapping(mapping, read_spec):
    """No file reads or implicit defaults. A compiled value is not authorization."""
    if (type(mapping) is dict and type(mapping.get('snapshot_materialization')) is dict
            and mapping['snapshot_materialization'].get('schema_version')=='aos.snapshot-materialization/v2'):
        from aos_api.pipeline_snapshot_materialization_v2 import compile_v2
        return compile_v2(mapping,read_spec)
    try:
        if type(mapping) is not dict or type(read_spec) is not MappingReadSpec:
            raise ValueError('mapping and exact read specification required')
        spec = MappingReadSpec(read_spec.table,read_spec.object_type,read_spec.primary_key,read_spec.columns,read_spec.filters)
        if (mapping.get('source_table'),mapping.get('target_ot'),mapping.get('primary_key'),mapping.get('incremental_strategy')) != (spec.table,spec.object_type,spec.primary_key,'snapshot'):
            raise ValueError('mapping identities differ')
        if tuple(sorted(_parse_site_filter(mapping.get('site_filter')).items())) != tuple(sorted(spec.filters)):
            raise ValueError('declared source filter differs')
        raw_fields = mapping['field_mappings']
        if type(raw_fields) is not list or not 1 <= len(raw_fields) <= 100:
            raise ValueError('bounded fields required')
        fields = []
        for field in raw_fields:
            if type(field) is not dict or set(field) != {'source','target','type'} or field['type'] not in ('string','int','timestamp'):
                raise ValueError('unsupported field operation')
            fields.append((_identifier(field['source']),_identifier(field['target']),field['type']))
        if tuple(source for source,_,_ in fields) != spec.columns or len({target.casefold() for _,target,_ in fields}) != len(fields):
            raise ValueError('mapping field binding differs')
        validation = mapping['validation']
        if type(validation) is not dict or set(validation) != {'required'} or type(validation['required']) is not list:
            raise ValueError('explicit required fields needed')
        required = tuple(_identifier(value) for value in validation['required'])
        if len(set(required)) != len(required) or not set(required) <= set(spec.columns):
            raise ValueError('required source fields differ')
        config = mapping['snapshot_materialization']
        if type(config) is not dict or set(config) != {'schema_version','platform','shop_key','source_timezone','property_defaults'} or config['schema_version'] != 'aos.snapshot-materialization/v1':
            raise ValueError('explicit snapshot materialization required')
        platform,shop_key,offset = config['platform'],_identifier(config['shop_key']),config['source_timezone']
        if type(platform) is not str or re.fullmatch(r'[a-z][a-z0-9_.-]{0,63}',platform) is None:
            raise ValueError('canonical platform required')
        filters = dict(spec.filters)
        shop = filters.get(shop_key)
        if shop_key not in spec.columns or type(shop) not in (str,int) or not str(shop) or len(str(shop))>160:
            raise ValueError('shop must be explicitly filtered')
        if type(offset) is not str or re.fullmatch(r'[+-](?:0[0-9]|1[0-4]):[0-5][0-9]',offset) is None or (offset[1:3]=='14' and offset[4:]!='00'):
            raise ValueError('explicit fixed source timezone required')
        defaults = config['property_defaults']
        if type(defaults) is not dict or len(defaults)>32:
            raise ValueError('bounded property defaults required')
        targets = {target.casefold() for _,target,_ in fields}
        for key,value in defaults.items():
            if _identifier(key).casefold() in targets:
                raise ValueError('property default overwrites mapping')
            if type(value) not in (str,int,float,bool) or (type(value) is float and not math.isfinite(value)) or (type(value) is str and len(value)>2048):
                raise ValueError('scalar property default required')
            targets.add(key.casefold())
        pattern = mapping['unique_key_pattern']
        if type(pattern) is not str or not 1<=len(pattern)<=512:
            raise ValueError('bounded identity template required')
        parts = []
        names = []
        for literal,name,format_spec,conversion in Formatter().parse(pattern):
            if format_spec or conversion or (name is not None and name not in {'pk',*spec.columns}):
                raise ValueError('unsafe identity template')
            if name is not None:names.append(name)
            parts.append((literal,name))
        if 'pk' not in names:
            raise ValueError('primary key identity required')
        return SnapshotMapping(spec,tuple(fields),required,tuple(parts),platform,shop_key,str(shop),offset,tuple(sorted(defaults.items())))
    except (KeyError,TypeError,ValueError,AttributeError) as exc:
        raise ValueError('SNAPSHOT_MAPPING_INVALID') from None


def _convert(value, kind):
    if kind=='string' and type(value) is str:return value
    if kind=='int' and type(value) is int:return value
    if kind=='timestamp' and type(value) is int and value>=0:
        return None if value==0 else datetime.fromtimestamp(value,tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    raise ValueError('invalid mapped value')


def materialize_snapshot(rows, mapping, *, observed_at):
    """Produce one whole immutable-observation batch or reject it; no partial output."""
    from aos_api.pipeline_snapshot_materialization_v2 import SnapshotMappingV2, materialize_v2
    if type(mapping) is SnapshotMappingV2:
        return materialize_v2(rows,mapping,observed_at=observed_at)
    try:
        if type(mapping) is not SnapshotMapping or type(rows) is not list or len(rows)>1000:
            raise ValueError('bounded declared snapshot required')
        if type(observed_at) is not datetime or observed_at.utcoffset() is None:
            raise ValueError('explicit observation time required')
        observed_at = observed_at.astimezone(timezone.utc)
        spec = mapping.read_spec
        output,identities,primary_keys = [],set(),set()
        for row in rows:
            if type(row) is not dict or set(row) != set(spec.columns):
                raise ValueError('source fields differ')
            if any(row[name] is None or (type(row[name]) is str and not row[name].strip()) for name in mapping.required):
                raise ValueError('required source value absent')
            if any(row.get(key) != value or type(row.get(key)) is bool for key,value in spec.filters):
                raise ValueError('source scope differs')
            pk = row[spec.primary_key]
            if type(pk) not in (str,int) or not str(pk):
                raise ValueError('source primary key required')
            if str(pk) in primary_keys or str(pk)!=str(pk).strip() or not str(pk).isprintable():
                raise ValueError('unique canonical source key required')
            primary_keys.add(str(pk))
            props = dict(mapping.defaults)
            props.update({target:_convert(row[source],kind) for source,target,kind in mapping.fields})
            def identity_value(name):
                value=pk if name=='pk' else row[name]
                if type(value) not in (str,int):raise ValueError('identity scalar required')
                return str(value)
            identity = ''.join(literal+(identity_value(name) if name is not None else '') for literal,name in mapping.identity_parts)
            if not 1<=len(identity)<=200 or not identity.isprintable() or identity!=identity.strip() or identity in identities:
                raise ValueError('unique canonical identity required')
            identities.add(identity)
            output.append(dict(ot=spec.object_type,source_pk=str(pk),external_id=identity,source_updated_at=observed_at,
                source_timezone=mapping.source_timezone,is_deleted=False,properties=props))
        return output
    except (KeyError,TypeError,ValueError,OverflowError,OSError) as exc:
        raise ValueError('SNAPSHOT_MATERIALIZATION_INVALID') from None
