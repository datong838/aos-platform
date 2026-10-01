"""Verify subject-review claims; durable issuer/Owner authority remains separate."""
from __future__ import annotations
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Literal
from pydantic import Field, StrictBool, field_validator, model_validator
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import AssetRevisionRef, AssetType, JudgeRevisionRef
from aos_api.aip_eval_subject_proof_contracts import Digest, Identifier, SubjectReviewEnvelope, subject_envelope_hash
from aos_api.asset_registry.signature import TrustRoot, FrozenTrustRootProvider, verify_ed25519

Purpose = Literal['source-witness', 'judge']


class SubjectCertificate(AipContractModel):
    schema_version: Literal['aos.eval-subject-certificate/v1'] = 'aos.eval-subject-certificate/v1'
    identity_id: Identifier
    tenant: TenantContext
    purpose: Purpose
    executor_ref: AssetRevisionRef | JudgeRevisionRef
    issuer_id: Identifier
    issuer_key_id: Identifier
    public_key_base64: str = Field(min_length=1, max_length=128)
    valid_from: datetime
    valid_until: datetime
    signature_base64: str = Field(min_length=1, max_length=256)

    @field_validator('executor_ref', mode='before')
    @classmethod
    def _strict_judge_revision(cls, value):
        if isinstance(value, AipContractModel):
            value=value.model_dump(mode='python')
        if isinstance(value, dict) and ('judge_id' in value or 'judgeId' in value):
            if type(value.get('revision')) is not int:
                raise ValueError('strict Judge revision required')
        return value

    @field_validator('valid_from','valid_until')
    @classmethod
    def _aware(cls,v):
        if v.utcoffset() is None: raise ValueError('aware certificate time required')
        return v.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _shape(self):
        if self.valid_from >= self.valid_until: raise ValueError('invalid certificate interval')
        if self.purpose == 'source-witness':
            if not isinstance(self.executor_ref,AssetRevisionRef) or self.executor_ref.asset_type != AssetType.SKILL_TEMPLATE:
                raise ValueError('witness binds original generating Skill, not an execution claim')
        elif not isinstance(self.executor_ref,JudgeRevisionRef): raise ValueError('judge reference required')
        _key(self.public_key_base64)
        return self


class SubjectReceipt(AipContractModel):
    schema_version: Literal['aos.eval-subject-receipt/v1'] = 'aos.eval-subject-receipt/v1'
    receipt_id: Digest
    tenant: TenantContext
    purpose: Purpose
    identity_id: Identifier
    certificate_hash: Digest
    envelope_hash: Digest
    occurred_at: datetime
    source_receipt_hash: Digest | None = None
    structure_passed: StrictBool | None = None
    detail_code: Identifier | None = None
    signature_base64: str = Field(min_length=1,max_length=256)

    @field_validator('occurred_at')
    @classmethod
    def _aware(cls,v):
        if v.utcoffset() is None: raise ValueError('aware receipt time required')
        return v.astimezone(timezone.utc)

    @model_validator(mode='after')
    def _shape(self):
        fields=(self.source_receipt_hash,self.structure_passed,self.detail_code)
        if self.purpose=='source-witness' and any(x is not None for x in fields):
            raise ValueError('source witness cannot judge a result')
        if self.purpose=='judge' and any(x is None for x in fields):
            raise ValueError('judge requires bound source and structure result')
        return self


@dataclass(frozen=True)
class SubjectIssuerRoot:
    trust_root: TrustRoot
    purpose: Literal['subject-review'] = 'subject-review'


@dataclass(frozen=True)
class VerifiedSubjectPair:
    envelope_hash: str
    source_claim_hash: str
    judge_claim_hash: str
    structure_passed: bool
    detail_code: str


def _key(value):
    key=base64.b64decode(value,validate=True)
    if len(key)!=32 or base64.b64encode(key).decode()!=value:
        raise ValueError('canonical Ed25519 key required')
    return key


