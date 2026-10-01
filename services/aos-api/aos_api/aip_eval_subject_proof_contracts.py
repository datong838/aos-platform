"""Subject-review signing input only; this envelope grants no execution authority."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from aos_api.aip_contracts import AipContractModel, ExactContractRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef, AssetType, EvalContractRevisionRef, EvalGatePolicyRef,
    EvalStageAttemptRef, EvalSubjectArtifactRef, JudgeRevisionRef, SHA256_PATTERN,
)

Digest = Annotated[str, Field(pattern=SHA256_PATTERN)]
Identifier = Annotated[str, Field(min_length=1, max_length=200)]


class SubjectReviewEnvelope(AipContractModel):
    """Metadata references and raw-byte digests, never source text or a passed flag."""
    schema_version: Literal['aos.eval-subject-envelope/v1'] = 'aos.eval-subject-envelope/v1'
    purpose: Literal['subject-review'] = 'subject-review'
    tenant: TenantContext
    task_run_id: Identifier
    eval_run_id: Identifier
    case_id: Identifier
    suite_ref: AssetRevisionRef
    judge_ref: JudgeRevisionRef
    rule_input_hash: Digest
    expected_hash: Digest
    generation_skill_ref: AssetRevisionRef
    generation_attempt_ref: EvalStageAttemptRef
    agent_run_id: Identifier
    request_hash: Digest
    query_ref: EvalSubjectArtifactRef
    subject_artifact_ref: EvalSubjectArtifactRef
    query_bytes_hash: Digest
    subject_bytes_hash: Digest
    subject_ref: ExactContractRef
    stage: Literal['portrait', 'diagnosis', 'solution-design']
    stage_attempt_ref: EvalStageAttemptRef
    contract_ref: EvalContractRevisionRef
    policy_ref: EvalGatePolicyRef
    cutoff: datetime
    package_hash: Digest
    generation: int = Field(strict=True, ge=1)
    epoch: int = Field(strict=True, ge=1)
    configuration_ref: ExactContractRef
    command_key: Identifier

    @model_validator(mode='before')
    @classmethod
    def _no_boolean_coercion(cls, value):
        # No field in this signing input admits booleans. Reject before nested
        # legacy reference models could coerce True into revision/attempt 1.
        def check(item):
            if isinstance(item, AipContractModel):
                item = item.model_dump(mode='python')
            if isinstance(item, bool):
                raise ValueError('subject envelope does not admit boolean values')
            if isinstance(item, dict):
                for child in item.values(): check(child)
            elif isinstance(item, (list, tuple)):
                for child in item: check(child)
        check(value)
        return value

    @field_validator('judge_ref', 'subject_ref', 'contract_ref', 'policy_ref',
                     'configuration_ref', 'generation_attempt_ref', 'stage_attempt_ref',
                     mode='before')
    @classmethod
    def _strict_reference_numbers(cls, value):
        if isinstance(value, AipContractModel):
            value = value.model_dump(mode='python')
        if isinstance(value, dict):
            key = 'attempt' if 'attempt' in value else 'revision'
            if type(value.get(key)) is not int:
                raise ValueError('strict numeric reference revision/attempt required')
        return value

    @field_validator('cutoff')
    @classmethod
    def _utc_cutoff(cls, value):
        if value.utcoffset() is None:
            raise ValueError('cutoff must include timezone')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _source_shape(self):
        if not self.tenant.org_id.strip() or not self.tenant.project_id.strip():
            raise ValueError('nonempty tenant required')
        if self.suite_ref.asset_type != AssetType.EVAL_SUITE:
            raise ValueError('exact EvalSuite required')
        if self.generation_skill_ref.asset_type != AssetType.SKILL_TEMPLATE:
            raise ValueError('original generating SkillTemplate required')
        if any(ref.run_id != self.task_run_id for ref in
               (self.generation_attempt_ref, self.stage_attempt_ref)):
            raise ValueError('original attempts must belong to expected TaskRun')
        for ref in (self.subject_ref, self.configuration_ref):
            if not re.fullmatch(SHA256_PATTERN, ref.content_hash):
                raise ValueError('exact subject/configuration digest required')
        return self


def canonical_subject_envelope_bytes(envelope: SubjectReviewEnvelope) -> bytes:
    # model_copy/model_construct can bypass pydantic validation. Reparse before
    # producing signing bytes, including all nested references.
    item = SubjectReviewEnvelope.model_validate(envelope.model_dump(mode='python'))
    payload = json.dumps(item.model_dump(mode='json', by_alias=True),
                         ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                         allow_nan=False).encode('utf-8')
    return b'AOS-EVAL-SUBJECT-ENVELOPE-v1\n' + payload


def subject_envelope_hash(envelope: SubjectReviewEnvelope) -> str:
    return hashlib.sha256(canonical_subject_envelope_bytes(envelope)).hexdigest()


def require_subject_bytes(envelope: SubjectReviewEnvelope, *, query: bytes, subject: bytes) -> None:
    """Check raw content only; callers must independently verify original Owners."""
    canonical_subject_envelope_bytes(envelope)
    if (type(query) is not bytes or type(subject) is not bytes
            or hashlib.sha256(query).hexdigest() != envelope.query_bytes_hash
            or hashlib.sha256(subject).hexdigest() != envelope.subject_bytes_hash):
        raise ValueError('original query or subject bytes drifted')
