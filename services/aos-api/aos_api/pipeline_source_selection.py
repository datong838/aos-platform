"""Interpret pinned mapping assets; a read specification never grants permission."""
from dataclasses import dataclass
import math
import re

from aos_api.ec_source_adapter import _parse_site_filter

_IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')


def _identifier(value):
    if type(value) is not str or not _IDENTIFIER.fullmatch(value):
        raise ValueError('canonical mapping identifier required')
    return value


def _fields(value):
    if type(value) is not list:
        raise ValueError('explicit field list required')
    fields = tuple(_identifier(item) for item in value)
    if len(fields) != len({field.casefold() for field in fields}):
        raise ValueError('duplicate mapping fields')
    return fields


@dataclass(frozen=True)
class MappingReadSpec:
    table: str
    object_type: str
    primary_key: str
    columns: tuple[str, ...]
    filters: tuple[tuple[str, str | int | float], ...]

    def __post_init__(self):
        for value in (self.table, self.object_type, self.primary_key):
            _identifier(value)
        if type(self.columns) is not tuple or not 1 <= len(self.columns) <= 100:
            raise ValueError('bounded immutable columns required')
        _fields(list(self.columns))
        if self.primary_key not in self.columns:
            raise ValueError('primary key must be selected')
        if type(self.filters) is not tuple or not 1 <= len(self.filters) <= 8:
            raise ValueError('bounded immutable scope required')
        names = []
        for term in self.filters:
            if type(term) is not tuple or len(term) != 2:
                raise ValueError('immutable equality pair required')
            column, value = term
            names.append(_identifier(column).casefold())
            if (type(value) not in (str, int, float)
                    or (type(value) is float and not math.isfinite(value))
                    or (type(value) is str and len(value) > 160)):
                raise ValueError('bounded scalar scope value required')
        if len(names) != len(set(names)):
            raise ValueError('duplicate equality scope')


def derive_mapping_read_spec(mapping, schema, masking) -> MappingReadSpec:
    """Caller must verify asset digests and current authority separately.

    Snapshot-only preparation. Fingerprint matching proves declared identities,
    not current source column types, source freshness or permission to query.
    """
    if any(type(document) is not dict for document in (mapping, schema, masking)):
        raise ValueError('mapping, schema and masking documents required')
    if mapping.get('incremental_strategy') != 'snapshot':
        raise ValueError('only an explicit snapshot mapping is supported')
    table = _identifier(mapping.get('source_table'))
    primary_key = _identifier(mapping.get('primary_key'))
    object_type = _identifier(mapping.get('target_ot'))
    pipeline = _identifier(mapping.get('pipeline_id'))
    fields = mapping.get('field_mappings')
    if type(fields) is not list or not 1 <= len(fields) <= 100 or any(type(item) is not dict for item in fields):
        raise ValueError('bounded explicit field mappings required')
    columns = _fields([item.get('source') for item in fields])
    if primary_key not in columns:
        raise ValueError('primary key must be selected')
    tables = schema.get('tables')
    if type(schema.get('version')) is not int or schema['version'] != 1 or type(tables) is not list:
        raise ValueError('supported schema fingerprint required')
    if any(type(item) is not dict for item in tables):
        raise ValueError('invalid schema table')
    matches = [item for item in tables if item.get('name') == table]
    if len(matches) != 1 or (
        matches[0].get('primaryKey'), matches[0].get('targetOt'), matches[0].get('pipelineId')
    ) != (primary_key, object_type, pipeline):
        raise ValueError('mapping and schema identities differ')
    policies = masking.get('tables')
    if type(masking.get('version')) is not int or masking['version'] != 1 or type(policies) is not dict:
        raise ValueError('supported masking document required')
    policy = policies.get(table)
    if type(policy) is not dict or masking.get('policy') != {'pii_direct': 'drop', 'pii_quasi': 'drop_or_mask'}:
        raise ValueError('explicit table masking policy required')
    blocked = set(_fields(policy.get('pii_direct'))) | set(_fields(policy.get('pii_quasi')))
    blocked.update(_fields(policy.get('sensitive_mask', [])))
    blocked.update(_fields(masking.get('global_drop_on_project_node')))
    blocked.update(_fields(mapping.get('pii_exclusion', [])))
    if {field.casefold() for field in blocked}.intersection(field.casefold() for field in columns):
        raise ValueError('mapping selects a field prohibited from leaving source')
    try:
        filters = _parse_site_filter(mapping.get('site_filter'))
    except (TypeError, ValueError):
        raise ValueError('explicit bounded equality scope required') from None
    if not 1 <= len(filters) <= 8:
        raise ValueError('explicit bounded equality scope required')
    for column, value in filters.items():
        _identifier(column)
        if (type(value) not in (str, int, float)
                or (type(value) is float and not math.isfinite(value))
                or (type(value) is str and len(value) > 160)):
            raise ValueError('bounded scalar scope value required')
    return MappingReadSpec(table, object_type, primary_key, columns, tuple(sorted(filters.items())))
