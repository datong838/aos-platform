"""Snapshot resume wire contracts; parsing is never execution authority."""
from datetime import datetime, timedelta
import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_runtime import CanonicalRuntimeRef
from aos_api.aip_contracts import AipContractModel, TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.semver import parse_version
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_runtime_adapters import (
    _ANALYSIS_RESUME_FIELDS, _analysis_command_hash, _analysis_exact_ref,
)
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope

OPERATION = 'runtime.analysis.resume_snapshot'
SCHEMA = 'aos.analysis-snapshot-fulfillment-resume-result/v1'
_FIELDS = (_ANALYSIS_RESUME_FIELDS - {'mappingRef'}) | {'businessEvidenceRef', 'readinessPolicyRef'}
_REFS = {
    'occurrenceRef': 'AutomationOccurrence', 'caseRef': 'BusinessInvestigationCaseRevision',
    'profileRef': 'InvestigationProfileRevision', 'priorReceiptRef': 'AnalysisRuntimeReceipt',
    'requirementRef': 'DataRequirementRevision', 'fulfillmentRef': 'DataFulfillmentReceipt',
    'checkpointRef': 'CheckpointRevision', 'priorPlanRef': 'PlanRevision',
    'sourceReadinessRef': 'SourceReadinessEnvelope', 'businessEvidenceRef': 'Evidence',
}
_RECEIPTS = {'AnalysisRuntimeReceipt', 'DataFulfillmentReceipt', 'SourceReadinessEnvelope'}


def _exact(value, kind):
    ref = _analysis_exact_ref(value, kind, receipt_required=kind in _RECEIPTS)
    if kind in _RECEIPTS and (ref.receipt_id != ref.resource_id or ref.revision != 1):
        raise ValueError('snapshot resume requires the original receipt identity')
    if kind not in _RECEIPTS and ref.receipt_id is not None:
        raise ValueError('snapshot revision cannot substitute a receipt')
    return ref


def strict_snapshot_resume_command(command):
    if type(command) is not dict or set(command) != _FIELDS or command.get('operation') != OPERATION:
        raise ValueError('snapshot resume has an invalid envelope')
    key, request_hash = command['idempotencyKey'], command['requestHash']
    if type(key) is not str or key != key.strip() or not 1 <= len(key) <= 200:
        raise ValueError('snapshot resume idempotency key is invalid')
    if type(request_hash) is not str or not re.fullmatch(r'sha256:[0-9a-f]{64}', request_hash):
        raise ValueError('snapshot resume request hash is invalid')
    if _analysis_command_hash({k:v for k,v in command.items() if k != 'requestHash'}) != request_hash:
        raise ValueError('snapshot resume request hash drifted')
    if type(command['cutoffAt']) is not str or type(command['observedAt']) is not str:
        raise ValueError('snapshot resume requires ISO times')
    cutoff, observed = datetime.fromisoformat(command['cutoffAt']), datetime.fromisoformat(command['observedAt'])
    if (cutoff.utcoffset() is None or observed.utcoffset() is None
            or observed < cutoff or observed-cutoff > timedelta(hours=24)):
        raise ValueError('snapshot resume observation is outside the bounded window')
    parsed = {name:_exact(command[name], kind) for name,kind in _REFS.items()}
    raw = command['readinessPolicyRef']
    if type(raw) is not dict:
        raise ValueError('snapshot readiness policy needs an exact installed reference')
    policy = PipelineExactRef.model_validate(raw)
    if (policy.resource_type != 'SnapshotReadinessPolicy' or type(policy.revision) is not str
            or policy.model_dump(mode='json', by_alias=True, exclude_none=True) != raw):
        raise ValueError('snapshot readiness policy reference differs')
    parse_version(policy.revision)
    evidence = command['evidenceRefs']
    if type(evidence) is not list or len(evidence) != 1:
        raise ValueError('snapshot resume requires one exact delivered bundle')
    parsed.update(operation=OPERATION, key=key, cutoff=cutoff, observedAt=observed,
        readinessPolicyRef=policy, evidenceRefs=(_exact(evidence[0], 'EvidenceBundleRevision'),))
    return parsed


