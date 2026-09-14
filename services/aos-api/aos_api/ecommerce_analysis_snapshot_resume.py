"""Exact internal snapshot session; no public runtime registration or effects."""
from copy import deepcopy

from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext, _CurrentSnapshotResumeStage
from aos_api.ecommerce_analysis_snapshot_resume_contracts import strict_snapshot_resume_command
from aos_api.ecommerce_business_investigation_profile_catalog import EcommerceInvestigationProfileCatalog
from aos_api.ecommerce_growth_runtime_adapters import AnalysisAdvanceHostService, AnalysisAdvanceAdapter, _analysis_command_hash
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
        self._reading = False

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
        actual = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if (actual['org_id'],actual['project_id']) != scope.key:
            raise PermissionError('snapshot session actual database tenant differs')
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

    def resume(self):
        """Read a committed outcome first; only an unissued request may transition."""
        from aos_api.ecommerce_growth_host_composition import build_analysis_snapshot_resume_registry, build_ecommerce_growth_host_ports
        from aos_api.ecommerce_growth_canonical_router import IssuedDispatchRef
        from aos_api.ecommerce_growth_host_ports import HostTransaction
        from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,_HostAnalysisReceiptStore

        if self._active or self._reading:
            raise ValueError('snapshot session is already executing or checking a receipt')
        self._same_transaction(self.conn,self.scope)

        def probe(origin):
            tx = HostTransaction(self.conn)
            receipts = _HostAnalysisReceiptStore(tx,self.scope)
            saved = receipts.read(self.command['idempotencyKey'])
            if saved is not None:
                if (saved.get('requestHash') != self.command['requestHash']
                        or receipts.read_exact(saved.get('receiptRef')) != saved):
                    raise ValueError('snapshot committed command or exact Receipt differs')
                self._reading = True
                try:
                    return _CurrentSnapshotAnalysisHost(self)._verify_snapshot_commit(
                        transaction=tx,scope=self.scope,command=self.command,receipt=saved,committed=True)
                finally:
                    self._reading = False
            trace = tx.execute("""SELECT
                EXISTS(SELECT 1 FROM aip_evidence WHERE org_id=%s AND project_id=%s
                    AND evidence_type='run.control' AND source_ref=%s) AS task_trace,
                EXISTS(SELECT 1 FROM public.ecommerce_investigation_run_state_transition_receipt
                    WHERE org_id=%s AND project_id=%s AND operation='business_investigation_run.resume_after_data'
                    AND idempotency_key=%s) AS domain_trace""",
                (*self.scope.key,'run-control:resume:'+self.control_key,*self.scope.key,self.control_key+':domain')).fetchone()
            if trace['task_trace'] or trace['domain_trace']:
                raise ValueError('snapshot resume has transition traces; reconcile the missing unified Receipt before retrying')
            return None

        def consume(current):
            def origin_current(origin):
                ports = build_ecommerce_growth_host_ports(build_analysis_snapshot_resume_registry(current),
                    connect_factory=TransactionBoundConnectFactory(HostTransaction(self.conn),self.scope))
                return ports.runtime_port.commit(dispatch_ref=IssuedDispatchRef(**origin['context']['dispatch']),command=self.command)
            return self.context.origin.run_current(self.conn,receipt_ref=self.command['priorReceiptRef'],execute=origin_current)
        with self.conn.transaction():
            committed = self.context.origin.run_current(self.conn,
                receipt_ref=self.command['priorReceiptRef'],execute=probe)
            if committed is not None:
                return committed
            return self.run_current(consume)

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

    def _resume_states(self):
        """Internal first transition only; the caller must still save its unified Receipt."""
        from aos_api.aip_task_store import AipTaskStore
        from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
        from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinder
        from aos_api.aip_business_investigation_fulfillment_saga import BusinessInvestigationFulfillmentResumeSaga
        from aos_api.data_requirement_store import DataRequirementStore
        from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
        from aos_api.ecommerce_growth_host_ports import HostTransaction
        from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, _AnalysisRunAndTaskResumer
        from aos_api.ecommerce_analysis_snapshot_resume_contracts import validate_snapshot_resume_result

        self._same_transaction(self.conn,self.scope)
        if not self._active or type(self._stage) is not _CurrentSnapshotResumeStage:
            raise PermissionError('state transition requires the enclosing snapshot session')
        self._stage.assert_current(self.conn,self.scope)
        parsed = strict_snapshot_resume_command(self.command)
        requirement, runtime = self._stage.requirement, self._stage.runtime
        tx = HostTransaction(self.conn)
        factory = TransactionBoundConnectFactory(tx,self.scope)
        runs = BusinessInvestigationRunStore(factory)
        tasks = AipTaskStore(factory,_analysis_resume_session=self)
        run = runs.get_verified(self.scope,requirement.run_ref.resource_id)
        if (run.authority.version != requirement.run_ref.revision
                or run.authority.content_hash != requirement.run_ref.content_hash
                or run.authority.case_ref != parsed['caseRef']
                or run.state.lifecycle.value != 'WAITING_DATA' or run.state.control.value != 'RUNNING'
                or run.state.pending_requirement_ref != parsed['requirementRef']
                or run.state.uncertain_command is not None
                or DataRequirementStore(factory).get_current(self.scope,requirement.requirement_id) != requirement):
            raise ValueError('snapshot state transition requires the original current waiting Run')
        compilation = BusinessInvestigationCompilationReceiptStore(factory).get_for_run(self.scope,requirement.run_ref)
        current_runtime = BusinessInvestigationRuntimeBinder(tasks).bind_receipt(self.scope,compilation,run)
        checkpoint = current_runtime.checkpoint_ref
        if (current_runtime != runtime or checkpoint is None
                or checkpoint.resource_id != parsed['checkpointRef'].resource_id
                or checkpoint.sequence != parsed['checkpointRef'].revision
                or 'sha256:'+checkpoint.state_hash != parsed['checkpointRef'].content_hash
                or runtime.plan_ref.resource_id != parsed['priorPlanRef'].resource_id
                or runtime.plan_ref.revision != parsed['priorPlanRef'].revision
                or 'sha256:'+runtime.plan_ref.content_hash != parsed['priorPlanRef'].content_hash):
            raise ValueError('snapshot current runtime differs from its prepared original stage')
        event_time = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        resumer = _AnalysisRunAndTaskResumer(runs,tasks,parsed['requirementRef'],
            run.authority.run_id,run.state.version,event_time)
        result = resumer.resume_run(self.scope,runtime.task_run_ref.resource_id,
            expected_run_version=runtime.task_run_ref.version,expected_task_version=runtime.task_ref.version,
            actor=AnalysisAdvanceHostService.executor_identity,idempotency_key=self.control_key,
            reason=SNAPSHOT_RESUME_REASON)
        BusinessInvestigationFulfillmentResumeSaga._validate_resume_result(result,runtime)
        after = runs.get_verified(self.scope,run.authority.run_id)
        domain_receipt = runs.read_data_resume_receipt(self.scope,run.authority.run_id,parsed['requirementRef'],
            expected_version=run.state.version,idempotency_key=self.control_key+':domain')
        timeline = tasks.timeline(self.scope,runtime.task_run_ref.resource_id)
        if (after.authority != run.authority or domain_receipt is None or domain_receipt != after.state
                or resumer.run_state != after.state or after.state.version != run.state.version+1
                or timeline.run != result.run or timeline.task != result.task):
            raise ValueError('snapshot original state transition receipts differ')
        control = tasks._control_request('resume',runtime.task_run_ref.version,runtime.task_ref.version,SNAPSHOT_RESUME_REASON)
        controls = tx.execute("""SELECT payload,created_by FROM aip_evidence
            WHERE org_id=%s AND project_id=%s AND run_id=%s AND evidence_type='run.control' AND source_ref=%s""",
            (*self.scope.key,runtime.task_run_ref.resource_id,'run-control:resume:'+self.control_key)).fetchall()
        if (len(controls) != 1 or controls[0]['payload'] != control
                or controls[0]['created_by'] != AnalysisAdvanceHostService.executor_identity):
            raise ValueError('snapshot original Task control Receipt differs')
        bundle = dict(self._command['evidenceRefs'][0])
        bundle['contentHash'] = bundle['contentHash'][7:]
        return validate_snapshot_resume_result(self.command,dict(
            tenant=dict(orgId=self.scope.org_id,projectId=self.scope.project_id),
            commandId=parsed['key'],requestHash=self._command['requestHash'],
            dataRequirementRef=self._command['requirementRef'],fulfillmentReceiptRef=self._command['fulfillmentRef'],
            sourceReadinessRef=self._command['sourceReadinessRef'],businessEvidenceRef=self._command['businessEvidenceRef'],
            evidenceBundleRef=bundle,checkpointRef=self._command['checkpointRef'],
            taskRef=dict(resourceType='Task',resourceId=result.task.id,version=result.task.version),
            taskRunRef=dict(resourceType='TaskRun',resourceId=result.run.id,version=result.run.version)),scope=self.scope)


