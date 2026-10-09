"""Descriptive Model execution plan only; no issuance, admission or runtime route."""
from typing import Literal
from datetime import datetime, timezone
import hashlib
import json
import base64
import binascii

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_store import canonical_hash

SHA256 = r'^[0-9a-f]{64}$'


def _plain_contract_input(value):
    # model_copy/model_construct do not validate. Preserve even undeclared
    # instance fields so extra="forbid" can reject them during fresh parsing.
    if isinstance(value, BaseModel):
        value = {**value.__dict__, **(value.model_extra or {})}
    if isinstance(value, dict):
        return {key: _plain_contract_input(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_contract_input(item) for item in value]
    return value


class _ModelExecutionContract(AipContractModel):
    model_config = ConfigDict(revalidate_instances='always')

    @model_validator(mode='before')
    @classmethod
    def _fresh_input(cls, value):
        return _plain_contract_input(value)


class ModelEvalExecutionLeg(_ModelExecutionContract):
    tenant: TenantContext
    purpose: Literal['target', 'judge']
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    source_ref: VersionedAssetRef
    physical_account_ref: VersionedAssetRef
    approval_ref: BudgetExactRef
    budget_hold_ref: BudgetExactRef
    budget_allocation_ref: BudgetExactRef
    allocation_upper_bound_minor: int = Field(strict=True, gt=0, le=100_000_000)
    joint_receipt_ref: BudgetExactRef
    intent_ref: BudgetExactRef
    identity_id: str = Field(min_length=1, max_length=200)
    identity_key_hash: str = Field(pattern=SHA256)
    attempt: Literal[1]

    @field_validator('identity_id')
    @classmethod
    def _exact_identity_id(cls, value):
        if value != value.strip():
            raise ValueError('exact execution identity required')
        return value

    @field_validator('attempt', mode='before')
    @classmethod
    def _exact_attempt(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('one native integer attempt required')
        return value

    @model_validator(mode='after')
    def _reference_kinds(self):
        for ref, kind in (
            (self.model_ref, 'RegisteredModelRevision'),
            (self.provider_ref, 'ProviderInstanceRevision'),
            (self.price_ref, 'ModelPriceSnapshotRevision'),
            (self.quota_policy_ref, 'QuotaPolicyRevision'),
            (self.budget_policy_ref, 'BudgetPolicyRevision'),
            (self.source_ref, 'ProviderCapacitySourceRevision'),
            (self.physical_account_ref, 'ProviderPhysicalAccountCandidateRevision'),
        ):
            if ref.asset_type != kind:
                raise ValueError('exact execution leg asset kinds required')
        for ref, kind in (
            (self.approval_ref, 'ActionApprovalEvent'),
            (self.budget_hold_ref, 'ModelEvalBudgetReservation'),
            (self.budget_allocation_ref, 'ModelEvalBudgetAllocation'),
            (self.joint_receipt_ref, 'ModelEvalJointAdmissionReceipt'),
            (self.intent_ref, 'ModelEvalExecutionIntent'),
        ):
            if ref.resource_type != kind:
                raise ValueError('exact execution leg fact kinds required')
        if self.identity_id.strip() != self.identity_id:
            raise ValueError('exact executor identity required')
        return self


class ModelEvalExecutorCertificateSigningInput(_ModelExecutionContract):
    """Unsigned description only: no trusted issuer or current admission."""
    schema_version: Literal['aos.model-eval-executor-certificate-signing-input/v1']
    tenant: TenantContext
    execution_id: str = Field(min_length=1, max_length=200)
    manifest_hash: str = Field(pattern=SHA256)
    request_hash: str = Field(pattern=SHA256)
    case_id: str = Field(min_length=1, max_length=200)
    purpose: Literal['target', 'judge']
    candidate_ref: VersionedAssetRef
    leg: ModelEvalExecutionLeg
    issuer_id: str = Field(min_length=1, max_length=200)
    issuer_key_id: str = Field(min_length=1, max_length=200)
    public_key_base64: str = Field(min_length=1, max_length=100)
    valid_from: datetime
    valid_until: datetime

    @field_validator('execution_id', 'case_id', 'issuer_id', 'issuer_key_id')
    @classmethod
    def _exact_identifier(cls, value):
        if not value.strip() or value != value.strip():
            raise ValueError('exact nonempty identifier required')
        return value

    @field_validator('valid_from', 'valid_until')
    @classmethod
    def _aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timezone-aware certificate interval required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _key_and_interval(self):
        try:
            raw = base64.b64decode(self.public_key_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('canonical Ed25519 public key required') from exc
        if len(raw) != 32 or base64.b64encode(raw).decode('ascii') != self.public_key_base64:
            raise ValueError('canonical Ed25519 public key required')
        if hashlib.sha256(raw).hexdigest() != self.leg.identity_key_hash:
            raise ValueError('certificate public key must match exact leg identity key')
        if self.valid_from >= self.valid_until:
            raise ValueError('nonempty half-open certificate interval required')
        if self.tenant != self.leg.tenant or self.purpose != self.leg.purpose:
            raise ValueError('exact certificate leg tenant and purpose required')
        return self


class ModelEvalIssuerVerificationInput(_ModelExecutionContract):
    """Presented issuer facts, not a trusted/current persisted root."""
    schema_version: Literal['aos.model-eval-issuer-verification-input/v1']
    purpose: Literal['model-eval-execution']
    tenant: TenantContext
    issuer_id: str = Field(min_length=1, max_length=200)
    issuer_key_id: str = Field(min_length=1, max_length=200)
    public_key_base64: str = Field(min_length=1, max_length=100)
    valid_from: datetime
    valid_until: datetime
    revoked_at: datetime | None

    @field_validator('issuer_id', 'issuer_key_id')
    @classmethod
    def _exact_identifier(cls, value):
        if not value.strip() or value != value.strip():
            raise ValueError('exact nonempty issuer identifier required')
        return value

    @field_validator('valid_from', 'valid_until', 'revoked_at')
    @classmethod
    def _aware_time(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('timezone-aware issuer time required')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _key_and_interval(self):
        try:
            raw = base64.b64decode(self.public_key_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('canonical issuer Ed25519 key required') from exc
        if len(raw) != 32 or base64.b64encode(raw).decode('ascii') != self.public_key_base64:
            raise ValueError('canonical issuer Ed25519 key required')
        if self.valid_from >= self.valid_until:
            raise ValueError('nonempty issuer interval required')
        return self


def canonical_model_certificate_signing_bytes(manifest, certificate) -> bytes:
    """Bind unsigned certificate input; never verifies current issuer authority."""
    plan = ModelEvalExecutionManifest.model_validate(manifest)
    claim = ModelEvalExecutorCertificateSigningInput.model_validate(certificate)
    case = next((item for item in plan.cases if item.case_id == claim.case_id), None)
    if (case is None or claim.tenant != plan.tenant
            or claim.execution_id != plan.execution_id
            or claim.manifest_hash != canonical_hash(plan.model_dump(mode='json', by_alias=True))
            or claim.request_hash != plan.request_hash
            or claim.candidate_ref != plan.request.target_ref
            or claim.leg != getattr(case, claim.purpose)):
        raise ValueError('certificate must bind complete original Model manifest and case leg')
    payload = json.dumps(claim.model_dump(mode='json', by_alias=True), sort_keys=True,
                         ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return b'AOS-MODEL-EVAL-EXECUTOR-CERTIFICATE-SIGNING-INPUT-v1\n' + payload.encode('utf-8')


class ModelEvalCaseSigningInput(_ModelExecutionContract):
    """Signing input only, never verified execution, fees or admission."""
    schema_version: Literal['aos.model-eval-case-signing-input/v1']
    tenant: TenantContext
    execution_id: str = Field(min_length=1, max_length=200)
    manifest_hash: str = Field(pattern=SHA256)
    request_hash: str = Field(pattern=SHA256)
    case_id: str = Field(min_length=1, max_length=200)
    purpose: Literal['target', 'judge']
    candidate_ref: VersionedAssetRef
    leg: ModelEvalExecutionLeg
    input_hash: str = Field(pattern=SHA256)
    output_hash: str = Field(pattern=SHA256)
    occurred_at: datetime
    target_claim_hash: str | None = Field(default=None, pattern=SHA256)
    actual_hash: str | None = Field(default=None, pattern=SHA256)
    expected_hash: str | None = Field(default=None, pattern=SHA256)
    passed: bool | None = Field(default=None, strict=True)
    detail_code: str | None = Field(default=None, min_length=1, max_length=120)

    @field_validator('execution_id', 'case_id', 'detail_code')
    @classmethod
    def _exact_ids(cls, value):
        if value is not None and (not value.strip() or value.strip() != value):
            raise ValueError('exact nonempty identifier required')
        return value

    @field_validator('occurred_at')
    @classmethod
    def _aware_utc(cls, value):
        if value.utcoffset() is None:
            raise ValueError('case signing input time requires timezone')
        return value.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _purpose_fields(self):
        if self.leg.purpose != self.purpose or self.leg.tenant != self.tenant:
            raise ValueError('case signing input purpose/tenant drifted')
        fields = (self.target_claim_hash, self.actual_hash, self.expected_hash,
                  self.passed, self.detail_code)
        if self.purpose == 'target' and any(x is not None for x in fields):
            raise ValueError('Target cannot assert Judge result')
        if self.purpose == 'judge' and any(x is None for x in
                (self.target_claim_hash, self.actual_hash, self.passed, self.detail_code)):
            raise ValueError('Judge must bind Target claim and result')
        return self


def _model_case_signing_bytes(claim: ModelEvalCaseSigningInput) -> bytes:
    payload = json.dumps(claim.model_dump(mode='json', by_alias=True),
        ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return b'AOS-MODEL-EVAL-CASE-SIGNING-INPUT-v1\n' + payload.encode('utf-8')


def _bound_model_case(plan, claim):
    case = next((x for x in plan.cases if x.case_id == claim.case_id), None)
    if (case is None or claim.tenant != plan.tenant
            or claim.execution_id != plan.execution_id
            or claim.manifest_hash != canonical_hash(plan.model_dump(mode='json', by_alias=True))
            or claim.request_hash != plan.request_hash
            or claim.candidate_ref != plan.request.target_ref
            or claim.leg != getattr(case, claim.purpose)):
        raise ValueError('Model case signing input is not exactly bound to plan')
    if claim.purpose == 'target' and claim.input_hash != case.input_hash:
        raise ValueError('Target input drifted from original case')
    return case


def canonical_model_case_signing_bytes(manifest, claim, *, input_bytes: bytes,
        output_bytes: bytes, target_claim=None) -> bytes:
    """Check exact descriptive claims and raw bytes; no signature or authority check."""
    plan = ModelEvalExecutionManifest.model_validate(manifest)
    item = ModelEvalCaseSigningInput.model_validate(claim)
    case = _bound_model_case(plan, item)
    if (type(input_bytes) is not bytes or type(output_bytes) is not bytes
            or hashlib.sha256(input_bytes).hexdigest() != item.input_hash
            or hashlib.sha256(output_bytes).hexdigest() != item.output_hash):
        raise ValueError('Model case signing raw bytes drifted')
    if item.purpose == 'target':
        if target_claim is not None:
            raise ValueError('Target cannot borrow another Target claim')
    else:
        target = ModelEvalCaseSigningInput.model_validate(target_claim)
        _bound_model_case(plan, target)
        if (target.purpose != 'target' or target.case_id != item.case_id
                or item.expected_hash != case.expected_hash
                or item.actual_hash != target.output_hash
                or target.occurred_at > item.occurred_at
                or item.target_claim_hash != hashlib.sha256(_model_case_signing_bytes(target)).hexdigest()):
            raise ValueError('Judge is not exactly bound to original Target claim')
    return _model_case_signing_bytes(item)


class ModelEvalCaseInputBinding(_ModelExecutionContract):
    """Complete case input declaration; hashes grant no artifact access."""
    case_id: str = Field(min_length=1, max_length=200, strict=True)
    input_hash: str = Field(pattern=SHA256, strict=True)
    expected_hash: str | None = Field(pattern=SHA256, strict=True)

    @field_validator('case_id')
    @classmethod
    def _exact_case_id(cls, value):
        if not value.strip() or value.strip() != value:
            raise ValueError('exact nonempty case identifier required')
        return value


class ModelEvalCaseExecutionPlan(_ModelExecutionContract):
    case_id: str = Field(min_length=1, max_length=200)
    input_hash: str = Field(pattern=SHA256)
    expected_hash: str | None = Field(default=None, pattern=SHA256)
    target: ModelEvalExecutionLeg
    judge: ModelEvalExecutionLeg

    @field_validator('case_id')
    @classmethod
    def _exact_case_id(cls, value):
        if not value.strip() or value.strip() != value:
            raise ValueError('exact nonempty identifier required')
        return value

    @model_validator(mode='after')
    def _independent_legs(self):
        if (self.target.purpose != 'target' or self.judge.purpose != 'judge'
                or self.target.tenant != self.judge.tenant
                or self.target.identity_id == self.judge.identity_id
                or self.target.identity_key_hash == self.judge.identity_key_hash
                or self.target.approval_ref.resource_id == self.judge.approval_ref.resource_id):
            raise ValueError('independent Target and Judge authority required')
        return self


class ModelEvalParentBudgetLimit(_ModelExecutionContract):
    """Presented parent limit, not evidence of an actual hold or allocation."""
    parent_hold_ref: BudgetExactRef
    request_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    approval_ref: BudgetExactRef
    budget_policy_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    currency: Literal['CNY']
    upper_bound_minor: int = Field(strict=True, gt=0, le=100_000_000)

    @model_validator(mode='after')
    def _exact_parent(self):
        if (self.parent_hold_ref.resource_type != 'ModelEvalBudgetReservation'
                or self.approval_ref.resource_type != 'ActionApprovalEvent'
                or self.budget_policy_ref.asset_type != 'BudgetPolicyRevision'
                or self.price_ref.asset_type != 'ModelPriceSnapshotRevision'
                or self.request_id != self.request_id.strip()):
            raise ValueError('exact parent request and budget kinds required')
        return self


class ModelJudgeParentBudgetLimit(_ModelExecutionContract):
    """New-purpose declaration; native backing and joint proof remain required.

    Deliberately separate from the quality-eval v1 parent and manifest.
    Parsing this declaration neither verifies its sources nor grants execution.
    """
    schema_version: Literal['aos.model-judge-parent-budget/v1']
    purpose: Literal['model-judge-call']
    tenant: TenantContext
    parent_hold_ref: BudgetExactRef
    request_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    approval_ref: BudgetExactRef
    budget_policy_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    currency: Literal['CNY']
    upper_bound_minor: int = Field(strict=True, gt=0, le=100_000_000)
    execution_allowed: Literal[False] = False

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError('native false Judge declaration required')
        return value

    @field_validator('parent_hold_ref', mode='before')
    @classmethod
    def _immutable_hold_revision(cls, value):
        raw = _plain_contract_input(value)
        revision = raw.get('revision') if isinstance(raw, dict) else None
        if type(revision) is not int or revision != 1:
            raise ValueError('native immutable Judge hold revision required')
        return value

    @model_validator(mode='after')
    def _exact_judge_parent(self):
        if (self.parent_hold_ref.resource_type != 'ModelJudgeBudgetReservation'
                or self.approval_ref.resource_type != 'ActionApprovalEvent'
                or self.budget_policy_ref.asset_type != 'BudgetPolicyRevision'
                or self.price_ref.asset_type != 'ModelPriceSnapshotRevision'
                or not self.request_id.strip()
                or self.request_id != self.request_id.strip()):
            raise ValueError('exact new-purpose Judge parent kinds required')
        return self


class ModelEvalExecutionManifest(_ModelExecutionContract):
    schema_version: Literal[1]
    tenant: TenantContext
    execution_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    request: ModelEvalRequestCreate
    cases: list[ModelEvalCaseExecutionPlan] = Field(min_length=1, max_length=10000)
    parent_budget_limits: list[ModelEvalParentBudgetLimit] = Field(min_length=1, max_length=20000)
    case_set_hash: str = Field(pattern=SHA256)
    execution_allowed: Literal[False] = False

    @field_validator('execution_id', 'request_id')
    @classmethod
    def _exact_manifest_ids(cls, value):
        if not value.strip() or value.strip() != value:
            raise ValueError('exact nonempty identifier required')
        return value

    @field_validator('schema_version', mode='before')
    @classmethod
    def _exact_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('native integer schema version required')
        return value

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError('explicit nonexecuting manifest required')
        return value

    @model_validator(mode='after')
    def _bind_original_request_and_cases(self):
        request = ModelEvalRequestCreate.model_validate(
            self.request.model_dump(mode='json', by_alias=True))
        if (request.tenant != self.tenant
                or canonical_hash(request.model_dump(mode='json', by_alias=True)) != self.request_hash):
            raise ValueError('exact original Model request hash and tenant required')
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError('unique complete case identities required')
        inputs = [dict(caseId=c.case_id, inputHash=c.input_hash, expectedHash=c.expected_hash)
                  for c in self.cases]
        if canonical_hash(inputs) != self.case_set_hash:
            raise ValueError('exact case input set hash required')
        parents = {p.parent_hold_ref.resource_id: p for p in self.parent_budget_limits}
        if (len(parents) != len(self.parent_budget_limits)
                or len({p.request_id for p in parents.values()}) != len(parents)
                or len({p.approval_ref.resource_id for p in parents.values()}) != len(parents)):
            raise ValueError('unique original parent hold request and approval required')
        intents, allocations, used, target_parents = set(), set(), set(), set()
        totals, purposes = {}, {}
        for case in self.cases:
            target = case.target
            if (target.model_ref != request.source_ref
                    or target.provider_ref != request.provider_ref
                    or target.price_ref != request.price_ref
                    or target.quota_policy_ref != request.quota_policy_ref
                    or target.budget_policy_ref != request.budget_policy_ref):
                raise ValueError('Target must use original approved Model governance')
            for leg in (target, case.judge):
                if leg.tenant != self.tenant:
                    raise ValueError('execution leg tenant drifted')
                intent, allocation = leg.intent_ref.resource_id, leg.budget_allocation_ref.resource_id
                if intent in intents or allocation in allocations:
                    raise ValueError('per-call unique Intent and budget allocation required')
                intents.add(intent)
                allocations.add(allocation)
                hold = leg.budget_hold_ref.resource_id
                parent = parents.get(hold)
                if (parent is None or parent.parent_hold_ref != leg.budget_hold_ref
                        or parent.approval_ref != leg.approval_ref
                        or parent.budget_policy_ref != leg.budget_policy_ref
                        or parent.price_ref != leg.price_ref):
                    raise ValueError('exact parent hold approval and governance required')
                if hold in purposes and purposes[hold] != leg.purpose:
                    raise ValueError('Judge cannot borrow Target parent hold')
                purposes[hold] = leg.purpose
                if leg.purpose == 'target':
                    target_parents.add(hold)
                    if (parent.request_id != self.request_id or parent.request_hash != self.request_hash
                            or parent.upper_bound_minor > request.upper_bound_minor):
                        raise ValueError('Target parent must bind original approved request upper bound')
                elif parent.request_id == self.request_id:
                    raise ValueError('independent Judge parent request required')
                used.add(hold)
                totals[hold] = totals.get(hold, 0) + leg.allocation_upper_bound_minor
                if totals[hold] > parent.upper_bound_minor:
                    raise ValueError('case allocations exceed parent budget upper bound')
        if used != set(parents) or len(target_parents) != 1:
            raise ValueError('complete used parents and single Target request hold required')
        return self


class ModelEvalSignedCertificateEnvelope(_ModelExecutionContract):
    """Complete signed bytes; structural validity does not confer issuer trust."""
    schema_version: Literal['aos.model-eval-signed-certificate-envelope/v1']
    certificate: ModelEvalExecutorCertificateSigningInput
    signature_base64: str

    @field_validator('signature_base64', mode='before')
    @classmethod
    def _canonical_signature(cls, value):
        if type(value) is not str or len(value) != 88:
            raise ValueError('canonical Ed25519 signature required')
        try:
            raw = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError('canonical Ed25519 signature required') from exc
        if len(raw) != 64 or base64.b64encode(raw).decode('ascii') != value:
            raise ValueError('canonical Ed25519 signature required')
        return value


class ModelEvalCaseSignaturePayload(_ModelExecutionContract):
    """Signed identity binds the complete certificate envelope, not only its key."""
    schema_version: Literal['aos.model-eval-case-signature-payload/v1']
    certificate_hash: str = Field(pattern=SHA256)
    claim: ModelEvalCaseSigningInput


class ModelEvalSignedCaseEnvelope(_ModelExecutionContract):
    schema_version: Literal['aos.model-eval-signed-case-envelope/v1']
    payload: ModelEvalCaseSignaturePayload
    signature_base64: str

    @field_validator('signature_base64', mode='before')
    @classmethod
    def _canonical_signature(cls, value):
        return ModelEvalSignedCertificateEnvelope._canonical_signature(value)


def canonical_model_signed_case_bytes(manifest, payload, *, input_bytes: bytes,
                                      output_bytes: bytes, target_claim=None) -> bytes:
    """Exact signing payload only; raw bytes are not proof of transport origin."""
    item = ModelEvalCaseSignaturePayload.model_validate(payload)
    canonical_model_case_signing_bytes(manifest, item.claim, input_bytes=input_bytes,
        output_bytes=output_bytes, target_claim=target_claim)
    raw = json.dumps(item.model_dump(mode='json', by_alias=True), sort_keys=True,
                     ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return b'AOS-MODEL-EVAL-SIGNED-CASE-v1\n' + raw.encode('utf-8')


class ModelEvalCasePersistenceBinding(_ModelExecutionContract):
    """Expected immutable bytes/current epochs; no caller-declared trust flags."""
    case_hash: str = Field(pattern=SHA256)
    certificate_hash: str = Field(pattern=SHA256)
    root_hash: str = Field(pattern=SHA256)
    root_epoch: int = Field(strict=True, ge=1)
    certificate_epoch: int = Field(strict=True, ge=1)


class ModelEvalPersistedCaseInput(_ModelExecutionContract):
    """Whole-case read witnesses only; bytes confer no transport authority."""
    case_id: str = Field(min_length=1, max_length=200)
    target_binding: ModelEvalCasePersistenceBinding
    judge_binding: ModelEvalCasePersistenceBinding
    target_identity_epoch: int = Field(strict=True, ge=1)
    judge_identity_epoch: int = Field(strict=True, ge=1)
    target_input: bytes = Field(strict=True)
    target_output: bytes = Field(strict=True)
    judge_input: bytes = Field(strict=True)
    judge_output: bytes = Field(strict=True)

    @field_validator('case_id')
    @classmethod
    def _exact_case_id(cls, value):
        if value != value.strip():
            raise ValueError('exact whole-case identifier required')
        return value


class ModelEvalPersistedExecutorInput(_ModelExecutionContract):
    """Necessary pretransport certificate binding; never an execution grant."""
    case_id: str = Field(min_length=1, max_length=200)
    purpose: Literal['target', 'judge']
    certificate_hash: str = Field(pattern=SHA256)
    root_hash: str = Field(pattern=SHA256)
    root_epoch: int = Field(strict=True, ge=1)
    certificate_epoch: int = Field(strict=True, ge=1)
    identity_epoch: int = Field(strict=True, ge=1)

    @field_validator('case_id')
    @classmethod
    def _exact_case_id(cls,value):
        if value!=value.strip():
            raise ValueError('exact executor case required')
        return value


# Explicitly separate new-purpose descriptions. Old v1 signers/parsers retain
# their exact schema and ModelEvalBudgetReservation boundary.
class ModelJudgeCallExecutionLeg(_ModelExecutionContract):
    tenant: TenantContext
    purpose: Literal['judge']
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    source_ref: VersionedAssetRef
    physical_account_ref: VersionedAssetRef
    approval_ref: BudgetExactRef
    budget_hold_ref: BudgetExactRef
    budget_allocation_ref: BudgetExactRef
    allocation_upper_bound_minor: int = Field(strict=True, gt=0, le=100_000_000)
    joint_receipt_ref: BudgetExactRef
    intent_ref: BudgetExactRef
    identity_id: str = Field(min_length=1, max_length=200)
    identity_key_hash: str = Field(pattern=SHA256)
    attempt: Literal[1]

    @field_validator('identity_id')
    @classmethod
    def _exact_identity_id(cls, value):
        if value != value.strip():
            raise ValueError('exact execution identity required')
        return value

    @field_validator('attempt', mode='before')
    @classmethod
    def _exact_attempt(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError('one native integer attempt required')
        return value

    @model_validator(mode='after')
    def _reference_kinds(self):
        for ref, kind in (
            (self.model_ref, 'RegisteredModelRevision'),
            (self.provider_ref, 'ProviderInstanceRevision'),
            (self.price_ref, 'ModelPriceSnapshotRevision'),
            (self.quota_policy_ref, 'QuotaPolicyRevision'),
            (self.budget_policy_ref, 'BudgetPolicyRevision'),
            (self.source_ref, 'ProviderCapacitySourceRevision'),
            (self.physical_account_ref, 'ProviderPhysicalAccountCandidateRevision'),
        ):
            if ref.asset_type != kind:
                raise ValueError('exact execution leg asset kinds required')
        for ref, kind in (
            (self.approval_ref, 'ActionApprovalEvent'),
            (self.budget_hold_ref, 'ModelJudgeBudgetReservation'),
            (self.budget_allocation_ref, 'ModelEvalBudgetAllocation'),
            (self.joint_receipt_ref, 'ModelEvalJointAdmissionReceipt'),
            (self.intent_ref, 'ModelEvalExecutionIntent'),
        ):
            if ref.resource_type != kind:
                raise ValueError('exact execution leg fact kinds required')
        if self.identity_id.strip() != self.identity_id:
            raise ValueError('exact executor identity required')
        return self



class ModelTargetJudgeCaseExecutionPlan(ModelEvalCaseExecutionPlan):
    judge: ModelJudgeCallExecutionLeg


class ModelEvalTargetJudgeExecutionManifest(_ModelExecutionContract):
    """Whole original Judge request description, never trusted runtime evidence."""
    schema_version: Literal['aos.model-eval-target-judge-manifest/v2']
    tenant: TenantContext
    execution_id: str = Field(min_length=1, max_length=200)
    judge_request_id: str = Field(min_length=1, max_length=200)
    judge_request_hash: str = Field(pattern=SHA256)
    # Preserve the immutable raw request exactly; parsing the nested contracts
    # must not normalize timestamps or alter the original persisted hash.
    judge_request: dict
    target_parent_budget: ModelEvalParentBudgetLimit
    judge_parent_budget: ModelJudgeParentBudgetLimit
    cases: list[ModelTargetJudgeCaseExecutionPlan] = Field(min_length=1, max_length=10000)
    case_set_hash: str = Field(pattern=SHA256)
    execution_allowed: Literal[False] = False

    @field_validator('execution_id', 'judge_request_id')
    @classmethod
    def _exact_ids(cls, value):
        if not value.strip() or value != value.strip():
            raise ValueError('exact nonempty identifier required')
        return value

    @field_validator('execution_allowed', mode='before')
    @classmethod
    def _nonexecuting(cls, value):
        if type(value) is not bool or value is not False:
            raise ValueError('native nonexecuting manifest required')
        return value

    @model_validator(mode='after')
    def _whole_original_binding(self):
        from aos_api.aip_eval_contracts import AssetType, EvalCaseDefinition, JudgeRevisionRef
        from aos_api.aip_model_eval_judge_authorization import ModelJudgeRuleSourceRef, ModelJudgeRuleDefinition
        raw = self.judge_request
        expected = {'schemaVersion','tenant','purpose','executionAllowed','createdBy',
            'targetApplication','judgeGovernanceApplication','suiteRef','evalContractRef',
            'judgeRef','cases','caseSetHash','currency','upperBoundMinor','expiresAt','ruleFacts'}
        if (set(raw) != expected or raw['schemaVersion'] != 'aos.model-judge-call-request/v2'
                or raw['purpose'] != 'model-judge-call' or raw['executionAllowed'] is not False
                or raw['currency'] != 'CNY' or type(raw['upperBoundMinor']) is not int
                or not 0 < raw['upperBoundMinor'] <= 100_000_000
                or TenantContext.model_validate(raw['tenant']) != self.tenant
                or canonical_hash(raw) != self.judge_request_hash):
            raise ValueError('exact original new-purpose Judge request required')
        def exact_id(value):
            if type(value) is not str or not value.strip() or value != value.strip():
                raise ValueError('exact original identifiers required')
        exact_id(raw['createdBy'])
        def aware_time(value):
            if type(value) is not str:
                raise ValueError('exact aware original timestamp required')
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ValueError('exact aware original timestamp required')
            return parsed
        expiry = aware_time(raw['expiresAt'])
        applications = []
        for key in ('targetApplication','judgeGovernanceApplication'):
            app = raw[key]
            if type(app) is not dict or set(app) != {'requestId','requestHash','request',
                    'approvalEventId','proposalId','proposalHash'}:
                raise ValueError('complete original application provenance required')
            for field in ('requestId','approvalEventId','proposalId'):
                exact_id(app[field])
            if any(type(app[f]) is not str or len(app[f]) != 64
                    or any(c not in '0123456789abcdef' for c in app[f])
                    for f in ('requestHash','proposalHash')):
                raise ValueError('exact application hashes required')
            request = ModelEvalRequestCreate.model_validate(app['request'])
            if (canonical_hash(app['request']) != app['requestHash']
                    or request.tenant != self.tenant or request.expires_at < expiry):
                raise ValueError('original application hash tenant and interval required')
            applications.append((app, request))
        (target_app, target_request), (governance_app, judge_request) = applications
        if any(target_app[f] == governance_app[f] for f in ('requestId','approvalEventId','proposalId')):
            raise ValueError('independent original applications required')
        if self.judge_request_id in (target_app['requestId'],governance_app['requestId']):
            raise ValueError('independent new-purpose request required')
        if (VersionedAssetRef.model_validate(raw['suiteRef']) != target_request.suite_ref
                or VersionedAssetRef.model_validate(raw['evalContractRef']) != target_request.eval_contract_ref):
            raise ValueError('original Target suite and Eval contract required')
        judge = JudgeRevisionRef.model_validate(raw['judgeRef'])
        route = judge.model_route
        if route is None or route.asset_type is not AssetType.REGISTERED_MODEL or (route.asset_id,str(route.revision),route.content_hash) != (
                judge_request.source_ref.asset_id,
                str(judge_request.source_ref.revision),judge_request.source_ref.content_hash):
            raise ValueError('original Judge model route required')
        facts = raw['ruleFacts']
        if (type(facts) is not dict or set(facts) != {'source','rule','rootRevision',
                'validUntil','ruleHash','signatureFingerprint','releaseEvidenceRevision',
                'approvalAllowed','executionAllowed'} or facts['approvalAllowed'] is not False
                or facts['executionAllowed'] is not False):
            raise ValueError('complete nonexecuting Rule facts required')
        for field in ('rootRevision','signatureFingerprint','releaseEvidenceRevision'):
            digest = facts[field]
            if field == 'rootRevision' and digest is None:
                continue
            if (type(digest) is not str or not digest.startswith('sha256:')
                    or len(digest) != 71 or any(c not in '0123456789abcdef' for c in digest[7:])):
                raise ValueError('exact original Rule source digest required')
        source = ModelJudgeRuleSourceRef.model_validate(facts['source'])
        rule = ModelJudgeRuleDefinition.model_validate(facts['rule'])
        if (canonical_hash(facts['rule']) != facts['ruleHash']
                or (rule.judge_id,rule.revision,facts['ruleHash']) != (judge.judge_id,judge.revision,judge.content_hash)
                or rule.model_ref != judge_request.source_ref
                or rule.template_digest != source.template_artifact.digest
                or rule.implementation_digest != source.implementation_artifact.digest):
            raise ValueError('original Rule body hash and model required')
        if facts['validUntil'] is not None:
            valid_until = aware_time(facts['validUntil'])
            if valid_until < expiry:
                raise ValueError('Rule source interval must contain request')
        if type(raw['cases']) is not list or not raw['cases'] or len(raw['cases']) > 10000:
            raise ValueError('complete bounded original cases required')
        originals = [EvalCaseDefinition.model_validate(c) for c in raw['cases']]
        inputs = [dict(caseId=c.case_id,inputHash=c.input_artifact.content_hash,
            expectedHash=None if c.expected_artifact is None else c.expected_artifact.content_hash) for c in originals]
        planned = [dict(caseId=c.case_id,inputHash=c.input_hash,expectedHash=c.expected_hash) for c in self.cases]
        if (len({c.case_id for c in originals}) != len(originals)
                or canonical_hash(raw['cases']) != raw['caseSetHash']
                or planned != inputs or canonical_hash(planned) != self.case_set_hash):
            raise ValueError('complete ordered original case obligations required')
        target_parent, judge_parent = self.target_parent_budget, self.judge_parent_budget
        if (target_parent.request_id != target_app['requestId']
                or target_parent.request_hash != target_app['requestHash']
                or target_parent.approval_ref.resource_id != target_app['approvalEventId']
                or target_parent.upper_bound_minor > target_request.upper_bound_minor
                or judge_parent.tenant != self.tenant
                or judge_parent.request_id != self.judge_request_id
                or judge_parent.request_hash != self.judge_request_hash
                or judge_parent.upper_bound_minor != raw['upperBoundMinor']
                or judge_parent.approval_ref.resource_id in (target_app['approvalEventId'],governance_app['approvalEventId'])
                or target_parent.parent_hold_ref.resource_id == judge_parent.parent_hold_ref.resource_id):
            raise ValueError('independent exact Target and new Judge parent required')
        intents, allocations = set(), set()
        totals = {'target':0, 'judge':0}
        for case in self.cases:
            for leg, request, parent in ((case.target,target_request,target_parent),
                                        (case.judge,judge_request,judge_parent)):
                if (leg.tenant != self.tenant or leg.model_ref != request.source_ref
                        or any(getattr(leg,f) != getattr(request,f) for f in
                            ('provider_ref','price_ref','quota_policy_ref','budget_policy_ref'))
                        or leg.budget_hold_ref != parent.parent_hold_ref
                        or leg.approval_ref != parent.approval_ref
                        or leg.price_ref != parent.price_ref or leg.budget_policy_ref != parent.budget_policy_ref):
                    raise ValueError('exact per-purpose original governance and parent required')
                intent = leg.intent_ref.resource_id
                shared = self.schema_version == 'aos.model-eval-target-judge-shared-risk-manifest/v3'
                allocation = None if shared else leg.budget_allocation_ref.resource_id
                if intent in intents or (not shared and allocation in allocations):
                    raise ValueError('unique per-call Intent and allocation required')
                intents.add(intent)
                if not shared:
                    allocations.add(allocation)
                    totals[leg.purpose] += leg.allocation_upper_bound_minor
                    if totals[leg.purpose] > parent.upper_bound_minor:
                        raise ValueError('case allocations exceed independent parent upper bound')
        return self


class ModelSharedParentRiskLeg(_ModelExecutionContract):
    """A complete plan obligation referencing a parent, never per-leg money."""
    tenant: TenantContext
    purpose: Literal['target', 'judge']
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    source_ref: VersionedAssetRef
    physical_account_ref: VersionedAssetRef
    approval_ref: BudgetExactRef
    budget_hold_ref: BudgetExactRef
    joint_receipt_ref: BudgetExactRef
    intent_ref: BudgetExactRef
    identity_id: str = Field(min_length=1, max_length=200)
    identity_key_hash: str = Field(pattern=SHA256)
    attempt: Literal[1]

    @field_validator('identity_id')
    @classmethod
    def _identity(cls, value):
        return ModelEvalExecutionLeg._exact_identity_id(value)

    @field_validator('attempt', mode='before')
    @classmethod
    def _attempt(cls, value):
        return ModelEvalExecutionLeg._exact_attempt(value)

    @model_validator(mode='after')
    def _reference_kinds(self):
        for field, kind in (
            ('model_ref', 'RegisteredModelRevision'), ('provider_ref', 'ProviderInstanceRevision'),
            ('price_ref', 'ModelPriceSnapshotRevision'), ('quota_policy_ref', 'QuotaPolicyRevision'),
            ('budget_policy_ref', 'BudgetPolicyRevision'), ('source_ref', 'ProviderCapacitySourceRevision'),
            ('physical_account_ref', 'ProviderPhysicalAccountCandidateRevision')):
            if getattr(self, field).asset_type != kind:
                raise ValueError('exact shared-parent leg asset kinds required')
        for field, kind in (
            ('approval_ref', 'ActionApprovalEvent'),
            ('budget_hold_ref', 'ModelEvalBudgetReservation' if self.purpose == 'target' else 'ModelJudgeBudgetReservation'),
            ('joint_receipt_ref', 'ModelEvalJointAdmissionReceipt'), ('intent_ref', 'ModelEvalExecutionIntent')):
            if getattr(self, field).resource_type != kind:
                raise ValueError('exact shared-parent leg fact kinds required')
        return self


class ModelSharedParentRiskCase(_ModelExecutionContract):
    case_id: str = Field(min_length=1, max_length=200)
    input_hash: str = Field(pattern=SHA256)
    expected_hash: str | None = Field(default=None, pattern=SHA256)
    target: ModelSharedParentRiskLeg
    judge: ModelSharedParentRiskLeg

    @model_validator(mode='after')
    def _purposes(self):
        if self.case_id != self.case_id.strip() or self.target.purpose != 'target' or self.judge.purpose != 'judge':
            raise ValueError('exact original case and independent leg purposes required')
        return self


class ModelEvalTargetJudgeSharedRiskManifest(ModelEvalTargetJudgeExecutionManifest):
    """Complete shared-parent risk description; no signed or committed grant.

    The common whole-request validator reads the same original governance and
    ordered cases as v2. Only v3 omits unproven per-leg allocation declarations.
    Old parsers and signing domains reject this new version.
    """
    schema_version: Literal['aos.model-eval-target-judge-shared-risk-manifest/v3']
    cases: list[ModelSharedParentRiskCase] = Field(min_length=1, max_length=10000)


class ModelOriginalTargetCaseSigningInput(ModelEvalCaseSigningInput):
    """Original v2 Target signing description; never proof of transport or commit."""
    schema_version: Literal['aos.model-eval-original-target-case-signing-input/v2']
    purpose: Literal['target']
    # Dataset bytes and actual transport bytes have distinct hashes.
    case_input_hash: str = Field(pattern=SHA256, strict=True)


def canonical_original_target_case_signing_bytes(manifest, claim, *,
        input_bytes: bytes, output_bytes: bytes) -> bytes:
    """Bind the complete original v2 plan to raw wire/output hash witnesses.

    Original artifacts, rendered wire provenance, certificates, trusted issuer,
    current native admission and committed producer remain independent checks.
    This pure function never authenticates an actual Provider result.
    """
    plan = ModelEvalTargetJudgeExecutionManifest.model_validate(manifest)
    item = ModelOriginalTargetCaseSigningInput.model_validate(claim)
    original = plan.judge_request['targetApplication']
    request = ModelEvalRequestCreate.model_validate(original['request'])
    case = next((c for c in plan.cases if c.case_id == item.case_id), None)
    if (case is None or item.tenant != plan.tenant or item.execution_id != plan.execution_id
            or item.manifest_hash != canonical_hash(plan.model_dump(mode='json', by_alias=True))
            or item.request_hash != original['requestHash']
            or item.candidate_ref != request.target_ref or item.leg != case.target
            or item.case_input_hash != case.input_hash
            or item.occurred_at >= datetime.fromisoformat(plan.judge_request['expiresAt'])):
        raise ValueError('original v2 Target claim must bind complete case and original application')
    if (type(input_bytes) is not bytes or type(output_bytes) is not bytes
            or len(input_bytes) > 1048576 or len(output_bytes) > 1048576
            or hashlib.sha256(input_bytes).hexdigest() != item.input_hash
            or hashlib.sha256(output_bytes).hexdigest() != item.output_hash):
        raise ValueError('exact bounded original v2 Target wire/output bytes required')
    payload = json.dumps(item.model_dump(mode='json', by_alias=True), ensure_ascii=False,
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return b'AOS-MODEL-EVAL-ORIGINAL-TARGET-CASE-SIGNING-INPUT-v2\n' + payload


class ModelOriginalTargetCertificateSigningInput(ModelEvalExecutorCertificateSigningInput):
    """Unsigned original v2 Target certificate; not a registered issuer grant."""
    schema_version: Literal['aos.model-eval-original-target-certificate-signing-input/v2']
    purpose: Literal['target']


class ModelOriginalTargetSignedCertificateEnvelope(ModelEvalSignedCertificateEnvelope):
    schema_version: Literal['aos.model-eval-original-target-signed-certificate-envelope/v2']
    certificate: ModelOriginalTargetCertificateSigningInput


class ModelOriginalTargetCaseSignaturePayload(ModelEvalCaseSignaturePayload):
    schema_version: Literal['aos.model-eval-original-target-case-signature-payload/v2']
    claim: ModelOriginalTargetCaseSigningInput


class ModelOriginalTargetSignedCaseEnvelope(ModelEvalSignedCaseEnvelope):
    schema_version: Literal['aos.model-eval-original-target-signed-case-envelope/v2']
    payload: ModelOriginalTargetCaseSignaturePayload


def canonical_original_target_certificate_signing_bytes(manifest, certificate) -> bytes:
    """Bind original v2 Target certificate descriptions in their own domain."""
    plan = ModelEvalTargetJudgeExecutionManifest.model_validate(manifest)
    claim = ModelOriginalTargetCertificateSigningInput.model_validate(certificate)
    original = plan.judge_request['targetApplication']
    request = ModelEvalRequestCreate.model_validate(original['request'])
    case = next((c for c in plan.cases if c.case_id == claim.case_id), None)
    if (case is None or claim.tenant != plan.tenant or claim.execution_id != plan.execution_id
            or claim.manifest_hash != canonical_hash(plan.model_dump(mode='json', by_alias=True))
            or claim.request_hash != original['requestHash'] or claim.candidate_ref != request.target_ref
            or claim.leg != case.target
            or claim.valid_until > datetime.fromisoformat(plan.judge_request['expiresAt'])):
        raise ValueError('original v2 Target certificate must bind complete original plan')
    raw = json.dumps(claim.model_dump(mode='json', by_alias=True), sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return b'AOS-MODEL-EVAL-ORIGINAL-TARGET-CERTIFICATE-SIGNING-INPUT-v2\n' + raw


def canonical_original_target_signed_case_bytes(manifest, payload, *,
        input_bytes: bytes, output_bytes: bytes) -> bytes:
    """Bind raw witnesses to the complete certificate envelope hash, no trust."""
    item = ModelOriginalTargetCaseSignaturePayload.model_validate(payload)
    canonical_original_target_case_signing_bytes(manifest, item.claim,
        input_bytes=input_bytes, output_bytes=output_bytes)
    raw = json.dumps(item.model_dump(mode='json', by_alias=True), sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return b'AOS-MODEL-EVAL-ORIGINAL-TARGET-SIGNED-CASE-v2\n' + raw


def _original_target_signature_require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_original_target_certificate_signature(manifest, certificate, *,
        issuer_input, signature_base64: str, checked_at: datetime,
        revoked_identity_ids: frozenset[str]) -> None:
    """Presented original v2 certificate crypto only; no trusted root or grant."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    from aos_api.aip_model_eval_execution_contracts import (
        ModelOriginalTargetCertificateSigningInput,
        canonical_original_target_certificate_signing_bytes)
    claim = ModelOriginalTargetCertificateSigningInput.model_validate(certificate)
    root = ModelEvalIssuerVerificationInput.model_validate(issuer_input)
    raw = canonical_original_target_certificate_signing_bytes(manifest, claim)
    _original_target_signature_require(type(checked_at) is datetime and checked_at.utcoffset() is not None,
             'aware original Target check time required')
    _original_target_signature_require(type(revoked_identity_ids) is frozenset
             and all(type(v) is str and v and v == v.strip() for v in revoked_identity_ids),
             'exact immutable original Target identity revocations required')
    _original_target_signature_require((root.tenant, root.issuer_id, root.issuer_key_id) ==
             (claim.tenant, claim.issuer_id, claim.issuer_key_id),
             'exact original Target issuer tenant and key required')
    _original_target_signature_require(root.valid_from <= claim.valid_from < claim.valid_until <= root.valid_until
             and claim.valid_from <= checked_at < claim.valid_until
             and root.valid_from <= checked_at < root.valid_until,
             'current contained original Target certificate interval required')
    _original_target_signature_require((root.revoked_at is None or checked_at < root.revoked_at)
             and claim.leg.identity_id not in revoked_identity_ids,
             'original Target issuer or executor revoked')
    from aos_api.aip_model_eval_execution_contracts import ModelEvalSignedCertificateEnvelope
    ModelEvalSignedCertificateEnvelope._canonical_signature(signature_base64)
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(root.public_key_base64, validate=True)).verify(
            base64.b64decode(signature_base64, validate=True), raw)
    except (InvalidSignature, binascii.Error, ValueError) as exc:
        raise ValueError('invalid original Target certificate signature') from exc


def validate_original_target_case_signature(manifest, envelope, *,
        certificate_envelope, issuer_input, checked_at: datetime,
        revoked_identity_ids: frozenset[str], input_bytes: bytes, output_bytes: bytes) -> None:
    """Exact v2 original Target crypto; not proof of transport or committed origin."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.exceptions import InvalidSignature
    from aos_api.aip_model_eval_execution_contracts import (
        ModelOriginalTargetSignedCaseEnvelope, ModelOriginalTargetSignedCertificateEnvelope,
        canonical_original_target_signed_case_bytes)
    signed = ModelOriginalTargetSignedCaseEnvelope.model_validate(envelope)
    certificate = ModelOriginalTargetSignedCertificateEnvelope.model_validate(certificate_envelope)
    cert, claim = certificate.certificate, signed.payload.claim
    _original_target_signature_require(signed.payload.certificate_hash == canonical_hash(
        certificate.model_dump(mode='json', by_alias=True)), 'complete original Target certificate envelope required')
    validate_original_target_certificate_signature(manifest, cert, issuer_input=issuer_input,
        signature_base64=certificate.signature_base64, checked_at=checked_at,
        revoked_identity_ids=revoked_identity_ids)
    _original_target_signature_require((claim.tenant, claim.execution_id, claim.manifest_hash, claim.request_hash,
              claim.case_id, claim.purpose, claim.candidate_ref, claim.leg) ==
             (cert.tenant, cert.execution_id, cert.manifest_hash, cert.request_hash,
              cert.case_id, cert.purpose, cert.candidate_ref, cert.leg),
             'case must bind complete original Target executor certificate')
    _original_target_signature_require(cert.valid_from <= claim.occurred_at < cert.valid_until
             and claim.occurred_at <= checked_at, 'original Target case time outside certificate')
    raw = canonical_original_target_signed_case_bytes(manifest, signed.payload,
        input_bytes=input_bytes, output_bytes=output_bytes)
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(cert.public_key_base64, validate=True)).verify(
            base64.b64decode(signed.signature_base64, validate=True), raw)
    except (InvalidSignature, binascii.Error, ValueError) as exc:
        raise ValueError('invalid original Target executor case signature') from exc


class ModelSharedParentRiskCertificateSigningInput(ModelEvalExecutorCertificateSigningInput):
    """Unsigned v3 identity description; not an issuer or joint admission grant."""
    schema_version: Literal['aos.model-eval-shared-parent-certificate-signing-input/v3']
    leg: ModelSharedParentRiskLeg
    description_hash: str = Field(strict=True, pattern=r'^sha256:[0-9a-f]{64}$')
    original_risk_hash: str = Field(strict=True, pattern=r'^sha256:[0-9a-f]{64}$')
    caller_xid: str = Field(strict=True, pattern=r'^[1-9][0-9]*$')
    caller_pid: int = Field(strict=True, gt=0)


class ModelSharedParentRiskSignedCertificateEnvelope(ModelEvalSignedCertificateEnvelope):
    schema_version: Literal['aos.model-eval-shared-parent-signed-certificate-envelope/v3']
    certificate: ModelSharedParentRiskCertificateSigningInput


def canonical_shared_parent_certificate_signing_bytes(description, certificate) -> bytes:
    """Bind full prepared description and original origin; never assert DB or trust."""
    from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation
    prepared = SharedParentRiskDescriptionPreparation.model_validate(description)
    plan = prepared.immutable.manifest
    claim = ModelSharedParentRiskCertificateSigningInput.model_validate(certificate)
    case = next((c for c in plan.cases if c.case_id == claim.case_id), None)
    app_key = 'targetApplication' if claim.purpose == 'target' else 'judgeGovernanceApplication'
    app = plan.judge_request[app_key]
    candidate = ModelEvalRequestCreate.model_validate(app['request']).target_ref
    request_hash = app['requestHash'] if claim.purpose == 'target' else plan.judge_request_hash
    if (case is None or claim.tenant != plan.tenant or claim.execution_id != plan.execution_id
            or claim.manifest_hash != prepared.immutable.manifest_hash
            or claim.description_hash != prepared.content_hash
            or claim.original_risk_hash != prepared.immutable.original_risk_hash
            or (claim.caller_xid, claim.caller_pid) != (
                prepared.immutable.caller_xid, prepared.immutable.caller_pid)
            or claim.request_hash != request_hash or claim.candidate_ref != candidate
            or claim.leg != getattr(case, claim.purpose)
            or claim.valid_until > datetime.fromisoformat(plan.judge_request['expiresAt'])):
        raise ValueError('complete original v3 description/case/request/origin binding required')
    raw = json.dumps(claim.model_dump(mode='json', by_alias=True), sort_keys=True,
        ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return b'AOS-MODEL-EVAL-SHARED-PARENT-CERTIFICATE-SIGNING-INPUT-v3\n' + raw


def validate_shared_parent_certificate_signature(description, envelope, *, issuer_input,
        checked_at: datetime, revoked_identity_ids: frozenset[str]) -> None:
    """Necessary crypto/time only. Presented root/withdrawals confer no authority.

    Stored current issuer/certificate/identity heads, root provenance, original
    approval, Source and final joint admission remain independent requirements.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    signed = ModelSharedParentRiskSignedCertificateEnvelope.model_validate(envelope)
    claim = signed.certificate
    root = ModelEvalIssuerVerificationInput.model_validate(issuer_input)
    raw = canonical_shared_parent_certificate_signing_bytes(description, claim)
    if (type(checked_at) is not datetime or checked_at.utcoffset() is None
            or type(revoked_identity_ids) is not frozenset
            or any(type(v) is not str or not v or v != v.strip() for v in revoked_identity_ids)
            or root.tenant != claim.tenant or root.issuer_id != claim.issuer_id
            or root.issuer_key_id != claim.issuer_key_id
            or not root.valid_from <= claim.valid_from < claim.valid_until <= root.valid_until
            or not claim.valid_from <= checked_at < claim.valid_until
            or not root.valid_from <= checked_at < root.valid_until
            or (root.revoked_at is not None and checked_at >= root.revoked_at)
            or claim.leg.identity_id in revoked_identity_ids):
        raise ValueError('current contained v3 certificate interval and presented issuer required')
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(root.public_key_base64, validate=True)).verify(
            base64.b64decode(signed.signature_base64, validate=True), raw)
    except (InvalidSignature, ValueError, binascii.Error) as exc:
        raise ValueError('invalid v3 shared-parent certificate signature') from exc