def _canonical(value,model,domain):
    item=model.model_validate(value.model_dump(mode='python'))
    body=json.dumps(item.model_dump(mode='json',by_alias=True,exclude={'signature_base64'}),
                    sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
    return domain+b'\n'+body


def certificate_bytes(c):return _canonical(c,SubjectCertificate,b'AOS-EVAL-SUBJECT-CERTIFICATE-v1')
def receipt_bytes(r):return _canonical(r,SubjectReceipt,b'AOS-EVAL-SUBJECT-RECEIPT-v1')
def claim_hash(item):
    return hashlib.sha256(certificate_bytes(item) if isinstance(item,SubjectCertificate) else receipt_bytes(item)).hexdigest()


def receipt_identity(envelope,purpose):
    if purpose not in ('source-witness','judge'): raise ValueError('subject purpose required')
    return hashlib.sha256(b'AOS-EVAL-SUBJECT-RECEIPT-ID-v1\n'+
                          subject_envelope_hash(envelope).encode()+b'\n'+purpose.encode()).hexdigest()


def verify_subject_pair(*, expected_envelope, issuer_roots, revoked_identity_ids, now,
                        source_certificate, source_receipt, judge_certificate, judge_receipt):
    """Caller must supply current authorized roots/revocations and Owner-read envelope.

    Returns a verified structure claim, never permission to execute or publish.
    """
    if not isinstance(revoked_identity_ids,frozenset) or now.utcoffset() is None:
        raise ValueError('current revocation snapshot and aware clock required')
    e=SubjectReviewEnvelope.model_validate(expected_envelope.model_dump(mode='python'))
    certificates=[SubjectCertificate.model_validate(c.model_dump(mode='python')) for c in (source_certificate,judge_certificate)]
    receipts=[SubjectReceipt.model_validate(r.model_dump(mode='python')) for r in (source_receipt,judge_receipt)]
    if (certificates[0].identity_id==certificates[1].identity_id
            or _key(certificates[0].public_key_base64)==_key(certificates[1].public_key_base64)):
        raise ValueError('independent witness and judge required')
    digest=subject_envelope_hash(e)
    roots=dict(issuer_roots)
    for c,r,purpose,ref in zip(certificates,receipts,('source-witness','judge'),(e.generation_skill_ref,e.judge_ref)):
        if (c.purpose!=purpose or r.purpose!=purpose or c.tenant!=e.tenant or r.tenant!=e.tenant
                or c.executor_ref!=ref or c.identity_id in revoked_identity_ids
                or r.identity_id!=c.identity_id or r.certificate_hash!=claim_hash(c)
                or r.envelope_hash!=digest or r.receipt_id!=receipt_identity(e,purpose)
                or not c.valid_from<=r.occurred_at<=now<c.valid_until):
            raise ValueError('subject identity or exact claim drifted')
        wrapped=roots.get((c.issuer_id,c.issuer_key_id))
        if not isinstance(wrapped,SubjectIssuerRoot) or wrapped.purpose!='subject-review':
            raise ValueError('current subject-review issuer required')
        root=wrapped.trust_root
        if root.not_before is None or root.not_after is None:
            raise ValueError('bounded issuer validity required')
        provider=FrozenTrustRootProvider({(c.issuer_id,c.issuer_key_id):root})
        for checked_at in (r.occurred_at,now):
            if not verify_ed25519(payload=certificate_bytes(c),signature_b64=c.signature_base64,
                    publisher=c.issuer_id,key_id=c.issuer_key_id,trust_roots=provider,verified_at=checked_at):
                raise ValueError('subject certificate signature/root validity rejected')
        key=_key(c.public_key_base64)
        executor=TrustRoot(c.identity_id,c.identity_id,key,'sha256:'+hashlib.sha256(key).hexdigest(),c.valid_from,c.valid_until)
        if not verify_ed25519(payload=receipt_bytes(r),signature_b64=r.signature_base64,
                publisher=c.identity_id,key_id=c.identity_id,
                trust_roots=FrozenTrustRootProvider({(c.identity_id,c.identity_id):executor}),verified_at=now):
            raise ValueError('subject receipt signature rejected')
    source,judge=receipts
    if judge.source_receipt_hash!=claim_hash(source) or not e.cutoff<=source.occurred_at<=judge.occurred_at:
        raise ValueError('judge/source chronology or binding drifted')
    return VerifiedSubjectPair(digest,claim_hash(source),claim_hash(judge),judge.structure_passed,judge.detail_code)
