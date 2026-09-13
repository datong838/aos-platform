"""Transaction-bound current UI caller facts; no grants or execution decision."""
from dataclasses import dataclass

from aos_api.openfga import openfga_api_url, user_key, marking_key
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.lifecycle_store import _require_transaction, _values, RuntimeConflict


@dataclass(frozen=True, slots=True)
class CurrentUiPrincipal:
    scope: TenantScope
    subject: str
    roles: tuple[str, ...]
    markings: tuple[str, ...]


def _exact(value):
    return type(value) is str and bool(value) and value == value.strip() and value.isprintable()


def read_current_ui_principal(*, conn, scope: TenantScope, subject: str,
                              required_markings: tuple[str, ...]) -> CurrentUiPrincipal:
    _require_transaction(conn)
    if type(scope) is not TenantScope or not _exact(subject):
        raise RuntimeConflict('exact current caller required')
    if (type(required_markings) is not tuple or len(required_markings) > 500
            or any(not _exact(label) for label in required_markings)
            or len(set(required_markings)) != len(required_markings)):
        raise RuntimeConflict('exact marking requirements required')
    if openfga_api_url():
        raise RuntimeConflict('remote authorization requires its current authority adapter')
    row = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                       "current_setting('aos.project_id',true) AS project_id").fetchone()
    if _values(row, ('org_id', 'project_id')) != scope.key:
        raise RuntimeConflict('current caller scope differs')
    rows = conn.execute('''SELECT role FROM meta_membership
        WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''', (*scope.key, subject)).fetchall()
    if len(rows) != 1:
        raise RuntimeConflict('current caller membership unavailable')
    role = _values(rows[0], ('role',))[0]
    if not _exact(role):
        raise RuntimeConflict('current caller role unavailable')
    for label in sorted(required_markings):
        rows = conn.execute('''SELECT object_key FROM authz_tuple
            WHERE org_id=%s AND project_id=%s AND user_key=%s
              AND relation='bearer' AND object_key=%s FOR SHARE''',
            (*scope.key, user_key(subject), marking_key(label))).fetchall()
        if len(rows) != 1 or _values(rows[0], ('object_key',))[0] != marking_key(label):
            raise RuntimeConflict('current caller marking unavailable')
    return CurrentUiPrincipal(scope=scope, subject=subject, roles=(role,), markings=tuple(sorted(required_markings)))
