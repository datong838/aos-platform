"""Use existing ingress/recovery records under a fixed current control binding."""
from aos_api.ec_ingress_journal import IngressJournal, IngressJournalConflict
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_runtime_control_owner import _ref_identity
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner, _text
from aos_api.tenant_scope import TenantScope


class ControlledIngressJournal(IngressJournal):
    def __init__(self, *, claims, scope, run_id, control_ref, actor, saved_recovery=False, completed_read=False):
        if type(claims) is not PipelineSourceClaimOwner or type(scope) is not TenantScope:
            raise TypeError('exact claim Owner and tenant required')
        if type(saved_recovery) is not bool:
            raise TypeError('explicit saved recovery mode required')
        if type(completed_read) is not bool or (saved_recovery and completed_read):
            raise ValueError('distinct completed read mode required')
        self._completed_read = completed_read
        self._saved_recovery = saved_recovery
        self._scope = scope
        self._run_id = _text(run_id,200)
        self._actor = _text(actor,240)
        self._ref = PipelineExactRef.model_validate(control_ref)
        _ref_identity(self._ref,'PipelineRuntimeControlRevision','pipeline-control-')
        self._claims = claims
        super().__init__(storage_schema=claims._journal.schema)

    def _fixed(self, scope, run_id):
        if type(scope) is not TenantScope or scope != self._scope or run_id != self._run_id:
            raise PermissionError('controlled ingress target differs')

    def lock_run(self, conn, scope, run_id):
        self._fixed(scope,run_id)
        # Current installation/configuration locks precede the run lock. The
        # run may still be stopped/failed during the existing recovery claim.
        return self._claims._controls.run_current(conn,scope=scope,ref=self._ref,actor=self._actor,
            execute=lambda draft,spec:IngressJournal.lock_run(self,conn,scope,run_id))

    def verify_running_schedule(self, conn, scope, **args):
        self._fixed(scope,args['run_id'])
        read = self._claims.read_completed_current if self._completed_read else (
            self._claims.read_saved_current if self._saved_recovery else self._claims.read_current)
        read(conn,scope=scope,run_id=self._run_id,control_ref=self._ref,actor=self._actor)
        # Also bind the supplied original batch, not only the current draft.
        verify=super().verify_completed_schedule_binding if self._completed_read else super().verify_schedule_binding
        verify(conn,scope,**args)

    def read(self, conn, scope, run_id):
        self._fixed(scope,run_id)
        return super().read(conn,scope,run_id)

    def read_derived(self, conn, scope, run_id):
        self._fixed(scope,run_id)
        return super().read_derived(conn,scope,run_id)

    def _verify_parent(self, conn, scope, envelope):
        self.verify_running_schedule(conn,scope,run_id=envelope['runId'],pipeline_id=envelope['pipelineId'],
            source_id=envelope['sourceId'],source_revision=envelope['sourceRevision'],pipeline_hash=envelope['pipelineHash'])

    def _save_envelope(self, conn, scope, envelope):
        if self._completed_read:raise PermissionError('completed input is read only')
        self._verify_parent(conn,scope,envelope)
        return super()._save_envelope(conn,scope,envelope)

    def save_derived(self, conn, scope, run_id, commands):
        if self._completed_read:raise PermissionError('completed input is read only')
        parent = self.read(conn,scope,run_id)
        if parent is None:
            raise IngressJournalConflict('INGRESS_PARENT_REQUIRED')
        self._verify_parent(conn,scope,parent)
        return super().save_derived(conn,scope,run_id,commands)
