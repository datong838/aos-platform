"""Current original-event evidence for analysis startup, never business coverage."""
from copy import deepcopy
from datetime import datetime
import re

from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseRevision
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_event_analysis_port import validate_analysis_compilation_blueprint
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService


_TYPE = 'analysis-startup-lineage'


class AnalysisStartupEvidenceService:
    def __init__(self, analysis):
        if type(analysis) is not ProductEventAnalysisService:
            raise TypeError('exact current event analysis service required')
        self.analysis = analysis

    def record(self, conn, *, claimed, run_ref, domain_profile, blueprint):
        if type(run_ref) is not InvestigationExactRef:
            raise TypeError('exact business Run reference required')
        ref = InvestigationExactRef.model_validate(run_ref.model_dump(mode='json',by_alias=True))
        if ref.resource_type != 'BusinessInvestigationRun' or ref.receipt_id is not None:
            raise ValueError('business Run authority reference required')
        blueprint = validate_analysis_compilation_blueprint(domain_profile,blueprint)
        scope = self.analysis.scope
        tx = HostTransaction(conn)
        runs = BusinessInvestigationRunStore(TransactionBoundConnectFactory(tx,scope))

        def current(snapshot, request, _dispatch):
            case = BusinessInvestigationCaseRevision.model_validate(snapshot['source']['case'])
            run = runs.get_verified(scope,ref.resource_id)
            authority,state = run.authority,run.state
            if (any((t.org_id,t.project_id)!=scope.key for t in (case.tenant,authority.tenant,state.tenant))
                    or case.lifecycle.value!='ACTIVE' or case.calculated_content_hash()!=case.content_hash
                    or case.investigation_profile_ref!=domain_profile.exact_ref
                    or case.analysis_type.value!=domain_profile.analysis_type
                    or authority.calculated_content_hash()!=authority.content_hash
                    or (authority.run_id,authority.version,authority.content_hash)!=(ref.resource_id,ref.revision,ref.content_hash)
                    or authority.case_ref.model_dump(mode='json',by_alias=True,exclude_none=True)!=request['caseRef']
                    or authority.analysis_type!=case.analysis_type or state.run_id!=authority.run_id
                    or authority.trigger_key!=claimed.target_idempotency_key
                    or state.lifecycle.value!='PREPARING' or state.control.value!='RUNNING'):
                raise ValueError('startup evidence current Case/Run lineage differs')
            cutoff = datetime.fromisoformat(request['cutoffAt'])
            now = tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            common = dict(
                tenant=dict(orgId=scope.org_id,projectId=scope.project_id),purpose='analysis-start',
                factIds=blueprint['startupContextPolicy']['requiredFactIds'],businessFactCoverage='not-evaluated',
                pendingBusinessFactProfiles=list(domain_profile.required_fact_profiles),
                caseRef=deepcopy(request['caseRef']),runRef=ref.model_dump(mode='json',by_alias=True,exclude_none=True),
                domainProfileRef=deepcopy(blueprint['profileRef']),blueprintHash=blueprint['contentHash'],
                occurrenceRef=deepcopy(request['occurrenceRef']),
                sourceBatchRunId=snapshot['origin']['runId'],
                sourceActor=snapshot['origin']['actor'],sourceSnapshotHash=canonical_sha256(snapshot),
                observedAt=authority.created_at.isoformat())
            if snapshot['occurrence']['triggerSource'] == 'event':
                events = snapshot['source']['events']
                if (len(events)!=1 or events[0]['event_key']!=snapshot['origin']['sourceEventId']
                        or re.fullmatch('[0-9a-f]{64}',events[0].get('payload_hash','')) is None):
                    raise ValueError('startup evidence original event proof differs')
                event = events[0]
                event_at = datetime.fromisoformat(event['created_at'])
                if event_at.utcoffset() is None or cutoff.utcoffset() is None:
                    raise ValueError('startup evidence chronology differs')
                chronological = (cutoff <= event_at <= authority.created_at <= now
                    if 'sourceGroup' in snapshot else event_at <= cutoff <= authority.created_at <= now)
                if not chronological:
                    raise ValueError('startup evidence chronology differs')
                payload = dict(schemaVersion='aos.ecommerce.analysis-startup-evidence/v1', **common,
                    sourceEventId=event['event_key'],sourcePayloadHash=event['payload_hash'])
            elif snapshot['occurrence']['triggerSource'] == 'schedule':
                scheduled_at = datetime.fromisoformat(snapshot['occurrence']['scheduledAt'])
                if (snapshot['source']['events'] or snapshot['occurrence']['sourceEventId'] is not None
                        or snapshot['origin'].get('triggerSource') != 'schedule'
                        or cutoff.utcoffset() is None or scheduled_at.utcoffset() is None
                        or not cutoff <= scheduled_at <= authority.created_at <= now):
                    raise ValueError('startup evidence scheduled source proof differs')
                payload = dict(schemaVersion='aos.ecommerce.analysis-startup-evidence/v2', **common,
                    triggerSource='schedule',sourceSchedulePolicyRef=deepcopy(snapshot['origin']['schedulePolicyRef']),
                    sourceSnapshotGroup=deepcopy(snapshot['sourceGroup']))
            else:
                raise ValueError('startup evidence trigger source differs')
            evidence = self._put(tx,scope,payload,actor=self.analysis.source.actor,observed_at=authority.created_at)
            if runs.get_verified(scope,ref.resource_id)!=run:
                raise ValueError('startup evidence Run changed during recording')
            return evidence

        # Re-enters the original SourceOwner and live claim boundary; caller
        # supplied metadata is never accepted as a current authorization proof.
        return self.analysis._phase(conn,claimed,current)

    @staticmethod
    def _put(tx, scope, payload, *, actor, observed_at):
        digest = canonical_sha256(payload).removeprefix('sha256:')
        identity = 'evidence-analysis-start-' + canonical_sha256(
            [*scope.key,payload['runRef']['resourceId']]).removeprefix('sha256:')
        subject = payload['runRef']
        tx.execute('''INSERT INTO public.aip_evidence
            (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
             observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
            VALUES(%s,%s,%s,NULL,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,clock_timestamp())
            ON CONFLICT (org_id,project_id,evidence_id) DO NOTHING''',
            (*scope.key,identity,_TYPE,Jsonb(subject),_TYPE,
             payload.get('sourceEventId',payload['occurrenceRef']['resourceId']),
             observed_at,observed_at,digest,Jsonb(payload),actor))
        row = tx.execute('''SELECT e.*,EXISTS(SELECT 1 FROM public.aip_evidence_revoke_event r
            WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
              AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked
            FROM public.aip_evidence e WHERE e.org_id=%s AND e.project_id=%s AND e.evidence_id=%s''',
            (*scope.key,identity)).fetchone()
        expected = dict(org_id=scope.org_id,project_id=scope.project_id,evidence_id=identity,
            run_id=None,evidence_type=_TYPE,subject_ref=subject,source_type=_TYPE,
            source_ref=payload.get('sourceEventId',payload['occurrenceRef']['resourceId']),
            observed_at=observed_at,freshness_at=observed_at,content_hash=digest,redaction={},payload=payload,created_by=actor)
        if (row is None or row['revoked'] or any(row[key]!=value for key,value in expected.items())
                or canonical_sha256(row['payload'])!='sha256:'+digest
                or row['created_at']<observed_at):
            raise ValueError('startup evidence is revoked or differs from original record')
        return InvestigationExactRef(resourceType='Evidence',resourceId=identity,revision=1,contentHash='sha256:'+digest)
