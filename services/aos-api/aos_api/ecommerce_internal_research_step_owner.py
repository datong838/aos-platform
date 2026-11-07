"""Accept an already delivered research memo into original TAOR checkpoints."""
from aos_api.db import connect_serializable
from aos_api.tenant_scope import TenantScope
from aos_api.aip_task_store import AipTaskStore
from aos_api.aip_research_job_store import AipResearchJobStore
from aos_api.aip_research_job import ResearchJobStatus
from aos_api.aip_handoff_service import AipHandoffService
from aos_api.aip_handoff_reference_authority import AipHandoffReferenceAuthority
from aos_api.aip_agent_registry_store import AipAgentRegistryStore
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, TaskGraphRevision
from aos_api.ecommerce_analyst_canonical_tasks import task_creation_ref
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


class InternalResearchStepBlocked(ValueError):
    pass


def configured_content_hash_resolver():
    from aos_api.aip_research_artifact_storage import configured_artifact_hash_resolver

    return configured_artifact_hash_resolver()


def _require(condition, message):
    if not condition:
        raise InternalResearchStepBlocked(message)


def _identity(ref):
    return (ref['resourceType'], ref['resourceId'], str(ref['revision']), ref['contentHash'].removeprefix('sha256:'))


class InternalResearchStepOwner:
    actor = 'aos:internal-research-step-owner'

    def __init__(self, *, connect_factory=None, content_hash_resolver=None):
        self._connect = connect_factory or connect_serializable
        self._hash = content_hash_resolver

    def _proof(self, conn, scope, factory, job_id):
        research = AipResearchJobStore(factory)
        job = research._job(conn, scope, job_id)
        snap = research.get_job(scope, job_id)
        _require(snap.status is ResearchJobStatus.SUCCEEDED and not snap.has_gap, 'gap-free succeeded research job required')
        research._validate_current_binding(conn, scope, job)
        delivery = conn.execute('SELECT * FROM aip_research_delivery_receipt WHERE org_id=%s AND project_id=%s AND job_id=%s ORDER BY created_at DESC,receipt_id DESC LIMIT 1', (*scope.key, job_id)).fetchone()
        _require(delivery is not None and delivery['status'] == 'succeeded', 'latest succeeded research delivery required')
        _require(delivery['provider_execution_id'] == snap.provider_execution_id, 'delivery execution drifted')
        research._validate_artifacts(conn, scope, job, delivery['artifact_ids'])
        task = conn.execute('SELECT t.*,r.status AS run_status,r.plan_revision_id AS run_plan FROM aip_task t JOIN aip_task_run r USING(org_id,project_id,task_id) WHERE t.org_id=%s AND t.project_id=%s AND r.run_id=%s FOR SHARE OF t,r', (*scope.key, snap.run_id)).fetchone()
        _require(task is not None and task['task_type'] == 'analysis' and (task['status'],task['run_status']) in {('executing','running'),('completed','succeeded')}, 'current executing or completed research task required')
        _require(task['current_plan_revision_id'] == task['run_plan'] == snap.plan_revision_id and snap.step_key == 'research_memo', 'current research plan or step drifted')
        plan = conn.execute('SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s FOR SHARE', (*scope.key, snap.plan_revision_id)).fetchone()
        _require(plan['content_hash'] == canonical_hash(dict(steps=plan['steps'],dependencies=plan['dependencies'],risk=plan['risk'])), 'research plan content hash drifted')
        _require([s['stepKey'] for s in plan['steps']] == ['research_sources','research_memo','research_review'], 'original research steps required')
        dependencies = plan['dependencies']
        graph_refs = [d for d in dependencies if d.get('resourceType') == 'TaskGraphRevision']
        brief_refs = [d for d in dependencies if d.get('resourceType') == 'TaskBriefRevision']
        _require(len(graph_refs) == len(brief_refs) == 1, 'one exact graph and brief required')
        graph_ref, brief_ref = graph_refs[0], brief_refs[0]
        row = conn.execute('SELECT payload FROM ecommerce_analyst_task_graph_revision WHERE org_id=%s AND project_id=%s AND graph_id=%s AND revision=%s', (*scope.key, graph_ref['resourceId'],graph_ref['revision'])).fetchone()
        _require(row is not None, 'original task graph missing')
        graph = TaskGraphRevision.model_validate(row['payload'])
        _require(graph.content_hash == graph_ref['contentHash'], 'task graph hash drifted')
        creation = task_creation_ref(task)
        _require(sum(m.task_ref == creation for m in graph.mappings) == 1, 'original task graph creation mapping required')
        materialization = task['goal'].get('materialization')
        _require(isinstance(materialization, dict), 'original task source lineage missing')
        brief = conn.execute('SELECT b.*,h.current_revision FROM aip_task_brief_revision b JOIN aip_task_brief_head h USING(org_id,project_id,brief_id) WHERE b.org_id=%s AND b.project_id=%s AND b.brief_id=%s AND b.revision=%s', (*scope.key,brief_ref['resourceId'],brief_ref['revision'])).fetchone()
        _require(brief is not None and brief['task_id'] == task['task_id'] and brief['brief_type'] == 'internal_research' and brief['current_revision'] == brief_ref['revision'], 'current original research brief required')
        _require(brief['content_hash'] == brief_ref['contentHash'] == canonical_hash(dict(briefType=brief['brief_type'],schemaRef=brief['schema_ref'],spec=brief['spec'])), 'brief content hash drifted')
        expected_lineage = dict(taskRef=creation.model_dump(mode='json',by_alias=True),taskGraphRef=graph_ref,**materialization)
        _require(brief['spec'].get('sourceLineage') == expected_lineage, 'research brief source lineage drifted')
        source_plan = AnalystExactRef.model_validate(materialization['approvedPlanRef'])
        plans = EcommerceAnalystAuthorityStore(factory)
        approved = plans.get_plan_exact(scope, source_plan)
        _require(approved.lifecycle.value == 'approved' and plans.is_current_plan(scope, source_plan) and graph.plan_ref == source_plan, 'current approved source plan required')
        handoffs = AipHandoffService(factory)
        handoff = handoffs.get(scope, materialization['handoffId'])
        ref = materialization['acceptedDecisionRef']
        decision = handoffs.get_decision(scope, ref['resourceId'])
        head = conn.execute('SELECT current_revision,terminal_decision FROM aip_handoff_decision_head WHERE org_id=%s AND project_id=%s AND handoff_id=%s FOR SHARE', (*scope.key,handoff.handoff_id)).fetchone()
        _require(handoff.status == 'consumed' and decision.handoff_id == handoff.handoff_id and decision.decision.value == 'accepted' and decision.revision == ref['revision'] and decision.content_hash == ref['contentHash'] and head and head['current_revision'] == decision.revision and head['terminal_decision'] == 'accepted', 'current accepted handoff decision required')
        body = handoff.envelope
        receiver = AipAgentRegistryStore(factory).get_instance(scope,body.receiver_instance.asset_id)
        _require(receiver.status.value == 'active' and receiver.instance_ref == body.receiver_instance == decision.receiver_instance, 'current accepted receiver required')
        _require(body.context.get('targetModuleId') == 'ecommerce.content-campaign' and len(body.object_refs) == 1 and _identity(body.object_refs[0].model_dump(mode='json',by_alias=True)) == _identity(materialization['approvedPlanRef']), 'handoff target or plan drifted')
        _require(len(body.artifact_refs) == len(materialization['artifactRefs']) == 4 and {_identity(r.model_dump(mode='json',by_alias=True)) for r in body.artifact_refs} == {_identity(r) for r in materialization['artifactRefs']}, 'four original artifact sources required')
        authority = AipHandoffReferenceAuthority(factory)
        _require(all(authority(scope,r,body.receiver_instance) for r in [*body.object_refs,*body.artifact_refs]), 'source exact references no longer resolve')
        artifacts = conn.execute('SELECT a.artifact_id,a.run_id,a.content_ref,a.content_hash,r.content_hash AS receipt_hash,r.artifact_receipt_id FROM aip_artifact a JOIN aip_research_artifact_receipt r USING(org_id,project_id,artifact_id) WHERE a.org_id=%s AND a.project_id=%s AND r.job_id=%s AND a.artifact_id=ANY(%s) ORDER BY a.artifact_id', (*scope.key,job_id,delivery['artifact_ids'])).fetchall()
        _require(artifacts and len(artifacts) == len(delivery['artifact_ids']), 'complete delivered artifact set required')
        for a in artifacts:
            _require(a['run_id'] == snap.run_id and a['content_hash'] == a['receipt_hash'] == self._hash(scope,a['content_ref']), 'delivered content hash drifted')
        return dict(jobId=job_id,runId=snap.run_id,planId=snap.plan_revision_id,planHash=plan['content_hash'],manifestHash=snap.manifest_hash,
                    taskRef=creation.model_dump(mode='json',by_alias=True),briefRef=brief_ref,taskGraphRef=graph_ref,
                    deliveryRef=dict(resourceType='ResearchDeliveryReceipt',resourceId=delivery['receipt_id'],contentHash=delivery['source_hash']),
                    artifactRefs=[dict(resourceType='aip.artifact',resourceId=a['artifact_id'],revision=a['content_hash'],authority='aos.artifact') for a in artifacts])

    def _complete(self, conn, scope, factory, proof, step_key, *, queued_step_id=None):
        proof_hash = canonical_hash(proof)
        outputs = proof['artifactRefs'] if step_key in {'research_memo','research_review'} else []
        prior = conn.execute('SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key=%s ORDER BY attempt DESC LIMIT 1 FOR UPDATE', (*scope.key,proof['runId'],step_key)).fetchone()
        if prior is not None and prior['status'] == 'succeeded':
            observe = conn.execute('SELECT payload,content_hash FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s', (*scope.key,prior['observe_ref']['evidenceId'])).fetchone()
            checkpoint = conn.execute("SELECT checkpoint_id,state_hash,state_snapshot_ref,artifact_refs FROM aip_checkpoint WHERE org_id=%s AND project_id=%s AND run_id=%s AND state_snapshot_ref->>'stepRunId'=%s ORDER BY sequence DESC LIMIT 1", (*scope.key,proof['runId'],prior['step_run_id'])).fetchone()
            _require(observe and observe['content_hash'] == canonical_hash(observe['payload']) and observe['payload']['payload'].get('proofHash') == proof_hash, 'completed research step proof drifted')
            _require(checkpoint and checkpoint['state_hash'] == canonical_hash(checkpoint['state_snapshot_ref']) and checkpoint['artifact_refs'] == outputs and checkpoint['state_snapshot_ref']['inputHash'] == prior['input_hash'], 'research checkpoint drifted')
            return checkpoint['checkpoint_id'],True
        # An existing running/unknown attempt is not permission to claim again.
        _require(prior is None if queued_step_id is None else prior is not None and prior['step_run_id'] == queued_step_id and prior['status'] == 'queued', 'existing research attempt requires read-only reconciliation')
        store = AipTaskStore(factory)
        lease = store.claim_step(scope,proof['runId'],step_key,self.actor,lease_seconds=60)
        _require(queued_step_id is None or lease.step_run_id == queued_step_id, 'repair claim identity drifted')
        updated = conn.execute("UPDATE aip_step_run SET output_refs=%s::jsonb WHERE org_id=%s AND project_id=%s AND step_run_id=%s AND status='running' AND lease_owner=%s AND fence=%s RETURNING step_run_id", (store._json(outputs),*scope.key,lease.step_run_id,self.actor,lease.fence)).fetchone()
        _require(updated is not None, 'research artifact binding lost owned step')
        for phase in ('think','act','verify','observe'):
            payload=dict(kind='reconcile_existing_research_review' if step_key=='research_review' else 'reconcile_existing_research_delivery',proofHash=proof_hash,jobId=proof['jobId'],deliveryRef=proof['deliveryRef'],artifactRefs=outputs)
            for key in ('reviewIssueRef','reviewReceiptRef','effectReviewRef','memoryCandidate'):
                if key in proof:payload[key]=proof[key]
            store.record_step_phase(scope,lease.step_run_id,self.actor,lease.fence,self.actor,phase,payload)
        return store.complete_step(scope,lease.step_run_id,self.actor,lease.fence,self.actor),False

    def accept(self, scope, job_id):
        if type(scope) is not TenantScope or not isinstance(job_id,str) or not job_id.strip():
            raise ValueError('exact tenant and research job identity required')
        if self._hash is None:
            raise InternalResearchStepBlocked('trusted content hash resolver is required')
        with self._connect(scope) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (':'.join((*scope.key,job_id,'research-step-accept')),))
            factory = TransactionBoundConnectFactory(HostTransaction(conn),scope)
            proof = self._proof(conn,scope,factory,job_id)
            sources,source_replay = self._complete(conn,scope,factory,proof,'research_sources')
            memo,memo_replay = self._complete(conn,scope,factory,proof,'research_memo')
            conn.commit()
            return dict(jobId=job_id,runId=proof['runId'],sourceCheckpointId=sources,memoCheckpointId=memo,
                        artifactRefs=proof['artifactRefs'],replayed=source_replay and memo_replay,reviewCompleted=False,providerInvocationCount=0)

    def accept_repair(self, scope, job_id, decision_id):
        """Consume a regenerated delivery for one original queued RETURN attempt."""
        if type(scope) is not TenantScope or not all(isinstance(v,str) and v.strip() for v in (job_id,decision_id)):
            raise ValueError('exact tenant, job and repair identity required')
        if self._hash is None:
            raise InternalResearchStepBlocked('trusted content hash resolver is required')
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_research_job import ResearchJobManifest, canonical_research_manifest_hash
        with self._connect(scope) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (':'.join((*scope.key,job_id,'research-step-accept')),))
            factory=TransactionBoundConnectFactory(HostTransaction(conn),scope)
            proof=self._proof(conn,scope,factory,job_id)
            contracts=AipProductionContractStore(factory)
            decision=contracts.get_return_decision(scope,decision_id)
            issue=contracts.get_review_issue(scope,decision.issue_id,conn=conn,for_update=True)
            expected_hash=canonical_hash(dict(issueId=decision.issue_id,issueVersion=decision.issue_version,runId=decision.run_id,stepKey=decision.step_key,stepRunId=decision.step_run_id,attempt=decision.attempt,attemptIdempotencyKey=decision.attempt_idempotency_key,reason=decision.reason,actor=decision.actor))
            _require(decision.run_id==proof['runId'] and decision.step_key=='research_memo' and decision.attempt>1 and decision.decision_hash==expected_hash, 'exact research return decision required')
            _require(issue.status.value=='returned' and issue.version==decision.issue_version+1 and issue.return_stage=='research_memo' and issue.updated_by==decision.actor, 'current returned research issue required')
            _require(decision.impact_readiness=='exact' and {i.step_key:i.action.value for i in decision.impact_decisions}==dict(research_sources='reuse',research_memo='invalidate',research_review='invalidate'), 'research return impact drifted')
            event=conn.execute("SELECT * FROM aip_review_issue_event WHERE org_id=%s AND project_id=%s AND issue_id=%s AND event_type='returned' AND issue_version=%s",(*scope.key,issue.issue_id,issue.version)).fetchone()
            receipts=conn.execute("SELECT * FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='review_issue.return' AND result_ref->>'resourceId'=%s",(*scope.key,decision_id)).fetchall()
            _require(event and len(receipts)==1 and event['actor']==receipts[0]['created_by']==decision.actor and event['payload_hash']==canonical_hash(event['payload']), 'original research return receipt required')
            payload=event['payload'];request={k:v for k,v in payload.items() if k not in {'decisionHash','stepRunId'}}
            _require(payload.get('decisionHash')==decision.decision_hash and payload.get('stepRunId')==decision.step_run_id and receipts[0]['request_hash']==canonical_hash(dict(issueId=issue.issue_id,**request)) and receipts[0]['result_ref'].get('contentHash')==decision.decision_hash, 'research return event or receipt drifted')
            _require(conn.execute('SELECT 1 FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*scope.key,decision.actor)).fetchone() is not None, 'research return reviewer membership required')
            latest=conn.execute("SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='research_memo' ORDER BY attempt DESC LIMIT 1 FOR UPDATE",(*scope.key,proof['runId'])).fetchone()
            _require(latest and latest['step_run_id']==decision.step_run_id and latest['attempt']==decision.attempt and latest['status'] in {'queued','succeeded'}, 'current queued or reconciled repair attempt required')
            _require(any(r.get('resourceType')=='ReturnDecision' and r.get('resourceId')==decision_id and r.get('contentHash')==decision.decision_hash for r in latest['input_refs']), 'repair attempt decision input drifted')
            previous=conn.execute("SELECT output_refs FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='research_memo' AND attempt=%s AND status='succeeded'",(*scope.key,proof['runId'],decision.attempt-1)).fetchone()
            _require(previous and any(r.get('resourceId')==issue.artifact_ref.artifact_id and r.get('revision')==issue.artifact_ref.content_hash for r in previous['output_refs']), 'returned artifact must belong to the prior research attempt')
            job=AipResearchJobStore(factory)._job(conn,scope,job_id)
            _require(canonical_research_manifest_hash(ResearchJobManifest.model_validate(job['manifest']))==proof['manifestHash'], 'repair manifest content hash drifted')
            required=[dict(resourceType='ReturnDecision',resourceId=decision_id,revision=decision.decision_hash,authority='aos.production'),dict(resourceType='StepRun',resourceId=decision.step_run_id,revision=str(decision.attempt),authority='aos.task'),dict(resourceType='Artifact',resourceId=issue.artifact_ref.artifact_id,revision=issue.artifact_ref.content_hash,authority='aos.artifact')]
            _require(all(r in job['manifest']['scopedRefs'] for r in required), 'repair manifest exact decision, attempt and source artifact required')
            _require(all(r['resourceId']!=issue.artifact_ref.artifact_id for r in proof['artifactRefs']), 'returned artifact cannot be accepted as regenerated output')
            source=conn.execute("SELECT e.payload FROM aip_step_run s JOIN aip_evidence e ON e.org_id=s.org_id AND e.project_id=s.project_id AND e.evidence_id=s.observe_ref->>'evidenceId' WHERE s.org_id=%s AND s.project_id=%s AND s.run_id=%s AND s.step_key='research_sources' AND s.status='succeeded' ORDER BY s.attempt DESC LIMIT 1",(*scope.key,proof['runId'])).fetchone()
            _require(source is not None, 'original succeeded research source proof required')
            old_job=source['payload']['payload']['jobId']
            _require(old_job!=job_id, 'new repair research job required')
            original=self._proof(conn,scope,factory,old_job)
            _require(all(original[k]==proof[k] for k in ('runId','planId','planHash','taskRef','briefRef','taskGraphRef')), 'repair research source lineage drifted')
            sources,source_replayed=self._complete(conn,scope,factory,original,'research_sources')
            _require(source_replayed, 'repair must reuse the original source checkpoint')
            memo,replayed=self._complete(conn,scope,factory,proof,'research_memo',queued_step_id=decision.step_run_id)
            conn.commit()
            return dict(jobId=job_id,runId=proof['runId'],returnDecisionId=decision_id,attempt=decision.attempt,sourceCheckpointId=sources,memoCheckpointId=memo,artifactRefs=proof['artifactRefs'],replayed=replayed,reviewCompleted=False,providerInvocationCount=0)

    def _review_proof(self, conn, scope, factory, proof, issue_id):
        from aos_api.aip_production_contract_store import AipProductionContractStore
        contracts=AipProductionContractStore(factory)
        issue=contracts.get_review_issue(scope,issue_id,conn=conn,for_update=True)
        _require(len(proof['artifactRefs'])==1, 'single research memo review required')
        _require(issue.status.value=='resolved', 'resolved research review required')
        _require(issue.return_stage=='research_memo' and any(r['resourceId']==issue.artifact_ref.artifact_id and r['revision']==issue.artifact_ref.content_hash for r in proof['artifactRefs']), 'research review artifact drifted')
        contracts._require_eval_report(conn,scope,issue.eval_report_ref)
        contracts._require_content_eval_subject(conn,scope,issue.artifact_ref,issue.eval_report_ref)
        event=conn.execute("SELECT * FROM aip_review_issue_event WHERE org_id=%s AND project_id=%s AND issue_id=%s AND event_type='resolved' AND issue_version=%s",(*scope.key,issue_id,issue.version)).fetchone()
        receipts=conn.execute("SELECT * FROM aip_production_contract_receipt WHERE org_id=%s AND project_id=%s AND operation='review_issue.resolve' AND result_ref->>'resourceId'=%s AND (result_ref->>'version')::bigint=%s",(*scope.key,issue_id,issue.version)).fetchall()
        _require(event and len(receipts)==1, 'unique original research resolution receipt required')
        receipt=receipts[0]
        _require(event['actor']==receipt['created_by']==issue.updated_by and event['payload_hash']==canonical_hash(event['payload']) and receipt['request_hash']==canonical_hash(dict(issueId=issue_id,**event['payload'])), 'research resolution event or actor drifted')
        expected=dict(resourceType='Artifact',resourceId=issue.artifact_ref.artifact_id,revision=1,contentHash=issue.artifact_ref.content_hash)
        _require(expected in event['payload'].get('resolutionRefs',[]), 'exact memo resolution evidence required')
        member=conn.execute('SELECT 1 FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*scope.key,issue.updated_by)).fetchone()
        _require(member is not None, 'current tenant reviewer membership required')
        blocking=conn.execute("SELECT 1 FROM aip_review_issue WHERE org_id=%s AND project_id=%s AND artifact_id=%s AND issue_id<>%s AND (status='returned' OR (status='open' AND severity IN ('error','critical'))) LIMIT 1",(*scope.key,issue.artifact_ref.artifact_id,issue_id)).fetchone()
        _require(blocking is None, 'another blocking research review exists')
        return dict(proof,reviewIssueRef=dict(resourceType='ReviewIssue',resourceId=issue_id,version=issue.version),reviewReceiptRef=dict(resourceType='ProductionContractReceipt',resourceId=receipt['receipt_id'],contentHash=receipt['request_hash']),reviewer=issue.updated_by,reviewObservedAt=issue.updated_at.isoformat())

    def _feedback(self, conn, scope, factory, proof):
        from datetime import datetime,timedelta
        from aos_api.aip_contracts import ResourceRef,ArtifactRef
        from aos_api.aip_effect_review import CreateEffectReviewRequest
        from aos_api.aip_effect_review_store import AipEffectReviewStore
        from aos_api.aip_memory_store import AipMemoryStore
        from aos_api.aip_memory_contracts import KnowledgeSourceRef,SubmitMemoryCandidateRequest,KnowledgeScope
        identity=canonical_hash(dict(jobId=proof['jobId'],reviewIssueRef=proof['reviewIssueRef'],reviewReceiptRef=proof['reviewReceiptRef']))[:32]
        subject_id='research-effect-'+identity
        effect_store=AipEffectReviewStore()
        row=conn.execute('SELECT * FROM aip_effect_review_revision WHERE org_id=%s AND project_id=%s AND subject_id=%s AND revision=1',(*scope.key,subject_id)).fetchone()
        issue=proof['reviewIssueRef']
        subject=ResourceRef(resourceType='ReviewIssue',resourceId=issue['resourceId'],revision=str(issue['version']),authority='aos.production-contracts')
        at=datetime.fromisoformat(proof['reviewObservedAt'])
        body=CreateEffectReviewRequest(subjectId=subject_id,subjectRef=subject,sampleCount=0,minSample=1,cutoffAt=at,eventTimeAt=at,accepted=False,reasonCode='research_accepted_effect_evidence_pending')
        if row is None:
            effect=effect_store.create_review_in_transaction(scope,body,self.actor,now=at,transaction=conn)
        else:
            effect=effect_store._review_row(scope,row)
        _require(effect.subject_ref==subject and effect.sample_count==0 and effect.accepted is False and effect.effect_completed is False and effect.maturity_status.value=='insufficient' and effect.reason_code==body.reason_code, 'research feedback effect axis drifted')
        source=KnowledgeSourceRef(sourceKind='effect_review',sourceRef=ResourceRef(resourceType='EffectReviewRevision',resourceId=effect.review_id,revision='1',authority='aip-effect-review'),observedAt=effect.created_at,freshnessExpiresAt=effect.created_at+timedelta(days=30),licenseId='aos-internal',usagePolicy='pending-governance-only',contentHash=effect.content_hash,provider='aos-research-feedback',providerVersion='1',applicability=['ecommerce-internal-research-method'])
        ref=proof['artifactRefs'][0]
        request=SubmitMemoryCandidateRequest(candidateLayer='episodic',taskId=proof['taskRef']['resourceId'],runId=proof['runId'],subject=subject,payload=ArtifactRef(artifactId=ref['resourceId'],artifactType='internal_research_memo',revision='1',contentHash=ref['revision']),source=source,confidence=0,marking=['internal','insufficient_evidence','pending_governance'])
        memory=AipMemoryStore(factory);source_id='research-source-'+identity;candidate_id='research-candidate-'+identity
        existing=conn.execute('SELECT 1 FROM aip_memory_candidate WHERE org_id=%s AND project_id=%s AND candidate_id=%s',(*scope.key,candidate_id)).fetchone()
        if existing:
            candidate=memory.get_candidate(scope,candidate_id)
            _require(candidate.request==request and candidate.scope is KnowledgeScope.WORKSPACE,'research memory candidate content drifted')
        else:
            memory.create_source_revision_in_transaction(scope,source_id,1,source,actor=self.actor,transaction=conn)
            candidate=memory.submit_candidate_in_transaction(scope,candidate_id,request,source_id=source_id,source_revision=1,knowledge_scope=KnowledgeScope.WORKSPACE,actor=self.actor,occurred_at=at,transaction=conn)
        _require(candidate.status.value=='pending', 'research candidate is not pending governance')
        return dict(effectReviewRef=dict(resourceType='EffectReviewRevision',resourceId=effect.review_id,revision=effect.revision,contentHash=effect.content_hash),memoryCandidate=dict(candidateId=candidate.candidate_id,version=candidate.version,status=candidate.status.value,requestHash=canonical_hash(candidate.request.model_dump(mode='json',by_alias=True))))

    def accept_review(self, scope, job_id, issue_id):
        if type(scope) is not TenantScope or not isinstance(job_id,str) or not job_id.strip() or not isinstance(issue_id,str) or not issue_id.strip():
            raise ValueError('exact tenant, job and review identity required')
        if self._hash is None:
            raise InternalResearchStepBlocked('trusted content hash resolver is required')
        with self._connect(scope) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(':'.join((*scope.key,job_id,'research-review-accept')),))
            factory=TransactionBoundConnectFactory(HostTransaction(conn),scope)
            proof=self._review_proof(conn,scope,factory,self._proof(conn,scope,factory,job_id),issue_id)
            # Complete-run also checks all latest attempts. Read the two prerequisites
            # explicitly before feedback or review writes, including repair queues.
            completed=conn.execute("SELECT DISTINCT ON(step_key) step_key,status FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key IN ('research_sources','research_memo') ORDER BY step_key,attempt DESC",(*scope.key,proof['runId'])).fetchall()
            _require({r['step_key']:r['status'] for r in completed}==dict(research_sources='succeeded',research_memo='succeeded'),'research prerequisite steps are not current successes')
            feedback=self._feedback(conn,scope,factory,proof)
            checkpoint,replayed=self._complete(conn,scope,factory,dict(proof,**feedback),'research_review')
            current=conn.execute('SELECT status FROM aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s',(*scope.key,proof['runId'])).fetchone()
            if current['status']=='running':AipTaskStore(factory).complete_run(scope,proof['runId'])
            else:_require(current['status']=='succeeded' and replayed,'research completion state drifted')
            conn.commit()
            return dict(jobId=job_id,runId=proof['runId'],reviewIssueRef=proof['reviewIssueRef'],reviewCheckpointId=checkpoint,**feedback,replayed=replayed,reviewCompleted=True,taskRunStatus='succeeded',providerInvocationCount=0)
