"""Current bootstrap reviewer eligibility; never grants execution or memberships."""
from aos_api.aip_action_policy import ACTION_APPROVAL_ROLES
from aos_api.ecommerce_growth_cutover_proposal_gate import action_snapshot_from_row
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.openfga import openfga_api_url, user_key, marking_key
from aos_api.tenant_scope import TenantScope


def require_current_bootstrap_review_identity(*, transaction, scope, actor, maker, action_snapshot, checker):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope or type(checker) is not bool:
        raise TypeError('exact bootstrap transaction, tenant and review operation required')
    if openfga_api_url():
        raise PermissionError('current remote bootstrap review adapter required')
    for identity in (actor, maker):
        if type(identity) is not str or not identity or identity != identity.strip() or not identity.isprintable():
            raise PermissionError('current bootstrap identity invalid')
    if (checker and actor == maker) or (not checker and actor != maker):
        raise PermissionError('bootstrap maker and reviewer must remain distinct')
    current = transaction.execute("SELECT current_setting('aos.org_id',true) AS org_id, "
                                  "current_setting('aos.project_id',true) AS project_id").fetchone()
    if current is None or (current['org_id'], current['project_id']) != scope.key:
        raise PermissionError('current bootstrap transaction tenant differs')
    if not isinstance(action_snapshot, dict) or action_snapshot.get('id') != 'ecommerce_analysis_bootstrap':
        raise ValueError('exact bootstrap action required')
    row = transaction.execute('''SELECT id,name,object_type,parameters,required_markings,submission_criteria
        FROM meta_action_type WHERE id=%s FOR SHARE''', (action_snapshot['id'],)).fetchone()
    if row is None or action_snapshot_from_row(row) != action_snapshot:
        raise ValueError('current bootstrap action snapshot differs')
    markings = action_snapshot['requiredMarkings']
    if type(markings) is not list or any(type(label) is not str or not label or label != label.strip() for label in markings):
        raise ValueError('current bootstrap action markings invalid')
    roles = {}
    for identity in sorted({actor, maker}):
        rows = transaction.execute('''SELECT role FROM meta_membership
            WHERE org_id=%s AND project_id=%s AND subject=%s FOR SHARE''', (*scope.key, identity)).fetchall()
        if len(rows) != 1 or not isinstance(rows[0]['role'], str):
            raise PermissionError('current bootstrap membership unavailable')
        roles[identity] = rows[0]['role']
        if checker and identity == actor and roles[identity].lower() not in ACTION_APPROVAL_ROLES:
            raise PermissionError('current bootstrap reviewer role denied')
        for label in sorted(set(markings)):
            grants = transaction.execute('''SELECT object_key FROM authz_tuple
                WHERE org_id=%s AND project_id=%s AND user_key=%s
                AND relation='bearer' AND object_key=%s FOR SHARE''',
                (*scope.key, user_key(identity), marking_key(label))).fetchall()
            if len(grants) != 1:
                raise PermissionError('current bootstrap action marking denied')
    return (roles[actor],)


