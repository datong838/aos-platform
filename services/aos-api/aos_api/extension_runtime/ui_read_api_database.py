"""Fixed database calls for the restricted UI API role; no direct table access."""
from datetime import datetime
from uuid import UUID

from psycopg.types.json import Jsonb
from psycopg.errors import InsufficientPrivilege, CheckViolation

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict, _require_transaction, _values
from aos_api.extension_runtime.ui_current_principal import CurrentUiPrincipal, _exact
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from aos_api.extension_runtime.ui_read_store import UiReadDelivery
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope


def _scope(conn, scope):
    _require_transaction(conn)
    if type(scope) is not TenantScope:
        raise RuntimeConflict('exact UI tenant required')
    row = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                       "current_setting('aos.project_id',true) AS project_id").fetchone()
    if _values(row, ('org_id', 'project_id')) != scope.key:
        raise RuntimeConflict('UI database scope differs')


def read_api_ui_principal(*, conn, scope, subject, required_markings):
    _scope(conn, scope)
    if (not _exact(subject) or type(required_markings) is not tuple
            or len(required_markings)>500 or any(not _exact(x) for x in required_markings)
            or len(set(required_markings)) != len(required_markings)):
        raise RuntimeConflict('exact current UI principal required')
    if openfga_api_url():
        raise RuntimeConflict('remote authorization requires its current authority adapter')
    markings = tuple(sorted(required_markings))
    try:
        row = conn.execute('SELECT public.extension_ui_read_principal_a0v_032(%s,%s) AS role',
                           (subject, list(markings))).fetchone()
    except InsufficientPrivilege as exc:
        raise RuntimeConflict('current UI principal unavailable') from exc
    role = _values(row, ('role',))[0]
    if not _exact(role):
        raise RuntimeConflict('current UI role unavailable')
    return CurrentUiPrincipal(scope=scope, subject=subject, roles=(role,), markings=markings)


def enqueue_api_ui_read(*, conn, scope, subject, idempotency_key, request):
    _scope(conn, scope)
    if type(request) is not UiReadRequest or not _exact(subject) or not _exact(idempotency_key):
        raise RuntimeConflict('exact UI read request required')
    body = request.model_dump(mode='json')
    try:
        row = conn.execute('SELECT public.extension_ui_read_enqueue_a0v_032(%s,%s,%s) AS delivery',
                           (subject, idempotency_key, Jsonb(body))).fetchone()
    except (InsufficientPrivilege, CheckViolation) as exc:
        raise RuntimeConflict('UI read delivery rejected') from exc
    value = _values(row, ('delivery',))[0]
    expected = canonical_sha256({'tenant': {'orgId':scope.org_id,'projectId':scope.project_id},
                                 'subject':subject,'request':body})
    if (type(value) is not dict or set(value) != {'requestId','requestHash','state','revision','deadline'}
            or value['requestHash'] != expected or type(value['revision']) is not int or value['revision']<1
            or value['state'] not in ('requested','claimed','succeeded','denied','failed','expired')):
        raise RuntimeConflict('UI delivery response differs')
    try:
        request_id = UUID(value['requestId'])
        deadline = datetime.fromisoformat(value['deadline'])
        if str(request_id) != value['requestId'] or deadline.tzinfo is None:
            raise ValueError('exact delivery identity required')
    except (ValueError, TypeError, AttributeError) as exc:
        raise RuntimeConflict('UI delivery response differs') from exc
    return UiReadDelivery(request_id,expected,value['state'],value['revision'],deadline)
