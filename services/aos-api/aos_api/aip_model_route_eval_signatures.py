"""Presented governed-eval certificate checks, never trusted execution proof.

No issuer is registered, no key is loaded and no connection is opened here.
Original Model v2/v3 native proofs and Owner checks remain mandatory; this
new domain cannot replace them or authorize Route/Model execution or release.
Presented result signatures do not establish transport, committed origin or cost.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime
import hashlib
import json
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import Field, field_validator, model_validator

from aos_api.aip_budget_reservation_contracts import BudgetExactRef
from aos_api.aip_contracts import TenantContext, AipContractModel
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_model_route_eval_manifest import (
    CONTEXT_DOMAIN, MANIFEST_DOMAIN, SHA, _RouteContract, _alias_input,
    _aware, _canonical, compile_eval_execution_manifest, route_eval_call_key,
)

CERTIFICATE_DOMAIN = b'AOS-GOVERNED-EVAL-CERTIFICATE-SIGNING-v1\n'
CASE_DOMAIN = b'AOS-GOVERNED-EVAL-CASE-SIGNING-v1\n'
WIRE_LIMIT = 1048576


def _key_bytes(value):
    if type(value) is not str:
        raise ValueError('canonical presented Ed25519 public key required')
    try:
        raw=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise ValueError('canonical presented Ed25519 public key required') from exc
    if len(raw)!=32 or base64.b64encode(raw).decode('ascii')!=value:
        raise ValueError('canonical presented Ed25519 public key required')
    return raw


def _signature_bytes(value):
    if type(value) is not str or len(value)!=88:
        raise ValueError('canonical Ed25519 certificate signature required')
    try:
        raw=base64.b64decode(value,validate=True)
    except (ValueError,binascii.Error) as exc:
        raise ValueError('canonical Ed25519 certificate signature required') from exc
    if len(raw)!=64 or base64.b64encode(raw).decode('ascii')!=value:
        raise ValueError('canonical Ed25519 certificate signature required')
    return raw


class _SignatureContract(_RouteContract):
    execution_allowed: Literal[False] = False

    @field_validator('execution_allowed',mode='before')
    @classmethod
    def _nonexecuting(cls,value):
        if type(value) is not bool or value is not False:
            raise ValueError('native false descriptive declaration required')
        return value


class GovernedEvalIssuerInput(_SignatureContract):
    schema_version: Literal['aos.governed-eval-issuer-input/v1'] = 'aos.governed-eval-issuer-input/v1'
    purpose: Literal['governed-model-route-eval-execution'] = 'governed-model-route-eval-execution'
    tenant: TenantContext
    issuer_id: str = Field(strict=True,min_length=1,max_length=200)
    issuer_key_id: str = Field(strict=True,min_length=1,max_length=200)
    public_key_base64: str = Field(strict=True,min_length=1,max_length=100)
    valid_from: datetime
    valid_until: datetime
    revoked_at: datetime | None = None

    @field_validator('issuer_id','issuer_key_id')
    @classmethod
    def _ids(cls,value):
        if value!=value.strip():raise ValueError('exact issuer identity required')
        return value

    @field_validator('valid_from','valid_until','revoked_at',mode='before')
    @classmethod
    def _times(cls,value):
        return None if value is None else _aware(value)

    @model_validator(mode='after')
    def _key_interval(self):
        _key_bytes(self.public_key_base64)
        if self.valid_from>=self.valid_until:raise ValueError('nonempty presented root interval required')
        return self


class GovernedEvalCertificate(_SignatureContract):
    schema_version: Literal['aos.governed-eval-certificate/v1'] = 'aos.governed-eval-certificate/v1'
    tenant: TenantContext
    subject_kind: Literal['RegisteredModelRevision','ModelRouteRevision']
    execution_id: str = Field(strict=True,min_length=1,max_length=200)
    manifest_hash: str = Field(strict=True,pattern=SHA)
    context_binding_hash: str = Field(strict=True,pattern=SHA)
    case_id: str = Field(strict=True,min_length=1,max_length=200)
    purpose: Literal['target','judge']
    call_binding_hash: str = Field(strict=True,pattern=SHA)
    identity_id: str = Field(strict=True,min_length=1,max_length=200)
    identity_key_hash: str = Field(strict=True,pattern=SHA)
    public_key_base64: str = Field(strict=True,min_length=1,max_length=100)
    issuer_id: str = Field(strict=True,min_length=1,max_length=200)
    issuer_key_id: str = Field(strict=True,min_length=1,max_length=200)
    intent_ref: BudgetExactRef
    joint_admission_ref: BudgetExactRef
    valid_from: datetime
    valid_until: datetime

    @field_validator('execution_id','case_id','identity_id','issuer_id','issuer_key_id')
    @classmethod
    def _ids(cls,value):
        if value!=value.strip():raise ValueError('exact certificate identity required')
        return value

    @field_validator('valid_from','valid_until',mode='before')
    @classmethod
    def _times(cls,value):return _aware(value)

    @model_validator(mode='after')
    def _key_interval(self):
        if hashlib.sha256(_key_bytes(self.public_key_base64)).hexdigest()!=self.identity_key_hash:
            raise ValueError('certificate key must match complete call identity')
        if self.valid_from>=self.valid_until:raise ValueError('nonempty certificate interval required')
        return self


def _manifest(raw):
    if type(raw) is not bytes or not raw.startswith(MANIFEST_DOMAIN):
        raise ValueError('complete governed Manifest bytes required')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise ValueError('duplicate governed Manifest JSON key')
            out[k]=v
        return out
    def nonfinite(value):raise ValueError('nonfinite governed Manifest JSON')
    body=json.loads(raw[len(MANIFEST_DOMAIN):],object_pairs_hook=unique,parse_constant=nonfinite)
    common={'schemaVersion','tenant','executionId','compiledAt','context','contextBindingHash','executionAllowed'}
    if type(body) is not dict or MANIFEST_DOMAIN+_canonical(body)!=raw:
        raise ValueError('exact canonical governed Manifest required')
    fields=set(body)-common
    if not common<=set(body) or fields not in ({'modelPlan'},{'routeApplication','routeBudgetBindings'}):
        raise ValueError('complete original governed Manifest field set required')
    at=_aware(body['compiledAt'])
    kwargs=({'model_plan':body['modelPlan']} if fields=={'modelPlan'} else
            {'route_application':body['routeApplication'],'route_budget_bindings':body['routeBudgetBindings']})
    rebuilt=compile_eval_execution_manifest(CONTEXT_DOMAIN+_canonical(body['context']),execution_id=body['executionId'],checked_at=at,**kwargs)
    if rebuilt!=raw:raise ValueError('complete original governed Manifest revalidation drifted')
    return body


def _call(body,*,case_id,purpose):
    if type(case_id) is not str or not case_id or case_id!=case_id.strip() or purpose not in ('target','judge'):
        raise ValueError('exact governed case and purpose required')
    if 'modelPlan' in body:
        plan=body['modelPlan'];case=next((c for c in plan['cases'] if c['caseId']==case_id),None)
        if case is None:raise ValueError('case outside original complete Model plan')
        leg=case[purpose];parent=plan['targetParentBudget' if purpose=='target' else 'judgeParentBudget']
        binding={'case':case,'purpose':purpose,'originalParent':parent}
        return binding,leg,_aware(plan['judgeRequest']['expiresAt'])
    app=body['routeApplication'];leg=next((c for c in app['calls'] if (c['caseId'],c['purpose'])==(case_id,purpose)),None)
    if leg is None:raise ValueError('case outside original complete Route application')
    key=route_eval_call_key(body['executionId'],body['contextBindingHash'],case_id,purpose)
    budget=next(b for b in body['routeBudgetBindings'] if b['callKey']==key)
    return {'recipe':leg,'originalBudgetBinding':budget},leg,_aware(app['expiresAt'])


def _binding_hash(raw,binding):
    return hashlib.sha256(b'AOS-GOVERNED-EVAL-CALL-BINDING-v1\n'+_canonical({
        'manifestHash':hashlib.sha256(raw).hexdigest(),'call':binding})).hexdigest()


def governed_call_binding_hash(manifest_bytes: bytes,*,case_id: str,purpose: str) -> str:
    """Complete descriptive call hash, never an Intent or joint admission."""
    body=_manifest(manifest_bytes);binding,_,_=_call(body,case_id=case_id,purpose=purpose)
    return _binding_hash(manifest_bytes,binding)


def canonical_governed_certificate_bytes(manifest_bytes: bytes,certificate) -> bytes:
    """Prepare a necessary signing input without loading a key or trusting refs."""
    body=_manifest(manifest_bytes);cert=GovernedEvalCertificate.model_validate(_alias_input(certificate))
    binding,leg,expiry=_call(body,case_id=cert.case_id,purpose=cert.purpose)
    kind=body['context']['subject']['candidate']['sourceRef']['assetType']
    if (cert.tenant.model_dump(mode='json',by_alias=True)!=body['tenant'] or cert.subject_kind!=kind
        or cert.execution_id!=body['executionId'] or cert.manifest_hash!=hashlib.sha256(manifest_bytes).hexdigest()
        or cert.context_binding_hash!=body['contextBindingHash'] or cert.call_binding_hash!=_binding_hash(manifest_bytes,binding)
        or (cert.identity_id,cert.identity_key_hash)!=(leg['identityId'],leg['identityKeyHash'])
        or not _aware(body['compiledAt'])<=cert.valid_from<cert.valid_until<=expiry):
        raise ValueError('certificate must bind exact complete governed call and interval')
    if 'modelPlan' in body:
        if (cert.intent_ref.model_dump(mode='json',by_alias=True)!=leg['intentRef']
            or cert.joint_admission_ref.model_dump(mode='json',by_alias=True)!=leg['jointReceiptRef']):
            raise ValueError('original Model Intent and joint references required')
    elif (cert.intent_ref.resource_type!='GovernedEvalExecutionIntent'
          or cert.joint_admission_ref.resource_type!='GovernedEvalJointAdmissionReceipt'):
        raise ValueError('dedicated Route Intent and joint reference kinds required')
    return CERTIFICATE_DOMAIN+_canonical(cert.model_dump(mode='json',by_alias=True))


def validate_governed_certificate_signature(manifest_bytes: bytes,certificate,*,issuer_input,
        signature_base64: str,checked_at: datetime,revoked_identity_ids: frozenset[str]) -> None:
    """Verify presented crypto/time only; caller must separately establish trust.

    No native issuer provenance/epoch, Source, approval, original Model proof,
    transport/Usage or committed execution is established by a None return.
    """
    cert=GovernedEvalCertificate.model_validate(_alias_input(certificate))
    root=GovernedEvalIssuerInput.model_validate(_alias_input(issuer_input))
    raw=canonical_governed_certificate_bytes(manifest_bytes,cert);at=_aware(checked_at)
    if (type(revoked_identity_ids) is not frozenset or any(type(v) is not str or not v or v!=v.strip() for v in revoked_identity_ids)
        or (root.tenant,root.issuer_id,root.issuer_key_id)!=(cert.tenant,cert.issuer_id,cert.issuer_key_id)
        or not root.valid_from<=cert.valid_from<cert.valid_until<=root.valid_until
        or not cert.valid_from<=at<cert.valid_until or not root.valid_from<=at<root.valid_until
        or (root.revoked_at is not None and at>=root.revoked_at) or cert.identity_id in revoked_identity_ids):
        raise ValueError('exact unrevoked presented issuer, identity and current interval required')
    try:
        Ed25519PublicKey.from_public_bytes(_key_bytes(root.public_key_base64)).verify(_signature_bytes(signature_base64),raw)
    except (InvalidSignature,ValueError,binascii.Error) as exc:
        raise ValueError('invalid presented governed certificate signature') from exc


class GovernedEvalSignedCertificate(_SignatureContract):
    schema_version: Literal['aos.governed-eval-signed-certificate/v1'] = 'aos.governed-eval-signed-certificate/v1'
    certificate: GovernedEvalCertificate
    signature_base64: str

    @field_validator('signature_base64',mode='before')
    @classmethod
    def _signature(cls,value):
        _signature_bytes(value)
        return value


class GovernedEvalCaseClaim(_SignatureContract):
    schema_version: Literal['aos.governed-eval-case-claim/v1'] = 'aos.governed-eval-case-claim/v1'
    tenant: TenantContext
    subject_kind: Literal['RegisteredModelRevision','ModelRouteRevision']
    execution_id: str = Field(strict=True,min_length=1,max_length=200)
    manifest_hash: str = Field(strict=True,pattern=SHA)
    context_binding_hash: str = Field(strict=True,pattern=SHA)
    call_binding_hash: str = Field(strict=True,pattern=SHA)
    certificate_hash: str = Field(strict=True,pattern=SHA)
    case_id: str = Field(strict=True,min_length=1,max_length=200)
    purpose: Literal['target','judge']
    case_input_hash: str = Field(strict=True,pattern=SHA)
    expected_hash: str | None = Field(default=None,strict=True,pattern=SHA)
    wire_input_hash: str = Field(strict=True,pattern=SHA)
    output_hash: str = Field(strict=True,pattern=SHA)
    occurred_at: datetime
    target_envelope_hash: str | None = Field(default=None,strict=True,pattern=SHA)
    target_output_hash: str | None = Field(default=None,strict=True,pattern=SHA)
    legacy_model_proof_hash: str | None = Field(default=None,strict=True,pattern=SHA)
    passed: bool | None = Field(default=None,strict=True)
    detail_code: str | None = Field(default=None,strict=True,min_length=1,max_length=120)

    @field_validator('execution_id','case_id','detail_code')
    @classmethod
    def _ids(cls,value):
        if value is not None and value!=value.strip():raise ValueError('exact case identifier required')
        return value

    @field_validator('occurred_at',mode='before')
    @classmethod
    def _time(cls,value):return _aware(value)

    @model_validator(mode='after')
    def _purposes(self):
        fields=(self.target_envelope_hash,self.target_output_hash,self.passed,self.detail_code)
        if self.purpose=='target' and any(v is not None for v in fields):
            raise ValueError('Target cannot assert Judge dependencies or verdict')
        if self.purpose=='judge' and any(v is None for v in fields):
            raise ValueError('Judge must bind complete Target and verdict description')
        return self


class GovernedEvalSignedCase(_SignatureContract):
    schema_version: Literal['aos.governed-eval-signed-case/v1'] = 'aos.governed-eval-signed-case/v1'
    claim: GovernedEvalCaseClaim
    signature_base64: str

    @field_validator('signature_base64',mode='before')
    @classmethod
    def _signature(cls,value):
        _signature_bytes(value)
        return value


class ModelLegacyProofWitness(AipContractModel):
    """Complete presented old-domain evidence, never native provenance or trust."""
    schema_version: Literal['aos.governed-eval-model-legacy-witness/v1'] = 'aos.governed-eval-model-legacy-witness/v1'
    target_certificate: dict
    target_case: dict
    target_issuer: dict
    shared_risk_description: dict | None = None
    judge_certificate: dict | None = None
    judge_case: dict | None = None
    judge_issuer: dict | None = None
    execution_allowed: Literal[False] = False

    @field_validator('execution_allowed',mode='before')
    @classmethod
    def _nonexecuting(cls,value):return _SignatureContract._nonexecuting(value)


def _json_hash(model):return canonical_hash(model.model_dump(mode='json',by_alias=True))


def _bytes_hash(raw):
    if type(raw) is not bytes or len(raw)>WIRE_LIMIT:
        raise ValueError('bounded exact case byte witness required')
    return hashlib.sha256(raw).hexdigest()


def _case_artifacts(body,case_id,artifact_input_bytes,expected_output):
    case=next((c for c in body['context']['suite']['cases'] if c['caseId']==case_id),None)
    if case is None or _bytes_hash(artifact_input_bytes)!=case['inputArtifact']['contentHash']:
        raise ValueError('original case Artifact bytes required')
    expected=None if case['expectedArtifact'] is None else case['expectedArtifact']['contentHash']
    if (expected is None and expected_output is not None) or (expected is not None and _bytes_hash(expected_output)!=expected):
        raise ValueError('original exact expected Artifact bytes required')
    return case['inputArtifact']['contentHash'],expected


def _original(cls,value):
    """Reject normalized copied old evidence while retaining its original domain."""
    item=cls.model_validate(value)
    if _canonical(value)!=_canonical(item.model_dump(mode='json',by_alias=True)):
        raise ValueError('complete canonical original Model evidence required')
    return item


def _target_legacy(witness):
    if witness is None:return None
    w=ModelLegacyProofWitness.model_validate(_alias_input(witness))
    return w.model_copy(update={'judge_certificate':None,'judge_case':None,'judge_issuer':None})


def _legacy_case(body,claim,witness,*,checked_at,revoked_identity_ids,input_bytes,output_bytes,
                 target_input_bytes,target_output_bytes,expected_output):
    """Necessary original crypto/codec only; native v2 builder is an Owner gate."""
    from aos_api import aip_model_eval_execution_contracts as old
    if witness is None:raise ValueError('complete original Model proof witness required')
    w=ModelLegacyProofWitness.model_validate(_alias_input(witness));plan=body['modelPlan']
    if claim.legacy_model_proof_hash!=_json_hash(w):raise ValueError('complete legacy Model witness hash required')
    target_only=claim.purpose=='target'
    if target_only and any(v is not None for v in (w.judge_certificate,w.judge_case,w.judge_issuer)):
        raise ValueError('Model Target cannot borrow Judge proof')
    ti=input_bytes if target_only else target_input_bytes;to=output_bytes if target_only else target_output_bytes
    root=_original(old.ModelEvalIssuerVerificationInput,w.target_issuer)
    is_v2=plan['schemaVersion']=='aos.model-eval-target-judge-manifest/v2'
    if is_v2:
        if w.shared_risk_description is not None or any(v is not None for v in (w.judge_certificate,w.judge_case,w.judge_issuer)):
            raise ValueError('v2 proof cannot borrow v3 description or a fabricated legacy Judge')
        target=_original(old.ModelOriginalTargetSignedCaseEnvelope,w.target_case)
        cert=_original(old.ModelOriginalTargetSignedCertificateEnvelope,w.target_certificate)
        old.validate_original_target_case_signature(plan,target,certificate_envelope=cert,issuer_input=root,
            checked_at=checked_at,revoked_identity_ids=revoked_identity_ids,input_bytes=ti,output_bytes=to)
        if not target_only:
            case=next(c for c in plan['cases'] if c['caseId']==claim.case_id)
            # This is a necessary comparison to the documented v2 wire codec.
            # It does NOT replace build_original_target_judge_input's native reads.
            payload=dict(schemaVersion='aos.model-eval-original-target-judge-input/v2',tenant=plan['tenant'],
                executionId=plan['executionId'],manifestHash=canonical_hash(plan),judgeRequestHash=plan['judgeRequestHash'],
                caseId=claim.case_id,judgeLeg=case['judge'],targetCaseHash=_json_hash(target),
                targetCertificateHash=target.payload.certificate_hash,actualHash=target.payload.claim.output_hash,
                actualBase64=base64.b64encode(to).decode('ascii'),expectedHash=case['expectedHash'],
                expectedBase64=None if expected_output is None else base64.b64encode(expected_output).decode('ascii'),executionAllowed=False)
            if input_bytes!=_canonical(payload):raise ValueError('complete original v2 Judge wire codec required')
    else:
        from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation
        desc=_original(SharedParentRiskDescriptionPreparation,w.shared_risk_description)
        if _canonical(desc.immutable.manifest.model_dump(mode='json',by_alias=True))!=_canonical(plan):
            raise ValueError('same original v3 risk description and complete Model plan required')
        target=_original(old.ModelSharedParentRiskSignedCaseEnvelope,w.target_case)
        cert=_original(old.ModelSharedParentRiskSignedCertificateEnvelope,w.target_certificate)
        args=dict(certificate_envelope=cert,issuer_input=root,checked_at=checked_at,revoked_identity_ids=revoked_identity_ids)
        old.validate_shared_parent_case_signature(desc,target,input_bytes=ti,output_bytes=to,**args)
        if not target_only:
            judge=_original(old.ModelSharedParentRiskSignedCaseEnvelope,w.judge_case)
            jc=_original(old.ModelSharedParentRiskSignedCertificateEnvelope,w.judge_certificate)
            jr=_original(old.ModelEvalIssuerVerificationInput,w.judge_issuer)
            old.validate_shared_parent_case_signature(desc,judge,certificate_envelope=jc,issuer_input=jr,
                checked_at=checked_at,revoked_identity_ids=revoked_identity_ids,input_bytes=input_bytes,output_bytes=output_bytes,
                target_envelope=target,target_certificate_envelope=cert,target_issuer_input=root,target_input_bytes=ti,target_output_bytes=to)
            old.validate_shared_parent_target_judge_input(desc,target,judge_input_bytes=input_bytes,
                target_input_bytes=ti,target_output_bytes=to,expected_output=expected_output,**args)
            if (judge.payload.claim.occurred_at,judge.payload.claim.passed,judge.payload.claim.detail_code)!=(claim.occurred_at,claim.passed,claim.detail_code):
                raise ValueError('new Model Judge must retain original signed result description')
    if (target.payload.claim.purpose!='target' or target.payload.claim.case_id!=claim.case_id
        or (target_only and target.payload.claim.occurred_at!=claim.occurred_at)
        or target.payload.claim.occurred_at>claim.occurred_at):
        raise ValueError('same original Model Target event and causal time required')


def _route_judge_wire(body,target,certificate,target_output_bytes,expected_output):
    app=body['routeApplication'];recipe=next(c for c in app['calls'] if (c['caseId'],c['purpose'])==(target.claim.case_id,'judge'))
    payload=dict(schemaVersion='aos.governed-route-target-judge-input/v1',inputProtocol=recipe['inputProtocol'],
        tenant=body['tenant'],executionId=body['executionId'],manifestHash=target.claim.manifest_hash,
        contextBindingHash=body['contextBindingHash'],caseId=target.claim.case_id,judgeRuleHash=canonical_hash(app['judgeRule']),
        judgeRuleSourceHash=canonical_hash(app['judgeRuleSource']),judgeRecipeHash=canonical_hash(recipe),
        targetEnvelopeHash=_json_hash(target),targetCertificateHash=_json_hash(certificate),
        actualHash=target.claim.output_hash,actualBase64=base64.b64encode(target_output_bytes).decode('ascii'),
        expectedHash=target.claim.expected_hash,expectedBase64=None if expected_output is None else base64.b64encode(expected_output).decode('ascii'),executionAllowed=False)
    raw=_canonical(payload);_bytes_hash(raw)
    return raw


def build_governed_route_judge_input(manifest_bytes,*,target_envelope,target_certificate_envelope,target_issuer_input,
        checked_at,revoked_identity_ids,target_input_bytes,target_output_bytes,artifact_input_bytes,expected_output=None):
    """Build necessary Route wire after presented Target crypto, not native trust."""
    body=_manifest(manifest_bytes)
    if 'routeApplication' not in body:raise ValueError('Model must retain its original Judge wire builders')
    target=GovernedEvalSignedCase.model_validate(_alias_input(target_envelope))
    if target.claim.purpose!='target':raise ValueError('Route Judge requires independent Target purpose')
    validate_governed_case_signature(manifest_bytes,target,certificate_envelope=target_certificate_envelope,
        issuer_input=target_issuer_input,checked_at=checked_at,revoked_identity_ids=revoked_identity_ids,
        input_bytes=target_input_bytes,output_bytes=target_output_bytes,artifact_input_bytes=artifact_input_bytes,expected_output=expected_output)
    certificate=GovernedEvalSignedCertificate.model_validate(_alias_input(target_certificate_envelope))
    return _route_judge_wire(body,target,certificate,target_output_bytes,expected_output)


def canonical_governed_case_bytes(manifest_bytes,claim,*,certificate_envelope,issuer_input,checked_at,revoked_identity_ids,
        input_bytes,output_bytes,artifact_input_bytes,expected_output=None,target_envelope=None,
        target_certificate_envelope=None,target_issuer_input=None,target_input_bytes=None,target_output_bytes=None,legacy_model_proof=None):
    """Necessary complete signing bytes; never native proof or execution admission."""
    body=_manifest(manifest_bytes);item=GovernedEvalCaseClaim.model_validate(_alias_input(claim));at=_aware(checked_at)
    certificate=GovernedEvalSignedCertificate.model_validate(_alias_input(certificate_envelope));cert=certificate.certificate
    validate_governed_certificate_signature(manifest_bytes,cert,issuer_input=issuer_input,signature_base64=certificate.signature_base64,
        checked_at=at,revoked_identity_ids=revoked_identity_ids)
    fields=('tenant','subject_kind','execution_id','manifest_hash','context_binding_hash','call_binding_hash','case_id','purpose')
    ih,eh=_case_artifacts(body,item.case_id,artifact_input_bytes,expected_output)
    if (any(getattr(item,f)!=getattr(cert,f) for f in fields) or item.certificate_hash!=_json_hash(certificate)
        or (item.case_input_hash,item.expected_hash)!=(ih,eh)
        or item.wire_input_hash!=_bytes_hash(input_bytes) or item.output_hash!=_bytes_hash(output_bytes)
        or not cert.valid_from<=item.occurred_at<cert.valid_until or item.occurred_at>at):
        raise ValueError('exact case certificate, original artifacts, wire/output and time required')
    target_args=(target_envelope,target_certificate_envelope,target_issuer_input,target_input_bytes,target_output_bytes)
    if item.purpose=='target':
        if any(v is not None for v in target_args):raise ValueError('Target cannot borrow or ignore Judge dependencies')
    else:
        target=GovernedEvalSignedCase.model_validate(_alias_input(target_envelope))
        if target.claim.purpose!='target' or target.claim.case_id!=item.case_id:raise ValueError('same-case independent Target result required')
        validate_governed_case_signature(manifest_bytes,target,certificate_envelope=target_certificate_envelope,
            issuer_input=target_issuer_input,checked_at=at,revoked_identity_ids=revoked_identity_ids,
            input_bytes=target_input_bytes,output_bytes=target_output_bytes,artifact_input_bytes=artifact_input_bytes,
            expected_output=expected_output,legacy_model_proof=_target_legacy(legacy_model_proof))
        if (item.target_envelope_hash!=_json_hash(target) or item.target_output_hash!=target.claim.output_hash
            or target.claim.occurred_at>item.occurred_at):raise ValueError('Judge must bind whole signed Target and causal time')
        if 'routeApplication' in body:
            tc=GovernedEvalSignedCertificate.model_validate(_alias_input(target_certificate_envelope))
            if input_bytes!=_route_judge_wire(body,target,tc,target_output_bytes,expected_output):
                raise ValueError('exact Target-derived Route Judge wire required')
    if 'modelPlan' in body:
        _legacy_case(body,item,legacy_model_proof,checked_at=at,revoked_identity_ids=revoked_identity_ids,
            input_bytes=input_bytes,output_bytes=output_bytes,target_input_bytes=target_input_bytes,
            target_output_bytes=target_output_bytes,expected_output=expected_output)
    else:
        if legacy_model_proof is not None or item.legacy_model_proof_hash is not None:
            raise ValueError('Route cannot borrow Model legacy proof')
        if item.purpose=='target':
            _,leg,_=_call(body,case_id=item.case_id,purpose='target')
            if item.wire_input_hash!=leg['wireInputHash']:raise ValueError('Route Target wire must match approved recipe')
    return CASE_DOMAIN+_canonical(item.model_dump(mode='json',by_alias=True))


def validate_governed_case_signature(manifest_bytes,envelope,**case_args) -> None:
    """Presented case/certificate/Target crypto only; no native execution proof."""
    signed=GovernedEvalSignedCase.model_validate(_alias_input(envelope))
    raw=canonical_governed_case_bytes(manifest_bytes,signed.claim,**case_args)
    certificate=GovernedEvalSignedCertificate.model_validate(_alias_input(case_args['certificate_envelope']))
    try:
        Ed25519PublicKey.from_public_bytes(_key_bytes(certificate.certificate.public_key_base64)).verify(_signature_bytes(signed.signature_base64),raw)
    except (InvalidSignature,ValueError,binascii.Error) as exc:
        raise ValueError('invalid presented governed case signature') from exc
