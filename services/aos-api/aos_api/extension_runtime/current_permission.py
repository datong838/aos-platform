"""Current local-PG control authorization; never grants or bootstraps members."""
from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION, VERIFY_INSTALLATION_OPERATION,
    CONFIGURE_RUNTIME_OPERATION, ENABLE_RUNTIME_OPERATION,
    require_control_role, require_target_markings,
)
from aos_api.asset_registry.installation_service import _load_current_lock
from aos_api.openfga import openfga_api_url, user_key, marking_key
from .lifecycle_store import _require_transaction, _values, RuntimeConflict


class CurrentControlPermission:
    def __init__(self, *, operation):
        if operation not in {APPLY_INSTALLATION_OPERATION, VERIFY_INSTALLATION_OPERATION,
                             CONFIGURE_RUNTIME_OPERATION, ENABLE_RUNTIME_OPERATION}:
            raise ValueError('unsupported current control permission')
        self.operation=operation

    def __call__(self, *, conn, locked, actor):
        _require_transaction(conn)
        if openfga_api_url():
            raise RuntimeConflict('remote authorization requires its current authority adapter')
        if type(actor) is not str or not actor or actor!=actor.strip() or not actor.isprintable():
            raise RuntimeConflict('exact operation actor required')
        scope=(locked.org_id,locked.project_id)
        row=conn.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                         "current_setting('aos.project_id',true) AS project_id").fetchone()
        if any(type(v) is not str or not v for v in scope) or _values(row,('org_id','project_id'))!=scope:
            raise RuntimeConflict('current permission tenant differs')
        rows=conn.execute('''SELECT role FROM meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''',(*scope,actor)).fetchall()
        if len(rows)!=1:
            raise RuntimeConflict('current persisted membership unavailable')
        permission_operation=(APPLY_INSTALLATION_OPERATION if self.operation in {
            CONFIGURE_RUNTIME_OPERATION,ENABLE_RUNTIME_OPERATION} else self.operation)
        require_control_role(roles=[_values(rows[0],('role',))[0]],operation=permission_operation)
        lock=_load_current_lock(conn,locked=locked,org_id=scope[0],project_id=scope[1])
        target=lock.payload.permission_diff.target.markings
        granted=[]
        for label in sorted(set(target)):
            rows=conn.execute('''SELECT object_key FROM authz_tuple
                WHERE org_id=%s AND project_id=%s AND user_key=%s
                AND relation='bearer' AND object_key=%s FOR SHARE''',
                (*scope,user_key(actor),marking_key(label))).fetchall()
            if len(rows)==1:granted.append(label)
        require_target_markings(principal_markings=granted,target_markings=target)
        return True
