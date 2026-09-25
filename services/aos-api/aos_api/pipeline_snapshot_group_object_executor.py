"""Resume original object/projection/dataset stages, never collect source again."""
from contextlib import contextmanager
from aos_api.ec_ingress_journal import IngressJournalConflict
from aos_api.ec_ingress_recovery import _check_active,read_saved_projection_completion
from aos_api.pipeline_controlled_executor import ControlledSnapshotExecutor
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_group_relationship_journal import PipelineSnapshotGroupRelationshipJournal
from aos_api.extension_runtime.host_lease import OptInHostLease


class ControlledSnapshotGroupObjectExecutor:
    def __init__(self,*,claims,store,connect,eng,host_lease=None):
        if host_lease is not None and type(host_lease) is not OptInHostLease:
            raise TypeError('exact snapshot Object Host lease required')
        self._single=ControlledSnapshotExecutor(claims=claims,store=store,connect=connect,eng=eng)
        self._host_lease=host_lease
        self._claims,self._store=claims,store
        self._journal=PipelineSnapshotGroupRelationshipJournal(claims=claims)

    @contextmanager
    def _transaction(self,scope):
        with self._single._ingress._transaction(scope) as conn:
            if self._host_lease is not None:
                self._host_lease.fence_in_transaction(
                    conn,dict(org_id=scope.org_id,project_id=scope.project_id))
            yield conn

    def execute(self,*,scope,group_id,actor,bindings,policy_ref,deadline=None,cancel_event=None):
        """Independently recoverable members; final group reconciliation is mandatory.

        Do not retain group run locks while opening a member's independent
        metadata transaction. Each member retains the original current guards.
        This neither applies relationships nor completes schedule runs.
        """
        if type(bindings) is not tuple:raise ValueError('exact group run bindings required')
        bindings=tuple((PipelineExactRef.model_validate(ref),run) for ref,run in bindings)
        args=dict(scope=scope,group_id=group_id,actor=actor,bindings=bindings,policy_ref=policy_ref)
        active=dict(deadline=deadline,cancel_event=cancel_event)
        _check_active(**active)
        with self._transaction(scope) as conn:
            prepared=self._journal.prepare_or_materialize(conn,**args)
        if self._claims._recovery is not None and not hasattr(prepared,'assessment_hash'):
            assessed=self._journal._assessments.assess_materialized(prepared)
            _check_active(**active)
            with self._transaction(scope) as conn:
                prepared=self._journal.prepare_assessed_current(conn,assessed,**args)
        # The preparation transaction and connection both exited successfully.
        _check_active(**active)
        results=[]
        for ref,run in sorted(bindings,key=lambda pair:pair[0].resource_id):
            _check_active(**active)
            with self._transaction(scope) as conn:
                saved=self._journal.read_current(conn,**args)
                if saved.assessment_hash!=prepared.assessment_hash:raise IngressJournalConflict('GROUP_PREPARATION_CHANGED')
            result=self._single.resume_saved(scope=scope,run_id=run,control_ref=ref,actor=actor,**active)
            results.append(dict(run_id=run,dataset_ref=result['output_ref'],completion=result['completion'],
                rows_written=result['rows_written'],completed_replay=result['completed_replay']))
        _check_active(**active)
        with self._transaction(scope) as conn:
            def verify(current):
                saved=self._journal.read_current(conn,**args)
                if saved.assessment_hash!=prepared.assessment_hash or current.content_hash!=prepared.assessment_hash:
                    raise IngressJournalConflict('GROUP_PREPARATION_CHANGED')
                completions={}
                for (ref,_,_),parent in zip(current.input.group.members,current.input.parents):
                    _check_active(**active)
                    run=parent['runId']
                    journal=ControlledIngressJournal(claims=self._claims,scope=scope,run_id=run,control_ref=ref,actor=actor)
                    completion=read_saved_projection_completion(conn,scope,run,journal=journal,store=self._store)
                    if completion['pending']!=0:raise IngressJournalConflict('GROUP_OBJECT_PROJECTION_PENDING')
                    completions[run]=completion
                return completions
            completions=self._journal.run_current(conn,**args,execute=verify)
            _check_active(**active)
        for result in results:result['completion']=completions[result['run_id']]
        return dict(group_id=group_id,input_manifest_hash=prepared.payload['inputManifestHash'],
            assessment_hash=prepared.assessment_hash,members=results,relationships_applied=False)
