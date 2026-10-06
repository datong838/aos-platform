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


@pytest.fixture
def native_profile_runner():
    if not os.environ.get("AOS_CRYPTO_TEST_CONTAINER"):
        pytest.skip("explicit isolated native verifier required")
    target = os.environ["AOS_CRYPTO_TEST_CONTAINER"]
    assert target.startswith("aos-ed25519-test-")
    prefix = ["docker", "--context", "colima-aos-a0v-test-only"]
    state = json.loads(subprocess.check_output(prefix+["inspect", target], text=True))[0]
    assert state["Image"] == os.environ["AOS_CRYPTO_TEST_IMAGE"]
    assert state["HostConfig"]["NetworkMode"] == "none" and not state["HostConfig"]["PortBindings"]
    assert not state["HostConfig"]["Privileged"]
    assert state["Config"]["Labels"]["aos.task"] == "gt-capacity-sql-ed25519-20261006"
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_SIGNED_BODY_PROFILE_SQL

    def run(statement, success=True):
        result = subprocess.run(prefix+["exec", "-i", target, "psql", "-U", "aos_app", "-d", "aos_test_ed25519", "-Atq", "-v", "ON_ERROR_STOP=1", "-f", "-"], input="BEGIN; CREATE SCHEMA aos_capacity_publication_private;\n"+CAPACITY_SIGNED_BODY_PROFILE_SQL+"\n"+statement+"\nROLLBACK;", text=True, capture_output=True, timeout=60)
        if success:
            assert result.returncode == 0, result.stderr
            return result.stdout.strip()
        assert result.returncode != 0
        return result.stderr
    return run


