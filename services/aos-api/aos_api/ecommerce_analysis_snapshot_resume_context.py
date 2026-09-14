"""Same-transaction snapshot checks without reentering the old paused state."""
from copy import deepcopy

from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateBriefRequest
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_fulfillment_store import DataFulfillmentStore
from aos_api.data_requirement_store import DataRequirementStore
from aos_api.data_requirement_quality_evidence import QualityEvidenceStore
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_analysis_snapshot_brief import AnalysisSnapshotBriefSpec, _schema
from aos_api.ecommerce_analysis_snapshot_fulfillment import AnalysisSnapshotFulfillment
from aos_api.ecommerce_analysis_snapshot_quality_evidence import CurrentSnapshotQuality
from aos_api.ecommerce_analysis_snapshot_readiness import _with_requirement, _match_current
from aos_api.ecommerce_analysis_snapshot_readiness_context import _assemble
from aos_api.ecommerce_analysis_snapshot_resume_contracts import strict_snapshot_resume_command
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, _analysis_command_hash
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.pipeline_snapshot_business_facts import compile_business_fact_policy
from aos_api.pipeline_snapshot_readiness_policy import compile_snapshot_readiness_policy
from aos_api.source_readiness_contracts import ExactResourceRef
from aos_api.source_readiness_receipt_store import SourceReadinessReceiptStore


def _json(value):
    return value.model_dump(mode='json', by_alias=True, exclude_none=True)


def _identity(conn):
    return dict(conn.execute('SELECT pg_backend_pid() AS pid,txid_current() AS xid').fetchone())


class _CurrentSnapshotResumeStage:
    """Internal frame only. No TaskStore or runtime port accepts this as a grant."""
    def __init__(self, conn, scope, command, *, requirement, runtime, fulfillment, bundle, readiness, deadline):
        self._scope, self._identity = scope, _identity(conn)
        self._command = deepcopy(command)
        self._command_hash = _analysis_command_hash(self._command)
        self._values = {name:value.model_copy(deep=True) for name,value in dict(requirement=requirement,
            runtime=runtime,fulfillment=fulfillment,bundle=bundle,readiness=readiness).items()}
        self._deadline = deadline
        self._values_hash = self._digest()
        self._active = False

    def _digest(self):
        return _analysis_command_hash(dict(values={k:_json(v) for k,v in self._values.items()},
            deadline=self._deadline.isoformat(),tenant=self._scope.key))

    @property
    def command(self): return deepcopy(self._command)

    @property
    def runtime(self): return self._values['runtime'].model_copy(deep=True)

    @property
    def requirement(self): return self._values['requirement'].model_copy(deep=True)

    @property
    def fulfillment(self): return self._values['fulfillment'].model_copy(deep=True)

    @property
    def readiness(self): return self._values['readiness'].model_copy(deep=True)

    @property
    def bundle(self): return self._values['bundle'].model_copy(deep=True)

    def assert_current(self, conn, scope):
        if not self._active or scope != self._scope or _identity(conn) != self._identity:
            raise PermissionError('snapshot resume stage requires its active original transaction')
        row = conn.execute("SELECT current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id,clock_timestamp() AS now").fetchone()
        if (row['org_id'], row['project_id']) != scope.key:
            raise PermissionError('snapshot resume stage tenant differs')
        if row['now'] >= self._deadline:
            raise ValueError('snapshot resume stage expired')
        if _analysis_command_hash(self._command) != self._command_hash or self._digest() != self._values_hash:
            raise ValueError('snapshot resume stage inputs changed')
        strict_snapshot_resume_command(self._command)


