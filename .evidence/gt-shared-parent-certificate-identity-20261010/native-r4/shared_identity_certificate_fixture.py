"""Experiment keys stay in memory. Presented roots are never authority."""
import base64, copy, hashlib
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from aos_api.aip_model_eval_execution_contracts import (
    canonical_shared_parent_certificate_signing_bytes,
    validate_shared_parent_certificate_signature)
from aos_api.aip_model_runtime_store import canonical_hash


def public(key):
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def keys_for_manifest(manifest):
    keys = {p: Ed25519PrivateKey.generate() for p in ('target', 'judge')}
    for case in manifest['cases']:
        for purpose, key in keys.items():
            case[purpose]['identityKeyHash'] = hashlib.sha256(public(key)).hexdigest()
    return keys


def issue(description, keys, checked_at):
    manifest = description['immutable']['manifest']
    end = datetime.fromisoformat(manifest['judgeRequest']['expiresAt'])
    start = checked_at - timedelta(seconds=1)
    assert start < checked_at < end
    root_key = Ed25519PrivateKey.generate()
    root = dict(schemaVersion='aos.model-eval-issuer-verification-input/v1',
        purpose='model-eval-execution', tenant=manifest['tenant'], issuerId='isolated-v3-presented-issuer',
        issuerKeyId='isolated-v3-root-key', publicKeyBase64=base64.b64encode(public(root_key)).decode(),
        validFrom=start.isoformat(), validUntil=end.isoformat(), revokedAt=None)
    certificates = []
    for case in manifest['cases']:
        for purpose in ('target', 'judge'):
            app = manifest['judgeRequest']['targetApplication' if purpose == 'target' else 'judgeGovernanceApplication']
            claim = dict(schemaVersion='aos.model-eval-shared-parent-certificate-signing-input/v3',
                tenant=manifest['tenant'], executionId=manifest['executionId'],
                manifestHash=description['immutable']['manifestHash'],
                requestHash=app['requestHash'] if purpose == 'target' else manifest['judgeRequestHash'],
                caseId=case['caseId'], purpose=purpose, candidateRef=app['request']['targetRef'],
                leg=case[purpose], issuerId=root['issuerId'], issuerKeyId=root['issuerKeyId'],
                publicKeyBase64=base64.b64encode(public(keys[purpose])).decode(),
                validFrom=start.isoformat(), validUntil=min(end,checked_at+timedelta(seconds=8)).isoformat(),
                descriptionHash=description['contentHash'], originalRiskHash=description['immutable']['originalRiskHash'],
                callerXid=description['immutable']['callerXid'], callerPid=description['immutable']['callerPid'])
            raw = canonical_shared_parent_certificate_signing_bytes(description, claim)
            envelope = dict(schemaVersion='aos.model-eval-shared-parent-signed-certificate-envelope/v3',
                certificate=copy.deepcopy(claim), signatureBase64=base64.b64encode(root_key.sign(raw)).decode())
            validate_shared_parent_certificate_signature(description, envelope, issuer_input=root,
                checked_at=checked_at, revoked_identity_ids=frozenset())
            certificates.append(envelope)
    return dict(certificates=certificates, presented_root=root, checked_at=checked_at.isoformat(),
        root_provenance_verified=False, issuer_metadata_current=False, execution_allowed=False)
