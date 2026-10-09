"""An approved test application alone must never grant typed execution authority."""
import importlib
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_runtime_store import canonical_hash


def _certificate_input():
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    module, plan, _, _, _ = _signing_inputs()
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    body = plan.model_dump(mode='json', by_alias=True)
    body['cases'][0]['target']['identityKeyHash'] = hashlib.sha256(pub).hexdigest()
    plan = module.ModelEvalExecutionManifest.model_validate(body)
    cert = dict(schemaVersion='aos.model-eval-executor-certificate-signing-input/v1',
        tenant=body['tenant'], executionId=plan.execution_id,
        manifestHash=canonical_hash(plan.model_dump(mode='json', by_alias=True)),
        requestHash=plan.request_hash, caseId='case-1', purpose='target',
        candidateRef=plan.request.target_ref.model_dump(mode='json', by_alias=True),
        leg=plan.cases[0].target.model_dump(mode='json', by_alias=True),
        issuerId='isolated-issuer', issuerKeyId='isolated-issuer-key',
        publicKeyBase64=base64.b64encode(pub).decode(),
        validFrom=datetime(2026,10,8,tzinfo=timezone.utc),
        validUntil=datetime(2026,10,9,tzinfo=timezone.utc))
    return module, plan, cert, key


def _issuer_signature_inputs():
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    module, plan, cert, _ = _certificate_input()
    issuer = Ed25519PrivateKey.generate()
    root = dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',
        purpose='model-eval-execution', tenant=cert['tenant'],
        issuerId=cert['issuerId'], issuerKeyId=cert['issuerKeyId'],
        publicKeyBase64=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),
        validFrom=cert['validFrom'], validUntil=cert['validUntil'], revokedAt=None)
    signature = base64.b64encode(issuer.sign(module.canonical_model_certificate_signing_bytes(plan,cert))).decode()
    return plan, cert, root, signature


def test_model_certificate_signature_is_a_pure_necessary_check():
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    plan, cert, root, sig = _issuer_signature_inputs()
    assert reader.validate_model_certificate_signature(plan,cert,
        issuer_input=root,signature_base64=sig,checked_at=cert['validFrom'],
        revoked_identity_ids=frozenset()) is None


@pytest.mark.parametrize('change',['issuer','key','purpose','tenant','root_expired',
    'root_future','root_revoked','identity_revoked','certificate_end','naive_check',
    'signature','signature_length','root_key','tamper','root_interval','mutable_revocations','copied'])
