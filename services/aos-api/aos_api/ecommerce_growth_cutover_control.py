"""Current product authority around existing receipt-first cutover phases."""
from contextlib import contextmanager
from uuid import UUID

from aos_api.ecommerce_growth_cutover import (
    EcommerceGrowthCutoverStore, EcommerceGrowthCutoverConflict, CutoverPrepareRequest, CutoverCommitRequest,
    CutoverFinalizeRequest, CutoverRollbackRequest, CutoverExactRef,
)
from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService

_PHASES = {
    'prepare': (CutoverPrepareRequest, 'prepare_activation'),
    'pause': (CutoverCommitRequest, 'begin_activation_commit'),
    'commit': (CutoverCommitRequest, 'commit_activation'),
    'validate': (CutoverFinalizeRequest, 'validate_activation'),
    'resume': (CutoverFinalizeRequest, 'resume_activation'),
    'rollback-prepare': (CutoverRollbackRequest, 'prepare_validation_rollback'),
    'rollback-commit': (CutoverRollbackRequest, 'commit_validation_rollback'),
}


class EcommerceGrowthCutoverControl:
    def __init__(self, store):
        if (type(store) is not EcommerceGrowthCutoverStore
                or type(store._registration_service) is not FirstDispatchRegistrationService):
            raise TypeError('current production cutover and registration services required')
        self._store = store

    def execute(self, *, scope, phase, request, actor, validate_receipt_ref=None,
                expected_installation_id=None, expected_installation_etag=None):
        FirstDispatchRegistrationService._identity(scope, actor)
        if expected_installation_id is not None or expected_installation_etag is not None:
            if (type(expected_installation_id) is not str
                    or str(UUID(expected_installation_id)) != expected_installation_id
                    or type(expected_installation_etag) is not int or expected_installation_etag < 1):
                raise ValueError('exact installation precondition required')
        if type(phase) is not str or phase not in _PHASES:
            raise ValueError('explicit cutover phase required')
        request_type, method = _PHASES[phase]
        if type(request) is not request_type:
            raise TypeError('exact cutover phase request required')
        request = request_type.model_validate(request.model_dump(mode='python', by_alias=True))
        if phase == 'resume':
            if type(validate_receipt_ref) is not CutoverExactRef:
                raise TypeError('exact validation receipt required')
            validate_receipt_ref = CutoverExactRef.model_validate(validate_receipt_ref.model_dump(mode='python'))
        elif validate_receipt_ref is not None:
            raise ValueError('unexpected validation receipt')
        source = self._store
        with source._connect_factory(scope) as conn:
            source._require_maintainer(conn)
            if phase == 'prepare':
                installation_id = str(request.target_installation_id)
            else:
                operation_id = (request.activation_operation_id if isinstance(request, CutoverRollbackRequest)
                                else request.cutover_operation_id)
                row = conn.execute(f'''SELECT target_installation_id FROM {source._schema}.extension_dispatch_cutover_operation
                    WHERE org_id=%s AND project_id=%s AND cutover_operation_id=%s AND kind='activate' ''',
                    (*scope.key, operation_id)).fetchone()
                if row is None:
                    raise LookupError('current activation unavailable')
                installation_id = str(row['target_installation_id'])
            if expected_installation_id is not None and installation_id != expected_installation_id:
                raise EcommerceGrowthCutoverConflict('cutover installation differs from product target')
            conn.execute('SET LOCAL ROLE aos_runtime')
            source._registration_service._authorize_receipt_access(conn, scope, installation_id, actor)
            if expected_installation_etag is not None:
                row = conn.execute(f"""SELECT etag_version FROM {source._schema}.bundle_installation
                    WHERE org_id=%s AND project_id=%s AND installation_id=%s""",
                    (*scope.key, installation_id)).fetchone()
                if row is None or row['etag_version'] != expected_installation_etag:
                    from aos_api.extension_runtime.lifecycle_store import RuntimeRevisionConflict
                    raise RuntimeRevisionConflict('installation precondition changed')
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            borrowed = False
            @contextmanager
            def same_transaction(current_scope):
                nonlocal borrowed
                if borrowed or current_scope != scope:
                    raise ValueError('one scoped cutover transaction required')
                borrowed = True
                yield conn
            store = EcommerceGrowthCutoverStore(same_transaction, schema=source._schema,
                registration_service=source._registration_service)
            extra = {'validate_receipt_ref': validate_receipt_ref} if phase == 'resume' else {}
            return getattr(store, method)(scope, request, actor=actor, **extra)
