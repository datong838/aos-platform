"""Synthetic in-memory keys: presented signature checks confer no authority."""
import base64
from datetime import timedelta
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import pytest

from aos_api.aip_model_route_eval_manifest import compile_eval_execution_manifest
from aos_api.aip_model_route_eval_signatures import (
    GovernedEvalCertificate, GovernedEvalIssuerInput,
    canonical_governed_certificate_bytes, governed_call_binding_hash,
    validate_governed_certificate_signature,
    GovernedEvalSignedCertificate, GovernedEvalCaseClaim, GovernedEvalSignedCase,
    ModelLegacyProofWitness, canonical_governed_case_bytes,
    validate_governed_case_signature, build_governed_route_judge_input,
)
from aos_api.aip_model_route_eval_owner import (
    PresentedRouteEvalCase, prepare_route_eval_presented_case_bundle,
)
from test_model_route_eval_manifest import route_inputs, model_inputs, bref, dump, NOW, TENANT


def public(key):
    return key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)


def certificate_inputs(kind='route',purpose='target',*,with_keys=False,artifact_input=None,expected_output=None):
    keys={p:Ed25519PrivateKey.generate() for p in ('target','judge')}
    if kind=='route':
        raw,app,bindings=route_inputs(outside_judge=True)
        if artifact_input is not None:
            raw=artifact_context(raw,artifact_input,expected_output)
            from aos_api.aip_model_route_eval_manifest import eval_context_binding_hash,route_eval_call_key
            h=eval_context_binding_hash(raw);app=app.model_copy(update={'context_binding_hash':h})
            for i,c in enumerate(app.calls):
                app.calls[i]=c.model_copy(update={'input_hash':sha(artifact_input),'expected_hash':None if expected_output is None else sha(expected_output),
                    'wire_input_hash':sha(b'actual target wire') if c.purpose=='target' else None,
                    'target_call_key':None if c.purpose=='target' else route_eval_call_key(app.execution_id,h,c.case_id,'target')})
                key=route_eval_call_key(app.execution_id,h,c.case_id,c.purpose);req=bindings[i].request.model_copy(update={'invocation_key':key})
                res=bindings[i].reservation.model_copy(update={'invocation_key':key,'request_hash':req.request_hash()})
                bindings[i]=bindings[i].model_copy(update={'call_key':key,'request':req,'reservation':res})
        for i,p in enumerate(('target','judge')):
            app.calls[i]=app.calls[i].model_copy(update={'identity_key_hash':hashlib.sha256(public(keys[p])).hexdigest()})
        manifest=compile_eval_execution_manifest(raw,execution_id=app.execution_id,checked_at=NOW,route_application=app,route_budget_bindings=bindings)
        identity=next(c for c in app.calls if c.purpose==purpose)
        intent=bref('GovernedEvalExecutionIntent','intent-'+purpose)
        joint=bref('GovernedEvalJointAdmissionReceipt','joint-'+purpose)
    else:
        raw,plan=model_inputs(2 if kind=='model2' else 3)
        if artifact_input is not None:
            raw=artifact_context(raw,artifact_input,expected_output);plan=artifact_model_plan(plan,raw)
            plan=plan.model_copy(update={'execution_id':'e11b6293-c651-4db7-a9bd-003f01d9eb78'})
        for p in ('target','judge'):
            setattr(plan.cases[0],p,getattr(plan.cases[0],p).model_copy(update={'identity_key_hash':hashlib.sha256(public(keys[p])).hexdigest()}))
        manifest=compile_eval_execution_manifest(raw,execution_id=plan.execution_id,checked_at=NOW,model_plan=plan)
        identity=getattr(plan.cases[0],purpose);intent=dump(identity.intent_ref);joint=dump(identity.joint_receipt_ref)
    body=json.loads(manifest.split(b'\n',1)[1]);issuer=Ed25519PrivateKey.generate()
    cert=GovernedEvalCertificate(tenant=TENANT,subjectKind=body['context']['subject']['candidate']['sourceRef']['assetType'],
        executionId=body['executionId'],manifestHash=hashlib.sha256(manifest).hexdigest(),contextBindingHash=body['contextBindingHash'],
        caseId='case',purpose=purpose,callBindingHash=governed_call_binding_hash(manifest,case_id='case',purpose=purpose),
        identityId=identity.identity_id,identityKeyHash=identity.identity_key_hash,publicKeyBase64=base64.b64encode(public(keys[purpose])).decode(),
        issuerId='synthetic-issuer',issuerKeyId='synthetic-root',intentRef=intent,jointAdmissionRef=joint,
        validFrom=NOW,validUntil=NOW+timedelta(hours=1),executionAllowed=False)
    root=GovernedEvalIssuerInput(tenant=TENANT,issuerId=cert.issuer_id,issuerKeyId=cert.issuer_key_id,
        publicKeyBase64=base64.b64encode(public(issuer)).decode(),validFrom=NOW-timedelta(hours=1),validUntil=NOW+timedelta(hours=2),revokedAt=None,executionAllowed=False)
    signature=base64.b64encode(issuer.sign(canonical_governed_certificate_bytes(manifest,cert))).decode()
    out=(manifest,cert,root,signature)
    return (*out,keys,issuer) if with_keys else out