def test_model_certificate_signature_rejects_invalid_crypto_or_currentness(change):
    import base64
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan, cert, root, sig = _issuer_signature_inputs()
    checked=cert['validFrom']; revoked=frozenset()
    if change=='issuer':root['issuerId']='other'
    elif change=='key':root['issuerKeyId']='other'
    elif change=='purpose':root['purpose']='eval-execution'
    elif change=='tenant':root['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    elif change=='root_expired':checked=root['validUntil']
    elif change=='root_future':root['validFrom']=checked+timedelta(seconds=1)
    elif change=='root_revoked':root['revokedAt']=checked
    elif change=='identity_revoked':revoked=frozenset([cert['leg']['identityId']])
    elif change=='certificate_end':checked=cert['validUntil']
    elif change=='naive_check':checked=checked.replace(tzinfo=None)
    elif change=='signature':sig=base64.b64encode(bytes(64)).decode()
    elif change=='signature_length':sig=base64.b64encode(bytes(63)).decode()
    elif change=='root_key':root['publicKeyBase64']=base64.b64encode(bytes(32)).decode()
    elif change=='tamper':cert['issuerKeyId']='tampered'
    elif change=='root_interval':root['validUntil']=root['validFrom']
    elif change=='mutable_revocations':revoked=set()
    elif change=='copied':root=module.ModelEvalIssuerVerificationInput.model_validate(root).model_copy(update={'purpose':'eval-execution'})
    with pytest.raises(ValueError):
        reader.validate_model_certificate_signature(plan,cert,issuer_input=root,
            signature_base64=sig,checked_at=checked,revoked_identity_ids=revoked)


def test_model_certificate_signing_input_has_separate_domain_and_real_signature():
    from cryptography.exceptions import InvalidSignature
    module, plan, cert, key = _certificate_input()
    raw = module.canonical_model_certificate_signing_bytes(plan, cert)
    assert raw.startswith(b'AOS-MODEL-EVAL-EXECUTOR-CERTIFICATE-SIGNING-INPUT-v1\n')
    sig = key.sign(raw)
    key.public_key().verify(sig, raw)
    with pytest.raises(InvalidSignature):
        key.public_key().verify(sig, raw.replace(b'AOS-MODEL-EVAL-EXECUTOR-CERTIFICATE-SIGNING-INPUT-v1', b'AOS-EVAL-EXECUTOR-CERTIFICATE-v1',1))
    with pytest.raises(InvalidSignature):
        key.public_key().verify(sig, module.canonical_model_certificate_signing_bytes(plan, cert | {'issuerKeyId':'another-key'}))


def test_model_certificate_judge_and_timezone_use_exact_independent_leg():
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    module, plan, cert, _ = _certificate_input()
    key = Ed25519PrivateKey.generate()
    pub = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    body = plan.model_dump(mode='json', by_alias=True)
    body['cases'][0]['judge']['identityKeyHash'] = hashlib.sha256(pub).hexdigest()
    plan = module.ModelEvalExecutionManifest.model_validate(body)
    cert = cert | dict(purpose='judge', leg=body['cases'][0]['judge'],
        publicKeyBase64=base64.b64encode(pub).decode(),
        manifestHash=canonical_hash(plan.model_dump(mode='json', by_alias=True)))
    raw = module.canonical_model_certificate_signing_bytes(plan, cert)
    shifted = cert | {'validFrom': cert['validFrom'].astimezone(timezone(timedelta(hours=8)))}
    assert module.canonical_model_certificate_signing_bytes(plan, shifted) == raw
    key.public_key().verify(key.sign(raw), raw)
    with pytest.raises(ValueError):
        module.canonical_model_certificate_signing_bytes(plan, cert | {'leg':body['cases'][0]['target']})


@pytest.mark.parametrize('change', ['schema','manifest','request','case','candidate','identity',
    'purpose','key_hash','key_length','base64','empty_interval','naive_time','issuer','extra','copied'])
def test_model_certificate_signing_input_rejects_unbound_or_invalid_input(change):
    module, plan, cert, _ = _certificate_input()
    if change=='schema': cert['schemaVersion']='aos.eval-executor-certificate/v1'
    elif change=='manifest': cert['manifestHash']='f'*64
    elif change=='request': cert['requestHash']='f'*64
    elif change=='case': cert['caseId']='other-case'
    elif change=='candidate': cert['candidateRef']=plan.request.source_ref.model_dump(mode='json',by_alias=True)
    elif change=='identity': cert['leg']=cert['leg'] | {'identityId':'other-identity'}
    elif change=='purpose': cert['purpose']='judge'
    elif change=='key_hash': cert['leg']=cert['leg'] | {'identityKeyHash':'f'*64}
    elif change=='key_length': cert['publicKeyBase64']='YQ=='
    elif change=='base64': cert['publicKeyBase64']+='\n'
    elif change=='empty_interval': cert['validUntil']=cert['validFrom']
    elif change=='naive_time': cert['validFrom']=datetime(2026,10,8)
    elif change=='issuer': cert['issuerId']=' '
    elif change=='extra': cert['executionAllowed']=True
    elif change=='copied':
        cert=module.ModelEvalExecutorCertificateSigningInput.model_validate(cert).model_copy(update={'issuer_id':' padded'})
    with pytest.raises(ValueError): module.canonical_model_certificate_signing_bytes(plan,cert)


def _signing_inputs():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _plan_body()
    input_bytes, output_bytes = b'case input', b'target output'
    body['cases'][0]['inputHash'] = hashlib.sha256(input_bytes).hexdigest()
    body['caseSetHash'] = canonical_hash([dict(caseId='case-1',
        inputHash=body['cases'][0]['inputHash'], expectedHash='e'*64)])
    manifest = module.ModelEvalExecutionManifest.model_validate(body)
    target = dict(schemaVersion='aos.model-eval-case-signing-input/v1',
        tenant=body['tenant'], executionId=body['executionId'],
        manifestHash=canonical_hash(manifest.model_dump(mode='json', by_alias=True)),
        requestHash=body['requestHash'], caseId='case-1', purpose='target',
        candidateRef=body['request']['targetRef'], leg=body['cases'][0]['target'],
        inputHash=hashlib.sha256(input_bytes).hexdigest(),
        outputHash=hashlib.sha256(output_bytes).hexdigest(),
        occurredAt=datetime(2026, 10, 8, tzinfo=timezone.utc))
    return module, manifest, target, input_bytes, output_bytes


def test_model_case_signing_input_binds_target_raw_bytes_and_independent_domain():
    module, manifest, body, inp, out = _signing_inputs()
    claim = module.ModelEvalCaseSigningInput.model_validate(body)
    raw = module.canonical_model_case_signing_bytes(manifest, claim,
        input_bytes=inp, output_bytes=out)
    assert raw.startswith(b'AOS-MODEL-EVAL-CASE-SIGNING-INPUT-v1\n')
    payload = json.loads(raw.split(b'\n', 1)[1])
    assert payload['candidateRef'] == manifest.request.target_ref.model_dump(mode='json', by_alias=True)
    assert payload['leg']['modelRef'] == manifest.request.source_ref.model_dump(mode='json', by_alias=True)


@pytest.mark.parametrize('change', ['manifest', 'request', 'candidate', 'leg', 'case', 'input', 'output'])
def test_model_case_signing_input_rejects_exact_binding_drift(change):
    module, manifest, body, inp, out = _signing_inputs()
    if change == 'manifest': body['manifestHash'] = 'f'*64
    elif change == 'request': body['requestHash'] = 'f'*64
    elif change == 'candidate': body['candidateRef'] = manifest.request.source_ref.model_dump(mode='json', by_alias=True)
    elif change == 'leg': body['leg'] = manifest.cases[0].target.model_dump(mode='json', by_alias=True) | {'identityId':'wrong-identity'}
    elif change == 'case': body['caseId'] = 'missing-case'
    elif change == 'input': inp = b'drift'
    elif change == 'output': out = b'drift'
    with pytest.raises(ValueError):
        module.canonical_model_case_signing_bytes(manifest,
            module.ModelEvalCaseSigningInput.model_validate(body), input_bytes=inp, output_bytes=out)


def _judge_signing_inputs():
    module, plan, body, inp, out = _signing_inputs()
    target = module.ModelEvalCaseSigningInput.model_validate(body)
    raw = module.canonical_model_case_signing_bytes(plan, target, input_bytes=inp, output_bytes=out)
    judge_in, judge_out = b'original judge input', b'original judge output'
    judge = body | dict(purpose='judge', leg=plan.cases[0].judge.model_dump(mode='json', by_alias=True),
        inputHash=hashlib.sha256(judge_in).hexdigest(), outputHash=hashlib.sha256(judge_out).hexdigest(),
        targetClaimHash=hashlib.sha256(raw).hexdigest(), actualHash=target.output_hash,
        expectedHash=plan.cases[0].expected_hash, passed=False, detailCode='synthetic-mismatch',
        occurredAt=target.occurred_at + timedelta(seconds=1))
    return module, plan, target, judge, judge_in, judge_out


def test_model_case_signing_input_judge_binds_complete_target_and_preserves_false():
    module, plan, target, judge, inp, out = _judge_signing_inputs()
    raw = module.canonical_model_case_signing_bytes(plan, judge,
        input_bytes=inp, output_bytes=out, target_claim=target)
    payload = json.loads(raw.split(b'\n', 1)[1])
    assert payload['passed'] is False
    assert payload['leg']['identityId'] != target.leg.identity_id


@pytest.mark.parametrize('change', ['target_hash', 'actual', 'expected', 'past',
    'passed_integer', 'missing_target', 'copied_target', 'copied_plan', 'naive_time', 'raw_input'])
def test_model_case_signing_input_judge_rejects_detached_or_bypassed_target(change):
    module, plan, target, judge, inp, out = _judge_signing_inputs()
    if change == 'target_hash': judge['targetClaimHash'] = 'f'*64
    elif change == 'actual': judge['actualHash'] = 'f'*64
    elif change == 'expected': judge['expectedHash'] = 'f'*64
    elif change == 'past': judge['occurredAt'] = target.occurred_at - timedelta(seconds=1)
    elif change == 'passed_integer': judge['passed'] = 0
    elif change == 'missing_target': target = None
    elif change == 'copied_target': target = target.model_copy(update={'purpose':'judge'})
    elif change == 'copied_plan': plan = plan.model_copy(update={'execution_allowed': True})
    elif change == 'naive_time': judge['occurredAt'] = datetime(2026, 10, 8)
    elif change == 'raw_input': inp = bytearray(inp)
    with pytest.raises(ValueError):
        module.canonical_model_case_signing_bytes(plan, judge,
            input_bytes=inp, output_bytes=out, target_claim=target)


def test_model_case_signing_input_ephemeral_signature_cannot_cross_skill_domain():
    # Pure cryptographic experiment, no installed identity, root or authority.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.exceptions import InvalidSignature
    module, plan, target, judge, inp, out = _judge_signing_inputs()
    raw = module.canonical_model_case_signing_bytes(plan, judge,
        input_bytes=inp, output_bytes=out, target_claim=target)
    key = Ed25519PrivateKey.generate()
    signature = key.sign(raw)
    key.public_key().verify(signature, raw)
    payload = raw.split(b'\n', 1)[1]
    with pytest.raises(InvalidSignature):
        key.public_key().verify(signature, b'AOS-EVAL-EXECUTION-RECEIPT-v1\n'+payload)
    changed = json.loads(payload)
    changed['passed'] = True
    tampered = b'AOS-MODEL-EVAL-CASE-SIGNING-INPUT-v1\n' + json.dumps(changed,
        ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    with pytest.raises(InvalidSignature):
        key.public_key().verify(signature, tampered)


def test_original_approved_request_without_joint_and_judge_is_not_execution_manifest():
    # Frozen from the original isolated maker/checker application, not an invented
    # ordinary Task or synthetic new Provider permission.
    path = Path(__file__).resolve().parents[4] / '.evidence/gt-model-typed-proof-20261008/original-request-frozen.json'
    frozen = json.loads(path.read_text())
    original = ModelEvalRequestCreate.model_validate(frozen['request_json'])
    assert canonical_hash(original.model_dump(mode='json', by_alias=True)) == frozen['request_hash']
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    # Missing independent Judge, Source/physical/unique Intent and per-leg fees
    # must be a strict rejection, even though this original application parsed.
    with pytest.raises(ValidationError):
        module.ModelEvalExecutionManifest.model_validate({
            'schemaVersion': 1, 'tenant': original.tenant.model_dump(mode='json', by_alias=True),
            'requestId': frozen['request_id'], 'requestHash': frozen['request_hash'],
            'request': original.model_dump(mode='json', by_alias=True),
        })


def _plan_body():
    frozen = json.loads((Path(__file__).resolve().parents[4] / '.evidence/gt-model-typed-proof-20261008/original-request-frozen.json').read_text())
    request = frozen['request_json']
    def asset(kind, name):
        return dict(assetType=kind, assetId=name, revision=1, contentHash='a'*64)
    def fact(kind, name):
        return dict(resourceType=kind, resourceId=name, revision=1, contentHash='sha256:'+'a'*64)
    def leg(purpose):
        # All proof refs below are explicit synthetic plans, never held facts.
        return dict(tenant=request['tenant'], purpose=purpose, modelRef=request['sourceRef'],
            providerRef=request['providerRef'], priceRef=request['priceRef'],
            quotaPolicyRef=request['quotaPolicyRef'], budgetPolicyRef=request['budgetPolicyRef'],
            sourceRef=asset('ProviderCapacitySourceRevision', purpose+'-source'),
            physicalAccountRef=asset('ProviderPhysicalAccountCandidateRevision', 'shared-account'),
            approvalRef=fact('ActionApprovalEvent', purpose+'-approval'),
            budgetHoldRef=fact('ModelEvalBudgetReservation', purpose+'-hold'),
            budgetAllocationRef=fact('ModelEvalBudgetAllocation', purpose+'-allocation'),
            allocationUpperBoundMinor=1,
            jointReceiptRef=fact('ModelEvalJointAdmissionReceipt', purpose+'-joint'),
            intentRef=fact('ModelEvalExecutionIntent', purpose+'-intent'),
            identityId=purpose+'-identity', identityKeyHash=('b' if purpose=='target' else 'c')*64,
            attempt=1)
    case=dict(caseId='case-1', inputHash='d'*64, expectedHash='e'*64,
              target=leg('target'), judge=leg('judge'))
    return dict(schemaVersion=1, tenant=request['tenant'], executionId='test-plan',
        requestId=frozen['request_id'], requestHash=frozen['request_hash'], request=request,
        parentBudgetLimits=[dict(parentHoldRef=case[p]['budgetHoldRef'],
            requestId=frozen['request_id'] if p=='target' else 'judge-independent-request',
            requestHash=frozen['request_hash'] if p=='target' else 'a'*64,
            approvalRef=case[p]['approvalRef'],budgetPolicyRef=case[p]['budgetPolicyRef'],priceRef=case[p]['priceRef'],
            currency='CNY',upperBoundMinor=request['upperBoundMinor']) for p in ('target','judge')],
        cases=[case], caseSetHash=canonical_hash([dict(caseId='case-1',inputHash='d'*64,expectedHash='e'*64)]),
        executionAllowed=False)


def test_descriptive_plan_roundtrip_preserves_shared_policy_without_granting_execution():
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body=_plan_body();plan=module.ModelEvalExecutionManifest.model_validate(body)
    assert plan.execution_allowed is False
    assert module.ModelEvalExecutionManifest.model_validate(plan.model_dump(mode='json',by_alias=True))==plan


@pytest.mark.parametrize('field', ['executionId', 'requestId', 'caseId'])
@pytest.mark.parametrize('value', [' ', ' padded', 'padded '])
def test_plan_identifiers_are_exact_without_implicit_normalization(field, value):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _plan_body()
    if field == 'caseId':
        body['cases'][0][field] = value
        body['caseSetHash'] = canonical_hash([
            dict(caseId=value, inputHash='d'*64, expectedHash='e'*64)])
    else:
        body[field] = value
    with pytest.raises(ValidationError, match='exact nonempty identifier required'):
        module.ModelEvalExecutionManifest.model_validate(body)


@pytest.mark.parametrize('field', ['execution_id', 'request_id', 'case_id'])
def test_copied_plan_cannot_bypass_exact_identifier_validation(field):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan = module.ModelEvalExecutionManifest.model_validate(_plan_body())
    if field == 'case_id':
        case = plan.cases[0].model_copy(update={'case_id': ' case-1'})
        altered = plan.model_copy(update={'cases': [case], 'case_set_hash': canonical_hash([
            dict(caseId=' case-1', inputHash='d'*64, expectedHash='e'*64)])})
    else:
        altered = plan.model_copy(update={field: ' padded'})
    with pytest.raises(ValidationError, match='exact nonempty identifier required'):
        module.ModelEvalExecutionManifest.model_validate(altered)


@pytest.mark.parametrize('change', ['request_hash','tenant','input_hash','duplicate_case','identity','key','approval','hold','intent','price','source_kind','execution'])
def test_plan_rejects_unbound_or_borrowed_authority(change):
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body=_plan_body();case=body['cases'][0];target=case['target'];judge=case['judge']
    if change=='request_hash':body['requestHash']='f'*64
    elif change=='tenant':body['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    elif change=='input_hash':case['inputHash']='f'*64
    elif change=='duplicate_case':body['cases'].append(case)
    elif change=='identity':judge['identityId']=target['identityId']
    elif change=='key':judge['identityKeyHash']=target['identityKeyHash']
    elif change=='approval':judge['approvalRef']=target['approvalRef']
    elif change=='hold':judge['budgetHoldRef']=target['budgetHoldRef']
    elif change=='intent':judge['intentRef']=target['intentRef']
    elif change=='price':target['priceRef']={**target['priceRef'],'contentHash':'f'*64}
    elif change=='source_kind':judge['sourceRef']['assetType']='EvidenceBundleRevision'
    elif change=='execution':body['executionAllowed']=True
    with pytest.raises(ValidationError):module.ModelEvalExecutionManifest.model_validate(body)


@pytest.mark.parametrize('field', ['schemaVersion','attempt','executionAllowed'])
def test_plan_control_fields_do_not_coerce_boolean_or_integer(field):
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body=_plan_body()
    if field=='attempt':body['cases'][0]['target']['attempt']=True
    elif field=='executionAllowed':body[field]=0
    else:body[field]=True
    with pytest.raises(ValidationError):module.ModelEvalExecutionManifest.model_validate(body)


@pytest.mark.parametrize('change', ['manifest_version','manifest_allowed','leg_attempt','leg_key','source_hash','source_id'])
def test_copied_typed_instances_cannot_skip_nested_validation(change):
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan=module.ModelEvalExecutionManifest.model_validate(_plan_body())
    if change=='manifest_version':altered=plan.model_copy(update={'schema_version':True})
    elif change=='manifest_allowed':altered=plan.model_copy(update={'execution_allowed':0})
    else:
        case=plan.cases[0];leg=case.judge
        if change=='leg_attempt':leg=leg.model_copy(update={'attempt':True})
        elif change=='leg_key':leg=leg.model_copy(update={'identity_key_hash':'not-a-digest'})
        else:
            ref=leg.source_ref.model_copy(update={'content_hash':'not-a-digest'} if change=='source_hash' else {'asset_id':''})
            leg=leg.model_copy(update={'source_ref':ref})
        altered=plan.model_copy(update={'cases':[case.model_copy(update={'judge':leg})]})
    with pytest.raises(ValidationError):module.ModelEvalExecutionManifest.model_validate(altered)


def test_copied_unknown_proof_fields_are_rejected_instead_of_discarded():
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan=module.ModelEvalExecutionManifest.model_validate(_plan_body())
    changed=plan.model_copy(update={'unregistered_proof':{'executionAllowed':True}})
    with pytest.raises(ValidationError, match='Extra inputs'):
        module.ModelEvalExecutionManifest.model_validate(changed)


def test_typed_plan_revalidation_preserves_existing_exact_inputs():
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan=module.ModelEvalExecutionManifest.model_validate(_plan_body())
    rebuilt=module.ModelEvalExecutionManifest.model_validate(plan)
    assert rebuilt==plan and rebuilt is not plan
    assert rebuilt.cases[0].judge is not plan.cases[0].judge


@pytest.mark.parametrize('change', ['short', 'newline', 'padbits', 'extra', 'copied'])
def test_signed_certificate_envelope_rejects_noncanonical_or_unchecked_input(change):
    from aos_api.aip_model_eval_execution_contracts import ModelEvalSignedCertificateEnvelope
    _, cert, _, signature = _issuer_signature_inputs()
    body = dict(schemaVersion='aos.model-eval-signed-certificate-envelope/v1',
                certificate=cert, signatureBase64=signature)
    envelope = ModelEvalSignedCertificateEnvelope.model_validate(body)
    assert envelope.signature_base64 == signature
    if change == 'short': body['signatureBase64'] = signature[:-4]
    elif change == 'newline': body['signatureBase64'] = signature + '\n'
    elif change == 'padbits':
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        index = alphabet.index(signature[-3])
        body['signatureBase64'] = signature[:-3] + alphabet[index + 1] + '=='
    elif change == 'extra': body['trusted'] = True
    else: body = envelope.model_copy(update={'trusted': True})
    with pytest.raises(ValueError): ModelEvalSignedCertificateEnvelope.model_validate(body)


def _signed_model_case_fixture():
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    module, original, _, inp, out = _signing_inputs()
    keys = {purpose: Ed25519PrivateKey.generate() for purpose in ('target', 'judge')}
    issuer = Ed25519PrivateKey.generate()
    def public(key): return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    body = original.model_dump(mode='json', by_alias=True)
    for purpose in keys: body['cases'][0][purpose]['identityKeyHash'] = hashlib.sha256(public(keys[purpose])).hexdigest()
    plan = module.ModelEvalExecutionManifest.model_validate(body)
    start = datetime(2026, 10, 8, tzinfo=timezone.utc)
    root = dict(schemaVersion='aos.model-eval-issuer-verification-input/v1', purpose='model-eval-execution',
        tenant=body['tenant'], issuerId='case-issuer', issuerKeyId='case-key',
        publicKeyBase64=base64.b64encode(public(issuer)).decode(), validFrom=start, validUntil=start+timedelta(days=1), revokedAt=None)
    certs, envelopes, claims, raw = {}, {}, {}, {}
    for purpose in ('target', 'judge'):
        cert = dict(schemaVersion='aos.model-eval-executor-certificate-signing-input/v1', tenant=body['tenant'],
            executionId=plan.execution_id, manifestHash=canonical_hash(plan.model_dump(mode='json', by_alias=True)),
            requestHash=plan.request_hash, caseId='case-1', purpose=purpose, candidateRef=plan.request.target_ref,
            leg=getattr(plan.cases[0], purpose), issuerId='case-issuer', issuerKeyId='case-key',
            publicKeyBase64=base64.b64encode(public(keys[purpose])).decode(), validFrom=start, validUntil=start+timedelta(days=1))
        certs[purpose] = module.ModelEvalSignedCertificateEnvelope.model_validate(dict(
            schemaVersion='aos.model-eval-signed-certificate-envelope/v1',certificate=cert,
            signatureBase64=base64.b64encode(issuer.sign(module.canonical_model_certificate_signing_bytes(plan, cert))).decode()))
        raw[purpose] = (inp, out) if purpose == 'target' else (b'judge input', b'judge output')
        claim = dict(schemaVersion='aos.model-eval-case-signing-input/v1', tenant=body['tenant'], executionId=plan.execution_id,
            manifestHash=cert['manifestHash'], requestHash=plan.request_hash, caseId='case-1', purpose=purpose,
            candidateRef=plan.request.target_ref, leg=getattr(plan.cases[0],purpose), inputHash=hashlib.sha256(raw[purpose][0]).hexdigest(),
            outputHash=hashlib.sha256(raw[purpose][1]).hexdigest(), occurredAt=start+timedelta(minutes=1 if purpose=='target' else 2))
        if purpose=='judge':
            target_bytes=module.canonical_model_case_signing_bytes(plan,claims['target'], input_bytes=inp,output_bytes=out)
            claim.update(targetClaimHash=hashlib.sha256(target_bytes).hexdigest(),actualHash=claims['target'].output_hash,
                expectedHash=plan.cases[0].expected_hash,passed=False,detailCode='isolated-mismatch')
        claims[purpose]=module.ModelEvalCaseSigningInput.model_validate(claim)
        payload=module.ModelEvalCaseSignaturePayload.model_validate(dict(schemaVersion='aos.model-eval-case-signature-payload/v1',
            certificateHash=canonical_hash(certs[purpose].model_dump(mode='json',by_alias=True)),claim=claims[purpose]))
        signed=module.canonical_model_signed_case_bytes(plan,payload,input_bytes=raw[purpose][0],output_bytes=raw[purpose][1],
            target_claim=claims.get('target') if purpose=='judge' else None)
        envelopes[purpose]=module.ModelEvalSignedCaseEnvelope.model_validate(dict(schemaVersion='aos.model-eval-signed-case-envelope/v1',
            payload=payload,signatureBase64=base64.b64encode(keys[purpose].sign(signed)).decode()))
    return module,plan,root,certs,envelopes,claims,raw,keys


@pytest.mark.parametrize('purpose', ['target','judge'])
def test_model_signed_case_actual_executor_signature_necessary_check(purpose):
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    _,plan,root,certs,envelopes,claims,raw,_=_signed_model_case_fixture()
    assert reader.validate_model_case_signature(plan,envelopes[purpose],certificate_envelope=certs[purpose],issuer_input=root,
        checked_at=datetime(2026,10,8,0,10,tzinfo=timezone.utc),revoked_identity_ids=frozenset(),
        input_bytes=raw[purpose][0],output_bytes=raw[purpose][1],target_claim=claims['target'] if purpose=='judge' else None) is None


@pytest.mark.parametrize('change', ['signature','input','output','certificate_hash','case','leg','future','expired','revoked','judge_target','certificate_swap','wrong_key','old_domain','past_time','copied_extra'])
def test_model_signed_case_rejects_resigned_semantic_drift(change):
    import base64
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    module,plan,root,certs,envelopes,claims,raw,keys=_signed_model_case_fixture()
    purpose='judge' if change=='judge_target' else 'target'
    envelope=envelopes[purpose].model_dump(mode='json',by_alias=True)
    kwargs=dict(certificate_envelope=certs[purpose],issuer_input=root,
        checked_at=datetime(2026,10,8,0,10,tzinfo=timezone.utc),revoked_identity_ids=frozenset(),
        input_bytes=raw[purpose][0],output_bytes=raw[purpose][1],target_claim=claims['target'] if purpose=='judge' else None)
    if change=='signature': envelope['signatureBase64']=base64.b64encode(bytes(64)).decode()
    elif change=='input': kwargs['input_bytes']=b'borrowed input'
    elif change=='output': kwargs['output_bytes']=b'borrowed output'
    elif change=='revoked': kwargs['revoked_identity_ids']=frozenset([claims[purpose].leg.identity_id])
    elif change=='expired': kwargs['checked_at']=datetime(2026,10,9,tzinfo=timezone.utc)
    elif change=='certificate_swap': kwargs['certificate_envelope']=certs['judge']
    elif change in ('wrong_key','old_domain'):
        signing=module.canonical_model_signed_case_bytes(plan,envelopes[purpose].payload,
            input_bytes=raw[purpose][0],output_bytes=raw[purpose][1])
        if change=='old_domain': signing=module.canonical_model_case_signing_bytes(plan,claims[purpose],
            input_bytes=raw[purpose][0],output_bytes=raw[purpose][1])
        envelope['signatureBase64']=base64.b64encode(keys['judge' if change=='wrong_key' else purpose].sign(signing)).decode()
    elif change=='copied_extra': envelope=envelopes[purpose].model_copy(update={'trusted':True})
    else:
        if change=='certificate_hash': envelope['payload']['certificateHash']='f'*64
        elif change=='case': envelope['payload']['claim']['caseId']='borrowed'
        elif change=='leg': envelope['payload']['claim']['leg']['identityId']='borrowed'
        elif change=='future': envelope['payload']['claim']['occurredAt']='2026-10-08T00:11:00Z'
        elif change=='past_time': envelope['payload']['claim']['occurredAt']='2026-10-07T23:59:59Z'
        elif change=='judge_target': envelope['payload']['claim']['targetClaimHash']='f'*64
        # Re-sign mutated typed payload without using binding helper: rejection
        # must come from semantics, not merely a now-invalid signature.
        payload=module.ModelEvalCaseSignaturePayload.model_validate(envelope['payload'])
        signed=b'AOS-MODEL-EVAL-SIGNED-CASE-v1\n'+json.dumps(payload.model_dump(mode='json',by_alias=True),sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
        envelope['signatureBase64']=base64.b64encode(keys[purpose].sign(signed)).decode()
    with pytest.raises(ValueError):reader.validate_model_case_signature(plan,envelope,**kwargs)


def _allocation_plan_body():
    import copy
    body=_plan_body()
    # Keep parent mutations separate from leg/request fields, so semantic
    # negatives cannot pass merely because they also changed the request hash.
    body['parentBudgetLimits']=copy.deepcopy(body['parentBudgetLimits'])
    # Add a second call under the same application-level holds.
    body.setdefault('parentBudgetLimits',[])
    for leg in (body['cases'][0]['target'],body['cases'][0]['judge']):
        purpose=leg['purpose']
        leg.setdefault('budgetAllocationRef',dict(resourceType='ModelEvalBudgetAllocation',resourceId=purpose+'-allocation',revision=1,contentHash='sha256:'+'a'*64))
        leg.setdefault('allocationUpperBoundMinor',1)
        if not body['parentBudgetLimits'] or len(body['parentBudgetLimits'])<2:
            body['parentBudgetLimits'].append(dict(parentHoldRef=leg['budgetHoldRef'],requestId=body['requestId'] if purpose=='target' else 'judge-independent-request',requestHash=body['requestHash'] if purpose=='target' else 'a'*64,
                approvalRef=leg['approvalRef'],budgetPolicyRef=leg['budgetPolicyRef'],priceRef=leg['priceRef'],currency='CNY',upperBoundMinor=body['request']['upperBoundMinor']))
    case=copy.deepcopy(body['cases'][0]);case['caseId']='case-2'
    for leg in (case['target'],case['judge']):
        for field in ('intentRef','budgetAllocationRef','jointReceiptRef'):leg[field]['resourceId']+='-2'
    body['cases'].append(case);body['caseSetHash']=canonical_hash([dict(caseId=x['caseId'],inputHash=x['inputHash'],expectedHash=x['expectedHash']) for x in body['cases']]);return body


def test_multi_case_shares_request_parent_hold_with_unique_allocations():
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan=module.ModelEvalExecutionManifest.model_validate(_allocation_plan_body())
    assert plan.cases[0].target.budget_hold_ref==plan.cases[1].target.budget_hold_ref
    assert plan.cases[0].target.budget_allocation_ref!=plan.cases[1].target.budget_allocation_ref
    assert plan.execution_allowed is False


@pytest.mark.parametrize('change',['duplicate_allocation','over_limit','amount_bool','wrong_kind','missing_parent','unused_parent','approval','request','request_hash','price','borrow_judge_parent','parent_bool','approved_limit','missing_allocation'])
def test_multi_case_parent_allocation_rejects_drift(change):
    import copy
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts');body=_allocation_plan_body()
    target=body['cases'][0]['target'];other=body['cases'][1]['target'];parent=body['parentBudgetLimits'][0]
    if change=='duplicate_allocation':other['budgetAllocationRef']=target['budgetAllocationRef']
    elif change=='over_limit':target['allocationUpperBoundMinor']=parent['upperBoundMinor'];other['allocationUpperBoundMinor']=1
    elif change=='amount_bool':target['allocationUpperBoundMinor']=True
    elif change=='wrong_kind':target['budgetAllocationRef']['resourceType']='ModelEvalBudgetReservation'
    elif change=='missing_parent':body['parentBudgetLimits']=body['parentBudgetLimits'][1:]
    elif change=='unused_parent':
        extra=copy.deepcopy(parent);extra['parentHoldRef']['resourceId']='unused';extra['requestId']='unused';extra['approvalRef']['resourceId']='unused';body['parentBudgetLimits'].append(extra)
    elif change=='approval':parent['approvalRef']['resourceId']='borrowed'
    elif change=='request':parent['requestId']='borrowed'
    elif change=='request_hash':parent['requestHash']='f'*64
    elif change=='price':parent['priceRef']['contentHash']='f'*64
    elif change=='borrow_judge_parent':body['cases'][0]['judge']['budgetHoldRef']=target['budgetHoldRef']
    elif change=='parent_bool':parent['upperBoundMinor']=True
    elif change=='approved_limit':parent['upperBoundMinor']=body['request']['upperBoundMinor']+1
    elif change=='missing_allocation':del target['budgetAllocationRef']
    with pytest.raises(ValueError):module.ModelEvalExecutionManifest.model_validate(body)


@pytest.mark.parametrize('purpose',['target','judge'])
@pytest.mark.parametrize('identity',[' ',' target-identity','target-identity ','\u3000identity','identity\u00a0'])
def test_model_execution_identity_ids_require_exact_revocation_keys(purpose,identity):
    module,plan,_,_,_=_signing_inputs()
    body=plan.model_dump(mode='json',by_alias=True)
    body['cases'][0][purpose]['identityId']=identity
    with pytest.raises(ValidationError,match='exact execution identity'):
        module.ModelEvalExecutionManifest.model_validate(body)
    # Signing byte builders must revalidate copied nested typed values too.
    leg=getattr(plan.cases[0],purpose).model_copy(update={'identity_id':identity})
    with pytest.raises(ValidationError,match='exact execution identity'):
        module.ModelEvalExecutionLeg.model_validate(leg)


@pytest.mark.parametrize('change',['case','target_epoch_bool','judge_epoch_zero','input_text','output_mutable','extra','typed_copy'])
def test_whole_case_witnesses_are_strict_and_non_authorizing(change):
    module=importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    binding=dict(caseHash='a'*64,certificateHash='b'*64,rootHash='c'*64,rootEpoch=1,certificateEpoch=1)
    body=dict(caseId='case-1',targetBinding=binding,judgeBinding=binding,
        targetIdentityEpoch=1,judgeIdentityEpoch=1,targetInput=b'input',targetOutput=b'output',judgeInput=b'judge',judgeOutput=b'result')
    assert module.ModelEvalPersistedCaseInput.model_validate(body).case_id=='case-1'
    if change=='case':body['caseId']=' padded'
    elif change=='target_epoch_bool':body['targetIdentityEpoch']=True
    elif change=='judge_epoch_zero':body['judgeIdentityEpoch']=0
    elif change=='input_text':body['targetInput']='input'
    elif change=='output_mutable':body['judgeOutput']=bytearray(b'result')
    elif change=='extra':body['executionAllowed']=True
    elif change=='typed_copy':body=module.ModelEvalPersistedCaseInput.model_validate(body).model_copy(update={'judge_identity_epoch':True})
    with pytest.raises(ValidationError):module.ModelEvalPersistedCaseInput.model_validate(body)


def _judge_parent_body():
    body = dict(_plan_body()['parentBudgetLimits'][1])
    body.update(schemaVersion='aos.model-judge-parent-budget/v1',
                purpose='model-judge-call', tenant={'orgId': 'org-org', 'projectId': 'dev-project'},
                executionAllowed=False)
    body['parentHoldRef'] = {**body['parentHoldRef'], 'resourceType': 'ModelJudgeBudgetReservation'}
    return body


def test_judge_parent_declaration_is_separate_and_nonexecuting():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _judge_parent_body()
    parent = module.ModelJudgeParentBudgetLimit.model_validate(body)
    assert parent.model_dump(mode='json', by_alias=True) == body
    with pytest.raises(ValidationError):
        module.ModelEvalParentBudgetLimit.model_validate(body)
    manifest = _plan_body()
    manifest['parentBudgetLimits'][1] = body
    with pytest.raises(ValidationError):
        module.ModelEvalExecutionManifest.model_validate(manifest)


@pytest.mark.parametrize('change', ['quality_purpose', 'old_hold', 'wrong_approval',
    'wrong_policy', 'wrong_price', 'hold_revision_bool', 'hold_revision_two',
    'empty_request', 'space_request', 'amount_bool', 'amount_text', 'amount_zero',
    'execute_true', 'execute_zero', 'execute_text', 'permit', 'missing_purpose',
    'wrong_schema', 'missing_tenant', 'request_hash'])
def test_judge_parent_rejects_cross_purpose_or_unvalidated_declaration(change):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _judge_parent_body()
    if change == 'quality_purpose': body['purpose'] = 'quality-eval'
    elif change == 'old_hold': body['parentHoldRef']['resourceType'] = 'ModelEvalBudgetReservation'
    elif change == 'wrong_approval': body['approvalRef']['resourceType'] = 'ModelJudgeBudgetReservation'
    elif change == 'wrong_policy': body['budgetPolicyRef']['assetType'] = 'QuotaPolicyRevision'
    elif change == 'wrong_price': body['priceRef']['assetType'] = 'RegisteredModelRevision'
    elif change == 'hold_revision_bool': body['parentHoldRef']['revision'] = True
    elif change == 'hold_revision_two': body['parentHoldRef']['revision'] = 2
    elif change == 'empty_request': body['requestId'] = ' '
    elif change == 'space_request': body['requestId'] = ' '+body['requestId']
    elif change == 'amount_bool': body['upperBoundMinor'] = True
    elif change == 'amount_text': body['upperBoundMinor'] = '10'
    elif change == 'amount_zero': body['upperBoundMinor'] = 0
    elif change == 'execute_true': body['executionAllowed'] = True
    elif change == 'execute_zero': body['executionAllowed'] = 0
    elif change == 'execute_text': body['executionAllowed'] = 'false'
    elif change == 'permit': body['permit'] = True
    elif change == 'missing_purpose': del body['purpose']
    elif change == 'wrong_schema': body['schemaVersion'] = 1
    elif change == 'missing_tenant': del body['tenant']
    elif change == 'request_hash': body['requestHash'] = 'sha256:'+'a'*64
    with pytest.raises(ValidationError):
        module.ModelJudgeParentBudgetLimit.model_validate(body)


def test_judge_parent_revalidates_nested_model_copy():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    parent = module.ModelJudgeParentBudgetLimit.model_validate(_judge_parent_body())
    copied = parent.model_copy(update={'parent_hold_ref': parent.parent_hold_ref.model_copy(
        update={'resource_type': 'ModelEvalBudgetReservation'})})
    with pytest.raises(ValidationError):
        module.ModelJudgeParentBudgetLimit.model_validate(copied)


def _server_judge_preparation():
    path=Path(__file__).resolve().parents[4]/'.evidence/gt-judge-call-authority-20261008/judge-owner-prepare-wait-r2-native-proof.json'
    return json.loads(path.read_text())['judge_owner_preparation']['preparation']


def test_original_judge_preparation_requires_matching_current_parent_declaration():
    from aos_api.aip_model_eval_execution_owner import ModelJudgeApplicationPreparation
    body=_server_judge_preparation()
    parsed=ModelJudgeApplicationPreparation.model_validate(body)
    assert parsed.model_dump(mode='json',by_alias=True)==body
    # Presented preparation remains nonexecuting even when its hash is correct.
    assert parsed.execution_allowed is False


@pytest.mark.parametrize('fault',['hash','request_id','parent_hash','parent_request','parent_amount',
    'false_zero','false_text','extra','naive','expired','policy','price','missing_expiry'])
def test_judge_preparation_rejects_copied_or_rehashed_inconsistent_facts(fault):
    from aos_api.aip_model_eval_execution_owner import ModelJudgeApplicationPreparation
    body=_server_judge_preparation()
    if fault=='hash':body['requestHash']='0'*64
    elif fault=='request_id':body['requestId']=' '+body['requestId']
    elif fault=='parent_hash':body['parentLimit']['requestHash']='0'*64
    elif fault=='parent_request':body['parentLimit']['requestId']='other-request'
    elif fault=='parent_amount':body['parentLimit']['upperBoundMinor']+=1
    elif fault=='false_zero':body['executionAllowed']=0
    elif fault=='false_text':body['executionAllowed']='false'
    elif fault=='extra':body['dispatchAllowed']=True
    elif fault=='naive':body['checkedAt']='2026-10-08T00:00:00'
    elif fault=='expired':body['checkedAt']=body['request']['expiresAt']
    else:
        if fault=='missing_expiry':del body['request']['expiresAt']
        else:body['request']['judgeGovernanceApplication']['request']['budgetPolicyRef' if fault=='policy' else 'priceRef']['contentHash']='0'*64
        # Hash equality cannot replace exact governance/expiry consistency.
        body['requestHash']=canonical_hash(body['request'])
        body['parentLimit']['requestHash']=body['requestHash']
    parsed=ModelJudgeApplicationPreparation.model_construct(**{k:v for k,v in body.items()})
    if fault=='extra':parsed=parsed.model_copy(update={'dispatchAllowed':True})
    with pytest.raises(ValidationError):
        ModelJudgeApplicationPreparation.model_validate(parsed)


def test_case_input_binding_complete_strict_and_no_artifact_permission():
    from aos_api.aip_model_eval_execution_contracts import ModelEvalCaseInputBinding
    raw={'caseId':'case-1','inputHash':'a'*64,'expectedHash':None}
    item=ModelEvalCaseInputBinding.model_validate(raw)
    assert item.model_dump(mode='json',by_alias=True)==raw
    assert not hasattr(item,'execution_allowed')
    assert ModelEvalCaseInputBinding.model_validate(item)==item


@pytest.mark.parametrize('field,value',[
    ('caseId',' '),('caseId',' case-1'),('caseId',1),
    ('inputHash','A'*64),('inputHash',b'a'*64),('inputHash','a'*63),
    ('expectedHash',b'b'*64),('expectedHash',True),('expectedHash','b'*63),
    ('executionAllowed',False),('readExpected',True),
])
def test_case_input_binding_rejects_drift_or_permission(field,value):
    from aos_api.aip_model_eval_execution_contracts import ModelEvalCaseInputBinding
    raw={'caseId':'case-1','inputHash':'a'*64,'expectedHash':None}
    raw[field]=value
    with pytest.raises(ValidationError):
        ModelEvalCaseInputBinding.model_validate(raw)


def test_case_input_binding_requires_explicit_expected_and_rechecks_copy():
    from aos_api.aip_model_eval_execution_contracts import ModelEvalCaseInputBinding
    with pytest.raises(ValidationError):
        ModelEvalCaseInputBinding.model_validate({'caseId':'case-1','inputHash':'a'*64})
    item=ModelEvalCaseInputBinding(caseId='case-1',inputHash='a'*64,expectedHash=None)
    for copied in (item.model_copy(update={'input_hash':b'a'*64}),
                   item.model_copy(update={'readExpected':True})):
        with pytest.raises(ValidationError):
            ModelEvalCaseInputBinding.model_validate(copied)


# New-purpose fixture freezes an actual original native request. All execution
# references below are descriptive synthetic inputs, never admission evidence.
def _whole_newjudge_body():
    frozen = json.loads((Path(__file__).resolve().parents[4] /
        '.evidence/gt-model-typed-proof-20261008/whole-newjudge-original-frozen-1600.json').read_text())
    pending, parent = frozen['pending'], frozen['parent']
    request = pending['request_json']
    target_app = request['targetApplication']
    template = _plan_body()['cases'][0]
    cases = []
    for i, original in enumerate(request['cases']):
        case = json.loads(json.dumps(template))
        case.update(caseId=original['caseId'], inputHash=original['inputArtifact']['contentHash'],
            expectedHash=None if original['expectedArtifact'] is None else original['expectedArtifact']['contentHash'])
        for purpose, app in [('target', target_app), ('judge', request['judgeGovernanceApplication'])]:
            leg = case[purpose]
            for field in ('providerRef', 'priceRef', 'quotaPolicyRef', 'budgetPolicyRef'):
                leg[field] = json.loads(json.dumps(app['request'][field]))
            leg['modelRef'] = json.loads(json.dumps(app['request']['sourceRef']))
            for field in ('intentRef', 'budgetAllocationRef'):
                leg[field]['resourceId'] += '-'+str(i)
            if purpose == 'target':
                leg['approvalRef']['resourceId'] = app['approvalEventId']
            else:
                leg['budgetHoldRef'] = parent['parentHoldRef']
                leg['approvalRef'] = parent['approvalRef']
        cases.append(case)
    t = cases[0]['target']
    return dict(schemaVersion='aos.model-eval-target-judge-manifest/v2', tenant=request['tenant'],
        executionId='synthetic-newpurpose-plan', judgeRequestId=pending['request_id'],
        judgeRequestHash=pending['request_hash'], judgeRequest=request,
        targetParentBudget=dict(parentHoldRef=t['budgetHoldRef'],requestId=target_app['requestId'],
            requestHash=target_app['requestHash'],approvalRef=t['approvalRef'],priceRef=t['priceRef'],
            budgetPolicyRef=t['budgetPolicyRef'],currency='CNY',upperBoundMinor=target_app['request']['upperBoundMinor']),
        judgeParentBudget=parent, cases=cases,
        caseSetHash=canonical_hash([dict(caseId=c['caseId'],inputHash=c['inputHash'],expectedHash=c['expectedHash']) for c in cases]),
        executionAllowed=False)


def test_whole_newjudge_manifest_freezes_original_request_without_execution():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _whole_newjudge_body()
    plan = module.ModelEvalTargetJudgeExecutionManifest.model_validate(body)
    assert plan.model_dump(mode='json', by_alias=True) == body
    assert module.ModelEvalTargetJudgeExecutionManifest.model_validate(plan) == plan
    with pytest.raises(ValidationError):
        module.ModelEvalExecutionManifest.model_validate(body)


@pytest.mark.parametrize('fault', ['hash','tenant','case_missing','case_order','input','target_price',
    'judge_quota','judge_old_hold','borrow_approval','parent_request','amount_total','duplicate_intent',
    'duplicate_allocation','execute_zero','execute_true','extra','raw_request_extra','rule_hash'])
def test_whole_newjudge_manifest_rejects_cross_purpose_and_partial_obligations(fault):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _whole_newjudge_body()
    if fault == 'hash': body['judgeRequestHash'] = 'f'*64
    elif fault == 'tenant': body['tenant'] = dict(orgId='dev-org',projectId='dev-project')
    elif fault == 'case_missing': body['cases'].pop()
    elif fault == 'case_order': body['cases'].reverse()
    elif fault == 'input': body['cases'][0]['inputHash'] = 'f'*64
    elif fault == 'target_price': body['cases'][0]['target']['priceRef']['contentHash'] = 'f'*64
    elif fault == 'judge_quota': body['cases'][0]['judge']['quotaPolicyRef']['contentHash'] = 'f'*64
    elif fault == 'judge_old_hold': body['cases'][0]['judge']['budgetHoldRef']['resourceType'] = 'ModelEvalBudgetReservation'
    elif fault == 'borrow_approval': body['cases'][0]['judge']['approvalRef'] = body['cases'][0]['target']['approvalRef']
    elif fault == 'parent_request': body['judgeParentBudget']['requestId'] = body['targetParentBudget']['requestId']
    elif fault == 'amount_total':
        for c in body['cases']: c['judge']['allocationUpperBoundMinor'] = body['judgeParentBudget']['upperBoundMinor']
    elif fault == 'duplicate_intent': body['cases'][1]['judge']['intentRef'] = body['cases'][0]['target']['intentRef']
    elif fault == 'duplicate_allocation': body['cases'][1]['judge']['budgetAllocationRef'] = body['cases'][0]['target']['budgetAllocationRef']
    elif fault == 'execute_zero': body['executionAllowed'] = 0
    elif fault == 'execute_true': body['executionAllowed'] = True
    elif fault == 'extra': body['permit'] = True
    elif fault == 'raw_request_extra': body['judgeRequest']['permit'] = True
    elif fault == 'rule_hash': body['judgeRequest']['ruleFacts']['ruleHash'] = 'f'*64
    # Refresh caller-controlled hashes deliberately: structural binding must
    # still reject omitted/reordered cases and malformed raw original inputs.
    if fault in ('case_missing','case_order','input'):
        body['caseSetHash'] = canonical_hash([dict(caseId=c['caseId'],inputHash=c['inputHash'],expectedHash=c['expectedHash']) for c in body['cases']])
    if fault in ('raw_request_extra','rule_hash'):
        body['judgeRequestHash'] = canonical_hash(body['judgeRequest'])
        body['judgeParentBudget']['requestHash'] = body['judgeRequestHash']
    with pytest.raises(ValidationError):
        module.ModelEvalTargetJudgeExecutionManifest.model_validate(body)


def test_whole_newjudge_revalidates_copied_nested_authority():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan = module.ModelEvalTargetJudgeExecutionManifest.model_validate(_whole_newjudge_body())
    wrong = plan.cases[0].judge.model_copy(update={'purpose':'target'})
    copied = plan.model_copy(update={'cases':[plan.cases[0].model_copy(update={'judge':wrong}),plan.cases[1]]})
    with pytest.raises(ValidationError):
        module.ModelEvalTargetJudgeExecutionManifest.model_validate(copied)


@pytest.mark.parametrize('fault', ['expiry_null','expiry_naive','root_hash','signature_hash',
    'release_hash','raw_cases_empty','old_schema','raw_execute_zero','shared_application_approval',
    'raw_case_set_hash','rule_template_hash'])
def test_whole_newjudge_raw_request_cannot_hide_malformed_snapshot_by_rehashing(fault):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _whole_newjudge_body(); raw = body['judgeRequest']
    if fault == 'expiry_null': raw['expiresAt'] = None
    elif fault == 'expiry_naive': raw['expiresAt'] = '2026-10-08T19:00:00'
    elif fault == 'root_hash': raw['ruleFacts']['rootRevision'] = 'untrusted'
    elif fault == 'signature_hash': raw['ruleFacts']['signatureFingerprint'] = ''
    elif fault == 'release_hash': raw['ruleFacts']['releaseEvidenceRevision'] = 0
    elif fault == 'raw_cases_empty': raw['cases'] = []
    elif fault == 'old_schema': raw['schemaVersion'] = 'aos.model-judge-call-request/v1'
    elif fault == 'raw_execute_zero': raw['executionAllowed'] = 0
    elif fault == 'shared_application_approval': raw['judgeGovernanceApplication']['approvalEventId'] = raw['targetApplication']['approvalEventId']
    elif fault == 'raw_case_set_hash': raw['caseSetHash'] = 'f'*64
    elif fault == 'rule_template_hash': raw['ruleFacts']['source']['templateArtifact']['digest'] = 'sha256:'+'f'*64
    body['judgeRequestHash'] = canonical_hash(raw)
    body['judgeParentBudget']['requestHash'] = body['judgeRequestHash']
    with pytest.raises(ValidationError):
        module.ModelEvalTargetJudgeExecutionManifest.model_validate(body)


def test_whole_newjudge_cannot_enter_legacy_certificate_signer():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _whole_newjudge_body()
    with pytest.raises(ValidationError):
        module.canonical_model_certificate_signing_bytes(body, _signing_inputs()[1])


@pytest.mark.parametrize('purpose,field', [('target','priceRef'),('judge','quotaPolicyRef')])
def test_whole_newjudge_governance_fault_reaches_leg_binding_with_original_hash_intact(purpose,field):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _whole_newjudge_body()
    original_hash = canonical_hash(body['judgeRequest'])
    body['cases'][0][purpose][field]['contentHash'] = 'f'*64
    assert canonical_hash(body['judgeRequest']) == original_hash == body['judgeRequestHash']
    with pytest.raises(ValidationError,match='exact per-purpose original governance and parent required'):
        module.ModelEvalTargetJudgeExecutionManifest.model_validate(body)


def _original_target_signing_inputs():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    assert hasattr(module, 'ModelOriginalTargetCaseSigningInput'), 'original v2 Target signing claim missing'
    assert hasattr(module, 'canonical_original_target_case_signing_bytes'), 'original v2 Target signing domain missing'
    plan = module.ModelEvalTargetJudgeExecutionManifest.model_validate(_whole_newjudge_body())
    original = plan.judge_request['targetApplication']
    wire, output = b'{"messages":[{"role":"user","content":"test-only"}]}', ' 测试Target🙂\n'.encode()
    claim = dict(schemaVersion='aos.model-eval-original-target-case-signing-input/v2',
        tenant=plan.tenant.model_dump(mode='json', by_alias=True), executionId=plan.execution_id,
        manifestHash=canonical_hash(plan.model_dump(mode='json', by_alias=True)),
        requestHash=original['requestHash'], caseId=plan.cases[0].case_id, purpose='target',
        candidateRef=original['request']['targetRef'],
        leg=plan.cases[0].target.model_dump(mode='json', by_alias=True),
        caseInputHash=plan.cases[0].input_hash, inputHash=hashlib.sha256(wire).hexdigest(),
        outputHash=hashlib.sha256(output).hexdigest(),
        occurredAt=datetime.fromisoformat(plan.judge_request['expiresAt'])-timedelta(seconds=1))
    return module, plan, claim, wire, output


def test_original_target_case_signing_domain_preserves_full_newjudge_and_actual_wire():
    module, plan, claim, wire, output = _original_target_signing_inputs()
    encoded = module.canonical_original_target_case_signing_bytes(plan, claim,
        input_bytes=wire, output_bytes=output)
    prefix = b'AOS-MODEL-EVAL-ORIGINAL-TARGET-CASE-SIGNING-INPUT-v2\n'
    assert encoded.startswith(prefix)
    frozen = module.ModelOriginalTargetCaseSigningInput.model_validate(claim)
    assert encoded[len(prefix):] == json.dumps(frozen.model_dump(mode='json',by_alias=True),
        sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()
    assert claim['caseInputHash'] != claim['inputHash']
    with pytest.raises(ValueError):
        module.canonical_model_case_signing_bytes(plan, frozen, input_bytes=wire, output_bytes=output)


@pytest.mark.parametrize('fault', ['manifest','request','candidate','case','case_input','wire_hash',
    'output_hash','wire_bytes','output_bytes','mutable','oversized','purpose','judge_fields',
    'expired','naive','extra','legacy_domain','copied','tenant','execution','leg','deep_copied'])
def test_original_target_case_signing_rejects_borrowed_or_incomplete_origin(fault):
    module, plan, claim, wire, output = _original_target_signing_inputs()
    if fault=='manifest': claim['manifestHash']='f'*64
    elif fault=='request': claim['requestHash']=plan.judge_request_hash
    elif fault=='candidate': claim['candidateRef']=plan.judge_request['targetApplication']['request']['sourceRef']
    elif fault=='case': claim['caseId']='not-original'
    elif fault=='case_input': claim['caseInputHash']='f'*64
    elif fault=='wire_hash': claim['inputHash']=claim['caseInputHash']
    elif fault=='output_hash': claim['outputHash']='f'*64
    elif fault=='wire_bytes': wire+=b' '
    elif fault=='output_bytes': output+=b' '
    elif fault=='mutable': wire=bytearray(wire)
    elif fault=='oversized': output=b'x'*1048577;claim['outputHash']=hashlib.sha256(output).hexdigest()
    elif fault=='purpose': claim['purpose']='judge'
    elif fault=='judge_fields': claim['passed']=True
    elif fault=='expired': claim['occurredAt']=plan.judge_request['expiresAt']
    elif fault=='naive': claim['occurredAt']=datetime(2026,10,8)
    elif fault=='extra': claim['producerCommitted']=True
    elif fault=='legacy_domain': claim['schemaVersion']='aos.model-eval-case-signing-input/v1'
    elif fault=='tenant': claim['tenant']={'orgId':'dev-org','projectId':'dev-project'}
    elif fault=='execution': claim['executionId']='borrowed-execution'
    elif fault=='leg': claim['leg']['identityKeyHash']='f'*64
    elif fault=='deep_copied':
        frozen=module.ModelOriginalTargetCaseSigningInput.model_validate(claim)
        claim=frozen.model_copy(update={'leg':frozen.leg.model_copy(update={'budget_hold_ref':frozen.leg.budget_hold_ref.model_copy(update={'content_hash':'sha256:'+'f'*64})})})
    elif fault=='copied':
        claim=module.ModelOriginalTargetCaseSigningInput.model_validate(claim).model_copy(update={'request_hash':'f'*64})
    with pytest.raises(ValueError):
        module.canonical_original_target_case_signing_bytes(plan, claim, input_bytes=wire, output_bytes=output)


def test_original_target_signing_each_original_case_keeps_distinct_parent_leg():
    module, plan, claim, wire, output = _original_target_signing_inputs()
    for case in plan.cases:
        item = dict(claim, caseId=case.case_id, caseInputHash=case.input_hash,
            leg=case.target.model_dump(mode='json',by_alias=True))
        assert module.canonical_original_target_case_signing_bytes(plan,item,
            input_bytes=wire,output_bytes=output).startswith(b'AOS-MODEL-EVAL-ORIGINAL-TARGET-CASE-SIGNING-INPUT-v2\n')


def _original_target_crypto_inputs():
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    module, plan, claim, wire, output = _original_target_signing_inputs()
    assert hasattr(module,'ModelOriginalTargetCertificateSigningInput'), 'original Target certificate missing'
    reader=importlib.import_module('aos_api.aip_model_eval_execution_reader')
    issuer, executor=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate()
    pub=executor.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    body=plan.model_dump(mode='json',by_alias=True)
    body['cases'][0]['target']['identityKeyHash']=hashlib.sha256(pub).hexdigest()
    plan=module.ModelEvalTargetJudgeExecutionManifest.model_validate(body)
    claim.update(manifestHash=canonical_hash(plan.model_dump(mode='json',by_alias=True)),leg=body['cases'][0]['target'])
    at=claim['occurredAt'];end=datetime.fromisoformat(plan.judge_request['expiresAt'])
    cert=dict(schemaVersion='aos.model-eval-original-target-certificate-signing-input/v2',
        **{k:claim[k] for k in ('tenant','executionId','manifestHash','requestHash','caseId','purpose','candidateRef','leg')},
        issuerId='test-original-issuer',issuerKeyId='test-original-issuer-key',publicKeyBase64=base64.b64encode(pub).decode(),
        validFrom=at-timedelta(seconds=1),validUntil=end)
    root=dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',purpose='model-eval-execution',
        tenant=claim['tenant'],issuerId=cert['issuerId'],issuerKeyId=cert['issuerKeyId'],
        publicKeyBase64=base64.b64encode(issuer.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode(),
        validFrom=at-timedelta(seconds=2),validUntil=end+timedelta(seconds=1),revokedAt=None)
    signature=base64.b64encode(issuer.sign(module.canonical_original_target_certificate_signing_bytes(plan,cert))).decode()
    envelope=dict(schemaVersion='aos.model-eval-original-target-signed-certificate-envelope/v2',certificate=cert,signatureBase64=signature)
    payload=dict(schemaVersion='aos.model-eval-original-target-case-signature-payload/v2',
        certificateHash=canonical_hash(module.ModelOriginalTargetSignedCertificateEnvelope.model_validate(envelope).model_dump(mode='json',by_alias=True)),claim=claim)
    raw=module.canonical_original_target_signed_case_bytes(plan,payload,input_bytes=wire,output_bytes=output)
    case=dict(schemaVersion='aos.model-eval-original-target-signed-case-envelope/v2',payload=payload,signatureBase64=base64.b64encode(executor.sign(raw)).decode())
    return module, reader, plan, envelope, root, case, at, wire, output


def test_original_target_crypto_chain_verifies_actual_ed25519_without_authority():
    module,reader,plan,cert,root,case,at,wire,output=_original_target_crypto_inputs()
    assert module.validate_original_target_case_signature(plan,case,certificate_envelope=cert,
        issuer_input=root,checked_at=at,revoked_identity_ids=frozenset(),input_bytes=wire,output_bytes=output) is None
    with pytest.raises(ValueError):
        reader.validate_model_case_signature(plan,case,certificate_envelope=cert,issuer_input=root,
            checked_at=at,revoked_identity_ids=frozenset(),input_bytes=wire,output_bytes=output)


@pytest.mark.parametrize('fault',['cert_signature','case_signature','issuer','root_key','revoked','root_end',
    'cert_end','naive','mutable_revocations','case_hash','case_time','case_leg','wire','output','copied',
    'legacy_domain','cert_request','cert_interval','extra'])
def test_original_target_crypto_rejects_forgery_expiry_and_cross_domain(fault):
    import base64
    module,reader,plan,cert,root,case,at,wire,output=_original_target_crypto_inputs()
    revoked=frozenset()
    if fault=='cert_signature':cert['signatureBase64']=base64.b64encode(b'x'*64).decode()
    elif fault=='case_signature':case['signatureBase64']=base64.b64encode(b'x'*64).decode()
    elif fault=='issuer':root['issuerId']='borrowed'
    elif fault=='root_key':root['publicKeyBase64']=base64.b64encode(b'x'*32).decode()
    elif fault=='revoked':revoked=frozenset({cert['certificate']['leg']['identityId']})
    elif fault=='root_end':root['revokedAt']=at
    elif fault=='cert_end':at=cert['certificate']['validUntil']
    elif fault=='naive':at=at.replace(tzinfo=None)
    elif fault=='mutable_revocations':revoked=set()
    elif fault=='case_hash':case['payload']['certificateHash']='f'*64
    elif fault=='case_time':case['payload']['claim']['occurredAt']=at+timedelta(microseconds=1)
    elif fault=='case_leg':case['payload']['claim']['leg']['identityId']='borrowed'
    elif fault=='wire':wire+=b' '
    elif fault=='output':output+=b' '
    elif fault=='copied':
        value=module.ModelOriginalTargetSignedCaseEnvelope.model_validate(case)
        case=value.model_copy(update={'payload':value.payload.model_copy(update={'certificate_hash':'f'*64})})
    elif fault=='legacy_domain':case['schemaVersion']='aos.model-eval-signed-case-envelope/v1'
    elif fault=='cert_request':cert['certificate']['requestHash']=plan.judge_request_hash
    elif fault=='cert_interval':cert['certificate']['validUntil']+=timedelta(seconds=1)
    elif fault=='extra':case['executionAllowed']=True
    with pytest.raises(ValueError):
        module.validate_original_target_case_signature(plan,case,certificate_envelope=cert,
            issuer_input=root,checked_at=at,revoked_identity_ids=revoked,input_bytes=wire,output_bytes=output)


@pytest.mark.parametrize('fault',['signature','issuer_key','issuer_id','revoked_root','revoked_identity',
    'end','naive','mutable','request','copied','legacy_signed_domain'])
def test_original_target_certificate_directly_rejects_invalid_crypto_and_authority_inputs(fault):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    module,reader,plan,envelope,root,case,at,wire,output=_original_target_crypto_inputs()
    cert=envelope['certificate'];signature=envelope['signatureBase64'];revoked=frozenset()
    if fault=='signature':signature=base64.b64encode(b'x'*64).decode()
    elif fault=='issuer_key':root['publicKeyBase64']=base64.b64encode(b'x'*32).decode()
    elif fault=='issuer_id':root['issuerId']='borrowed'
    elif fault=='revoked_root':root['revokedAt']=at
    elif fault=='revoked_identity':revoked=frozenset({cert['leg']['identityId']})
    elif fault=='end':at=cert['validUntil']
    elif fault=='naive':at=at.replace(tzinfo=None)
    elif fault=='mutable':revoked=set()
    elif fault=='request':cert['requestHash']=plan.judge_request_hash
    elif fault=='copied':cert=module.ModelOriginalTargetCertificateSigningInput.model_validate(cert).model_copy(update={'issuer_key_id':'borrowed'})
    elif fault=='legacy_signed_domain':
        key=Ed25519PrivateKey.generate()
        root['publicKeyBase64']=base64.b64encode(key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode()
        raw=module.canonical_original_target_certificate_signing_bytes(plan,cert)
        old=raw.replace(b'AOS-MODEL-EVAL-ORIGINAL-TARGET-CERTIFICATE-SIGNING-INPUT-v2',b'AOS-MODEL-EVAL-EXECUTOR-CERTIFICATE-SIGNING-INPUT-v1',1)
        signature=base64.b64encode(key.sign(old)).decode()
    with pytest.raises(ValueError):
        module.validate_original_target_certificate_signature(plan,cert,issuer_input=root,
            signature_base64=signature,checked_at=at,revoked_identity_ids=revoked)


def test_original_target_case_wrong_signature_reaches_real_crypto_rejection():
    import base64
    module,reader,plan,cert,root,case,at,wire,output=_original_target_crypto_inputs()
    case['signatureBase64']=base64.b64encode(b'x'*64).decode()
    with pytest.raises(ValueError,match='invalid original Target executor case signature'):
        module.validate_original_target_case_signature(plan,case,certificate_envelope=cert,
            issuer_input=root,checked_at=at,revoked_identity_ids=frozenset(),input_bytes=wire,output_bytes=output)


def _shared_parent_body():
    body = _whole_newjudge_body()
    body['schemaVersion'] = 'aos.model-eval-target-judge-shared-risk-manifest/v3'
    for case in body['cases']:
        for purpose in ('target', 'judge'):
            del case[purpose]['allocationUpperBoundMinor']
            del case[purpose]['budgetAllocationRef']
    return body


def test_shared_parent_full_plan_keeps_original_risk_without_leg_money():
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    plan = module.ModelEvalTargetJudgeSharedRiskManifest.model_validate(_shared_parent_body())
    assert len(plan.cases) == 2
    assert (plan.target_parent_budget.upper_bound_minor, plan.judge_parent_budget.upper_bound_minor) == (10, 10)
    dumped = plan.model_dump(mode='json', by_alias=True)
    assert all('allocationUpperBoundMinor' not in c[p] and 'budgetAllocationRef' not in c[p]
               for c in dumped['cases'] for p in ('target', 'judge'))
    with pytest.raises(ValidationError):
        module.ModelEvalTargetJudgeExecutionManifest.model_validate(plan)


@pytest.mark.parametrize('fault', ['amount', 'allocation', 'missing_case', 'reordered',
    'duplicate_intent', 'wrong_parent', 'wrong_model', 'allowed', 'bool_attempt', 'copied_amount'])
def test_shared_parent_full_plan_rejects_unbound_obligations(fault):
    module = importlib.import_module('aos_api.aip_model_eval_execution_contracts')
    body = _shared_parent_body()
    leg = body['cases'][0]['target']
    if fault == 'amount': leg['allocationUpperBoundMinor'] = 1
    elif fault == 'allocation': leg['budgetAllocationRef'] = _whole_newjudge_body()['cases'][0]['target']['budgetAllocationRef']
    elif fault == 'missing_case': body['cases'].pop()
    elif fault == 'reordered': body['cases'].reverse()
    elif fault == 'duplicate_intent': body['cases'][1]['target']['intentRef'] = leg['intentRef']
    elif fault == 'wrong_parent': leg['budgetHoldRef'] = body['cases'][0]['judge']['budgetHoldRef']
    elif fault == 'wrong_model': leg['modelRef'] = body['cases'][0]['judge']['modelRef']
    elif fault == 'allowed': body['executionAllowed'] = True
    elif fault == 'bool_attempt': leg['attempt'] = True
    elif fault == 'copied_amount':
        plan = module.ModelEvalTargetJudgeSharedRiskManifest.model_validate(body)
        plan.cases[0].target = plan.cases[0].target.model_copy(update={'allocation_upper_bound_minor': 1})
        body = plan
    with pytest.raises(ValidationError):
        module.ModelEvalTargetJudgeSharedRiskManifest.model_validate(body)