class AnalysisSnapshotResumeContext:
    def __init__(self, fulfillment, origin):
        if type(fulfillment) is not AnalysisSnapshotFulfillment or type(origin) is not AnalysisContinuationOrigin:
            raise TypeError('original snapshot fulfillment and initialization owners required')
        if origin.context.analysis is not fulfillment.source.analysis:
            raise ValueError('snapshot resume owners must share the original analysis')
        self.fulfillment, self.origin = fulfillment, origin
        self.business, self.source, self.scope = fulfillment.business, fulfillment.source, fulfillment.scope

    def _policies(self, conn, snapshot, business, source, policy_ref):
        fields_owner = self.source._fields
        relation, quality, cohort, fields = fields_owner._load_policies(conn, snapshot,
            cohort_ref=source['selection']['cohortPolicyRef'],field_ref=source['selection']['fieldPolicyRef'])
        loader = fields_owner._business._snapshot._quality._assessments._policies
        group = snapshot.quality.assessment.input.group
        business_policy = compile_business_fact_policy(loader._load_exported_document(conn,self.scope,group,
            PipelineExactRef.model_validate(business['selection']['policyRef']),resource_type='SnapshotBusinessFactPolicy'),
            field_policy=fields)
        readiness = compile_snapshot_readiness_policy(loader._load_exported_document(conn,self.scope,group,
            policy_ref,resource_type='SnapshotReadinessPolicy'),field_policy=fields,quality_policy=quality)
        return relation, quality, cohort, fields, business_policy, readiness

    def run_current(self, conn, *, command, execute):
        if not callable(execute): raise TypeError('synchronous internal resume consumer required')
        command = deepcopy(command)
        parsed = strict_snapshot_resume_command(command)
        command_hash = _analysis_command_hash(command)
        stages = []
        with conn.transaction():
            transaction = _identity(conn)
            tx = HostTransaction(conn)
            factory = TransactionBoundConnectFactory(tx,self.scope)
            requirements = DataRequirementStore(factory)
            productions = AipProductionContractStore(factory)
            fulfillments = DataFulfillmentStore(factory)
            receipts = SourceReadinessReceiptStore(tx,self.scope)
            quality_store = QualityEvidenceStore(tx,self.scope)
            ready_ref = parsed['sourceReadinessRef']
            ready_ref = ExactResourceRef(resource_type=ready_ref.resource_type,resource_id=ready_ref.resource_id,
                revision=str(ready_ref.revision),content_hash=ready_ref.content_hash[7:],authority='postgres:source_readiness_receipt')
            business_ref, bundle_ref = parsed['businessEvidenceRef'], parsed['evidenceRefs'][0]

            def current_origin(origin):
                root = origin['analysisReceipt']
                for command_key, root_key in (('occurrenceRef','occurrenceRef'),('caseRef','caseRef'),
                        ('profileRef','profileRef'),('priorPlanRef','planRef')):
                    if _json(parsed[command_key]) != root[root_key]:
                        raise ValueError('snapshot resume command differs from original initialization')
                # Phase A: all old Pending/paused guards finish before Phase B.
                saved = self.fulfillment.read_current(conn, reference=parsed['fulfillmentRef'],
                    business_ref=business_ref,bundle_ref=bundle_ref,readiness_ref=ready_ref,
                    policy_ref=parsed['readinessPolicyRef'])
                if saved.requirement_ref != parsed['requirementRef'] or saved.cutoff_at != parsed['cutoff']:
                    raise ValueError('snapshot fulfillment belongs to another requirement or cutoff')
                req = requirements.lock_current(self.scope,parsed['requirementRef'])
                business, source, snapshot, quality = self.business._run_current_context(conn,
                    reference=business_ref,execute=lambda b,s,snapshot,q:(deepcopy(b),deepcopy(s),snapshot,q))
                if source['selection']['receiptRef'] != _json(parsed['priorReceiptRef']):
                    raise ValueError('snapshot source differs from the original analysis receipt')
                bundle = productions.get_evidence_bundle(self.scope,bundle_ref.resource_id,bundle_ref.revision)
                brief = productions.get_brief(self.scope,bundle.brief_ref.resource_id,bundle.brief_ref.revision)
                spec = AnalysisSnapshotBriefSpec.model_validate(brief.spec)
                ready = receipts.read_exact(ready_ref)
                if (ready is None or spec.requirement_ref != parsed['requirementRef']
                        or spec.business_evidence_ref != business_ref or req.checkpoint_ref != parsed['checkpointRef']
                        or _json(req.run_ref) != root['runRef']
                        or spec.runtime.task_run_ref.resource_id != root['taskRunRef']['resourceId']
                        or spec.runtime.task_run_ref.version != root['taskRunRef']['revision']
                        or 'sha256:'+spec.runtime.binding_hash != root['taskRunRef']['contentHash']):
                    raise ValueError('snapshot resume runtime or requirement lineage differs')
                now = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                if not saved.fulfilled_at <= parsed['observedAt'] <= now:
                    raise ValueError('snapshot resume observation must follow actual fulfillment')
                brief_ref = InvestigationExactRef(resource_type='TaskBriefRevision',resource_id=brief.brief_id,
                    revision=brief.revision,content_hash='sha256:'+brief.content_hash)
                request = CreateBriefRequest(task_id=spec.runtime.task_ref.resource_id,brief_type='analysis_snapshot',
                    schema_ref=_schema(),spec=spec.model_dump(mode='json',by_alias=True))

                def current_counts(counts):
                    original = counts.projection.input
                    if original != snapshot.quality.assessment.input or counts.projection.payload != source['projection']:
                        raise ValueError('snapshot resume current group differs from Phase A')
                    policies = self._policies(conn,snapshot,business,source,parsed['readinessPolicyRef'])
                    compiled = policies[-1]

                    def current_binding(binding):
                        deadline = min(req.expires_at,binding.expires_at,original.group.expires_at,
                            *(s.freshness_expires_at for s in ready.sources))
                        stage = _CurrentSnapshotResumeStage(conn,self.scope,command,requirement=req,
                            runtime=spec.runtime,fulfillment=saved,bundle=bundle,readiness=ready,deadline=deadline)
                        stages.append(stage)
                        stage._active = True

                        def revalidate():
                            stage.assert_current(conn,self.scope)
                            if (_identity(conn) != transaction or _analysis_command_hash(command) != command_hash
                                    or self.business._record(conn,business_ref) != business
                                    or self.source._record(conn,business['selection']['evidenceRef']) != source
                                    or self._policies(conn,snapshot,business,source,parsed['readinessPolicyRef']) != policies
                                    or requirements.get_current(self.scope,req.requirement_id) != req
                                    or fulfillments.read_exact(self.scope,parsed['fulfillmentRef']) != saved
                                    or receipts.read_exact(ready_ref) != ready
                                    or productions.get_evidence_bundle(self.scope,bundle_ref.resource_id,bundle_ref.revision) != bundle):
                                raise ValueError('snapshot resume immutable authority changed')
                            self.fulfillment.bundle.brief._read(tx,productions,request,business['actor'],brief_ref)
                            value = self.business.quality._value(tx,source,snapshot,
                                InvestigationExactRef.model_validate(business['selection']['evidenceRef']),
                                InvestigationExactRef.model_validate(business['selection']['queryRef']))
                            if value != quality.value or quality_store.read_exact(
                                    InvestigationExactRef.model_validate(business['selection']['qualityRef'])) != value:
                                raise ValueError('snapshot resume original quality changed')
                            current_quality = CurrentSnapshotQuality(value,self.business.quality._assess_current(tx,value))
                            checked = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                            inputs = _assemble(scope=self.scope,original=original,counts=counts.payload,
                                runs=self.fulfillment.readiness.context._runs(conn,original),quality=current_quality,
                                business=business,field_ref=source['selection']['fieldPolicyRef'],
                                policy_ref=parsed['readinessPolicyRef'],binding=binding,checked_at=checked)
                            _match_current(ready,_with_requirement(inputs,source['fieldContext']['requirement'],business))

                        revalidate()
                        result = execute(stage)
                        _reject_deferred(result)
                        revalidate()
                        return result
                    return self.fulfillment.readiness.context.binding.run_current(conn,
                        binding_id=compiled.query_binding_id,execute=current_binding)

                return self.source._projections.run_current_base_counts(conn,scope=self.scope,
                    group_id=source['projection']['groupId'],actor=self.source.analysis.source.actor,
                    bindings=tuple((PipelineExactRef.model_validate(m['controlRef']),m['runId'])
                        for m in source['projection']['members']),execute=current_counts)
            try:
                result = self.origin.run_current(conn,receipt_ref=_json(parsed['priorReceiptRef']),execute=current_origin)
                if len(stages) != 1: raise ValueError('snapshot resume requires exactly one current stage')
                stages[0].assert_current(conn,self.scope)
                return result
            finally:
                for stage in stages: stage._active = False
