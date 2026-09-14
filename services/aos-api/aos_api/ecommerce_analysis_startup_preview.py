"""Current compiled analysis -> inspectable bootstrap intent and startup preview."""
from copy import deepcopy
from datetime import datetime, timedelta
from psycopg.types.json import Jsonb
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import CreateImpactPreviewRequest, ExactRevisionRef, ImpactAssessment, ImpactDimension
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_bootstrap_contract import AnalysisBootstrapIntent
from aos_api.ecommerce_analysis_compilation_preparation import AnalysisCompilationPreparation
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.extension_runtime.runtime_gate import _reject_deferred


class AnalysisStartupPreviewPreparation:
    def __init__(self, compilation):
        if type(compilation) is not AnalysisCompilationPreparation:
            raise TypeError('exact current compilation preparation required')
        self.compilation = compilation

    def run_current(self, conn, *, claimed, run_ref, domain_profile, blueprint, execute):
        if not callable(execute):
            raise TypeError('synchronous startup preview callback required')
        analysis = self.compilation.context.analysis
        scope, actor = analysis.scope, analysis.source.actor
        tx = HostTransaction(conn)
        factory = TransactionBoundConnectFactory(tx, scope)
        contracts = AipProductionContractStore(factory)

        def compiled(prepared):
            def current(snapshot, request, _dispatch):
                binding, receipt = prepared['compilationBinding'], prepared['compilationReceipt']
                installed = snapshot['source']['dispatch']
                if any(binding[key] != installed[key] for key in ('installationId', 'generation', 'executionEpoch')):
                    raise ValueError('bootstrap compilation installation differs from current source')
                control = snapshot['source']['controlReceipt']
                body = dict(schemaVersion='aos.ecommerce.analysis-bootstrap-intent/v1', operation='ecommerce_analysis_bootstrap',
                    mode='paused-before-first-step', businessExecutionAuthorized=False, externalEffectAuthorized=False,
                    tenant=dict(orgId=scope.org_id, projectId=scope.project_id),
                    occurrenceRef=InvestigationExactRef.model_validate(request['occurrenceRef']).model_dump(mode='json', by_alias=True),
                    sourceControlReceiptRef=InvestigationExactRef.model_validate(control['receiptRef']).model_dump(mode='json', by_alias=True),
                    compilationBinding=deepcopy(binding), compilationReceipt=deepcopy(receipt))
                intent = AnalysisBootstrapIntent.model_validate(dict(body, contentHash=canonical_sha256(body)))
                run = BusinessInvestigationRunStore(factory).get_verified(scope, run_ref.resource_id)
                now = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                approval_ref = control['authority']['command']['approvalRef']
                approval = tx.execute('''SELECT expires_at FROM aip_action_approval_event
                    WHERE org_id=%s AND project_id=%s AND approval_event_id=%s''',
                    (*scope.key, approval_ref['resourceId'])).fetchone()
                if approval is None or approval['expires_at'] is None:
                    raise ValueError('bootstrap current source approval expiry required')
                deadlines = [run.authority.created_at + timedelta(minutes=10), approval['expires_at']]
                deadlines.extend(datetime.fromisoformat(item['readinessExpiresAt'])
                    for item in prepared['skillBindingSet']['bindings'])
                effective_until = snapshot['source']['policy'].get('effectiveUntil')
                if effective_until:
                    deadlines.append(datetime.fromisoformat(effective_until))
                expires_at = min(deadlines)
                if expires_at <= now:
                    raise ValueError('bootstrap current dependencies expired')
                evidence = self._put(tx, scope, intent, actor=actor, observed_at=run.authority.created_at)
                source = ResourceRef(resourceType='Evidence', resourceId=evidence.resource_id, revision='1', authority='aip')
                def dimension(value, *, measured=False):
                    return ImpactDimension(quality='measured' if measured else 'estimated', value=value,
                        sourceRefs=[source], cutoffAt=run.authority.created_at,
                        details=dict(purpose='analysis-bootstrap-only', intentHash=intent.content_hash))
                impact = ImpactAssessment(
                    objectScope=dimension(dict(caseRef=request['caseRef'], runRef=receipt['runRef'], taskId=receipt['taskId']), measured=True),
                    channelScope=dimension(dict(channel='internal-aip-runtime-control', externalChannels=[])),
                    cost=dimension(dict(providerCalls=0, externalCalls=0, scope='initialization-only')),
                    budget=dimension(dict(initializationConsumesProviderBudget=False, businessCapabilityBudget='requires-current-gate')),
                    risks=dimension(dict(businessExecutionAuthorized=False, externalEffectAuthorized=False, businessFacts='not-evaluated')),
                    reversibility=dimension(dict(transactionRollback=True, initialStepStatus='not-started')),
                    approvalChain=dimension(dict(parentControlReceipt=control['receiptRef'], startupActionApprovalRequired=True,
                        businessPlanReviewRequired=True)),
                    rateCapacityKill=dimension(dict(stepExecutionCount=0, runtimeStateOnCommit='paused-before-first-step',
                        currentEventControlReceipt=control['receiptRef'])))
                profile = binding['request']['profile']
                refs = self._mutable_refs(tx, scope, prepared)
                create = CreateImpactPreviewRequest(taskId=receipt['taskId'], planRef=receipt['planRef'],
                    productionContextRef=prepared['productionContextRef'], briefRef=prepared['taskBriefRef'],
                    evidenceBundleRef=prepared['startupBundleRef'], evalContractRef=prepared['startupEvalRef'],
                    responsibilityPlanRef=profile['responsibilityPlanRef'], stageTemplateRef=profile['stageTemplateRef'],
                    bindingRefs=refs, impact=impact, expiresAt=expires_at)
                key = 'analysis-startup-preview-' + canonical_sha256([*scope.key, run_ref.resource_id]).removeprefix('sha256:')
                view = contracts.create_impact_preview(scope, actor, key+'-create', create)
                view = contracts.get_impact_preview(scope, view.preview_id, conn=conn)
                if view.lifecycle.value == 'draft':
                    view = contracts.freeze_impact_preview(scope, actor, view.preview_id, view.version, key+'-freeze')
                ref = ExactRevisionRef(resourceType='ImpactPreviewRevision', resourceId=view.preview_id,
                    revision=view.revision, contentHash=view.content_hash)
                contracts.assert_frozen_preview_current(conn, scope, ref)
                result = execute(dict(deepcopy(prepared), bootstrapIntent=intent.model_dump(mode='json', by_alias=True),
                    bootstrapEvidenceRef=evidence.model_dump(mode='json', by_alias=True),
                    startupPreview=view.model_dump(mode='json', by_alias=True), startupPreviewRef=ref.model_dump(mode='json', by_alias=True)))
                _reject_deferred(result)
                if (self._put(tx, scope, intent, actor=actor, observed_at=run.authority.created_at) != evidence
                        or contracts.get_impact_preview(scope, view.preview_id, conn=conn) != view):
                    raise ValueError('bootstrap intent or preview changed during callback')
                contracts.assert_frozen_preview_current(conn, scope, ref)
                return result
            return analysis._phase(conn, claimed, current)
        return self.compilation.run_current(conn, claimed=claimed, run_ref=run_ref,
            domain_profile=domain_profile, blueprint=blueprint, execute=compiled)

    @staticmethod
    def _mutable_refs(tx, scope, prepared):
        configured = {}
        for slot in prepared['responsibilityPlan']['slots']:
            assignee = slot['assignee']
            if assignee['kind'] == 'agent_instance':
                identity, version = assignee['resourceId'], assignee['version']
                if identity in configured and configured[identity] != version:
                    raise ValueError('bootstrap configured agent version differs across slots')
                configured[identity] = version
        agents = sorted(configured)
        rows = tx.execute('''SELECT binding_id,version,capability_refs FROM aip_skill_binding
            WHERE org_id=%s AND project_id=%s AND instance_id=ANY(%s) AND status='active' ORDER BY binding_id''',
            (*scope.key, agents)).fetchall()
        chosen = {item['bindingId'] for item in prepared['skillBindingSet']['bindings']}
        if not chosen.issubset({row['binding_id'] for row in rows}):
            raise ValueError('bootstrap selected binding is no longer active')
        refs = [dict(resourceType='SkillBinding', resourceId=row['binding_id'], version=row['version']) for row in rows]
        caps = set()
        for row in rows:
            for value in row['capability_refs']:
                identifier = value if isinstance(value, str) else (
                    value.get('bindingId') or value.get('resourceId') if isinstance(value, dict) else None)
                if not isinstance(identifier, str) or not identifier or identifier != identifier.strip():
                    raise ValueError('bootstrap capability binding reference is invalid')
                caps.add(identifier)
        caps = sorted(caps)
        for kind, table, column, identities in (
            ('AgentInstance', 'aip_agent_instance', 'instance_id', agents),
            ('CapabilityBinding', 'aip_capability_binding', 'binding_id', caps)):
            current = tx.execute(f'SELECT {column} AS id,version,status FROM {table} WHERE org_id=%s AND project_id=%s AND {column}=ANY(%s) ORDER BY {column}',
                (*scope.key, identities)).fetchall()
            if {row['id'] for row in current} != set(identities) or any(row['status'] != 'active' for row in current):
                raise ValueError('bootstrap current mutable dependency unavailable')
            if kind == 'AgentInstance' and any(row['version'] != configured[row['id']] for row in current):
                raise ValueError('bootstrap configured agent version differs from current dependency')
            refs.extend(dict(resourceType=kind, resourceId=row['id'], version=row['version']) for row in current)
        return refs

    @staticmethod
    def _put(tx, scope, intent, *, actor, observed_at):
        intent = intent.checked()
        subject = intent.compilation_receipt.run_ref.model_dump(mode='json', by_alias=True)
        payload = dict(schemaVersion='aos.ecommerce.analysis-bootstrap-evidence/v1', purpose='analysis-bootstrap-only',
                       intent=intent.model_dump(mode='json', by_alias=True))
        digest = canonical_sha256(payload).removeprefix('sha256:')
        identity = 'evidence-analysis-bootstrap-' + canonical_sha256([*scope.key, subject['resourceId']]).removeprefix('sha256:')
        tx.execute('''INSERT INTO aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,'analysis-bootstrap-intent',%s,'analysis-bootstrap-intent',%s,%s,%s,%s,'{}',%s,%s,clock_timestamp())
            ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING''',
            (*scope.key, identity, Jsonb(subject), intent.content_hash, observed_at, observed_at, digest, Jsonb(payload), actor))
        row = tx.execute('''SELECT e.*,EXISTS(SELECT 1 FROM aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
              AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s''', (*scope.key, identity)).fetchone()
        expected = dict(run_id=None,evidence_type='analysis-bootstrap-intent',subject_ref=subject,
            source_type='analysis-bootstrap-intent',source_ref=intent.content_hash,observed_at=observed_at,
            freshness_at=observed_at,content_hash=digest,redaction={},payload=payload,created_by=actor)
        if (row is None or row['revoked'] or any(row[key] != value for key, value in expected.items())
                or canonical_sha256(row['payload']) != 'sha256:'+digest or row['created_at'] < observed_at):
            raise ValueError('bootstrap intent evidence is revoked or differs')
        return InvestigationExactRef(resourceType='Evidence', resourceId=identity, revision=1, contentHash='sha256:'+digest)
