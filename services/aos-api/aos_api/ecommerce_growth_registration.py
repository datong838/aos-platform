"""Registration Owner: current checks, restricted write, readback, then commit."""
from contextlib import contextmanager

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, validate_idempotency_key
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_preflight import validate_current_registration_target
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.tenant_scope import TenantScope


class FirstDispatchRegistrationService:
    def __init__(self, *, connect, installation_store, configuration_authorize):
        if (not callable(connect) or type(installation_store) is not PostgresInstallationStore
                or type(configuration_authorize) is not CurrentFourSourceConfigurationAuthorization):
            raise TypeError('current production registration dependencies required')
        self._connect=connect
        self._store=installation_store
        self._authorize=configuration_authorize

    @contextmanager
    def _serializable_connection(self):
        with self._connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise ValueError('registration requires an independent idle connection')
            previous=conn.isolation_level
            conn.isolation_level=IsolationLevel.SERIALIZABLE
            try:yield conn
            finally:conn.isolation_level=previous

    def _transaction(self,scope):
        return consumer_connection(self._serializable_connection,dict(org_id=scope.org_id,project_id=scope.project_id))

    @staticmethod
    def _identity(scope,actor):
        if (type(scope) is not TenantScope or type(actor) is not str or not 1<=len(actor)<=240
                or actor.strip()!=actor or not actor.isprintable()):
            raise ValueError('trusted registration actor and scope required')

    @staticmethod
    def _read(conn,scope,key):
        row=conn.execute('''SELECT org_id,project_id,receipt_id,installation_id,generation,group_id,
            idempotency_key,request_hash,payload,content_hash FROM extension_dispatch_registration_receipt
            WHERE org_id=%s AND project_id=%s AND idempotency_key=%s''',(*scope.key,key)).fetchone()
        if row is None:raise LookupError('registration receipt unavailable')
        return decode_registration_receipt(row,scope=scope)

    def register(self, *, scope: TenantScope, request: FirstDispatchRegistrationRequest, actor: str) -> dict:
        self._identity(scope,actor)
        if type(request) is not FirstDispatchRegistrationRequest:
            raise TypeError('validated first registration request required')
        request=FirstDispatchRegistrationRequest.model_validate(request.model_dump(mode='python',by_alias=True))
        with self._transaction(scope) as conn:
            checked=validate_current_registration_target(conn,scope=scope,request=request,actor=actor,
                installation_store=self._store,configuration_authorize=self._authorize)
            if (type(checked) is not dict or checked.get('currentConfigurationValidated') is not True
                    or checked.get('requestHash')!=request.request_hash()):
                raise PermissionError('current registration target was not validated')
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response=conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s) AS receipt',
                (Jsonb(request.model_dump(mode='json',by_alias=True)),actor)).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            result=self._read(conn,scope,request.idempotencyKey)
            if (result['requestHash']!=request.request_hash() or result['actor']!=actor
                    or result['receiptId']!=response.get('receiptId')
                    or result['contentHash']!=response.get('contentHash')
                    or type(response.get('replayed')) is not bool):
                raise ValueError('registration readback differs')
            result['replayed']=response['replayed']
        return result

    def read_receipt(self, *, scope: TenantScope, idempotency_key: str, actor: str) -> dict:
        self._identity(scope,actor);key=validate_idempotency_key(idempotency_key)
        with self._transaction(scope) as conn:
            result=self._read(conn,scope,key)
            row=conn.execute('''SELECT etag_version FROM bundle_installation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
                (*scope.key,result['installationId'])).fetchone()
            if row is None:raise LookupError('receipt installation unavailable')
            locked=self._store.lock_for_transition_in_transaction(conn,org_id=scope.org_id,
                project_id=scope.project_id,installation_id=result['installationId'],expected_etag_version=row['etag_version'])
            permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION)
            if permission(conn=conn,locked=locked,actor=actor) is not True:
                raise PermissionError('current receipt access denied')
            result['historical']=True
        return result