def test_native_full_permit_canonical_bytes_preserved(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
    payload = ProviderCapacitySigningPermit.model_validate(permit()).model_dump(mode="json", by_alias=True)
    raw = canonical_json(payload)
    assert native_profile_runner("SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex'))->>'purpose';" % raw.hex()) == "provider_capacity_source_signing_permit"


@pytest.mark.parametrize("fault", ["duplicate-purpose", "duplicate-target", "float", "exponent", "negative-zero", "spacing", "nul", "utf8", "array", "depth", "size"])
def test_native_complete_body_single_fault_rejected(native_profile_runner, fault):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
    payload = ProviderCapacitySigningPermit.model_validate(permit()).model_dump(mode="json", by_alias=True)
    raw = canonical_json(payload)
    if fault == "duplicate-purpose":
        value = json.dumps(payload["purpose"]).encode()
        raw = raw.replace(b'"purpose":'+value, b'"purpose":'+value+b',"purpose":'+value)
    elif fault == "duplicate-target": raw = raw.replace(b'"databaseOid":123', b'"databaseOid":123,"databaseOid":123')
    elif fault == "float": raw = raw.replace(b'"revision":1', b'"revision":1.0')
    elif fault == "exponent": raw = raw.replace(b'"revision":1', b'"revision":1e0')
    elif fault == "negative-zero": raw = raw.replace(b'"revision":1', b'"revision":-0')
    elif fault == "spacing": raw = json.dumps(payload).encode()
    elif fault == "nul": raw = canonical_json({**payload,"publisher":"authority\x00"})
    elif fault == "utf8": raw = raw[:-1]+b'\xff}'
    elif fault == "array": raw = canonical_json({**payload,"padding":[0]*1001})
    elif fault == "depth": raw = raw[:-1]+b',"padding":'+b'['*33+b'0'+b']'*33+b'}'
    else: raw = b' '*2097153
    error = native_profile_runner("SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex'));" % raw.hex(), False)
    assert "CAPACITY_SIGNED_BODY" in error


@pytest.mark.parametrize("value", [
    {}, [], True, None, 0, -1, 9223372036854775807,
    {"中":"\"\\\n\t", "z":[], "😀":{"x":None}, "é":[True,False,0]},
    [0]*1000, {str(i):i for i in range(1000)},
], ids=["empty-object","empty-array","true","null","zero","negative","bigint","unicode-escapes","array-limit","object-limit"])
def test_native_json_encoding_matches_python_without_granting_document_shape(native_profile_runner, value):
    raw = canonical_json(value)
    assert native_profile_runner("SELECT aos_capacity_publication_private.canonical_signed_json(aos_capacity_publication_private.read_signed_body(decode('%s','hex'))::json,1);" % raw.hex()) == raw.decode()


@pytest.mark.parametrize("kind", ["bootstrap", "published"])
def test_native_full_publication_profiles(native_profile_runner, kind):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap, PublishedProviderCapacitySource
    model,payload=(ProviderCapacityOriginBootstrap,bootstrap()) if kind=="bootstrap" else (PublishedProviderCapacitySource,published())
    raw=canonical_json(model.model_validate(payload).model_dump(mode="json",by_alias=True))
    assert native_profile_runner("SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex'))->>'purpose';" % raw.hex()) == payload["purpose"]


def test_native_function_catalog_and_explicit_compute_role(native_profile_runner):
    assert native_profile_runner("""
SELECT pg_catalog.current_setting('server_encoding');
SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='aos_capacity_publication_private' AND NOT p.prosecdef AND p.proisstrict
AND p.provolatile='i' AND p.proconfig=ARRAY['search_path=pg_catalog'];
SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
LATERAL aclexplode(p.proacl) a WHERE n.nspname='aos_capacity_publication_private' AND a.grantee=0;
SELECT count(*) FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a
WHERE n.nspname='aos_capacity_publication_private' AND a.grantee=0;
SELECT aos_capacity_publication_private.read_signed_body(NULL) IS NULL;
""") == "UTF8\n2\n0\n0\nt"
    error=native_profile_runner("CREATE ROLE profile_reader NOLOGIN; SET LOCAL ROLE profile_reader; SELECT aos_capacity_publication_private.read_signed_body(decode('7b7d','hex'));",False)
    assert "permission denied for schema aos_capacity_publication_private" in error
    error=native_profile_runner("CREATE ROLE profile_reader NOLOGIN; GRANT USAGE ON SCHEMA aos_capacity_publication_private TO profile_reader; SET LOCAL ROLE profile_reader; SELECT aos_capacity_publication_private.read_signed_body(decode('7b7d','hex'));",False)
    assert "permission denied for function read_signed_body" in error
    assert native_profile_runner("CREATE ROLE profile_reader NOLOGIN; GRANT USAGE ON SCHEMA aos_capacity_publication_private TO profile_reader; GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA aos_capacity_publication_private TO profile_reader; SET LOCAL ROLE profile_reader; SELECT aos_capacity_publication_private.read_signed_body(decode('7b7d','hex')); ") == "{}"


def test_native_bounded_object_depth_and_toast(native_profile_runner):
    oversized={str(i):i for i in range(1001)}
    assert "CAPACITY_SIGNED_BODY" in native_profile_runner("SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex'));" % canonical_json(oversized).hex(),False)
    for depth in (32,33):
        raw=b'['*depth+b'0'+b']'*depth
        statement="SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex')) IS NOT NULL;" % raw.hex()
        result=native_profile_runner(statement,depth==32)
        assert result=="t" if depth==32 else "CAPACITY_SIGNED_BODY" in result
    raw=canonical_json({"padding":["x"*2000]*1000})
    assert len(raw)<2097152
    assert native_profile_runner("CREATE TEMP TABLE signed_body_test(raw bytea); INSERT INTO signed_body_test VALUES(decode('%s','hex')); SELECT pg_column_size(raw)<octet_length(raw), aos_capacity_publication_private.read_signed_body(raw) IS NOT NULL FROM signed_body_test;" % raw.hex()) == "t|t"


@pytest.mark.parametrize("storage", ["EXTENDED", "EXTERNAL"])
def test_native_exact_message_size_boundary_in_storage(native_profile_runner, storage):
    limit=2097152
    raw=canonical_json({"padding":"x"*(limit-len(canonical_json({"padding":""})))})
    assert len(raw)==limit
    statement="CREATE TEMP TABLE signed_body_test(raw bytea); ALTER TABLE signed_body_test ALTER COLUMN raw SET STORAGE %s; INSERT INTO signed_body_test VALUES(decode('%s','hex')); SELECT octet_length(raw), pg_column_size(raw)<octet_length(raw), aos_capacity_publication_private.read_signed_body(raw) IS NOT NULL FROM signed_body_test;" % (storage,raw.hex())
    assert native_profile_runner(statement)==("2097152|t|t" if storage=="EXTENDED" else "2097152|f|t")
    oversized=raw[:-2]+b'x"}'
    assert len(oversized)==limit+1
    error=native_profile_runner("CREATE TEMP TABLE signed_body_test(raw bytea); ALTER TABLE signed_body_test ALTER COLUMN raw SET STORAGE %s; INSERT INTO signed_body_test VALUES(decode('%s','hex')); SELECT aos_capacity_publication_private.read_signed_body(raw) FROM signed_body_test;" % (storage,oversized.hex()),False)
    assert "CAPACITY_SIGNED_BODY_PROFILE_REQUIRED" in error


def test_python_complete_document_object_limit_rejection_stage():
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacitySigningPermit, parse_signed_capacity_body, CapacitySignedBodyProfileError)
    payload=ProviderCapacitySigningPermit.model_validate(permit()).model_dump(mode="json",by_alias=True)
    payload.update({"extra"+str(i):i for i in range(1000)})
    with pytest.raises(CapacitySignedBodyProfileError) as caught:
        parse_signed_capacity_body(canonical_json(payload),ProviderCapacitySigningPermit)
    assert caught.value.reason=="OBJECT"
