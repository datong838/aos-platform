"""Read historical initialization plus current identity; never authorize execution."""
from copy import deepcopy
from datetime import datetime

from aos_api.aip_production_contract_store import canonical_hash
from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_bootstrap_contract import AnalysisBootstrapIntent
from aos_api.ecommerce_analysis_bootstrap_authority import require_current_bootstrap_review_identity
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory,_analysis_plan_ref
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisContinuationOrigin:
    def __init__(self, context):
        if type(context) is not AnalysisContinuationContext:
            raise TypeError('exact current continuation context required')
        self.context=context

    def run_current(self, conn, *, receipt_ref, execute):
        if not callable(execute):raise TypeError('synchronous origin callback required')
        def current(context):
            before=self._read(conn,context)
            result=execute(deepcopy(before))
            _reject_deferred(result)
            if self._read(conn,context)!=before:raise ValueError('initialization origin changed during continuation')
            return result
        return self.context.run_current(conn,receipt_ref=receipt_ref,execute=current)

    def _read(self, conn, context):
        scope=self.context.analysis.scope
        actor=self.context.analysis.source.actor
        tx=HostTransaction(conn)
        root=context['analysisReceipt']
        decisions=conn.execute("""SELECT * FROM aip_production_start_decision WHERE org_id=%s AND project_id=%s
            AND task_run_ref->>'resourceId'=%s FOR SHARE""",(*scope.key,root['taskRunRef']['resourceId'])).fetchall()
        if len(decisions)!=1:raise ValueError('unique original start decision required')
        decision=decisions[0]
        proposal_ref=decision['action_proposal_ref']
        proposal=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,proposal_ref['proposalId'])).fetchone()
        if (decision['status']!='started' or decision['created_by']!=actor or decision['blockers']
                or proposal is None or proposal['action_type_id']!='ecommerce_analysis_bootstrap'
                or proposal['status'] not in {'drafted','approved'} or proposal['created_by']!=actor
                or proposal['version']!=proposal_ref['version'] or proposal['proposal_hash']!=proposal_ref['proposalHash']
                or proposal['task_id']!=decision['task_id'] or proposal['run_id'] is not None
                or (proposal['impact_preview_id'],proposal['impact_preview_revision'],proposal['impact_preview_hash']) !=
                   (decision['preview_ref']['resourceId'],decision['preview_ref']['revision'],decision['preview_ref']['contentHash'])
                or set(proposal['payload'])!={'bootstrapIntent'}):
            raise ValueError('original bootstrap proposal or decision drifted')
        intent=AnalysisBootstrapIntent.model_validate(proposal['payload']['bootstrapIntent']).checked()
        compilation=BusinessInvestigationCompilationReceiptStore(TransactionBoundConnectFactory(tx,scope)).get_for_run(
            scope,InvestigationExactRef.model_validate(root['runRef']))
        if (compilation!=intent.compilation_receipt or compilation.exact_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=root['compilationRef']
                or compilation.task_id!=decision['task_id'] or _analysis_plan_ref(compilation.plan_ref)!=root['planRef']
                or compilation.plan_ref.model_dump(mode='json',by_alias=True)!=decision['plan_ref']
                or intent.occurrence_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=root['occurrenceRef']
                or intent.source_control_receipt_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=context['source']['controlReceipt']['receiptRef']):
            raise ValueError('initialization compilation or source drifted')
        require_current_bootstrap_review_identity(transaction=tx,scope=scope,actor=actor,maker=proposal['created_by'],
                                                  action_snapshot=proposal['action_type_snapshot'],checker=False)
        draft=conn.execute('SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s ORDER BY proposal_version DESC LIMIT 1',
                           (*scope.key,proposal['proposal_id'])).fetchone()
        if (draft is None or canonical_hash(draft['snapshot'])!=proposal['proposal_hash']
                or draft['snapshot'].get('payload')!=proposal['payload']
                or draft['snapshot'].get('policy')!=proposal['policy_snapshot']
                or draft['snapshot'].get('actionBindingHash')!=proposal['action_binding_hash']):
            raise ValueError('initialization draft proof drifted')
        identity='evidence-initialization-authority-'+canonical_hash([*scope.key,intent.content_hash])
        evidence=conn.execute("""SELECT e.*,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
              AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s""",
            (*scope.key,identity)).fetchone()
        if evidence is None:raise ValueError('original initialization Evidence missing')
        payload=evidence['payload'];proof=payload.get('proof',{})
        if (evidence['revoked'] or evidence['run_id'] is not None or evidence['evidence_type']!='analysis-initialization-authority'
                or evidence['subject_ref']!=compilation.run_ref.model_dump(mode='json',by_alias=True)
                or evidence['source_ref']!=intent.content_hash or evidence['source_type']!=proof.get('kind')
                or evidence['created_by']!=actor or evidence['redaction']!={}
                or evidence['content_hash']!=canonical_hash(payload)
                or payload.get('schemaVersion')!='aos.ecommerce.initialization-authority/v1'
                or set(payload)!={'schemaVersion','proof','validatedAt'}
                or datetime.fromisoformat(payload['validatedAt'])!=evidence['observed_at']
                or evidence['observed_at']!=evidence['freshness_at'] or evidence['created_at']<evidence['observed_at']
                or evidence['observed_at']>conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                or proof.get('actor')!=actor or proof.get('intentHash')!=intent.content_hash
                or proof.get('proposalRef')!=proposal_ref or proof.get('previewRef')!=decision['preview_ref']):
            raise ValueError('original initialization Evidence drifted')
        if proof.get('kind')=='current-event-control-initialization':
            if (proof.get('sourceControlReceiptRef')!=intent.source_control_receipt_ref.model_dump(mode='json',by_alias=True)
                    or proof.get('occurrenceRef')!=intent.occurrence_ref.model_dump(mode='json',by_alias=True)
                    or proof.get('businessExecutionAuthorized') is not False or proof.get('externalEffectAuthorized') is not False):
                raise ValueError('original source initialization proof differs')
        elif proof.get('kind')=='current-independent-bootstrap-review':
            events=proof.get('approvalEvents')
            if type(events) is not list or not events:raise ValueError('original independent review missing')
            for event in events:
                row=conn.execute("SELECT actor_id,proposal_version,approval_policy_hash FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s AND proposal_id=%s AND decision='approved' FOR SHARE",
                    (*scope.key,event['eventId'],proposal['proposal_id'])).fetchone()
                if row is None or dict(row)!=dict(actor_id=event['actor'],proposal_version=event['proposalVersion'],approval_policy_hash=event['policyHash']):
                    raise ValueError('original independent review drifted')
        else:raise ValueError('unknown initialization origin')
        return dict(context=deepcopy(context),analysisReceipt=deepcopy(root),proposalRef=deepcopy(proposal_ref),
                    initializationEvidenceRef=dict(resourceType='Evidence',resourceId=identity,revision=1,
                                                   contentHash='sha256:'+evidence['content_hash']))
