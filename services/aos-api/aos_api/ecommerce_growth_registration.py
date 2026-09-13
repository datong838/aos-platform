"""Registration Owner: current checks, restricted write, readback, then commit."""
from contextlib import contextmanager
from uuid import UUID

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from aos_api.asset_registry.control_policy import APPLY_INSTALLATION_OPERATION, validate_idempotency_key
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.ecommerce_growth_registration_qualification import qualify_registration_release
from aos_api.ecommerce_growth_registration_contracts import FirstDispatchRegistrationRequest
from aos_api.ecommerce_growth_registration_preflight import validate_current_registration_target, validate_current_registration_assets
from aos_api.ecommerce_growth_registration_receipt import decode_registration_receipt
from aos_api.ecommerce_growth_registration_origin import RegistrationReceiptRef, verify_registration_origin
from aos_api.extension_runtime.configuration_authorization import CurrentFourSourceConfigurationAuthorization
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.current_permission import CurrentControlPermission
from aos_api.ecommerce_growth_registration_withdrawal import RegistrationWithdrawalRequest
from aos_api.ecommerce_growth_withdrawal_receipt import decode_withdrawal_receipt
from aos_api.tenant_scope import TenantScope
from aos_api.extension_runtime.storage_ports import require_runtime_role


class FirstDispatchRegistrationService:
    def __init__(self, *, connect, installation_store, configuration_authorize, release_policy):
        if (not callable(connect) or type(installation_store) is not PostgresInstallationStore
                or type(configuration_authorize) is not CurrentFourSourceConfigurationAuthorization
                or type(release_policy) is not ReleasePolicy):
            raise TypeError('current production registration dependencies required')
        self._connect=connect
        self._store=installation_store
        self._authorize=configuration_authorize
        self._release_policy=release_policy

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
    def _read(conn,scope,key,installation_id):
        row=conn.execute('''SELECT org_id,project_id,receipt_id,installation_id,generation,group_id,
            idempotency_key,request_hash,payload,content_hash FROM extension_dispatch_registration_receipt
            WHERE org_id=%s AND project_id=%s AND idempotency_key=%s AND installation_id=%s''',
            (*scope.key,key,installation_id)).fetchone()
        if row is None:raise LookupError('registration receipt unavailable')
        return decode_registration_receipt(row,scope=scope)

    @staticmethod
    def _require_current_transaction(conn,scope):
        if conn.info.transaction_status != TransactionStatus.INTRANS:
            raise PermissionError('current registration authority requires an active transaction')
        state=conn.execute("SELECT current_user AS role, current_setting('transaction_isolation') AS isolation").fetchone()
        if state['role']!='aos_runtime' or state['isolation']!='serializable':
            raise PermissionError('current registration authority requires serializable runtime scope')
        require_runtime_role(conn,org_id=scope.org_id,project_id=scope.project_id,
            protected_tables=('public.extension_runtime_binding','public.extension_dispatch_registration_receipt'))

    def validate_registration_origin_in_transaction(self,conn,**kwargs):
        return self._validate_origin(conn,require_ready=True,**kwargs)

    def validate_cutover_registration_assets_in_transaction(self,conn,**kwargs):
        """Assets and origin only; the cutover Owner validates the exact runtime phase."""
        return self._validate_origin(conn,require_ready=False,**kwargs)

    def _validate_origin(self,conn,*,scope: TenantScope,actor: str,require_ready: bool,
            receipt_ref: RegistrationReceiptRef,dispatch_snapshot: list[dict],installation_id: str,
            generation: str,execution_epoch: int,binding_revision: int) -> dict:
        """Compose stored provenance and current authority; caller retains transaction ownership."""
        self._identity(scope,actor)
        if type(receipt_ref) is not RegistrationReceiptRef:
            raise TypeError('exact registration Receipt reference required')
        receipt_ref=RegistrationReceiptRef.model_validate(receipt_ref.model_dump())
        self._require_current_transaction(conn,scope)
        row=conn.execute("""SELECT org_id,project_id,receipt_id,installation_id,generation,group_id,
            idempotency_key,request_hash,payload,content_hash FROM public.extension_dispatch_registration_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*scope.key,receipt_ref.resourceId)).fetchone()
        if row is None:
            raise LookupError('registration receipt unavailable')
        request=verify_registration_origin(row=row,scope=scope,receipt_ref=receipt_ref,
            dispatch_snapshot=dispatch_snapshot,installation_id=installation_id,generation=generation,
            execution_epoch=execution_epoch,binding_revision=binding_revision)
        result=self._validate_current_authority(conn,scope=scope,request=request,actor=actor,require_ready=require_ready)
        return dict(result,receiptRef=receipt_ref.model_dump(mode='json'))

    def validate_current_authority_in_transaction(self,conn,**kwargs):
        return self._validate_current_authority(conn,require_ready=True,**kwargs)

    def _validate_current_authority(self, conn, *, scope: TenantScope,require_ready: bool,
            request: FirstDispatchRegistrationRequest, actor: str) -> dict:
        """Revalidate current authority without owning or committing the caller's transaction."""
        self._identity(scope,actor)
        if type(request) is not FirstDispatchRegistrationRequest:
            raise TypeError('validated first registration request required')
        request=FirstDispatchRegistrationRequest.model_validate(request.model_dump(mode='python',by_alias=True))
        self._require_current_transaction(conn,scope)
        checked=(validate_current_registration_target if require_ready else validate_current_registration_assets)(conn,scope=scope,request=request,actor=actor,
            installation_store=self._store,configuration_authorize=self._authorize)
        if (type(checked) is not dict or checked.get('currentConfigurationValidated') is not True
                or checked.get('requestHash')!=request.request_hash()):
            raise PermissionError('current registration target was not validated')
        baseline=self._store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,
            project_id=scope.project_id,requested_ref=request.installationRef)
        qualified=qualify_registration_release(conn,lock=baseline.lock,release_policy=self._release_policy)
        if (type(qualified) is not dict
                or qualified.get('schemaVersion')!='aos.ecommerce.registration-release-qualification/v1'
                or qualified.get('lockHash')!=request.installationRef.lock_hash
                or qualified.get('packageId')!='solution.ecommerce.growth'
                or type(qualified.get('operationCount')) is not int or qualified['operationCount']!=9
                or qualified.get('executable') is not False):
            raise PermissionError('current signed registration release was not validated')
        return dict(requestHash=request.request_hash(),currentConfigurationValidated=True,
                    currentReleaseValidated=True,runtimeStateValidated=require_ready,executable=False)

    def register(self, *, scope: TenantScope, request: FirstDispatchRegistrationRequest, actor: str) -> dict:
        self._identity(scope,actor)
        if type(request) is not FirstDispatchRegistrationRequest:
            raise TypeError('validated first registration request required')
        request=FirstDispatchRegistrationRequest.model_validate(request.model_dump(mode='python',by_alias=True))
        with self._transaction(scope) as conn:
            self.validate_current_authority_in_transaction(conn,scope=scope,request=request,actor=actor)
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response=conn.execute('SELECT extension_dispatch_register_a0v_027(%s,%s) AS receipt',
                (Jsonb(request.model_dump(mode='json',by_alias=True)),actor)).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            result=self._read(conn,scope,request.idempotencyKey,request.installationRef.installation_id)
            if (result['requestHash']!=request.request_hash() or result['actor']!=actor
                    or result['receiptId']!=response.get('receiptId')
                    or result['contentHash']!=response.get('contentHash')
                    or type(response.get('replayed')) is not bool):
                raise ValueError('registration readback differs')
            result['replayed']=response['replayed']
        return result

    def read_receipt(self, *, scope: TenantScope, installation_id: str, idempotency_key: str, actor: str) -> dict:
        self._identity(scope,actor);key=validate_idempotency_key(idempotency_key)
        if type(installation_id) is not str or str(UUID(installation_id))!=installation_id:
            raise ValueError('canonical receipt installation required')
        with self._transaction(scope) as conn:
            result=self._read(conn,scope,key,installation_id)
            self._authorize_receipt_access(conn,scope,result['installationId'],actor)
            result['historical']=True
        return result

    def _authorize_receipt_access(self,conn,scope,installation_id,actor):
        row=conn.execute('''SELECT etag_version FROM bundle_installation
            WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR UPDATE''',
            (*scope.key,installation_id)).fetchone()
        if row is None:raise LookupError('receipt installation unavailable')
        locked=self._store.lock_for_transition_in_transaction(conn,org_id=scope.org_id,
            project_id=scope.project_id,installation_id=installation_id,expected_etag_version=row['etag_version'])
        permission=CurrentControlPermission(operation=APPLY_INSTALLATION_OPERATION)
        if permission(conn=conn,locked=locked,actor=actor) is not True:
            raise PermissionError('current receipt access denied')

    @staticmethod
    def _withdrawal_origin(conn,scope,receipt_id):
        row=conn.execute("""SELECT org_id,project_id,receipt_id,installation_id,generation,group_id,
            idempotency_key,request_hash,payload,content_hash FROM public.extension_dispatch_registration_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",(*scope.key,receipt_id)).fetchone()
        if row is None:raise LookupError('withdrawal origin unavailable')
        return row

    def _read_withdrawal(self,conn,scope,key,installation_id):
        row=conn.execute("""SELECT w.org_id,w.project_id,w.receipt_id,w.registration_receipt_id,
            w.idempotency_key,w.request_hash,w.payload,w.content_hash
            FROM public.extension_dispatch_withdrawal_receipt w
            JOIN public.extension_dispatch_registration_receipt r
              ON r.org_id=w.org_id AND r.project_id=w.project_id AND r.receipt_id=w.registration_receipt_id
            WHERE w.org_id=%s AND w.project_id=%s AND w.idempotency_key=%s AND r.installation_id=%s""",
            (*scope.key,key,installation_id)).fetchone()
        if row is None:raise LookupError('withdrawal receipt unavailable')
        origin=self._withdrawal_origin(conn,scope,row['registration_receipt_id'])
        return decode_withdrawal_receipt(row,registration_row=origin,scope=scope)

    def withdraw(self, *, scope: TenantScope, installation_id: str, request: RegistrationWithdrawalRequest, actor: str):
        self._identity(scope,actor)
        if type(installation_id) is not str or str(UUID(installation_id))!=installation_id:
            raise ValueError('canonical withdrawal installation required')
        if type(request) is not RegistrationWithdrawalRequest:
            raise TypeError('strict withdrawal request required')
        request=RegistrationWithdrawalRequest.model_validate(request.model_dump())
        with self._transaction(scope) as conn:
            self._require_current_transaction(conn,scope)
            require_runtime_role(conn,org_id=scope.org_id,project_id=scope.project_id,
                protected_tables=('public.extension_dispatch_withdrawal_receipt',))
            row=self._withdrawal_origin(conn,scope,request.registrationReceiptRef.resourceId)
            origin=decode_registration_receipt(row,scope=scope)
            if origin['installationId']!=installation_id:
                raise ValueError('withdrawal installation path differs')
            if origin['contentHash']!=request.registrationReceiptRef.contentHash:
                raise ValueError('withdrawal origin hash differs')
            # Same ordering as the restricted SQL entry; permission readers may
            # lock installation rows only after the shared cutover group lock.
            prefix=scope.org_id+chr(31)+scope.project_id+chr(31)
            for suffix in ('ecommerce-first-registration',origin['groupId'],origin['installationId'],
                    origin['installationId']+chr(31)+origin['generation']):
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(prefix+suffix,))
            self._authorize_receipt_access(conn,scope,origin['installationId'],actor)
            conn.execute('SET LOCAL ROLE aos_extension_maintainer')
            response=conn.execute('SELECT public.extension_dispatch_withdraw_a0v_030(%s,%s) AS receipt',
                (Jsonb(request.model_dump(mode='json')),actor)).fetchone()['receipt']
            conn.execute('SET LOCAL ROLE aos_runtime')
            result=self._read_withdrawal(conn,scope,request.idempotencyKey,origin['installationId'])
            if (result['requestHash']!=request.request_hash() or result['actor']!=actor
                    or result['receiptId']!=response.get('receiptId')
                    or result['contentHash']!=response.get('contentHash')
                    or type(response.get('replayed')) is not bool):
                raise ValueError('withdrawal readback differs')
            result['replayed']=response['replayed']
        return result

    def read_withdrawal_receipt(self, *, scope: TenantScope,installation_id: str,idempotency_key: str,actor: str):
        self._identity(scope,actor);key=validate_idempotency_key(idempotency_key)
        if type(installation_id) is not str or str(UUID(installation_id))!=installation_id:
            raise ValueError('canonical withdrawal installation required')
        with self._transaction(scope) as conn:
            self._require_current_transaction(conn,scope)
            require_runtime_role(conn,org_id=scope.org_id,project_id=scope.project_id,
                protected_tables=('public.extension_dispatch_withdrawal_receipt',))
            result=self._read_withdrawal(conn,scope,key,installation_id)
            self._authorize_receipt_access(conn,scope,installation_id,actor)
            result['historical']=True
        return result
