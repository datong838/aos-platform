from datetime import datetime, timezone, timedelta
from dataclasses import replace
import base64
import hashlib
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from aos_api.asset_registry.signature import TrustRoot
from aos_api.aip_eval_subject_proof_contracts import SubjectReviewEnvelope, subject_envelope_hash
from aos_api.aip_eval_subject_proof_authority import (
    SubjectCertificate, SubjectReceipt, SubjectIssuerRoot, certificate_bytes,
    receipt_bytes, claim_hash, receipt_identity, verify_subject_pair,
)
from test_aip_eval_subject_proof import payload

NOW=datetime(2026,10,1,9,tzinfo=timezone.utc)

def public(key):return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
def sign(item,key,encode):return item.model_copy(update={'signature_base64':base64.b64encode(key.sign(encode(item))).decode()})

def pair(passed=True):
    e=SubjectReviewEnvelope.model_validate(payload());issuer=Ed25519PrivateKey.generate()
    root=SubjectIssuerRoot(TrustRoot('issuer','root',public(issuer),'sha256:'+hashlib.sha256(public(issuer)).hexdigest(),NOW-timedelta(days=1),NOW+timedelta(days=1)))
    rows=[]
    for purpose,ref in [('source-witness',e.generation_skill_ref),('judge',e.judge_ref)]:
        key=Ed25519PrivateKey.generate()
        c=SubjectCertificate(identity_id=purpose,tenant=e.tenant,purpose=purpose,executor_ref=ref,
            issuer_id='issuer',issuer_key_id='root',public_key_base64=base64.b64encode(public(key)).decode(),
            valid_from=NOW-timedelta(hours=1),valid_until=NOW+timedelta(hours=1),signature_base64='pending')
        c=sign(c,issuer,certificate_bytes)
        r=SubjectReceipt(receipt_id=receipt_identity(e,purpose),tenant=e.tenant,purpose=purpose,
            identity_id=c.identity_id,certificate_hash=claim_hash(c),envelope_hash=subject_envelope_hash(e),
            occurred_at=NOW,signature_base64='pending',
            **({'source_receipt_hash':claim_hash(rows[0][1]),'structure_passed':passed,'detail_code':'structure_result'} if purpose=='judge' else {}))
        rows.append((c,sign(r,key,receipt_bytes),key))
    return e,root,rows,issuer

def verify(e,root,rows,**kw):
    args=dict(expected_envelope=e,issuer_roots={('issuer','root'):root},revoked_identity_ids=frozenset(),now=NOW,
        source_certificate=rows[0][0],source_receipt=rows[0][1],judge_certificate=rows[1][0],judge_receipt=rows[1][1])
    args.update(kw);return verify_subject_pair(**args)

@pytest.mark.parametrize('passed',[True,False])
def test_real_test_signatures_preserve_structure_result(passed):
    e,root,rows,_=pair(passed);v=verify(e,root,rows)
    assert v.structure_passed is passed
    assert v.envelope_hash==subject_envelope_hash(e)

@pytest.mark.parametrize('fault',['body','tenant','generation','source_hash','signature','root_purpose','root_revoked','expired','identity_revoked','missing_snapshot','future','same_key','same_identity','bool_result'])
def test_drifted_or_untrusted_pair_rejected(fault):
    e,root,rows,issuer=pair();kw={}
    if fault=='body':e=e.model_copy(update={'subject_bytes_hash':'0'*64})
    elif fault=='tenant':e=e.model_copy(update={'tenant':e.tenant.model_copy(update={'org_id':'dev-org'})})
    elif fault=='generation':e=e.model_copy(update={'generation':2})
    elif fault=='source_hash':
        c,r,k=rows[1];rows[1]=(c,sign(r.model_copy(update={'source_receipt_hash':'0'*64}),k,receipt_bytes),k)
    elif fault=='signature':
        c,r,k=rows[0];rows[0]=(c,r.model_copy(update={'signature_base64':'bad'}),k)
    elif fault=='root_purpose':root=replace(root,purpose='eval-execution')
    elif fault=='root_revoked':root=replace(root,trust_root=replace(root.trust_root,revoked_at=NOW))
    elif fault=='expired':kw['now']=NOW+timedelta(hours=2)
    elif fault=='identity_revoked':kw['revoked_identity_ids']=frozenset({'judge'})
    elif fault=='missing_snapshot':kw['revoked_identity_ids']=None
    elif fault=='future':kw['now']=NOW-timedelta(seconds=1)
    elif fault in ['same_key','same_identity']:
        c,r,k=rows[1]
        if fault=='same_key':k=rows[0][2];c=c.model_copy(update={'public_key_base64':rows[0][0].public_key_base64})
        else:c=c.model_copy(update={'identity_id':rows[0][0].identity_id})
        c=sign(c,issuer,certificate_bytes)
        r=r.model_copy(update={'identity_id':c.identity_id,'certificate_hash':claim_hash(c)})
        rows[1]=(c,sign(r,k,receipt_bytes),k)
    else:
        c,r,k=rows[1];rows[1]=(c,r.model_copy(update={'structure_passed':1}),k)
    with pytest.raises(ValueError):verify(e,root,rows,**kw)


@pytest.mark.parametrize('fault',['missing_root','root_expired','old_receipt_domain','source_has_result','receipt_id','judge_before_source'])
def test_purpose_domain_and_receipt_replay_boundaries(fault):
    e,root,rows,_=pair();kw={}
    if fault=='missing_root':kw['issuer_roots']={}
    elif fault=='root_expired':root=replace(root,trust_root=replace(root.trust_root,not_after=NOW))
    elif fault=='source_has_result':
        c,r,k=rows[0];rows[0]=(c,r.model_copy(update={'structure_passed':True}),k)
    else:
        c,r,k=rows[1]
        if fault=='old_receipt_domain':
            raw=receipt_bytes(r).replace(b'AOS-EVAL-SUBJECT-RECEIPT-v1',b'AOS-EVAL-EXECUTION-RECEIPT-v1',1)
            r=r.model_copy(update={'signature_base64':base64.b64encode(k.sign(raw)).decode()})
        elif fault=='receipt_id':r=sign(r.model_copy(update={'receipt_id':'0'*64}),k,receipt_bytes)
        else:r=sign(r.model_copy(update={'occurred_at':NOW-timedelta(seconds=1)}),k,receipt_bytes)
        rows[1]=(c,r,k)
    with pytest.raises(ValueError):verify(e,root,rows,**kw)


@pytest.mark.parametrize('revision',[True,1.0,'1'])
def test_certificate_judge_revision_not_coerced(revision):
    _,_,rows,_=pair()
    c=rows[1][0];c=c.model_copy(update={'executor_ref':c.executor_ref.model_copy(update={'revision':revision})})
    with pytest.raises(ValueError):certificate_bytes(c)
