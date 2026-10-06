"""Publication transport prerequisites; native COMMIT tests remain mandatory."""
import json
import os
import subprocess
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.asset_registry.canonical_json import canonical_json


def ref(kind, name="id"):
    return dict(assetType=kind, assetId=name, revision=1, contentHash="a" * 64)


def permit():
    now = datetime.now(UTC)
    return dict(schemaVersion=1, tenant=dict(orgId="org-org", projectId="dev-project"),
        assetId="permit", revision=1, publisher="authority", keyId="authority-key",
        validFrom=now-timedelta(minutes=1), validUntil=now+timedelta(hours=1),
        deploymentTarget=dict(host="127.0.0.1", port=5433, database="aos_test_publication",
            databaseOid=123, clusterIdentifier="1234567890123456789", issuerRole="aos_provider_capacity_issuer"),
        purpose="provider_capacity_source_signing_permit",
        sourcePolicyRef=ref("ProviderCapacitySourcePolicyRevision"),
        signerPublisher="source-signer", signerKeyId="source-key",
        signerRootRevision="sha256:"+"b"*64, signerPublicKey="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=")


def test_strict_signed_body_roundtrip_is_not_authority():
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit, parse_signed_capacity_body
    body = ProviderCapacitySigningPermit.model_validate(permit())
    raw = canonical_json(body.model_dump(mode="json", by_alias=True))
    parsed = parse_signed_capacity_body(raw, ProviderCapacitySigningPermit)
    assert parsed == body
    assert not hasattr(parsed, "verified")


@pytest.mark.parametrize("fault", ["purpose", "policy", "key", "private", "verified", "execute", "bool", "canary", "naive"])
def test_permit_rejects_confused_authority(fault):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
    raw = permit()
    if fault == "purpose": raw["purpose"] = "supplier_capacity_attestation"
    elif fault == "policy": raw["sourcePolicyRef"] = ref("EvidenceBundleRevision")
    elif fault == "key": raw["signerPublicKey"] = "AAAA"
    elif fault == "private": raw["privateKey"] = "forbidden"
    elif fault == "verified": raw["verified"] = True
    elif fault == "execute": raw["executionAllowed"] = True
    elif fault == "bool": raw["revision"] = True
    elif fault == "canary": raw["tenant"]["orgId"] = "dev-org"
    else: raw["validUntil"] = datetime.now()
    with pytest.raises(ValidationError): ProviderCapacitySigningPermit.model_validate(raw)


@pytest.mark.parametrize("raw", [
    b'{"purpose":"denied","purpose":"provider_capacity_source_signing_permit"}',
    b'{"nested":{"target":1,"target":2}}', b'{"revision":1.0}',
    b'{"revision":1e0}', b'{"revision":NaN}', b'{"revision":Infinity}',
    b'{"x":"\\ud800"}', b'{"x":"\\u0000"}', b'\xff',
    b'['*40+b'0'+b']'*40, b'{"x":['+b'0,'*1000+b'0]}', b' '*2097153,
], ids=["duplicate-purpose", "nested-duplicate", "float", "exponent", "nan", "infinity", "surrogate", "nul", "utf8", "depth", "array", "size"])
def test_raw_json_ambiguity_rejected(raw):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit, parse_signed_capacity_body
    with pytest.raises(ValueError): parse_signed_capacity_body(raw, ProviderCapacitySigningPermit)


def test_noncanonical_alias_spacing_and_time_rejected():
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit, parse_signed_capacity_body
    body = ProviderCapacitySigningPermit.model_validate(permit())
    payload = body.model_dump(mode="json", by_alias=True)
    for raw in [json.dumps(payload).encode(), canonical_json(body.model_dump(mode="json")),
                canonical_json({**payload, "validUntil":payload["validUntil"].replace("Z", "+00:00")})]:
        with pytest.raises(ValueError): parse_signed_capacity_body(raw, ProviderCapacitySigningPermit)


def bootstrap():
    raw = permit()
    for name in ("sourcePolicyRef", "signerPublisher", "signerKeyId", "signerRootRevision", "signerPublicKey"):
        raw.pop(name)
    raw.update(purpose="provider_capacity_origin_bootstrap", bootstrapId="bootstrap-once",
        publisherSubject="external-policy-publisher", policyPublisherRole="aos_provider_capacity_policy_publisher",
        anchorRevision="sha256:"+"c"*64, rootSnapshotHash="sha256:"+"d"*64,
        allowedDocumentRefs=[ref("ProviderCapacitySourcePolicyRevision"), ref("SupplierCapacityAttestationRevision"), ref("ProviderCapacitySigningPermitRevision")])
    return raw