class _CurrentSnapshotAnalysisHost(AnalysisAdvanceHostService):
    def __init__(self, session):
        if type(session) is not _AnalysisSnapshotResumeSession:
            raise TypeError('exact snapshot session required')
        self._session = session

    def _parse_command(self, command):
        return strict_snapshot_resume_command(command)

    def _matches(self, transaction, scope, command):
        self._session._same_transaction(transaction,scope)
        stage = self._session._stage
        if not self._session._active or type(stage) is not _CurrentSnapshotResumeStage:
            raise PermissionError('snapshot Host requires its active current stage')
        stage.assert_current(transaction,scope)
        if command != self._session.command or stage.command != command:
            raise ValueError('snapshot Host command differs from the current session')

    def revalidate(self, *, transaction, scope, dispatch, command):
        self._matches(transaction,scope,command)
        return super().revalidate(transaction=transaction,scope=scope,dispatch=dispatch,command=command)

    def _read_successor(self, transaction, scope, command, *, committed=False):
        from aos_api.aip_task_store import AipTaskStore
        from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
        from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
        from aos_api.data_requirement_store import DataRequirementStore
        from aos_api.ecommerce_growth_runtime_adapters import (
            TransactionBoundConnectFactory,_HostAnalysisReceiptStore,_validate_prior_analysis_receipt,_analysis_plan_ref,
            _strict_resume_control_receipt,
        )
        if committed:
            self._session._same_transaction(transaction,scope)
            if not self._session._reading or self._session._active or command != self._session.command:
                raise PermissionError('committed snapshot verification requires the current read-only frame')
        else:
            self._matches(transaction,scope,command)
        parsed = self._parse_command(command)
        stage = self._session._stage
        original = None if committed else stage.runtime
        factory = TransactionBoundConnectFactory(transaction,scope)
        prior = _HostAnalysisReceiptStore(transaction,scope).read_exact(command['priorReceiptRef'])
        _validate_prior_analysis_receipt(command,parsed,prior)
        requirement = DataRequirementStore(factory).get_exact(scope,parsed['requirementRef']) if committed else stage.requirement
        if (requirement.run_ref.model_dump(mode='json',by_alias=True,exclude_none=True) != prior['runRef']
                or requirement.case_ref != parsed['caseRef'] or requirement.checkpoint_ref != parsed['checkpointRef']
                or requirement.cutoff_at != parsed['cutoff']):
            raise ValueError('snapshot successor Run differs from its original receipt')
        runs = BusinessInvestigationRunStore(factory)
        run = runs.get_verified(scope,requirement.run_ref.resource_id)
        compilation = BusinessInvestigationCompilationReceiptStore(factory).get_for_run(scope,requirement.run_ref)
        if (run.authority.version != requirement.run_ref.revision or run.authority.content_hash != requirement.run_ref.content_hash
                or compilation.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True) != prior['compilationRef']
                or _analysis_plan_ref(compilation.plan_ref) != command['priorPlanRef']):
            raise ValueError('snapshot successor original Run or compilation changed')
        tasks = AipTaskStore(factory)
        task_run_id = prior['taskRunRef']['resourceId']
        controls = transaction.execute("""SELECT payload,created_by FROM aip_evidence
            WHERE org_id=%s AND project_id=%s AND run_id=%s AND evidence_type='run.control' AND source_ref=%s""",
            (*scope.key,task_run_id,'run-control:resume:'+self._session.control_key)).fetchall()
        if (len(controls) != 1 or not _strict_resume_control_receipt(controls[0]['payload'])
                or controls[0]['created_by'] != self.executor_identity):
            raise ValueError('snapshot successor Task control Receipt differs')
        control = controls[0]['payload']
        if (control['reason'] != SNAPSHOT_RESUME_REASON or control['expectedRunVersion'] != prior['taskRunRef']['revision']
                or (original is not None and (control['expectedRunVersion'] != original.task_run_ref.version
                    or control['expectedTaskVersion'] != original.task_ref.version
                    or original.task_run_ref.resource_id != task_run_id or original.task_ref.resource_id != compilation.task_id))):
            raise ValueError('snapshot successor original control versions differ')
        timeline = tasks.timeline(scope,task_run_id)
        if (timeline.run.id != task_run_id or timeline.run.task_id != compilation.task_id
                or timeline.run.version != control['expectedRunVersion']+1 or timeline.run.status.value != 'running'
                or timeline.task.id != compilation.task_id or timeline.task.version != control['expectedTaskVersion']+1
                or timeline.task.status.value != 'executing' or timeline.run.plan_revision_id != compilation.plan_ref.resource_id):
            raise ValueError('snapshot successor Task or TaskRun changed')
        state_prior = run.state.prior_ref
        if (state_prior is None or state_prior.resource_type != 'BusinessInvestigationRunStateRevision'
                or state_prior.resource_id != run.authority.run_id or state_prior.revision != run.state.version-1):
            raise ValueError('snapshot successor domain state predecessor differs')
        domain = runs.read_data_resume_receipt(scope,run.authority.run_id,parsed['requirementRef'],
            expected_version=run.state.version-1,idempotency_key=self._session.control_key+':domain')
        if domain is None or domain != run.state:
            raise ValueError('snapshot successor domain Receipt differs')
        runtime = self._runtime_binding_for_task_run(scope,compilation,run,tasks,task_run_id)
        return prior,runtime

    def _verify_snapshot_commit(self, *, transaction, scope, command, receipt, committed=False):
        from aos_api.ecommerce_growth_runtime_adapters import _analysis_json_equal
        prior,runtime = self._read_successor(transaction,scope,command,committed=committed)
        expected = self._running_receipt(command,prior,runtime,scope,command['idempotencyKey'])
        if not _analysis_json_equal(receipt,expected):
            raise ValueError('snapshot unified Receipt differs from original successor states')
        return expected

    def execute(self, *, transaction, scope, dispatch_ref, command, checked_at, occurred_at):
        from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore
        self._matches(transaction,scope,command)
        receipts = _HostAnalysisReceiptStore(transaction,scope)
        existing = receipts.read(command['idempotencyKey'])
        if existing is not None:
            return self._verify_snapshot_commit(transaction=transaction,scope=scope,command=command,receipt=existing)
        self._session._resume_states()
        prior,runtime = self._read_successor(transaction,scope,command)
        payload = self._running_receipt(command,prior,runtime,scope,command['idempotencyKey'])
        saved = receipts.put(command['idempotencyKey'],payload,dispatch_ref=dispatch_ref,checked_at=checked_at)
        return self._verify_snapshot_commit(transaction=transaction,scope=scope,command=command,receipt=saved)

    def verify_receipt(self, *, transaction, scope, dispatch, command, receipt):
        from aos_api.ecommerce_growth_runtime_adapters import _HostAnalysisReceiptStore,_analysis_json_equal
        self._matches(transaction,scope,command)
        saved = _HostAnalysisReceiptStore(transaction,scope).read(command['idempotencyKey'])
        if saved is None or not _analysis_json_equal(saved,receipt):
            return {}
        return self._verify_snapshot_commit(transaction=transaction,scope=scope,command=command,receipt=saved)


class _SnapshotAnalysisAdapter(AnalysisAdvanceAdapter):
    def __init__(self, service):
        if type(service) is not _CurrentSnapshotAnalysisHost:
            raise TypeError('exact current snapshot analysis Host required')
        super().__init__(service)

    def _analysis_protocol_command(self, command):
        return strict_snapshot_resume_command(command)
