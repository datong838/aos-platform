"""Scoped current report proof; callers still validate contract, sources and reviewer."""
import json
from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope

_BINDINGS = ('eval_contract_ref', 'subject_artifact_ref', 'stage_attempt_ref', 'gate_policy_ref')
_REPORT_JSON = dict(suiteRef='suite_ref', evalContractRef='eval_contract_ref', subjectArtifactRef='subject_artifact_ref',
    stageAttemptRef='stage_attempt_ref', gatePolicyRef='gate_policy_ref', target='target_ref', dataset='dataset_ref', judge='judge_ref', results='results')


def read_stage_eval_report(transaction, scope, ref, *, artifact_ref, stage_attempt_ref,
                           eval_contract_ref, gate_policy_ref, cutoff_at):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('stage report requires HostTransaction and TenantScope')
    ref = AnalystExactRef.model_validate(ref.model_dump())
    if ref.resource_type != 'EvalReportRevision':
        raise ValueError('exact EvalReportRevision required')
    row = transaction.execute('''SELECT * FROM aip_eval_report_revision
        WHERE org_id=%s AND project_id=%s AND report_id=%s AND revision=%s FOR SHARE''',
        (*scope.key, ref.resource_id, ref.revision)).fetchone()
    if row is None:
        raise ValueError('stage eval report unavailable in scope')
    report = AipEvalRunner._report_from_row(scope, row)
    typed = report.model_dump(mode='json', by_alias=True, exclude={'content_hash'})
    raw = dict(typed, **{key:row[column] for key,column in _REPORT_JSON.items()})
    now = transaction.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if (report.content_hash != ref.content_hash or compute_eval_report_hash(report) != ref.content_hash
        or canonical_hash(raw) != canonical_hash(typed) or not report.gate_passed
        or report.created_at.utcoffset() is None or report.created_at > now
        or any(getattr(report, key) is None for key in _BINDINGS)
        or report.evidence_cutoff_at is None or report.evidence_cutoff_at.utcoffset() is None
        or not report.evidence_cutoff_at <= report.created_at):
        raise ValueError('stage eval report is not a valid passed exact report')
    expected = dict(subject_artifact_ref=artifact_ref, stage_attempt_ref=stage_attempt_ref,
        eval_contract_ref=eval_contract_ref, gate_policy_ref=gate_policy_ref, evidence_cutoff_at=cutoff_at)
    if any(getattr(report, key) != value for key,value in expected.items()):
        raise ValueError('stage eval report inputs drifted')
    latest = transaction.execute('''SELECT report_id,revision FROM aip_eval_report_revision
        WHERE org_id=%s AND project_id=%s AND stage_attempt_ref=%s::jsonb
        ORDER BY created_at DESC,report_id DESC,revision DESC LIMIT 1 FOR SHARE''',
        (*scope.key, json.dumps(stage_attempt_ref.model_dump(mode='json', by_alias=True)))).fetchone()
    if latest is None or (latest['report_id'], latest['revision']) != (ref.resource_id, ref.revision):
        raise ValueError('stage eval report is no longer latest')
    run = transaction.execute('''SELECT * FROM aip_eval_run
        WHERE org_id=%s AND project_id=%s AND run_id=%s FOR SHARE''', (*scope.key, report.run_id)).fetchone()
    if run is None:
        raise ValueError('stage eval run unavailable')
    AipReleasePublicationService._verify_run(report, run)
    if (run['created_at'] is None or run['started_at'] is None or run['finished_at'] is None
        or not run['created_at'] <= run['started_at'] <= report.created_at <= run['finished_at'] <= now
        or run['evidence_cutoff_at'] != report.evidence_cutoff_at
        or any(canonical_hash(run[key]) != canonical_hash(getattr(report,key).model_dump(mode='json',by_alias=True)) for key in _BINDINGS)):
        raise ValueError('stage eval execution timing or inputs drifted')
    return report