def published():
    raw = permit()
    for name in ("sourcePolicyRef", "signerPublisher", "signerKeyId", "signerRootRevision", "signerPublicKey"):
        raw.pop(name)
    raw.update(purpose="provider_capacity_published_source",
        physicalAccountId="00112233-4455-4677-8899-aabbccddeeff", supplierId="supplier",
        supplierAccountFingerprint="b"*64, providerRefs=[ref("ProviderInstanceRevision")],
        evidenceRefs=[ref("EvidenceBundleRevision")], originEpoch=0,
        sourceWithdrawalEpoch=0, allocationWithdrawalEpoch=0, requestHash="e"*64,
        maxConcurrency=2, tokenLimit=dict(mode="inflight_upper_bound", unit="token", maxTokens=100),
        observedAt=datetime.now(UTC)-timedelta(minutes=1), issuedAt=datetime.now(UTC), executionAllowed=False)
    kinds = dict(sourceProposalRef="ActionProposal", sourceApprovalRef="ActionApprovalEvent",
        allocationRequestRef="ProviderCapacityRequest", allocationApprovalRef="ActionApprovalEvent",
        accountCandidateRef="ProviderPhysicalAccountCandidateRevision", basisCandidateRef="ProviderCapacityBasisCandidateRevision",
        sourcePolicyRef="ProviderCapacitySourcePolicyRevision", supplierAttestationRef="SupplierCapacityAttestationRevision",
        signingPermitRef="ProviderCapacitySigningPermitRevision", originRef="ProviderCapacityOriginBootstrapRevision")
    for name, kind in kinds.items(): raw[name] = ref(kind, name)
    raw["sourceProposalRef"]["revision"] = 2
    return raw


@pytest.mark.parametrize("kind", ["bootstrap", "published"])
def test_complete_document_profiles_preserve_exact_signed_bytes(kind):
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacityOriginBootstrap, PublishedProviderCapacitySource, parse_signed_capacity_body)
    model, payload = (ProviderCapacityOriginBootstrap, bootstrap()) if kind == "bootstrap" else (PublishedProviderCapacitySource, published())
    original = model.model_validate(payload)
    raw = canonical_json(original.model_dump(mode="json", by_alias=True))
    assert parse_signed_capacity_body(raw, model) == original


@pytest.mark.parametrize("fault", ["duplicate", "role", "kind", "key"])
def test_bootstrap_cannot_declare_source_issuer_as_authority(fault):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap
    raw = bootstrap()
    if fault == "duplicate": raw["allowedDocumentRefs"].append(raw["allowedDocumentRefs"][0])
    elif fault == "role": raw["policyPublisherRole"] = "aos_provider_capacity_issuer"
    elif fault == "kind": raw["allowedDocumentRefs"][0] = ref("ProviderInstanceRevision")
    else: raw["publicKey"] = "self-asserted"
    with pytest.raises(ValidationError): ProviderCapacityOriginBootstrap.model_validate(raw)


@pytest.mark.parametrize("fault", ["uuid", "execute", "duplicate", "evidence", "approval", "revision", "future", "epoch", "fraction", "private"])
def test_published_source_cannot_replace_provenance_or_grant_execution(fault):
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySource
    raw = published()
    if fault == "uuid": raw["physicalAccountId"] = "owner-alias"
    elif fault == "execute": raw["executionAllowed"] = True
    elif fault == "duplicate": raw["providerRefs"].append(raw["providerRefs"][0])
    elif fault == "evidence": raw["evidenceRefs"] = [ref("ProviderInstanceRevision")]
    elif fault == "approval": raw["allocationApprovalRef"] = raw["sourceApprovalRef"]
    elif fault == "revision": raw["sourceProposalRef"]["revision"] = 1
    elif fault == "future": raw["observedAt"] = raw["issuedAt"] + timedelta(seconds=1)
    elif fault == "epoch": raw["originEpoch"] = True
    elif fault == "fraction": raw["maxConcurrency"] = 1.0
    else: raw["privateKey"] = "forbidden"
    with pytest.raises(ValidationError): PublishedProviderCapacitySource.model_validate(raw)