def sha(raw):return hashlib.sha256(raw).hexdigest()


def artifact_context(raw,input_bytes,expected_bytes):
    from aos_api.aip_eval_contracts import EvalSuiteRevision
    from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
    from aos_api.aip_production_contracts import EvalContractRevision,CreateEvalContractRequest
    from aos_api.aip_model_runtime_store import canonical_hash
    body=json.loads(raw.split(b'\n',1)[1]);case=body['suite']['cases'][0]
    case['inputArtifact']['contentHash']=sha(input_bytes)
    if expected_bytes is not None:case['expectedArtifact']={**case['inputArtifact'],'artifactId':'expected','contentHash':sha(expected_bytes)}
    suite=EvalSuiteRevision.model_validate(body['suite']);h=compute_eval_suite_hash(suite)
    body['suite']['contentHash']=h;body['run']['suiteRef']['contentHash']=h;body['contract']['suiteRef']['contentHash']=h
    contract=EvalContractRevision.model_validate(body['contract'])
    req=CreateEvalContractRequest.model_validate({n:getattr(contract,n) for n in CreateEvalContractRequest.model_fields})
    body['contract']['contentHash']=canonical_hash(dump(req));body['run']['evalContractRef']['contentHash']=body['contract']['contentHash']
    return raw.split(b'\n',1)[0]+b'\n'+json.dumps(body,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()


def artifact_model_plan(plan,raw):
    from aos_api.aip_model_runtime_store import canonical_hash
    body=json.loads(raw.split(b'\n',1)[1]);p=dump(plan);j=p['judgeRequest'];t=j['targetApplication']
    req=t['request'];req['suiteRef']['contentHash']=body['suite']['contentHash'];req['evalContractRef']['contentHash']=body['contract']['contentHash']
    t['requestHash']=canonical_hash(req);j['suiteRef']=req['suiteRef'];j['evalContractRef']=req['evalContractRef'];j['cases']=body['suite']['cases'];j['caseSetHash']=canonical_hash(j['cases'])
    p['targetParentBudget']['requestHash']=t['requestHash'];p['judgeParentBudget']['requestHash']=p['judgeRequestHash']=canonical_hash(j)
    p['cases'][0]['inputHash']=body['suite']['cases'][0]['inputArtifact']['contentHash'];p['cases'][0]['expectedHash']=None if body['suite']['cases'][0]['expectedArtifact'] is None else body['suite']['cases'][0]['expectedArtifact']['contentHash']
    p['caseSetHash']=canonical_hash([{k:p['cases'][0][k] for k in ('caseId','inputHash','expectedHash')}])
    return type(plan).model_validate(p)


@pytest.mark.parametrize('kind',['route','model2','model3'])
@pytest.mark.parametrize('purpose',['target','judge'])
def test_all_original_model_and_complete_route_certificate_signatures_are_necessary_checks(kind,purpose):
    manifest,cert,root,sig=certificate_inputs(kind,purpose)
    assert canonical_governed_certificate_bytes(manifest,cert).startswith(b'AOS-GOVERNED-EVAL-CERTIFICATE-SIGNING-v1\n')
    assert cert.execution_allowed is False
    assert validate_governed_certificate_signature(manifest,cert,issuer_input=root,signature_base64=sig,checked_at=NOW,revoked_identity_ids=frozenset()) is None


@pytest.mark.parametrize('fault',['manifest','context','call','tenant','case','purpose','identity','key_hash','public_key','intent','joint','future','expired','extra','numeric_revision'])
def test_certificate_cannot_drift_from_complete_original_call(fault):
    manifest,cert,_,_=certificate_inputs('model3')
    fields={'manifest':('manifest_hash','0'*64),'context':('context_binding_hash','0'*64),'call':('call_binding_hash','0'*64),
        'tenant':('tenant',dict(orgId='dev-org',projectId='dev-project')),'case':('case_id','other'),
        'purpose':('purpose','judge'),'identity':('identity_id','other'),'key_hash':('identity_key_hash','0'*64),
        'public_key':('public_key_base64',base64.b64encode(bytes(32)).decode()),
        'intent':('intent_ref',bref('ModelEvalExecutionIntent','other')),'joint':('joint_admission_ref',bref('ModelEvalJointAdmissionReceipt','other')),
        'future':('valid_from',NOW-timedelta(seconds=1)),'expired':('valid_until',NOW+timedelta(hours=2)),
        'extra':('dispatchAllowed',True),'numeric_revision':('intent_ref',{**dump(cert.intent_ref),'revision':True})}
    k,v=fields[fault];bad=cert.model_copy(update={k:v})
    with pytest.raises(ValueError):canonical_governed_certificate_bytes(manifest,bad)


@pytest.mark.parametrize('fault',['signature','signature_size','noncanonical','wrong_root_key','wrong_issuer','wrong_tenant','root_expired','root_future','revoked','identity_revoked','mutable_revocations','naive_clock','certificate_end','extra_root'])
def test_presented_root_and_signature_must_be_exact_current_and_unrevoked(fault):
    manifest,cert,root,sig=certificate_inputs();at=NOW;revoked=frozenset()
    if fault=='signature':sig=base64.b64encode(bytes(64)).decode()
    elif fault=='signature_size':sig=base64.b64encode(bytes(63)).decode()
    elif fault=='noncanonical':sig+='\n'
    elif fault=='wrong_root_key':root=root.model_copy(update={'public_key_base64':base64.b64encode(bytes(32)).decode()})
    elif fault=='wrong_issuer':root=root.model_copy(update={'issuer_id':'other'})
    elif fault=='wrong_tenant':root=root.model_copy(update={'tenant':dict(orgId='dev-org',projectId='dev-project')})
    elif fault=='root_expired':root=root.model_copy(update={'valid_until':NOW})
    elif fault=='root_future':root=root.model_copy(update={'valid_from':NOW+timedelta(seconds=1)})
    elif fault=='revoked':root=root.model_copy(update={'revoked_at':NOW})
    elif fault=='identity_revoked':revoked=frozenset([cert.identity_id])
    elif fault=='mutable_revocations':revoked=set()
    elif fault=='naive_clock':at=NOW.replace(tzinfo=None)
    elif fault=='certificate_end':at=cert.valid_until
    else:root=root.model_copy(update={'trusted':True})
    with pytest.raises(ValueError):validate_governed_certificate_signature(manifest,cert,issuer_input=root,signature_base64=sig,checked_at=at,revoked_identity_ids=revoked)


@pytest.mark.parametrize('fault',['legacy_domain','manifest_extra','duplicate_key','noncanonical','call_missing','purpose_unknown'])
def test_certificate_binding_requires_complete_canonical_governed_manifest(fault):
    manifest,_,_,_=certificate_inputs();case='case';purpose='target'
    if fault=='legacy_domain':manifest=manifest.replace(b'AOS-GOVERNED-MODEL-ROUTE-EVAL-MANIFEST-v1',b'AOS-MODEL-EVAL-EXECUTION-MANIFEST-v1',1)
    elif fault=='manifest_extra':
        body=json.loads(manifest.split(b'\n',1)[1]);body['authorized']=True;manifest=manifest.split(b'\n',1)[0]+b'\n'+json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
    elif fault=='duplicate_key':manifest=manifest.replace(b'"executionAllowed":false',b'"executionAllowed":false,"executionAllowed":false',1)
    elif fault=='noncanonical':manifest=manifest.replace(b'\n{',b'\n{ ',1)
    elif fault=='call_missing':case='missing'
    else:purpose='provider'
    with pytest.raises(ValueError):governed_call_binding_hash(manifest,case_id=case,purpose=purpose)


def original_model_witness(kind,body,keys,issuer,wire,output,expected):
    """Fresh old-domain crypto fixtures, explicitly not native or human facts."""
    from aos_api import aip_model_eval_execution_contracts as old
    from aos_api.aip_model_runtime_store import canonical_hash
    plan=body['modelPlan'];case=plan['cases'][0];v3=kind=='model3'
    root=old.ModelEvalIssuerVerificationInput(schemaVersion='aos.model-eval-issuer-verification-input/v1',
        purpose='model-eval-execution',tenant=TENANT,issuerId='synthetic-issuer',issuerKeyId='synthetic-root',
        publicKeyBase64=base64.b64encode(public(issuer)).decode(),validFrom=NOW-timedelta(hours=1),
        validUntil=NOW+timedelta(hours=2),revokedAt=None)
    description=None
    if v3:
        from aos_api.aip_physical_capacity_occupation_contracts import SharedParentRiskDescriptionPreparation
        immutable=dict(schemaVersion='aos.shared-parent-risk-description-preparation/v1',planId=plan['executionId'],
            tenant=TENANT,originalRiskHash='sha256:'+'a'*64,manifest=plan,manifestHash=canonical_hash(plan),
            callerLogin='aos_provider_capacity_occupation',callerXid='123',callerPid=99,
            state='prepared_description_only',executorsAuthenticated=False,executionAllowed=False)
        description=SharedParentRiskDescriptionPreparation(planId=plan['executionId'],immutable=immutable,
            contentHash='sha256:'+canonical_hash(immutable),executionAllowed=False)
    def leg(purpose,wi,ou,at,target=None):
        app=plan['judgeRequest']['targetApplication' if purpose=='target' else 'judgeGovernanceApplication']
        common=dict(tenant=TENANT,executionId=plan['executionId'],manifestHash=canonical_hash(plan),
            requestHash=app['requestHash'] if purpose=='target' else plan['judgeRequestHash'],caseId='case',purpose=purpose,
            candidateRef=app['request']['targetRef'],leg=case[purpose])
        if v3:common.update(descriptionHash=description.content_hash,originalRiskHash=description.immutable.original_risk_hash,
            callerXid=description.immutable.caller_xid,callerPid=description.immutable.caller_pid)
        cert_class=old.ModelSharedParentRiskCertificateSigningInput if v3 else old.ModelOriginalTargetCertificateSigningInput
        cert=cert_class(schemaVersion='aos.model-eval-shared-parent-certificate-signing-input/v3' if v3 else 'aos.model-eval-original-target-certificate-signing-input/v2',
            **common,issuerId=root.issuer_id,issuerKeyId=root.issuer_key_id,publicKeyBase64=base64.b64encode(public(keys[purpose])).decode(),validFrom=NOW,validUntil=NOW+timedelta(hours=1))
        signed_bytes=old.canonical_shared_parent_certificate_signing_bytes(description,cert) if v3 else old.canonical_original_target_certificate_signing_bytes(plan,cert)
        cert_env_class=old.ModelSharedParentRiskSignedCertificateEnvelope if v3 else old.ModelOriginalTargetSignedCertificateEnvelope
        cert_env=cert_env_class(schemaVersion='aos.model-eval-shared-parent-signed-certificate-envelope/v3' if v3 else 'aos.model-eval-original-target-signed-certificate-envelope/v2',
            certificate=cert,signatureBase64=base64.b64encode(issuer.sign(signed_bytes)).decode())
        claim_class=old.ModelSharedParentRiskCaseSigningInput if v3 else old.ModelOriginalTargetCaseSigningInput
        extra={} if purpose=='target' else dict(targetClaimHash=canonical_hash(dump(target)),actualHash=sha(output),
            expectedHash=case['expectedHash'],passed=True,detailCode='synthetic-pass')
        claim=claim_class(schemaVersion='aos.model-eval-shared-parent-case-signing-input/v3' if v3 else 'aos.model-eval-original-target-case-signing-input/v2',
            **common,caseInputHash=case['inputHash'],inputHash=sha(wi),outputHash=sha(ou),occurredAt=at,**extra)
        payload_class=old.ModelSharedParentRiskCaseSignaturePayload if v3 else old.ModelOriginalTargetCaseSignaturePayload
        payload=payload_class(schemaVersion='aos.model-eval-shared-parent-case-signature-payload/v3' if v3 else 'aos.model-eval-original-target-case-signature-payload/v2',certificateHash=canonical_hash(dump(cert_env)),claim=claim)
        raw=old.canonical_shared_parent_signed_case_bytes(description,payload,input_bytes=wi,output_bytes=ou,target_envelope=target) if v3 else old.canonical_original_target_signed_case_bytes(plan,payload,input_bytes=wi,output_bytes=ou)
        env_class=old.ModelSharedParentRiskSignedCaseEnvelope if v3 else old.ModelOriginalTargetSignedCaseEnvelope
        env=env_class(schemaVersion='aos.model-eval-shared-parent-signed-case-envelope/v3' if v3 else 'aos.model-eval-original-target-signed-case-envelope/v2',payload=payload,signatureBase64=base64.b64encode(keys[purpose].sign(raw)).decode())
        return cert_env,env
    tc,te=leg('target',wire,output,NOW)
    witness=ModelLegacyProofWitness(targetCertificate=dump(tc),targetCase=dump(te),targetIssuer=dump(root),sharedRiskDescription=None if description is None else dump(description))
    if v3:
        judge_wire=old.build_shared_parent_target_judge_input(description,te,certificate_envelope=tc,issuer_input=root,
            checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset(),target_input_bytes=wire,target_output_bytes=output,expected_output=expected)
        jc,je=leg('judge',judge_wire,b'judge verdict',NOW+timedelta(seconds=1),te)
        full=witness.model_copy(update={'judge_certificate':dump(jc),'judge_case':dump(je),'judge_issuer':dump(root)})
    else:
        payload=dict(schemaVersion='aos.model-eval-original-target-judge-input/v2',tenant=plan['tenant'],executionId=plan['executionId'],
            manifestHash=canonical_hash(plan),judgeRequestHash=plan['judgeRequestHash'],caseId='case',judgeLeg=case['judge'],
            targetCaseHash=canonical_hash(dump(te)),targetCertificateHash=te.payload.certificate_hash,actualHash=sha(output),
            actualBase64=base64.b64encode(output).decode(),expectedHash=case['expectedHash'],
            expectedBase64=None if expected is None else base64.b64encode(expected).decode(),executionAllowed=False)
        judge_wire=json.dumps(payload,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode();full=witness
    return witness,full,judge_wire


def result_inputs(kind='route',*,with_expected=False):
    from aos_api.aip_model_runtime_store import canonical_hash
    artifact=b'original case Artifact';expected=b'expected result' if with_expected else None
    wire=b'actual target wire';output=b'actual target result'
    manifest,cert,root,sig,keys,issuer=certificate_inputs(kind,with_keys=True,artifact_input=artifact,expected_output=expected)
    body=json.loads(manifest.split(b'\n',1)[1]);tc=GovernedEvalSignedCertificate(certificate=cert,signatureBase64=sig)
    legacy,judge_legacy,judge_wire=(None,None,None) if kind=='route' else original_model_witness(kind,body,keys,issuer,wire,output,expected)
    args=dict(certificate_envelope=tc,issuer_input=root,checked_at=NOW+timedelta(seconds=2),revoked_identity_ids=frozenset(),
        input_bytes=wire,output_bytes=output,artifact_input_bytes=artifact,expected_output=expected,legacy_model_proof=legacy)
    common={k:v for k,v in dump(cert).items() if k in {'tenant','subjectKind','executionId','manifestHash','contextBindingHash','callBindingHash','caseId','purpose'}}
    claim=GovernedEvalCaseClaim(**common,certificateHash=canonical_hash(dump(tc)),caseInputHash=sha(artifact),expectedHash=None if expected is None else sha(expected),
        wireInputHash=sha(wire),outputHash=sha(output),occurredAt=NOW,legacyModelProofHash=None if legacy is None else canonical_hash(dump(legacy)))
    target=GovernedEvalSignedCase(claim=claim,signatureBase64=base64.b64encode(keys['target'].sign(canonical_governed_case_bytes(manifest,claim,**args))).decode())
    leg=next(c for c in body['routeApplication']['calls'] if c['purpose']=='judge') if kind=='route' else body['modelPlan']['cases'][0]['judge']
    jc=cert.model_copy(update={'purpose':'judge','call_binding_hash':governed_call_binding_hash(manifest,case_id='case',purpose='judge'),
        'identity_id':leg['identityId'],'identity_key_hash':leg['identityKeyHash'],'public_key_base64':base64.b64encode(public(keys['judge'])).decode(),
        'intent_ref':bref('GovernedEvalExecutionIntent','intent-judge') if kind=='route' else leg['intentRef'],
        'joint_admission_ref':bref('GovernedEvalJointAdmissionReceipt','joint-judge') if kind=='route' else leg['jointReceiptRef']})
    jcert=GovernedEvalSignedCertificate(certificate=jc,signatureBase64=base64.b64encode(issuer.sign(canonical_governed_certificate_bytes(manifest,jc))).decode())
    if kind=='route':judge_wire=build_governed_route_judge_input(manifest,target_envelope=target,target_certificate_envelope=tc,
        target_issuer_input=root,checked_at=args['checked_at'],revoked_identity_ids=frozenset(),target_input_bytes=wire,
        target_output_bytes=output,artifact_input_bytes=artifact,expected_output=expected)
    jargs={**args,'certificate_envelope':jcert,'input_bytes':judge_wire,'output_bytes':b'judge verdict','target_envelope':target,
        'target_certificate_envelope':tc,'target_issuer_input':root,'target_input_bytes':wire,'target_output_bytes':output,'legacy_model_proof':judge_legacy}
    jclaim=claim.model_copy(update={'purpose':'judge','call_binding_hash':jc.call_binding_hash,'certificate_hash':canonical_hash(dump(jcert)),
        'wire_input_hash':sha(judge_wire),'output_hash':sha(b'judge verdict'),'occurred_at':NOW+timedelta(seconds=1),
        'target_envelope_hash':canonical_hash(dump(target)),'target_output_hash':sha(output),'passed':True,'detail_code':'synthetic-pass',
        'legacy_model_proof_hash':None if judge_legacy is None else canonical_hash(dump(judge_legacy))})
    judge=GovernedEvalSignedCase(claim=jclaim,signatureBase64=base64.b64encode(keys['judge'].sign(canonical_governed_case_bytes(manifest,jclaim,**jargs))).decode())
    return manifest,target,args,judge,jargs


def presented_bundle_inputs(kind='route'):
    manifest,target,args,judge,jargs=result_inputs(kind,with_expected=True)
    target_item=PresentedRouteEvalCase(envelope=target,
        certificate_envelope=args['certificate_envelope'],issuer_input=args['issuer_input'],
        input_bytes=args['input_bytes'],output_bytes=args['output_bytes'],
        artifact_input_bytes=args['artifact_input_bytes'],expected_output=args['expected_output'])
    judge_item=PresentedRouteEvalCase(envelope=judge,
        certificate_envelope=jargs['certificate_envelope'],issuer_input=jargs['issuer_input'],
        input_bytes=jargs['input_bytes'],output_bytes=jargs['output_bytes'],
        artifact_input_bytes=jargs['artifact_input_bytes'],expected_output=jargs['expected_output'])
    return manifest,target_item,judge_item


def test_route_presented_bundle_requires_and_redacts_complete_target_judge_bytes():
    manifest,target,judge=presented_bundle_inputs()
    raw=prepare_route_eval_presented_case_bundle(manifest,checked_at=NOW+timedelta(seconds=2),
        revoked_identity_ids=frozenset(),cases=(target,judge))
    assert raw.startswith(b'AOS-ROUTE-EVAL-PRESENTED-CASE-BUNDLE-v1\n')
    body=json.loads(raw.split(b'\n',1)[1])
    assert body['executionAllowed'] is False and body['executionId']
    assert [(item['caseId'],item['passed']) for item in body['cases']]==[('case',True)]
    for secret in (target.input_bytes,target.output_bytes,target.artifact_input_bytes,
                   target.expected_output,judge.input_bytes,judge.output_bytes):
        assert secret not in raw


@pytest.mark.parametrize('fault',['missing_target','missing_judge','extra','duplicate','list','not_exact'])
def test_route_presented_bundle_requires_all_and_only_unique_exact_cases(fault):
    manifest,target,judge=presented_bundle_inputs();cases=(target,judge)
    if fault=='missing_target':cases=(judge,)
    elif fault=='missing_judge':cases=(target,)
    elif fault=='extra':cases=(target,judge,target)
    elif fault=='duplicate':cases=(target,target)
    elif fault=='list':cases=[target,judge]
    else:cases=(target,object())
    with pytest.raises(ValueError,match='ROUTE_EVAL_COMPLETE_PRESENTED_CASE_BUNDLE_REQUIRED'):
        prepare_route_eval_presented_case_bundle(manifest,checked_at=NOW+timedelta(seconds=2),
            revoked_identity_ids=frozenset(),cases=cases)


@pytest.mark.parametrize('fault',['target_output','target_certificate','judge_signature','revoked','naive_clock'])
def test_route_presented_bundle_rechecks_same_target_and_current_signature_snapshot(fault):
    manifest,target,judge=presented_bundle_inputs();at=NOW+timedelta(seconds=2);revoked=frozenset()
    if fault=='target_output':target=PresentedRouteEvalCase(**{**target.__dict__,'output_bytes':b'private wrong target'})
    elif fault=='target_certificate':target=PresentedRouteEvalCase(**{**target.__dict__,'certificate_envelope':judge.certificate_envelope})
    elif fault=='judge_signature':judge=PresentedRouteEvalCase(**{**judge.__dict__,'envelope':judge.envelope.model_copy(update={'signature_base64':base64.b64encode(bytes(64)).decode()})})
    elif fault=='revoked':revoked=frozenset([target.certificate_envelope.certificate.identity_id])
    else:at=at.replace(tzinfo=None)
    with pytest.raises(ValueError,match='ROUTE_EVAL_COMPLETE_PRESENTED_CASE_BUNDLE_REQUIRED') as error:
        prepare_route_eval_presented_case_bundle(manifest,checked_at=at,
            revoked_identity_ids=revoked,cases=(target,judge))
    assert 'private wrong target' not in str(error.value)


@pytest.mark.parametrize('kind',['model2','model3'])
def test_model_manifest_cannot_borrow_route_presented_bundle(kind):
    manifest,target,judge=presented_bundle_inputs(kind)
    with pytest.raises(ValueError,match='ROUTE_EVAL_COMPLETE_PRESENTED_CASE_BUNDLE_REQUIRED'):
        prepare_route_eval_presented_case_bundle(manifest,checked_at=NOW+timedelta(seconds=2),
            revoked_identity_ids=frozenset(),cases=(target,judge))


@pytest.mark.parametrize('kind',['route','model2','model3'])
@pytest.mark.parametrize('with_expected',[False,True])
def test_full_target_and_judge_signatures_keep_both_models_and_complete_route(kind,with_expected):
    manifest,target,args,judge,jargs=result_inputs(kind,with_expected=with_expected)
    assert validate_governed_case_signature(manifest,target,**args) is None
    assert validate_governed_case_signature(manifest,judge,**jargs) is None
    assert target.claim.case_input_hash!=target.claim.wire_input_hash
    assert b'allocat' not in manifest if kind=='model3' else True


@pytest.mark.parametrize('kind',['route','model2','model3'])
@pytest.mark.parametrize('fault',['bad_target_signature','bad_target_certificate','wrong_target_output','wrong_artifact','wrong_expected','wrong_wire','future','reverse','wrong_parent','extra','missing_legacy','old_risk'])
def test_complete_case_crypto_and_causal_input_reject_substitution(kind,fault):
    manifest,target,args,judge,jargs=result_inputs(kind,with_expected=True);bad=judge
    if fault=='bad_target_signature':jargs['target_envelope']=target.model_copy(update={'signature_base64':base64.b64encode(bytes(64)).decode()})
    elif fault=='bad_target_certificate':jargs['target_certificate_envelope']=args['certificate_envelope'].model_copy(update={'signature_base64':base64.b64encode(bytes(64)).decode()})
    elif fault=='wrong_target_output':jargs['target_output_bytes']=b'other'
    elif fault=='wrong_artifact':jargs['artifact_input_bytes']=b'other'
    elif fault=='wrong_expected':jargs['expected_output']=b'other'
    elif fault=='wrong_wire':jargs['input_bytes']=b'other'
    elif fault=='future':bad=judge.model_copy(update={'claim':judge.claim.model_copy(update={'occurred_at':NOW+timedelta(seconds=3)})})
    elif fault=='reverse':bad=judge.model_copy(update={'claim':judge.claim.model_copy(update={'occurred_at':NOW-timedelta(seconds=1)})})
    elif fault=='wrong_parent':bad=judge.model_copy(update={'claim':judge.claim.model_copy(update={'target_envelope_hash':'0'*64})})
    elif fault=='extra':bad=judge.model_copy(update={'claim':judge.claim.model_copy(update={'transportVerified':True})})
    elif fault=='missing_legacy':
        if kind=='route':jargs['legacy_model_proof']={'fabricated':True}
        else:jargs['legacy_model_proof']=None
    else:
        if kind=='route':bad=judge.model_copy(update={'claim':judge.claim.model_copy(update={'legacy_model_proof_hash':'a'*64})})
        else:jargs['legacy_model_proof']=jargs['legacy_model_proof'].model_copy(update={'target_case':{}})
    with pytest.raises(ValueError):validate_governed_case_signature(manifest,bad,**jargs)


@pytest.mark.parametrize('fault',['judge_dependency','wrong_wire','oversize','judge_verdict','wrong_signature','noncanonical_signature'])
def test_target_cannot_borrow_judge_or_ignore_raw_witnesses(fault):
    manifest,target,args,_,_=result_inputs();bad=target
    if fault=='judge_dependency':args['target_envelope']=target
    elif fault=='wrong_wire':args['input_bytes']=b'other'
    elif fault=='oversize':args['output_bytes']=b'x'*1048577
    elif fault=='judge_verdict':bad=target.model_copy(update={'claim':target.claim.model_copy(update={'passed':True})})
    elif fault=='wrong_signature':bad=target.model_copy(update={'signature_base64':base64.b64encode(bytes(64)).decode()})
    else:bad=target.model_copy(update={'signature_base64':target.signature_base64+'\n'})
    with pytest.raises(ValueError):validate_governed_case_signature(manifest,bad,**args)


@pytest.mark.parametrize('kind',['route','model2','model3'])
@pytest.mark.parametrize('fault',['self_consistent_wrong_judge_wire','target_issuer_revoked','target_identity_revoked','numeric_judge_verdict'])
def test_complete_judge_checks_reach_derivation_and_independent_target_currentness(kind,fault):
    manifest,target,args,judge,jargs=result_inputs(kind,with_expected=True);claim=judge.claim
    if fault=='self_consistent_wrong_judge_wire':
        jargs['input_bytes']=b'self-consistent fabricated wire';claim=claim.model_copy(update={'wire_input_hash':sha(jargs['input_bytes'])})
    elif fault=='target_issuer_revoked':jargs['target_issuer_input']=args['issuer_input'].model_copy(update={'revoked_at':NOW})
    elif fault=='target_identity_revoked':jargs['revoked_identity_ids']=frozenset([args['certificate_envelope'].certificate.identity_id])
    else:claim=claim.model_copy(update={'passed':1})
    with pytest.raises(ValueError):canonical_governed_case_bytes(manifest,claim,**jargs)


def test_route_target_cannot_resign_an_unapproved_wire_hash():
    manifest,target,args,_,_=result_inputs();args['input_bytes']=b'not the approved target wire'
    claim=target.claim.model_copy(update={'wire_input_hash':sha(args['input_bytes'])})
    with pytest.raises(ValueError,match='approved recipe'):canonical_governed_case_bytes(manifest,claim,**args)


@pytest.mark.parametrize('kind',['model2','model3'])
def test_model_target_cannot_erase_legacy_evidence_even_with_self_consistent_null_hash(kind):
    manifest,target,args,_,_=result_inputs(kind);args['legacy_model_proof']=None
    claim=target.claim.model_copy(update={'legacy_model_proof_hash':None})
    with pytest.raises(ValueError,match='original Model proof'):canonical_governed_case_bytes(manifest,claim,**args)