class SnapshotFulfillmentResumeResult(AipContractModel):
    """A claimed result still needs the original Store/CAS/Receipt readback."""
    schema_version: Literal[SCHEMA] = SCHEMA
    tenant: TenantContext
    command_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    data_requirement_ref: InvestigationExactRef
    fulfillment_receipt_ref: InvestigationExactRef
    source_readiness_ref: InvestigationExactRef
    business_evidence_ref: InvestigationExactRef
    evidence_bundle_ref: ExactRevisionRef
    checkpoint_ref: InvestigationExactRef
    task_ref: CanonicalRuntimeRef
    task_run_ref: CanonicalRuntimeRef
    task_run_status: Literal[TaskRunStatus.RUNNING] = TaskRunStatus.RUNNING
    task_run_transition_count: Literal[1] = 1
    source_read_count: Literal[0] = 0
    provider_invocation_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0
    external_effect_authorized: Literal[False] = False

    @field_validator('data_requirement_ref', 'fulfillment_receipt_ref', 'source_readiness_ref',
        'business_evidence_ref', 'checkpoint_ref', mode='before')
    @classmethod
    def exact_input(cls, value, info):
        kinds = dict(data_requirement_ref='DataRequirementRevision', fulfillment_receipt_ref='DataFulfillmentReceipt',
            source_readiness_ref='SourceReadinessEnvelope', business_evidence_ref='Evidence', checkpoint_ref='CheckpointRevision')
        if isinstance(value, InvestigationExactRef) and type(value.revision) is not int:
            raise ValueError('snapshot result revisions require integers')
        raw = value.model_dump(mode='json', by_alias=True, exclude_none=True) if isinstance(value, InvestigationExactRef) else value
        return _exact(raw, kinds[info.field_name])

    @field_validator('evidence_bundle_ref', mode='before')
    @classmethod
    def original_bundle_revision(cls, value):
        raw = value.model_dump() if isinstance(value, ExactRevisionRef) else value
        if type(raw) is not dict or type(raw.get('revision')) is not int:
            raise ValueError('snapshot bundle revision requires an integer')
        return raw

    @field_validator('external_effect_authorized', mode='before')
    @classmethod
    def boolean_effect_flag(cls, value):
        if type(value) is not bool:
            raise ValueError('snapshot effect flag requires a boolean')
        return value

    @field_validator('task_run_transition_count', 'source_read_count', 'provider_invocation_count',
        'external_business_mutation_count', mode='before')
    @classmethod
    def integer_counts(cls, value):
        if type(value) is not int:
            raise ValueError('snapshot resume counts require integers')
        return value

    @field_validator('task_ref', 'task_run_ref', mode='before')
    @classmethod
    def original_runtime_version(cls, value):
        raw = value.model_dump() if isinstance(value, CanonicalRuntimeRef) else value
        if type(raw) is not dict or type(raw.get('version')) is not int:
            raise ValueError('snapshot resume runtime versions require integers')
        return raw

    @model_validator(mode='after')
    def original_types(self):
        for ref,kind in ((self.data_requirement_ref,'DataRequirementRevision'),
                (self.fulfillment_receipt_ref,'DataFulfillmentReceipt'),
                (self.source_readiness_ref,'SourceReadinessEnvelope'),
                (self.business_evidence_ref,'Evidence'),(self.checkpoint_ref,'CheckpointRevision')):
            _exact(ref.model_dump(mode='json', by_alias=True, exclude_none=True),kind)
        if (self.evidence_bundle_ref.resource_type != 'EvidenceBundleRevision'
                or self.task_ref.resource_type != 'Task' or self.task_run_ref.resource_type != 'TaskRun'):
            raise ValueError('snapshot result original runtime or bundle type differs')
        return self


def validate_snapshot_resume_result(command, result, *, scope):
    if type(scope) is not TenantScope:
        raise TypeError('original host tenant scope required')
    parsed = strict_snapshot_resume_command(command)
    # Keep nested raw model values for before-validators: a Union serializer can
    # normalize an unchecked bool revision to 1 before validation sees it.
    raw = {name:getattr(result,name) for name in SnapshotFulfillmentResumeResult.model_fields} if isinstance(result, SnapshotFulfillmentResumeResult) else result
    saved = SnapshotFulfillmentResumeResult.model_validate(raw)
    if (saved.tenant.org_id, saved.tenant.project_id) != scope.key:
        raise ValueError('snapshot result belongs to another tenant')
    if saved.command_id != parsed['key'] or saved.request_hash != command['requestHash']:
        raise ValueError('snapshot result belongs to another command')
    for name, ref in (('requirementRef',saved.data_requirement_ref),('fulfillmentRef',saved.fulfillment_receipt_ref),
            ('sourceReadinessRef',saved.source_readiness_ref),('businessEvidenceRef',saved.business_evidence_ref),
            ('checkpointRef',saved.checkpoint_ref)):
        if ref != parsed[name]:
            raise ValueError('snapshot result lineage differs from command')
    bundle = saved.evidence_bundle_ref
    bundle_ref = InvestigationExactRef(resource_type=bundle.resource_type, resource_id=bundle.resource_id,
        revision=bundle.revision, content_hash='sha256:' + bundle.content_hash)
    if bundle_ref != parsed['evidenceRefs'][0]:
        raise ValueError('snapshot result bundle differs from delivered command')
    return saved
