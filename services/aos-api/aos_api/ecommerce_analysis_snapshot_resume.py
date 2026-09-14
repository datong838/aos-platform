"""Exact internal snapshot session; no public runtime registration or effects."""
from copy import deepcopy

from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext, _CurrentSnapshotResumeStage
from aos_api.ecommerce_analysis_snapshot_resume_contracts import strict_snapshot_resume_command
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService, _analysis_command_hash
from aos_api.extension_runtime.runtime_gate import _reject_deferred


SNAPSHOT_RESUME_REASON = 'A0V exact snapshot fulfillment/readiness/evidence resume'


class _AnalysisSnapshotResumeSession:
    def __init__(self, context, conn, command):
        if type(context) is not AnalysisSnapshotResumeContext:
            raise TypeError('exact original snapshot resume context required')
        self.context, self.conn, self.scope = context, conn, context.scope
        self._command = deepcopy(command)
        strict_snapshot_resume_command(self._command)
        self._command_hash = _analysis_command_hash(self._command)
        self._transaction = self._identity(conn)
        self._stage = None
        self._active = False

    @staticmethod
    def _identity(conn):
        return dict(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS xid').fetchone())

    @property
    def command(self):
        return deepcopy(self._command)

    @property
    def control_key(self):
        return 'bi-snapshot-resume-' + _analysis_command_hash(
            dict(tenant=self.scope.key,commandHash=self._command_hash))[7:]

    def _same_transaction(self, conn, scope):
        if scope != self.scope or self._identity(conn) != self._transaction:
            raise PermissionError('snapshot session requires its original tenant transaction')
        if _analysis_command_hash(self._command) != self._command_hash:
            raise ValueError('snapshot session command changed')
        strict_snapshot_resume_command(self._command)

    def run_current(self, execute):
        if not callable(execute):
            raise TypeError('synchronous internal snapshot consumer required')
        if self._active:
            raise ValueError('snapshot session is already executing')
        self._same_transaction(self.conn,self.scope)

        def current(stage):
            if type(stage) is not _CurrentSnapshotResumeStage or self._active:
                raise TypeError('exact active original snapshot stage required')
            stage.assert_current(self.conn,self.scope)
            if stage.command != self._command:
                raise ValueError('snapshot stage command differs')
            self._stage, self._active = stage, True
            try:
                result = execute(self)
                _reject_deferred(result)
                self._same_transaction(self.conn,self.scope)
                stage.assert_current(self.conn,self.scope)
                return result
            finally:
                self._stage, self._active = None, False

        return self.context.run_current(self.conn,command=self.command,execute=current)

    def authorize_task_resume(self, conn, scope, run, task, *, actor, idempotency_key, reason,
                              expected_run_version, expected_task_version):
        self._same_transaction(conn,scope)
        if not self._active or type(self._stage) is not _CurrentSnapshotResumeStage:
            raise PermissionError('Task resume requires the enclosing snapshot session')
        self._stage.assert_current(conn,scope)
        if self._stage.command != self._command:
            raise ValueError('snapshot stage command differs')
        if (actor != AnalysisAdvanceHostService.executor_identity or reason != SNAPSHOT_RESUME_REASON
                or idempotency_key != self.control_key):
            raise PermissionError('exact internal snapshot resume command required')
        runtime, requirement = self._stage.runtime, self._stage.requirement
        domain = EcommerceInvestigationProfileCatalog().read(requirement.purpose_code)
        if (domain is None or domain[0].safety_mode != 'read-only'
                or domain[0].exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True) != self._command['profileRef']):
            raise PermissionError('exact read-only analysis profile required')
        if (any(type(value) is not int for value in
                    (expected_run_version,expected_task_version,run['version'],task['version']))
                or (run['org_id'],run['project_id']) != scope.key
                or (task['org_id'],task['project_id']) != scope.key
                or run['run_id'] != runtime.task_run_ref.resource_id
                or run['task_id'] != task['task_id'] or task['task_id'] != runtime.task_ref.resource_id
                or run['version'] != expected_run_version or expected_run_version != runtime.task_run_ref.version
                or task['version'] != expected_task_version or expected_task_version != runtime.task_ref.version
                or run['status'] != 'paused' or task['status'] != 'paused'
                or run['plan_revision_id'] != runtime.plan_ref.resource_id):
            raise ValueError('snapshot session differs from the original paused Task and TaskRun')
