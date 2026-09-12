"""Niushop candidate status interpretation, not access or execution authority.

Use records read by an authorized Owner; recheck current versions before use.
Never filter the source event stream with this predicate: inactive/deleted
events must still invalidate previously selected candidates.
"""

from collections.abc import Mapping


def product_candidate_status(record, *, org_id: str, project_id: str, shop_id: str) -> str:
    """Classify without rewriting historical canonical states or source fields."""
    if not isinstance(record, Mapping) or record.get('object_type') != 'Product':
        return 'INVALID_RECORD'
    identity = record.get('identity')
    requested = (org_id, project_id, shop_id)
    if (any(type(value) is not str or not value or value.strip() != value for value in requested)
            or not isinstance(identity, Mapping)
            or (identity.get('org_id'), identity.get('workspace_id'),
                identity.get('shop_or_marketplace_id')) != requested
            or identity.get('platform') != 'niushop'
            or type(identity.get('external_id')) is not str
            or not identity['external_id']
            or identity['external_id'].strip() != identity['external_id']):
        return 'INVALID_IDENTITY'
    properties = record.get('properties')
    status = record.get('status')
    if (not isinstance(properties, Mapping) or not isinstance(status, Mapping)
            or type(record.get('is_deleted')) is not bool
            or type(status.get('unknown')) is not bool
            or any(type(properties.get(key)) is not int or properties[key] not in (0, 1)
                   for key in ('state', 'isDelete'))):
        return 'INVALID_STATE'
    value = (status.get('canonical_value'), status.get('raw_status'), status['unknown'])
    if record['is_deleted'] or properties['isDelete'] == 1:
        return ('DELETED' if record['is_deleted'] and properties['isDelete'] == 1
                and value == ('deleted', 'DELETED', False) else 'INVALID_STATE')
    if properties['state'] == 0:
        return ('INACTIVE' if value in (('unknown', 'INACTIVE', True),
                                       ('inactive', 'INACTIVE', False)) else 'INVALID_STATE')
    return 'ELIGIBLE_STATUS' if value == ('active', 'ACTIVE', False) else 'INVALID_STATE'
