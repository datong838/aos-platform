"""Match existing Eval metadata; this is not an execution or stage approval."""
from datetime import datetime
import json
from collections.abc import Mapping

from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_execution_authority import EvalExecutionRejected


def require_same_eval_context(report: EvalReportRevision, run: Mapping) -> None:
    references = ('eval_contract_ref', 'subject_artifact_ref',
                  'stage_attempt_ref', 'gate_policy_ref')
    stage = (report.subject_artifact_ref, report.stage_attempt_ref,
             report.gate_policy_ref, report.evidence_cutoff_at)
    if any(value is not None for value in stage) and (
        any(value is None for value in stage) or report.eval_contract_ref is None
    ):
        raise EvalExecutionRejected('Eval Run/Report context is incomplete')
    for name in references:
        value = getattr(report, name)
        expected = None if value is None else value.model_dump(mode='json', by_alias=True)
        if name not in run or json.dumps(run[name], sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise EvalExecutionRejected('Eval Run/Report context drifted')
    if 'evidence_cutoff_at' not in run:
        raise EvalExecutionRejected('Eval Run/Report context cutoff is missing')
    actual, expected = run['evidence_cutoff_at'], report.evidence_cutoff_at
    for value in (actual, expected):
        if value is not None and (not isinstance(value, datetime) or value.utcoffset() is None):
            raise EvalExecutionRejected('Eval Run/Report context cutoff requires timezone')
    if actual != expected:
        raise EvalExecutionRejected('Eval Run/Report context cutoff drifted')
