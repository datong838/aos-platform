"""Scoped data-resume transaction; never a general Task or Provider permission."""
from copy import deepcopy

from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_business_investigation_fulfillment_saga import RESUME_REASON
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
from aos_api.ecommerce_growth_runtime_adapters import (
    AnalysisAdvanceHostService,TransactionBoundConnectFactory,_strict_analysis_command,
    _analysis_exact_ref,_analysis_command_hash,
)


class _AnalysisDataResumeSession:
    def __init__(self, origin, conn, receipt_ref, command):
        if type(origin) is not AnalysisContinuationOrigin:
            raise TypeError('exact current continuation origin required')
        self.origin=origin
        self.conn=conn
        self.scope=origin.context.analysis.scope
        self._receipt_ref=_analysis_exact_ref(receipt_ref,'AnalysisRuntimeReceipt',receipt_required=True).model_dump(
            mode='json',by_alias=True,exclude_none=True)
        self._command=deepcopy(command)
        parsed=_strict_analysis_command(self._command)
        if parsed['operation']!='runtime.analysis.resume_data' or self._command['priorReceiptRef']!=self._receipt_ref:
            raise ValueError('initial data resume requires its original target Receipt')
        self._command_hash=_analysis_command_hash(self._command)
        self._transaction=self._transaction_identity(conn)
        self._active=False

    @property
    def command(self):
        return deepcopy(self._command)

    @staticmethod
    def _transaction_identity(conn):
        return dict(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS xid').fetchone())

    def _same_transaction(self, conn, scope):
        if scope!=self.scope or self._transaction_identity(conn)!=self._transaction:
            raise PermissionError('analysis resume must stay in its original tenant transaction')
        if _analysis_command_hash(self._command)!=self._command_hash:
            raise ValueError('analysis resume command changed')
        _strict_analysis_command(self._command)

    def resume(self):
        from aos_api.ecommerce_growth_host_composition import build_analysis_resume_registry,build_ecommerce_growth_host_ports
        self._same_transaction(self.conn,self.scope)
        def current(origin):
            if self._active:raise ValueError('analysis resume session is already executing')
            self._active=True
            try:
                ports=build_ecommerce_growth_host_ports(build_analysis_resume_registry(self),
                    connect_factory=TransactionBoundConnectFactory(HostTransaction(self.conn),self.scope))
                return ports.runtime_port.commit(dispatch_ref=IssuedDispatchRef(**origin['context']['dispatch']),command=self.command)
            finally:
                self._active=False
        return self.origin.run_current(self.conn,receipt_ref=self._receipt_ref,execute=current)

    def authorize_task_resume(self, conn, scope, run, task, *, actor, idempotency_key, reason,
                              expected_run_version, expected_task_version):
        self._same_transaction(conn,scope)
        if not self._active:
            raise PermissionError('Task resume requires the enclosing current-source session')
        if (actor!=AnalysisAdvanceHostService.executor_identity or reason!=RESUME_REASON
                or type(idempotency_key) is not str or not idempotency_key.startswith('bi-fulfillment-resume-')):
            raise PermissionError('fixed internal analysis data resume required')
        def current(origin):
            root=origin['analysisReceipt']
            domain=EcommerceInvestigationProfileCatalog().read(origin['context']['source']['case']['analysisType'])
            if domain is None or domain[0].safety_mode!='read-only':
                raise PermissionError('only read-only analysis may use this continuation')
            if (run['run_id']!=root['taskRunRef']['resourceId'] or run['task_id']!=task['task_id']
                    or run['version']!=expected_run_version or task['version']!=expected_task_version):
                raise ValueError('current analysis TaskRun differs')
            parsed=_strict_analysis_command(self._command)
            runtime=AnalysisAdvanceHostService()._resume_authorities(transaction=HostTransaction(conn),scope=scope,
                command=self.command,parsed=parsed,prior=root)[3]
            if (runtime.task_run_ref.resource_id!=run['run_id'] or runtime.task_run_ref.version!=expected_run_version
                    or runtime.task_ref.resource_id!=task['task_id'] or runtime.task_ref.version!=expected_task_version):
                raise ValueError('validated data runtime differs from resumed task')
        self.origin.run_current(self.conn,receipt_ref=self._receipt_ref,execute=current)


class _CurrentAnalysisResumeHost(AnalysisAdvanceHostService):
    def __init__(self, session):
        if type(session) is not _AnalysisDataResumeSession:raise TypeError('exact resume session required')
        self._session=session

    def _command_matches(self, transaction, scope, command):
        self._session._same_transaction(transaction,scope)
        if command!=self._session.command:raise ValueError('scoped analysis resume command differs')

    def revalidate(self, *, transaction, scope, dispatch, command):
        self._command_matches(transaction,scope,command)
        return super().revalidate(transaction=transaction,scope=scope,dispatch=dispatch,command=command)

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        self._command_matches(transaction,scope,command)
        return super().execute(transaction=transaction,scope=scope,dispatch_ref=dispatch_ref,command=command,
                               checked_at=checked_at,occurred_at=occurred_at)

    def _task_store_for_resume(self, transaction, scope):
        return AipTaskStore(TransactionBoundConnectFactory(transaction,scope),_analysis_resume_session=self._session)
