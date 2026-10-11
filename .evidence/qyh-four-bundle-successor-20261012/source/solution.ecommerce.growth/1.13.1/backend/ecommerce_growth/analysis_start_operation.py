"""Pure installed-package START command construction; never grants authority."""
from datetime import datetime, timedelta

from .analysis_runtime import AnalysisRuntimeRequest
from .aip_business_investigation_compiler import canonical_command_hash
from .sdk_ports import ExactRef


_FIELDS = {'kind', 'occurrenceRef', 'caseRef', 'profileRef', 'cutoffAt', 'idempotencyKey'}


def build_analysis_start(payload):
    if type(payload) is not dict or set(payload) != _FIELDS or payload['kind'] != 'build_analysis_start':
        raise ValueError('invalid analysis start computation envelope')
    key = payload['idempotencyKey']
    if type(key) is not str or not 1 <= len(key) <= 200 or key != key.strip() or not key.isprintable():
        raise ValueError('canonical analysis idempotency key required')
    if type(payload['cutoffAt']) is not str:
        raise ValueError('analysis cutoff must be UTC seconds')
    cutoff = datetime.fromisoformat(payload['cutoffAt'])
    if cutoff.utcoffset() != timedelta(0) or cutoff.microsecond:
        raise ValueError('analysis cutoff must be UTC seconds')

    def exact(name, kind):
        value = payload[name]
        if type(value) is not dict or set(value) != {'resourceType', 'resourceId', 'revision', 'contentHash'}:
            raise ValueError('strict analysis exact reference required')
        ref = ExactRef(value['resourceType'], value['resourceId'], value['revision'], value['contentHash'])
        if ref.resource_type != kind or ref.resource_id != ref.resource_id.strip() or not ref.resource_id.isprintable():
            raise ValueError('analysis reference purpose or identity drifted')
        return ref

    request = AnalysisRuntimeRequest(
        occurrence_ref=exact('occurrenceRef', 'AutomationOccurrence'),
        case_ref=exact('caseRef', 'BusinessInvestigationCaseRevision'),
        profile_ref=exact('profileRef', 'InvestigationProfileRevision'),
        cutoff_at=cutoff, idempotency_key=key,
    )
    command = request.command_payload()
    return {**command, 'requestHash': canonical_command_hash(command)}