class AnalysisBootstrapCurrentBinding:
    """Recheck source and stored bootstrap objects around a synchronous review operation."""
    def __init__(self, analysis):
        from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('exact original analysis owner required')
        self.analysis = analysis

    def run_current(self, conn, *, claimed, intent, preview_ref, execute):
        from copy import deepcopy
        from aos_api.ecommerce_analysis_bootstrap_contract import AnalysisBootstrapIntent
        from aos_api.aip_production_contracts import ExactRevisionRef
        from aos_api.business_investigation_shared_contracts import InvestigationExactRef
        from aos_api.extension_runtime.runtime_gate import _reject_deferred
        if not callable(execute):
            raise TypeError('synchronous current bootstrap callback required')
        intent = AnalysisBootstrapIntent.model_validate(intent).checked()
        preview_ref = ExactRevisionRef.model_validate(preview_ref)
        if preview_ref.resource_type != 'ImpactPreviewRevision':
            raise ValueError('bootstrap exact preview required')
        def current(snapshot, request, _dispatch):
            if (intent.occurrence_ref != InvestigationExactRef.model_validate(request['occurrenceRef'])
                    or intent.source_control_receipt_ref != InvestigationExactRef.model_validate(snapshot['source']['controlReceipt']['receiptRef'])):
                raise ValueError('bootstrap original occurrence or control receipt differs')
            before = self._read(conn, snapshot, intent, preview_ref)
            result = execute(deepcopy(before))
            _reject_deferred(result)
            if self._read(conn, snapshot, intent, preview_ref) != before:
                raise ValueError('bootstrap current binding changed during review')
            return result
        return self.analysis._phase(conn, claimed, current)

    def _read(self, conn, snapshot, intent, preview_ref):
        from uuid import UUID
        from aos_api.aip_business_investigation_compile_saga import BusinessInvestigationCompilationReceiptStore
        from aos_api.aip_production_contract_store import AipProductionContractStore
        from aos_api.aip_production_contracts import ExactRevisionRef
        from aos_api.asset_registry.canonical_json import canonical_sha256
        from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
        from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
        from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
        scope = self.analysis.scope
        intent = intent.checked()
        if (intent.tenant.org_id, intent.tenant.project_id) != scope.key:
            raise ValueError('bootstrap current tenant differs')
        tx = HostTransaction(conn)
        factory = TransactionBoundConnectFactory(tx, scope)
        receipt = intent.compilation_receipt
        run = BusinessInvestigationRunStore(factory).get_verified(scope, receipt.run_ref.resource_id)
        case = BusinessInvestigationCaseStore(factory).get(scope, run.authority.case_ref.resource_id)
        from aos_api.business_investigation_shared_contracts import InvestigationExactRef
        if (run.authority.case_ref != InvestigationExactRef.model_validate(snapshot['request']['caseRef'])
                or run.authority.trigger_key != snapshot['request']['idempotencyKey']):
            raise ValueError('bootstrap Run differs from original analysis request')
        installed = snapshot['source']['dispatch']
        intent.compilation_binding.validate_current(scope=scope,
            installation_id=UUID(str(installed['installationId'])), generation=UUID(str(installed['generation'])),
            execution_epoch=installed['executionEpoch'], case=case, run=run)
        if BusinessInvestigationCompilationReceiptStore(factory).get_for_run(scope, receipt.run_ref) != receipt:
            raise ValueError('bootstrap current compilation Receipt differs')
        task = tx.execute('''SELECT * FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s FOR UPDATE''',
                          (*scope.key, receipt.task_id)).fetchone()
        plan = tx.execute('''SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s FOR UPDATE''',
                          (*scope.key, receipt.plan_ref.resource_id)).fetchone()
        if (task is None or task['status'] not in {'planning', 'awaiting_approval'}
                or task['current_plan_revision_id'] != receipt.plan_ref.resource_id
                or plan is None or plan['task_id'] != receipt.task_id or plan['approval_status'] != 'draft'
                or plan['revision'] != receipt.plan_ref.revision or plan['content_hash'] != receipt.plan_ref.content_hash
                or not plan['risk'].get('productionContract', {}).get('productionStartGateRequired')):
            raise ValueError('bootstrap current draft Task Plan differs')
        if tx.execute('SELECT 1 FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s LIMIT 1',
                      (*scope.key, receipt.task_id)).fetchone() is not None:
            raise ValueError('bootstrap Task already has runtime lineage')
        preview = AipProductionContractStore(factory).assert_frozen_preview_current(conn, scope, preview_ref)
        profile = intent.compilation_binding.request.profile
        expected = {'plan_ref': receipt.plan_ref, 'production_context_ref': profile.production_context_ref,
                    'responsibility_plan_ref': profile.responsibility_plan_ref, 'stage_template_ref': profile.stage_template_ref}
        if preview['task_id'] != receipt.task_id or any(
                ExactRevisionRef.model_validate(preview[key]) != ref for key, ref in expected.items()):
            raise ValueError('bootstrap current preview binding differs')
        body = intent.model_dump(mode='json', by_alias=True)
        payload = dict(schemaVersion='aos.ecommerce.analysis-bootstrap-evidence/v1', purpose='analysis-bootstrap-only', intent=body)
        identity = 'evidence-analysis-bootstrap-' + canonical_sha256([*scope.key, receipt.run_ref.resource_id]).removeprefix('sha256:')
        evidence = tx.execute('''SELECT e.*,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
            AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked FROM aip_evidence e
            WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s''', (*scope.key, identity)).fetchone()
        if (evidence is None or evidence['revoked'] or evidence['run_id'] is not None
                or evidence['payload'] != payload or evidence['source_ref'] != intent.content_hash
                or evidence['source_type'] != 'analysis-bootstrap-intent' or evidence['evidence_type'] != 'analysis-bootstrap-intent'
                or evidence['content_hash'] != canonical_sha256(payload).removeprefix('sha256:')
                or evidence['subject_ref'] != receipt.run_ref.model_dump(mode='json', by_alias=True)
                or evidence['observed_at'] != run.authority.created_at or evidence['freshness_at'] != run.authority.created_at
                or evidence['created_by'] != self.analysis.source.actor or evidence['redaction'] != {}
                or evidence['created_at'] < run.authority.created_at):
            raise ValueError('bootstrap current intent Evidence differs')
        for dimension in preview['impact'].values():
            if (dimension['details'].get('purpose') != 'analysis-bootstrap-only'
                    or dimension['details'].get('intentHash') != intent.content_hash
                    or dimension['sourceRefs'] != [dict(resourceType='Evidence', resourceId=identity, revision='1', authority='aip')]):
                raise ValueError('bootstrap preview intent source differs')
        return dict(intent=body, task=dict(task), plan=dict(plan), preview=dict(preview), evidence=dict(evidence))