@pytest.mark.parametrize("fault,reason", [
    ("duplicate-purpose","DUPLICATE_KEY"), ("duplicate-target","DUPLICATE_KEY"),
    ("float","NON_INTEGER"), ("exponent","NON_INTEGER"), ("nul","NUL"),
    ("depth","DEPTH"), ("array","ARRAY"), ("spacing","NONCANONICAL"),
])
def test_complete_valid_document_single_fault_has_specific_rejection(fault, reason):
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacitySigningPermit, CapacitySignedBodyProfileError, parse_signed_capacity_body)
    model = ProviderCapacitySigningPermit.model_validate(permit())
    payload = model.model_dump(mode="json", by_alias=True)
    raw = canonical_json(payload)
    assert parse_signed_capacity_body(raw, ProviderCapacitySigningPermit) == model
    if fault == "duplicate-purpose":
        value = json.dumps(payload["purpose"]).encode()
        raw = raw.replace(b'"purpose":'+value, b'"purpose":'+value+b',"purpose":'+value)
    elif fault == "duplicate-target":
        raw = raw.replace(b'"databaseOid":123', b'"databaseOid":123,"databaseOid":123')
    elif fault == "float": raw = raw.replace(b'"revision":1', b'"revision":1.0')
    elif fault == "exponent": raw = raw.replace(b'"revision":1', b'"revision":1e0')
    elif fault == "nul": raw = canonical_json({**payload, "publisher":"authority\x00"})
    elif fault == "depth": raw = raw[:-1]+b',"padding":'+b'['*33+b'0'+b']'*33+b'}'
    elif fault == "array": raw = canonical_json({**payload,"padding":[0]*1001})
    else: raw = json.dumps(payload, ensure_ascii=False).encode()
    with pytest.raises(CapacitySignedBodyProfileError) as caught:
        parse_signed_capacity_body(raw, ProviderCapacitySigningPermit)
    assert caught.value.reason == reason
    assert "authority" not in str(caught.value)


@pytest.mark.skipif(not os.environ.get("AOS_CRYPTO_TEST_CONTAINER"), reason="explicit isolated native verifier required")
def test_original_signed_bytes_native_crypto_and_document_profile_are_separate():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacitySigningPermit, CapacitySignedBodyProfileError, parse_signed_capacity_body)
    target = os.environ["AOS_CRYPTO_TEST_CONTAINER"]
    assert target.startswith("aos-ed25519-test-")
    prefix = ["docker", "--context", "colima-aos-a0v-test-only"]
    state = json.loads(subprocess.check_output(prefix+["inspect", target], text=True))[0]
    assert state["Image"] == os.environ["AOS_CRYPTO_TEST_IMAGE"]
    assert state["HostConfig"]["NetworkMode"] == "none" and not state["HostConfig"]["PortBindings"]
    assert not state["HostConfig"]["Privileged"]
    assert state["Config"]["Labels"]["aos.task"] == "gt-capacity-sql-ed25519-20261006"
    model = ProviderCapacitySigningPermit.model_validate(permit())
    raw = canonical_json(model.model_dump(mode="json", by_alias=True))
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def native_verify(body):
        signature = key.sign(body)
        statement = "BEGIN READ ONLY; SELECT aos_ed25519.verify(decode('%s','hex'),decode('%s','hex'),decode('%s','hex')); COMMIT;" % (signature.hex(), body.hex(), public.hex())
        result = subprocess.run(prefix+["exec", "-i", target, "psql", "-U", "aos_app", "-d", "aos_test_ed25519", "-Atq", "-v", "ON_ERROR_STOP=1", "-f", "-"], input=statement, text=True, capture_output=True, check=True, timeout=30)
        return result.stdout.strip()

    assert native_verify(raw) == "t"
    assert parse_signed_capacity_body(raw, ProviderCapacitySigningPermit) == model
    ambiguous = raw.replace(b'"databaseOid":123', b'"databaseOid":123,"databaseOid":123')
    assert native_verify(ambiguous) == "t"
    with pytest.raises(CapacitySignedBodyProfileError) as caught:
        parse_signed_capacity_body(ambiguous, ProviderCapacitySigningPermit)
    assert caught.value.reason == "DUPLICATE_KEY"
