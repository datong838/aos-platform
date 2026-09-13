"""Current signed-resource check before reading an original subject's result."""
from datetime import datetime
from uuid import UUID

from psycopg.errors import InsufficientPrivilege

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from .lifecycle_store import RuntimeConflict, _values
from .ui_read_admission import require_current_catalog_read
from .ui_read_api_database import read_api_ui_principal
from .ui_read_contracts import UiReadRequest


class RuntimeUiReadQuery:
    def __init__(self, *, catalog):
        if type(catalog) is not RuntimeWorkshopCatalog:
            raise TypeError('current signed runtime catalog required')
        self.catalog = catalog

    def get(self, *, conn, scope, subject, required_markings, request_id):
        if type(request_id) is not UUID:
            raise RuntimeConflict('exact UI request identity required')
        principal = read_api_ui_principal(conn=conn, scope=scope, subject=subject,
                                          required_markings=required_markings)
        metadata = _call(conn, 'metadata', (subject, request_id))
        if (type(metadata) is not dict or set(metadata) != {'requestId', 'requestHash', 'request'}
                or metadata['requestId'] != str(request_id)):
            raise RuntimeConflict('UI request metadata differs')
        try:
            request = UiReadRequest.model_validate(metadata['request'])
        except ValueError as exc:
            raise RuntimeConflict('UI request metadata differs') from exc
        digest = canonical_sha256({'tenant': {'orgId': scope.org_id, 'projectId': scope.project_id},
                                    'subject': subject, 'request': request.model_dump(mode='json')})
        if metadata['requestHash'] != digest:
            raise RuntimeConflict('UI request digest differs')
        catalog = self.catalog.list_modules(org_id=scope.org_id, project_id=scope.project_id,
                                             roles=principal.roles, markings=principal.markings)
        require_current_catalog_read(catalog=catalog, principal=principal, request=request)
        value = _call(conn, 'result', (subject, request_id, digest))
        _validate_result(value, request_id, digest, scope)
        return value


def _call(conn, kind, arguments):
    queries = {
        'metadata': 'SELECT public.extension_ui_read_metadata_a0v_035(%s,%s) AS value',
        'result': 'SELECT public.extension_ui_read_result_a0v_035(%s,%s,%s) AS value',
    }
    try:
        value = _values(conn.execute(queries[kind], arguments).fetchone(), ('value',))[0]
    except InsufficientPrivilege as exc:
        raise RuntimeConflict('current UI read access unavailable') from exc
    if value is None:
        raise LookupError('current UI read unavailable')
    return value


def _validate_result(value, request_id, digest, scope):
    if (type(value) is not dict or set(value) != {'requestId', 'requestHash', 'state', 'revision',
            'deadline', 'completedAt', 'result', 'resultHash', 'failureCode'}
            or value['requestId'] != str(request_id) or value['requestHash'] != digest
            or type(value['revision']) is not int or value['revision'] < 1
            or value['state'] not in ('requested', 'claimed', 'succeeded', 'denied', 'failed', 'expired')):
        raise RuntimeConflict('UI result contract differs')
    terminal = value['state'] not in ('requested', 'claimed')
    try:
        if datetime.fromisoformat(value['deadline']).tzinfo is None:
            raise ValueError()
        if terminal:
            if datetime.fromisoformat(value['completedAt']).tzinfo is None:
                raise ValueError()
        elif value['completedAt'] is not None:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise RuntimeConflict('UI result timestamps differ') from exc
    if value['state'] == 'succeeded':
        result = value['result']
        if (type(result) is not dict or value['failureCode'] is not None
                or result.get('schemaVersion') != 'aos.analyst-workspace-view/v1'
                or result.get('tenant') != {'orgId': scope.org_id, 'projectId': scope.project_id}
                or result.get('executionAllowed') is not False
                or len(canonical_json(result)) > 900000 or canonical_sha256(result) != value['resultHash']):
            raise RuntimeConflict('UI result integrity differs')
    elif value['result'] is not None or value['resultHash'] is not None:
        raise RuntimeConflict('UI non-success result must be absent')
    elif terminal:
        if value['failureCode'] not in {'READ_ACCESS_REVOKED', 'READ_FAILED', 'READ_RESULT_INVALID',
                'READ_OUTCOME_UNKNOWN', 'READ_DEADLINE_EXPIRED', 'READ_RUNTIME_CHANGED', 'READ_ADMISSION_DENIED'}:
            raise RuntimeConflict('UI failure code differs')
    elif value['failureCode'] is not None:
        raise RuntimeConflict('UI pending failure must be absent')
