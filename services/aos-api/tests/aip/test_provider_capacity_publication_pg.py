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


def published_v2():
    raw = published()
    raw.update(schemaVersion=2, issuanceContext=dict(
        makerSubject="original-maker", oidcIssuer="https://identity.example.test/issuer",
        oidcAudience="capacity-source", authenticationExpiresAt=raw["issuedAt"]+timedelta(minutes=5),
        issuerRole="aos_provider_capacity_issuer", transactionId="123456789012",
        backendPid=123, attemptId="11223344-5566-4788-99aa-bbccddeeff00"))
    return raw


def test_issuance_context_v2_roundtrip_is_untrusted_and_v1_stays_distinct():
    from aos_api.aip_provider_capacity_publication_contracts import (
        PublishedProviderCapacitySource, PublishedProviderCapacitySourceV2, parse_signed_capacity_body)
    model = PublishedProviderCapacitySourceV2.model_validate(published_v2())
    raw = canonical_json(model.model_dump(mode="json", by_alias=True))
    assert parse_signed_capacity_body(raw, PublishedProviderCapacitySourceV2) == model
    assert not hasattr(model.issuance_context, "verified")
    with pytest.raises(ValidationError): PublishedProviderCapacitySource.model_validate(published_v2())
    with pytest.raises(ValidationError): PublishedProviderCapacitySourceV2.model_validate(published())


@pytest.mark.parametrize("fault", ["version", "maker", "unknown-maker", "issuer-http", "issuer-userinfo", "issuer-query",
    "issuer-fragment", "issuer-port", "issuer-host", "audience", "expired", "naive", "role",
    "tx-zero", "tx-leading-zero", "tx-overflow", "tx-number", "tx-negative", "pid-bool",
    "pid-zero", "pid-overflow", "attempt", "private", "verified", "extra"])
def test_issuance_context_complete_v2_single_fault_rejected(fault):
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2
    raw = published_v2()
    context = raw["issuanceContext"]
    if fault == "version": raw["schemaVersion"] = 1
    elif fault == "maker": context["makerSubject"] = " original-maker"
    elif fault == "unknown-maker": context["makerSubject"] = "unknown"
    elif fault == "issuer-http": context["oidcIssuer"] = "http://identity.example.test"
    elif fault == "issuer-userinfo": context["oidcIssuer"] = "https://user:pass@identity.example.test"
    elif fault == "issuer-query": context["oidcIssuer"] += "?token=forbidden"
    elif fault == "issuer-fragment": context["oidcIssuer"] += "#forbidden"
    elif fault == "issuer-port": context["oidcIssuer"] = "https://identity.example.test:65536"
    elif fault == "issuer-host": context["oidcIssuer"] = "https:///issuer"
    elif fault == "audience": context["oidcAudience"] = " "
    elif fault == "expired": context["authenticationExpiresAt"] = raw["issuedAt"]
    elif fault == "naive": context["authenticationExpiresAt"] = raw["issuedAt"].replace(tzinfo=None)
    elif fault == "role": context["issuerRole"] = "aos_runtime"
    elif fault == "tx-zero": context["transactionId"] = "0"
    elif fault == "tx-leading-zero": context["transactionId"] = "0123"
    elif fault == "tx-overflow": context["transactionId"] = str(2**64)
    elif fault == "tx-number": context["transactionId"] = 123
    elif fault == "tx-negative": context["transactionId"] = "-1"
    elif fault == "pid-bool": context["backendPid"] = True
    elif fault == "pid-zero": context["backendPid"] = 0
    elif fault == "pid-overflow": context["backendPid"] = 2**31
    elif fault == "attempt": context["attemptId"] = "11223344-5566-4788-99AA-BBCCDDEEFF00"
    elif fault == "private": context["privateKey"] = "forbidden"
    elif fault == "verified": context["verified"] = True
    else: context["extra"] = "forbidden"
    with pytest.raises(ValidationError): PublishedProviderCapacitySourceV2.model_validate(raw)


def test_issuance_context_v2_exact_xid_and_pid_upper_bounds():
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2
    raw = published_v2()
    raw["issuanceContext"].update(transactionId=str(2**64-1), backendPid=2**31-1)
    assert PublishedProviderCapacitySourceV2.model_validate(raw).schema_version == 2


def test_issuance_context_all_claims_are_bound_by_native_signature(native_profile_runner):
    import copy
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from aos_api.aip_provider_capacity_publication_contracts import PublishedProviderCapacitySourceV2, parse_signed_capacity_body
    payload = PublishedProviderCapacitySourceV2.model_validate(published_v2()).model_dump(mode="json", by_alias=True)
    raw = canonical_json(payload)
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    signature = key.sign(raw)
    statements = ["SELECT aos_ed25519.verify(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));" % (signature.hex(), raw.hex(), public.hex())]
    for name, value in dict(makerSubject="different-maker", oidcIssuer="https://different.example.test",
        oidcAudience="different-audience", authenticationExpiresAt=(payload["validUntil"]),
        transactionId="123456789013", backendPid=124,
        attemptId="11223344-5566-4788-99aa-bbccddeeff01").items():
        changed = copy.deepcopy(payload)
        changed["issuanceContext"][name] = value
        model = PublishedProviderCapacitySourceV2.model_validate(changed)
        altered = canonical_json(model.model_dump(mode="json", by_alias=True))
        # Valid claim shapes remain unauthenticated; the old signature must fail.
        assert parse_signed_capacity_body(altered, PublishedProviderCapacitySourceV2) == model
        statements.append("SELECT aos_ed25519.verify(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));" % (signature.hex(), altered.hex(), public.hex()))
    assert native_profile_runner("\n".join(statements)).splitlines() == ["t"]+["f"]*7


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


def _native_deployment_target(native_profile_runner, target, success=True):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
    raw = canonical_json(target).hex()
    statement = CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL + "\nSELECT aos_capacity_publication_private.read_deployment_target(decode('%s','hex'))::text;" % raw
    return native_profile_runner(statement, success=success)


@pytest.mark.parametrize('fault', ['missing', 'extra', 'null', 'host', 'port-bool', 'port-text',
    'port-float', 'port-zero', 'port-overflow', 'database-upper', 'database-long', 'database-newline',
    'oid-zero', 'oid-overflow', 'oid-text', 'cluster-number', 'cluster-short', 'cluster-long',
    'cluster-unicode', 'role', 'alias'])
def test_native_deployment_target_complete_single_fault(native_profile_runner, fault):
    from aos_api.aip_provider_capacity_source_contracts import CapacitySourceDeploymentTarget
    target = permit()['deploymentTarget']
    if fault == 'missing': target.pop('databaseOid')
    elif fault == 'extra': target['verified'] = True
    elif fault == 'null': target['database'] = None
    elif fault == 'host': target['host'] = 'localhost'
    elif fault == 'port-bool': target['port'] = True
    elif fault == 'port-text': target['port'] = '5433'
    elif fault == 'port-float': target['port'] = 5433.5
    elif fault == 'port-zero': target['port'] = 0
    elif fault == 'port-overflow': target['port'] = 65536
    elif fault == 'database-upper': target['database'] = 'Aos_test'
    elif fault == 'database-long': target['database'] = 'a'*64
    elif fault == 'database-newline': target['database'] = 'aos_test\n'
    elif fault == 'oid-zero': target['databaseOid'] = 0
    elif fault == 'oid-overflow': target['databaseOid'] = 2**32
    elif fault == 'oid-text': target['databaseOid'] = '123'
    elif fault == 'cluster-number': target['clusterIdentifier'] = 1234567890
    elif fault == 'cluster-short': target['clusterIdentifier'] = '123456789'
    elif fault == 'cluster-long': target['clusterIdentifier'] = '1'*21
    elif fault == 'cluster-unicode': target['clusterIdentifier'] = '１'*10
    elif fault == 'role': target['issuerRole'] = 'aos_app'
    else: target['database_oid'] = target.pop('databaseOid')
    if fault == 'alias':
        assert CapacitySourceDeploymentTarget.model_validate(target).model_dump(mode='json',by_alias=True) != target
    else:
        with pytest.raises(ValidationError): CapacitySourceDeploymentTarget.model_validate(target)
    failure = _native_deployment_target(native_profile_runner, target, success=False)
    assert 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' in failure


@pytest.mark.parametrize('host', ['127.0.0.1', '::1'])
def test_native_deployment_target_full_boundaries_roundtrip(native_profile_runner, host):
    from aos_api.aip_provider_capacity_source_contracts import CapacitySourceDeploymentTarget
    for port, oid, database, cluster in [(1,1,'a','0'*10),(65535,2**32-1,'a'*63,'9'*20)]:
        target = permit()['deploymentTarget']
        target.update(host=host,port=port,databaseOid=oid,database=database,clusterIdentifier=cluster)
        expected = CapacitySourceDeploymentTarget.model_validate(target).model_dump(mode='json',by_alias=True)
        assert json.loads(_native_deployment_target(native_profile_runner, target)) == expected


@pytest.mark.parametrize('literal', ['NULL', "convert_to('null','UTF8')", "convert_to('[]','UTF8')", "convert_to('true','UTF8')", "convert_to('123','UTF8')"])
def test_native_deployment_target_rejects_nonobject_and_sql_null(native_profile_runner, literal):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
    failure = native_profile_runner(CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL +
        '\nSELECT aos_capacity_publication_private.read_deployment_target('+literal+');', success=False)
    assert 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' in failure


@pytest.mark.parametrize('replacement', [b'1e3', b'5433.0'])
def test_native_deployment_target_original_integer_lexical_gate(native_profile_runner, replacement):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
    raw = canonical_json(permit()['deploymentTarget']).replace(b'"port":5433', b'"port":'+replacement)
    failure = native_profile_runner(CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL +
        "\nSELECT aos_capacity_publication_private.read_deployment_target(decode('%s','hex'));" % raw.hex(), success=False)
    assert 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' in failure


def test_native_deployment_target_duplicate_key_rejected(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
    raw = canonical_json(permit()['deploymentTarget']).replace(b'"port":5433', b'"port":5433,"port":5433')
    failure = native_profile_runner(CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL +
        "\nSELECT aos_capacity_publication_private.read_deployment_target(decode('%s','hex'));" % raw.hex(), success=False)
    assert 'CAPACITY_DEPLOYMENT_TARGET_REQUIRED' in failure


def test_native_deployment_target_function_boundary(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
    result = native_profile_runner(CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL + """
        SELECT p.proisstrict,p.prosecdef,p.provolatile,p.proconfig,
          (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='aos_capacity_publication_private' AND p.proname='read_deployment_target';
    """)
    assert result == 'f|f|i|{search_path=pg_catalog}|0'
    raw = canonical_json(permit()['deploymentTarget']).hex()
    failure = native_profile_runner(CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL + """
        CREATE ROLE capacity_target_reader NOLOGIN;
        GRANT USAGE ON SCHEMA aos_capacity_publication_private TO capacity_target_reader;
        SET ROLE capacity_target_reader;
        SELECT aos_capacity_publication_private.read_deployment_target(decode('%s','hex'));
    """ % raw, success=False)
    assert 'permission denied for function read_deployment_target' in failure


def _native_identifier(native_profile_runner, value, success=True):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_IDENTIFIER_PROFILE_SQL
    statement = CAPACITY_IDENTIFIER_PROFILE_SQL + "\nSELECT aos_capacity_publication_private.read_identifier(convert_from(decode('%s','hex'),'UTF8')::jsonb);" % canonical_json(value).hex()
    return native_profile_runner(statement, success=success)


@pytest.mark.parametrize('value', ['authority', '中文标识', 'a\u034fb', '😀', 'a'*200])
def test_native_identifier_original_unicode_positive(native_profile_runner, value):
    from aos_api.aip_provider_capacity_source_contracts import _identifier
    assert _identifier(value) == value
    assert _native_identifier(native_profile_runner, value) == value


@pytest.mark.parametrize('value', ['', 'a'*201, ' a', 'a ', 'a b', 'a\n', '\u00a0', '\u00ad',
    '\u200b', '\u200d', '\u2028', '\u202e', '\u2060', '\ue000', '\u0378', '\ufeff', None, True, 1])
def test_native_identifier_original_unicode_negative(native_profile_runner, value):
    from aos_api.aip_provider_capacity_source_contracts import _identifier
    with pytest.raises(ValueError): _identifier(value)
    assert 'CAPACITY_IDENTIFIER_REQUIRED' in _native_identifier(native_profile_runner, value, success=False)


def test_native_identifier_all_unicode_range_boundaries(native_profile_runner):
    import unicodedata
    from aos_api.aip_provider_capacity_source_contracts import _identifier
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL, CAPACITY_IDENTIFIER_UNICODE_VERSION)
    assert unicodedata.unidata_version == CAPACITY_IDENTIFIER_UNICODE_VERSION
    points = set()
    previous = False
    for cp in range(0x110000):
        value = chr(cp)
        allowed = value.isprintable() and not value.isspace()
        if allowed != previous:
            points.update([cp-1, cp])
        previous = allowed
    samples = []
    for cp in sorted(points):
        if not 1 <= cp <= 0x10ffff or 0xd800 <= cp <= 0xdfff:
            continue  # PostgreSQL UTF8 cannot carry NUL or surrogate scalars.
        try:
            _identifier(chr(cp))
            accepted = 'true'
        except ValueError:
            accepted = 'false'
        samples.append('(%s,%s)' % (cp,accepted))
    statement = CAPACITY_IDENTIFIER_PROFILE_SQL + """
        DO $probe$ DECLARE sample record; accepted boolean; BEGIN
          FOR sample IN SELECT * FROM (VALUES %s) AS cases(cp,expected) LOOP
            BEGIN
              PERFORM aos_capacity_publication_private.read_identifier(to_jsonb(chr(sample.cp)));
              accepted := true;
            EXCEPTION WHEN SQLSTATE '22023' THEN accepted := false;
            END;
            IF accepted IS DISTINCT FROM sample.expected THEN
              RAISE EXCEPTION 'identifier classification mismatch at codepoint %%',sample.cp;
            END IF;
          END LOOP;
        END $probe$;
        SELECT %s;
    """ % (','.join(samples),len(samples))
    assert native_profile_runner(statement) == str(len(samples))


def test_native_identifier_function_boundary(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_IDENTIFIER_PROFILE_SQL
    result = native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL + """
        SELECT p.proisstrict,p.prosecdef,p.provolatile,p.proconfig,
          (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='aos_capacity_publication_private' AND p.proname='read_identifier';
    """)
    assert result == 'f|f|i|{search_path=pg_catalog}|0'


def test_identifier_complete_frozen_manifest_matches_original_semantics():
    import hashlib
    import re
    import unicodedata
    from pathlib import Path
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL, CAPACITY_IDENTIFIER_UNICODE_VERSION,
        CAPACITY_IDENTIFIER_RANGES_SHA256)
    assert unicodedata.unidata_version == CAPACITY_IDENTIFIER_UNICODE_VERSION == '14.0.0'
    expected = []
    start = None
    for cp in range(0x110000):
        value = chr(cp)
        accepted = value.isprintable() and not value.isspace()
        if accepted and start is None:
            start = cp
        if start is not None and (not accepted or cp == 0x10ffff):
            expected.append([start,cp-1 if not accepted else cp])
            start = None
    arrays = []
    for name in ['starts','ends']:
        matches = re.findall(name+r' integer\[\] := ARRAY\[([0-9,]+)\];', CAPACITY_IDENTIFIER_PROFILE_SQL)
        assert len(matches) == 1
        arrays.append([int(value) for value in matches[0].split(',')])
    actual = [list(pair) for pair in zip(*arrays,strict=True)]
    assert actual == expected
    assert all(a <= b for a,b in actual)
    assert all(actual[index-1][1]+1 < a for index,(a,b) in enumerate(actual) if index)
    path = Path(__file__).resolve().parents[4] / '.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-gt-provider-capacity-publication-20261005/identifier-unicode-ranges.json'
    manifest = json.loads(path.read_text())
    assert manifest == dict(unicode_version='14.0.0',
        predicate='str.isprintable() and not str.isspace()',ranges=expected)
    frozen = json.dumps(manifest,separators=(',',':'),sort_keys=True).encode()
    assert hashlib.sha256(frozen).hexdigest() == CAPACITY_IDENTIFIER_RANGES_SHA256


def _native_permit(native_profile_runner, raw, success=True):
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL, CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL)
    return native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL + CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL +
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL + "\nSELECT aos_capacity_publication_private.read_signing_permit(decode('%s','hex'))::text;" % raw.hex(), success=success)


@pytest.mark.parametrize('fault', ['missing','extra','alias','schema','tenant','purpose','revision-bool',
    'revision-zero','publisher-invisible','ref-extra','ref-kind','ref-id','ref-revision','ref-hash',
    'root','key-newline','key-padding','key-size','naive','zero-fraction','utc-offset','invalid-date',
    'time-24','expired-window','long-window','target'])
def test_native_signing_permit_complete_typed_negative(native_profile_runner, fault):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit, parse_signed_capacity_body
    payload = ProviderCapacitySigningPermit.model_validate(permit()).model_dump(mode='json',by_alias=True)
    if fault == 'missing': payload.pop('signerPublisher')
    elif fault == 'extra': payload['verified'] = True
    elif fault == 'alias': payload['signer_publisher'] = payload.pop('signerPublisher')
    elif fault == 'schema': payload['schemaVersion'] = 2
    elif fault == 'tenant': payload['tenant']['orgId'] = 'dev-org'
    elif fault == 'purpose': payload['purpose'] = 'supplier_capacity_attestation'
    elif fault == 'revision-bool': payload['revision'] = True
    elif fault == 'revision-zero': payload['revision'] = 0
    elif fault == 'publisher-invisible': payload['publisher'] = '\u200b'
    elif fault == 'ref-extra': payload['sourcePolicyRef']['verified'] = True
    elif fault == 'ref-kind': payload['sourcePolicyRef']['assetType'] = 'EvidenceBundleRevision'
    elif fault == 'ref-id': payload['sourcePolicyRef']['assetId'] = 'white space'
    elif fault == 'ref-revision': payload['sourcePolicyRef']['revision'] = 0
    elif fault == 'ref-hash': payload['sourcePolicyRef']['contentHash'] = 'A'*64
    elif fault == 'root': payload['signerRootRevision'] = 'b'*64
    elif fault == 'key-newline': payload['signerPublicKey'] += '\n'
    elif fault == 'key-padding': payload['signerPublicKey'] = payload['signerPublicKey'][:-2]+'F='
    elif fault == 'key-size': payload['signerPublicKey'] = 'AAAA'
    elif fault == 'naive': payload['validFrom'] = '2026-01-01T00:00:00'
    elif fault == 'zero-fraction': payload.update(validFrom='2026-01-01T00:00:00.000000Z',validUntil='2026-01-02T00:00:00Z')
    elif fault == 'utc-offset': payload.update(validFrom='2026-01-01T00:00:00+00:00',validUntil='2026-01-02T00:00:00Z')
    elif fault == 'invalid-date': payload['validFrom'] = '2026-02-30T00:00:00Z'
    elif fault == 'time-24': payload['validFrom'] = '2026-01-01T24:00:00Z'
    elif fault == 'expired-window': payload['validUntil'] = payload['validFrom']
    elif fault == 'long-window': payload.update(validFrom='2026-01-01T00:00:00Z',validUntil='2027-01-03T00:00:00Z')
    else: payload['deploymentTarget']['databaseOid'] = True
    raw = canonical_json(payload)
    with pytest.raises(ValueError): parse_signed_capacity_body(raw, ProviderCapacitySigningPermit)
    assert 'CAPACITY_SIGNING_PERMIT_REQUIRED' in _native_permit(native_profile_runner, raw, success=False)


@pytest.mark.parametrize('offset', [0,480,-330,1439,-1439])
def test_native_signing_permit_original_complete_positive(native_profile_runner, offset):
    from datetime import timezone
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
    payload = permit()
    start = datetime(2020,1,1,0,0,0,100000,tzinfo=timezone(timedelta(minutes=offset)))
    payload.update(publisher='中文供应方😀',validFrom=start,validUntil=start+timedelta(days=366),revision=10**100)
    body = ProviderCapacitySigningPermit.model_validate(payload)
    expected = body.model_dump(mode='json',by_alias=True)
    assert json.loads(_native_permit(native_profile_runner, canonical_json(expected))) == expected


def test_native_signing_permit_private_properties(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL, CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL)
    assert native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL + CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
        + CAPACITY_SIGNING_PERMIT_PROFILE_SQL + """
        SELECT p.proname,p.prosecdef,p.provolatile,p.proisstrict,p.proconfig::text,
          (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='aos_capacity_publication_private'
          AND p.proname IN ('read_signed_time','read_signing_permit') ORDER BY p.proname;
        """) == ('read_signed_time|f|i|f|{search_path=pg_catalog}|0\n'
                   'read_signing_permit|f|i|f|{search_path=pg_catalog}|0')


@pytest.mark.parametrize('literal', ['NULL', "convert_to('null','UTF8')", "convert_to('[]','UTF8')"])
def test_native_signing_permit_null_shape_rejected(native_profile_runner, literal):
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL, CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL)
    error = native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL + CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL
        + CAPACITY_SIGNING_PERMIT_PROFILE_SQL
        + f'SELECT aos_capacity_publication_private.read_signing_permit({literal});', success=False)
    assert 'CAPACITY_SIGNING_PERMIT_REQUIRED' in error


@pytest.mark.parametrize('field', ['revision','policy-revision'])
@pytest.mark.parametrize('digits', [4300,4301,5000])
def test_native_signing_permit_integer_parse_limit(native_profile_runner, field, digits):
    import sys
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacitySigningPermit
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    assert sys.get_int_max_str_digits() == 4300
    document = ProviderCapacitySigningPermit.model_validate(permit()).model_dump(mode='json',by_alias=True)
    if field == 'revision':
        document['revision'] = 'INTEGER_PLACEHOLDER'
    else:
        document['sourcePolicyRef']['revision'] = 'INTEGER_PLACEHOLDER'
    raw = canonical_json(document).replace(b'"INTEGER_PLACEHOLDER"', b'1'*digits)
    if digits <= 4300:
        parsed = parse_signed_capacity_body(raw,ProviderCapacitySigningPermit)
        assert json.loads(_native_permit(native_profile_runner,raw)) == parsed.model_dump(mode='json',by_alias=True)
    else:
        with pytest.raises(ValueError):
            parse_signed_capacity_body(raw,ProviderCapacitySigningPermit)
        assert 'CAPACITY_SIGNING_PERMIT_REQUIRED' in _native_permit(native_profile_runner,raw,success=False)


@pytest.mark.parametrize("fault",[None,"purpose","role","canary","anchor","snapshot","empty","duplicate","kind","ref_extra","ref_hash","ref_bool","unknown","subject","ref_null","refs_scalar","ref_alias","same_identity_new_revision","expiry","schema_bool"])
def test_native_origin_bootstrap_original_complete_contract(native_profile_runner,fault):
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap,parse_signed_capacity_body
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL)
    model=ProviderCapacityOriginBootstrap.model_validate(bootstrap())
    payload=model.model_dump(mode="json",by_alias=True)
    if fault=="purpose":payload['purpose']='provider_capacity_source_signing_permit'
    elif fault=="role":payload['policyPublisherRole']='aos_provider_capacity_issuer'
    elif fault=="canary":payload['tenant']['orgId']='dev-org'
    elif fault=="anchor":payload['anchorRevision']='sha256:'+"A"*64
    elif fault=="snapshot":payload['rootSnapshotHash']='0'*64
    elif fault=="empty":payload['allowedDocumentRefs']=[]
    elif fault=="duplicate":payload['allowedDocumentRefs']*=2
    elif fault=="kind":payload['allowedDocumentRefs'][0]['assetType']='EvidenceBundleRevision'
    elif fault=="ref_extra":payload['allowedDocumentRefs'][0]['verified']=True
    elif fault=="ref_hash":payload['allowedDocumentRefs'][0]['contentHash']='wrong'
    elif fault=="ref_bool":payload['allowedDocumentRefs'][0]['revision']=True
    elif fault=="unknown":payload['verified']=True
    elif fault=="subject":payload['publisherSubject']=' original-subject'
    elif fault=="ref_null":payload['allowedDocumentRefs'][0]=None
    elif fault=="refs_scalar":payload['allowedDocumentRefs']={}
    elif fault=="ref_alias":payload['allowedDocumentRefs'][0]['asset_id']=payload['allowedDocumentRefs'][0].pop('assetId')
    elif fault=="same_identity_new_revision":payload['allowedDocumentRefs'].append({**payload['allowedDocumentRefs'][0],'revision':2})
    elif fault=="expiry":payload['validUntil']=payload['validFrom']
    elif fault=="schema_bool":payload['schemaVersion']=True
    raw=canonical_json(payload)
    if fault is not None:
        with pytest.raises(ValueError):parse_signed_capacity_body(raw,ProviderCapacityOriginBootstrap)
    else:assert parse_signed_capacity_body(raw,ProviderCapacityOriginBootstrap)==model
    statement=CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL
    result=native_profile_runner(statement+"\nSELECT aos_capacity_publication_private.read_origin_bootstrap(decode('%s','hex'))::text;"%raw.hex(),success=fault is None)
    if fault is None:assert json.loads(result)==payload


def test_native_origin_bootstrap_null_and_function_boundary(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL)
    ddl=CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL
    failure=native_profile_runner(ddl+"SELECT aos_capacity_publication_private.read_origin_bootstrap(NULL);",success=False)
    assert 'CAPACITY_ORIGIN_BOOTSTRAP_REQUIRED' in failure
    result=native_profile_runner(ddl+"""
SELECT prosecdef,provolatile,proisstrict,proconfig,
  NOT EXISTS(SELECT 1 FROM aclexplode(proacl) a WHERE a.grantee=0) AS no_public
FROM pg_proc WHERE oid='aos_capacity_publication_private.read_origin_bootstrap(bytea)'::regprocedure;
""")
    assert result=='f|i|f|{search_path=pg_catalog}|t'


@pytest.mark.parametrize("count,offset",[(1,0),(1000,14)])
def test_native_origin_bootstrap_refs_and_original_time_boundaries(native_profile_runner,count,offset):
    from datetime import timezone
    from aos_api.aip_provider_capacity_publication_contracts import ProviderCapacityOriginBootstrap,parse_signed_capacity_body
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL)
    payload=bootstrap();payload['publisherSubject']='发布者中文'
    payload['allowedDocumentRefs']=[ref('ProviderCapacitySourcePolicyRevision',str(i)) for i in range(count)]
    for key in ['validFrom','validUntil']:payload[key]=payload[key].astimezone(timezone(timedelta(hours=offset)))
    model=ProviderCapacityOriginBootstrap.model_validate(payload);body=model.model_dump(mode='json',by_alias=True)
    raw=canonical_json(body);assert parse_signed_capacity_body(raw,ProviderCapacityOriginBootstrap)==model
    result=native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL+
        "SELECT aos_capacity_publication_private.read_origin_bootstrap(decode('%s','hex'))::text;"%raw.hex())
    assert json.loads(result)==body


def source_policy():
    body=permit()
    return dict(schemaVersion=1,tenant=body['tenant'],assetId='policy',revision=1,
        publisher='aos-capacity-source-policy',keyId='policy-key',supplierId='供应方😀',
        validFrom=body['validFrom'],validUntil=body['validUntil'],purpose='provider_capacity_source',
        attestationPublisher='supplier',attestationKeyId='supplier-key',
        attestationRootRevision='sha256:'+'a'*64,maxObservationAgeSeconds=86400,
        maxFutureSkewSeconds=60,allowedTokenModes=['inflight_upper_bound','fixed_window_rate'],
        deploymentTarget=body['deploymentTarget'])


def _native_source_policy(runner,raw,success=True):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SOURCE_POLICY_PROFILE_SQL)
    return runner(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_SOURCE_POLICY_PROFILE_SQL+
        "SELECT aos_capacity_publication_private.read_source_policy(decode('%s','hex'));"%raw.hex(),success)


def test_native_source_policy_complete_roundtrip(native_profile_runner):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourcePolicy
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    from datetime import timezone
    for offset,age,skew,modes in [(0,1,0,['inflight_upper_bound']),
        (1439,86400,60,['fixed_window_rate']),(-1439,86400,60,['fixed_window_rate','inflight_upper_bound'])]:
        payload=source_policy();start=datetime(2020,1,1,0,0,0,100000,tzinfo=timezone(timedelta(minutes=offset)))
        payload.update(validFrom=start,validUntil=start+timedelta(days=366),revision=10**100,
            maxObservationAgeSeconds=age,maxFutureSkewSeconds=skew,allowedTokenModes=modes)
        model=ProviderCapacitySourcePolicy.model_validate(payload);expected=model.model_dump(mode='json',by_alias=True)
        raw=canonical_json(expected);assert parse_signed_capacity_body(raw,ProviderCapacitySourcePolicy)==model
        assert json.loads(_native_source_policy(native_profile_runner,raw))==expected


@pytest.mark.parametrize('fault',['missing','extra','publisher','purpose','canary','revision-bool',
    'revision-zero','identifier','root','age-bool','age-zero','age-high','skew-negative','skew-high',
    'skew-text','modes-empty','modes-duplicate','modes-extra','modes-unknown','modes-scalar',
    'deployment','naive','equal-window','long-window','alias','zero-fraction'])
def test_native_source_policy_complete_single_fault(native_profile_runner,fault):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourcePolicy
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    payload=ProviderCapacitySourcePolicy.model_validate(source_policy()).model_dump(mode='json',by_alias=True)
    if fault=='missing':payload.pop('supplierId')
    elif fault=='extra':payload['verified']=True
    elif fault=='publisher':payload['publisher']='caller'
    elif fault=='purpose':payload['purpose']='supplier_capacity_attestation'
    elif fault=='canary':payload['tenant']['orgId']='dev-org'
    elif fault=='revision-bool':payload['revision']=True
    elif fault=='revision-zero':payload['revision']=0
    elif fault=='identifier':payload['attestationKeyId']='white space'
    elif fault=='root':payload['attestationRootRevision']='A'*64
    elif fault=='age-bool':payload['maxObservationAgeSeconds']=True
    elif fault=='age-zero':payload['maxObservationAgeSeconds']=0
    elif fault=='age-high':payload['maxObservationAgeSeconds']=86401
    elif fault=='skew-negative':payload['maxFutureSkewSeconds']=-1
    elif fault=='skew-high':payload['maxFutureSkewSeconds']=61
    elif fault=='skew-text':payload['maxFutureSkewSeconds']='0'
    elif fault=='modes-empty':payload['allowedTokenModes']=[]
    elif fault=='modes-duplicate':payload['allowedTokenModes']=['inflight_upper_bound']*2
    elif fault=='modes-extra':payload['allowedTokenModes']=['inflight_upper_bound']*3
    elif fault=='modes-unknown':payload['allowedTokenModes']=['unbounded']
    elif fault=='modes-scalar':payload['allowedTokenModes']='inflight_upper_bound'
    elif fault=='deployment':payload['deploymentTarget']['databaseOid']=True
    elif fault=='naive':payload['validFrom']='2026-01-01T00:00:00'
    elif fault=='equal-window':payload['validUntil']=payload['validFrom']
    elif fault=='long-window':payload.update(validFrom='2026-01-01T00:00:00Z',validUntil='2027-01-03T00:00:00Z')
    elif fault=='alias':payload['supplier_id']=payload.pop('supplierId')
    else:payload.update(validFrom='2026-01-01T00:00:00.000000Z',validUntil='2026-01-02T00:00:00Z')
    raw=canonical_json(payload)
    with pytest.raises(ValueError):parse_signed_capacity_body(raw,ProviderCapacitySourcePolicy)
    assert 'CAPACITY_SOURCE_POLICY_REQUIRED' in _native_source_policy(native_profile_runner,raw,False)


@pytest.mark.parametrize('literal',['NULL',"convert_to('null','UTF8')","convert_to('[]','UTF8')"])
def test_native_source_policy_null_shape(native_profile_runner,literal):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SOURCE_POLICY_PROFILE_SQL)
    assert 'CAPACITY_SOURCE_POLICY_REQUIRED' in native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL+
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_SOURCE_POLICY_PROFILE_SQL+
        'SELECT aos_capacity_publication_private.read_source_policy('+literal+');',False)


def test_native_source_policy_private_catalog(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SOURCE_POLICY_PROFILE_SQL)
    assert native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_SOURCE_POLICY_PROFILE_SQL+"""
        SELECT p.prosecdef,p.provolatile,p.proisstrict,p.proconfig::text,
          (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='aos_capacity_publication_private' AND p.proname='read_source_policy';
        """)== 'f|i|f|{search_path=pg_catalog}|0'


def test_native_source_policy_original_integer_limit(native_profile_runner):
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourcePolicy
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    payload=ProviderCapacitySourcePolicy.model_validate(source_policy()).model_dump(mode='json',by_alias=True)
    original=canonical_json(payload)
    for field in ['revision','maxObservationAgeSeconds','maxFutureSkewSeconds']:
        old=('"'+field+'":'+str(payload[field])).encode()
        raw=original.replace(old,('"'+field+'":'+'9'*4301).encode())
        with pytest.raises(ValueError):parse_signed_capacity_body(raw,ProviderCapacitySourcePolicy)
        assert 'CAPACITY_SOURCE_POLICY_REQUIRED' in _native_source_policy(native_profile_runner,raw,False)


def supplier_attestation(mode='inflight_upper_bound'):
    policy=source_policy()
    token=dict(mode=mode,unit='token',maxTokens=10**12)
    if mode=='fixed_window_rate':token.update(windowSeconds=86400,windowAnchor=policy['validFrom'])
    return dict(schemaVersion=1,tenant=policy['tenant'],assetId='attestation',revision=1,
        publisher='供应方😀',keyId='supplier-key',supplierId=policy['supplierId'],
        validFrom=policy['validFrom'],validUntil=policy['validUntil'],purpose='supplier_capacity_attestation',
        supplierAccountFingerprint='b'*64,providerRefs=[ref('ProviderInstanceRevision')],
        evidenceRef=ref('EvidenceBundleRevision'),maxConcurrency=1000000,tokenLimit=token,
        observedAt=policy['validFrom']-timedelta(days=1))


def _native_attestation(runner,raw,success=True):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL)
    return runner(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+
        CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL+
        "SELECT aos_capacity_publication_private.read_supplier_attestation(decode('%s','hex'));"%raw.hex(),success)


@pytest.mark.parametrize('mode',['inflight_upper_bound','fixed_window_rate'])
def test_native_supplier_attestation_complete_roundtrip(native_profile_runner,mode):
    from aos_api.aip_provider_capacity_source_contracts import SupplierCapacityAttestation
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    from datetime import timezone
    for count,offset,limit in [(1,1439,1),(1000,-1439,10**12)]:
        payload=supplier_attestation(mode);start=datetime(2020,1,1,0,0,0,999999,tzinfo=timezone(timedelta(minutes=offset)))
        payload.update(validFrom=start,validUntil=start+timedelta(days=366),observedAt=start-timedelta(days=1),
            revision=10**100,providerRefs=[ref('ProviderInstanceRevision','p'+str(i)) for i in range(count)],
            maxConcurrency=1 if count==1 else 1000000)
        payload['tokenLimit']['maxTokens']=limit
        if mode=='fixed_window_rate':payload['tokenLimit'].update(windowAnchor=start,windowSeconds=1 if count==1 else 86400)
        model=SupplierCapacityAttestation.model_validate(payload);expected=model.model_dump(mode='json',by_alias=True)
        raw=canonical_json(expected);assert parse_signed_capacity_body(raw,SupplierCapacityAttestation)==model
        assert json.loads(_native_attestation(native_profile_runner,raw))==expected


@pytest.mark.parametrize('fault',['missing','extra','canary','purpose','revision-bool','identifier','fingerprint',
    'providers-empty','providers-many','provider-kind','provider-extra','provider-revision','provider-hash',
    'provider-id','provider-duplicate','evidence-kind','evidence-null','concurrency-zero','concurrency-high',
    'concurrency-bool','token-mode','token-unit','token-zero','token-high','token-bool','token-extra',
    'token-missing','window-zero','window-high','window-bool','window-naive','inflight-window',
    'observed-naive','observed-end','validity-naive','validity-equal','validity-long','alias'])
def test_native_supplier_attestation_complete_single_fault(native_profile_runner,fault):
    from aos_api.aip_provider_capacity_source_contracts import SupplierCapacityAttestation
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    payload=SupplierCapacityAttestation.model_validate(supplier_attestation('fixed_window_rate')).model_dump(mode='json',by_alias=True)
    token=payload['tokenLimit'];provider=payload['providerRefs'][0]
    if fault=='missing':payload.pop('supplierId')
    elif fault=='extra':payload['verified']=True
    elif fault=='canary':payload['tenant']['orgId']='dev-org'
    elif fault=='purpose':payload['purpose']='provider_capacity_source'
    elif fault=='revision-bool':payload['revision']=True
    elif fault=='identifier':payload['keyId']='white space'
    elif fault=='fingerprint':payload['supplierAccountFingerprint']='A'*64
    elif fault=='providers-empty':payload['providerRefs']=[]
    elif fault=='providers-many':payload['providerRefs']=[ref('ProviderInstanceRevision','p'+str(i)) for i in range(1001)]
    elif fault=='provider-kind':provider['assetType']='EvidenceBundleRevision'
    elif fault=='provider-extra':provider['verified']=True
    elif fault=='provider-revision':provider['revision']=False
    elif fault=='provider-hash':provider['contentHash']='A'*64
    elif fault=='provider-id':provider['assetId']='white space'
    elif fault=='provider-duplicate':payload['providerRefs'].append({**provider,'revision':2})
    elif fault=='evidence-kind':payload['evidenceRef']['assetType']='ProviderInstanceRevision'
    elif fault=='evidence-null':payload['evidenceRef']=None
    elif fault=='concurrency-zero':payload['maxConcurrency']=0
    elif fault=='concurrency-high':payload['maxConcurrency']=1000001
    elif fault=='concurrency-bool':payload['maxConcurrency']=True
    elif fault=='token-mode':token['mode']='unbounded'
    elif fault=='token-unit':token['unit']='request'
    elif fault=='token-zero':token['maxTokens']=0
    elif fault=='token-high':token['maxTokens']=10**12+1
    elif fault=='token-bool':token['maxTokens']=True
    elif fault=='token-extra':token['verified']=True
    elif fault=='token-missing':token.pop('unit')
    elif fault=='window-zero':token['windowSeconds']=0
    elif fault=='window-high':token['windowSeconds']=86401
    elif fault=='window-bool':token['windowSeconds']=True
    elif fault=='window-naive':token['windowAnchor']='2026-01-01T00:00:00'
    elif fault=='inflight-window':token['mode']='inflight_upper_bound'
    elif fault=='observed-naive':payload['observedAt']='2026-01-01T00:00:00'
    elif fault=='observed-end':payload['observedAt']=payload['validUntil']
    elif fault=='validity-naive':payload['validFrom']='2026-01-01T00:00:00'
    elif fault=='validity-equal':payload['validUntil']=payload['validFrom']
    elif fault=='validity-long':payload.update(validFrom='2026-01-01T00:00:00Z',validUntil='2027-01-03T00:00:00Z')
    else:payload['supplier_id']=payload.pop('supplierId')
    raw=canonical_json(payload)
    with pytest.raises(ValueError):parse_signed_capacity_body(raw,SupplierCapacityAttestation)
    assert 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' in _native_attestation(native_profile_runner,raw,False)


@pytest.mark.parametrize('literal',['NULL',"convert_to('null','UTF8')","convert_to('[]','UTF8')"])
def test_native_supplier_attestation_null_shape(native_profile_runner,literal):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL)
    assert 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' in native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL+
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL+CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL+
        'SELECT aos_capacity_publication_private.read_supplier_attestation('+literal+');',False)


def test_native_supplier_attestation_private_catalog(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_IDENTIFIER_PROFILE_SQL,
        CAPACITY_SIGNING_PERMIT_PROFILE_SQL,CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL)
    assert native_profile_runner(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+
        CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL+"""
        SELECT p.prosecdef,p.provolatile,p.proisstrict,p.proconfig::text,
          (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='aos_capacity_publication_private' AND p.proname='read_supplier_attestation';
        """)== 'f|i|f|{search_path=pg_catalog}|0'


@pytest.mark.parametrize('field',['revision','maxConcurrency','maxTokens','windowSeconds','providerRevision'])
def test_native_supplier_attestation_original_integer_limit(native_profile_runner,field):
    from aos_api.aip_provider_capacity_source_contracts import SupplierCapacityAttestation
    from aos_api.aip_provider_capacity_publication_contracts import parse_signed_capacity_body
    payload=SupplierCapacityAttestation.model_validate(supplier_attestation('fixed_window_rate')).model_dump(mode='json',by_alias=True)
    raw=canonical_json(payload);digits=b'9'*4301
    if field=='providerRevision':
        item=canonical_json(payload['providerRefs'][0])
        raw=raw.replace(item,item.replace(b'"revision":1',b'"revision":'+digits))
    elif field=='revision':raw=raw.replace(b'"revision":1,"schemaVersion"',b'"revision":'+digits+b',"schemaVersion"')
    else:
        value=payload[field] if field=='maxConcurrency' else payload['tokenLimit'][field]
        old=('"'+field+'":'+str(value)).encode();raw=raw.replace(old,('"'+field+'":').encode()+digits)
    with pytest.raises(ValueError):parse_signed_capacity_body(raw,SupplierCapacityAttestation)
    assert 'CAPACITY_SUPPLIER_ATTESTATION_REQUIRED' in _native_attestation(native_profile_runner,raw,False)


@pytest.mark.parametrize('kind',['policy','attestation','permit','bootstrap'])
@pytest.mark.parametrize('fault',['valid','raw-change','signature-change','key-change',
    'signed-duplicate','signed-schema','signed-purpose'])
def test_native_complete_profiles_real_signature_composition(native_profile_runner,kind,fault):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourcePolicy,SupplierCapacityAttestation
    from aos_api.aip_provider_capacity_publication_contracts import (
        ProviderCapacitySigningPermit,ProviderCapacityOriginBootstrap,parse_signed_capacity_body)
    from aos_api.aip_provider_capacity_publication_store import (
        CAPACITY_IDENTIFIER_PROFILE_SQL,CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL,CAPACITY_SIGNING_PERMIT_PROFILE_SQL,
        CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL,CAPACITY_SOURCE_POLICY_PROFILE_SQL,CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL)
    types={'policy':(ProviderCapacitySourcePolicy,source_policy,'read_source_policy'),
        'attestation':(SupplierCapacityAttestation,supplier_attestation,'read_supplier_attestation'),
        'permit':(ProviderCapacitySigningPermit,permit,'read_signing_permit'),
        'bootstrap':(ProviderCapacityOriginBootstrap,bootstrap,'read_origin_bootstrap')}
    model_type,make_body,function=types[kind]
    body=model_type.model_validate(make_body());payload=body.model_dump(mode='json',by_alias=True)
    raw=canonical_json(payload);assert parse_signed_capacity_body(raw,model_type)==body
    key=Ed25519PrivateKey.generate();public=key.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    signature=key.sign(raw)
    if fault=='raw-change':raw=canonical_json({**payload,'keyId':payload['keyId']+'-changed'})
    elif fault=='signature-change':signature=bytes([signature[0]^1])+signature[1:]
    elif fault=='key-change':public=Ed25519PrivateKey.generate().public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    elif fault=='signed-duplicate':
        purpose=json.dumps(payload['purpose']).encode()
        raw=raw.replace(b'"purpose":'+purpose,b'"purpose":'+purpose+b',"purpose":'+purpose)
        signature=key.sign(raw)
    elif fault=='signed-schema':raw=canonical_json({**payload,'schemaVersion':2});signature=key.sign(raw)
    elif fault=='signed-purpose':raw=canonical_json({**payload,'purpose':'wrong-document-domain'});signature=key.sign(raw)
    ddl=(CAPACITY_IDENTIFIER_PROFILE_SQL+CAPACITY_DEPLOYMENT_TARGET_PROFILE_SQL+CAPACITY_SIGNING_PERMIT_PROFILE_SQL+
        CAPACITY_ORIGIN_BOOTSTRAP_PROFILE_SQL+CAPACITY_SOURCE_POLICY_PROFILE_SQL+CAPACITY_SUPPLIER_ATTESTATION_PROFILE_SQL)
    verify="SELECT aos_ed25519.verify(decode('%s','hex'),decode('%s','hex'),decode('%s','hex'));"%(signature.hex(),raw.hex(),public.hex())
    read="SELECT aos_capacity_publication_private.%s(decode('%s','hex'));"%(function,raw.hex())
    if fault in ['raw-change','signature-change','key-change']:
        parse_signed_capacity_body(raw,model_type)
        assert native_profile_runner(ddl+verify)=='f'
    elif fault.startswith('signed-'):
        # Identical signed bytes really verify. Shape failure is independent.
        assert native_profile_runner(ddl+verify)=='t'
        with pytest.raises(ValueError):parse_signed_capacity_body(raw,model_type)
        assert 'CAPACITY_' in native_profile_runner(ddl+verify+read,False)
    else:
        result=native_profile_runner(ddl+verify+read+
            "SELECT encode(pg_catalog.sha256(decode('%s','hex')),'hex');"%raw.hex()).splitlines()
        assert result[0]=='t' and json.loads(result[1])==payload
        assert result[2]==hashlib.sha256(raw).hexdigest()


def test_original_full_root_snapshot_exceeds_signed_document_array_scope(native_profile_runner,tmp_path):
    import base64
    from aos_api.asset_registry.signature import FileTrustRootProvider
    public=base64.b64encode(bytes(range(32))).decode('ascii')
    roots=[dict(publisher='independent-authority',keyId='key-'+str(i),algorithm='Ed25519',
        publicKey=public,notBefore='2020-01-01T00:00:00Z',notAfter='2030-01-01T00:00:00Z',
        revokedAt=None,revision='sha256:'+'a'*64) for i in range(1001)]
    roots[0]['keyId']='key with internal space'
    roots[-1]['keyId']='k'*240
    raw=canonical_json(dict(trustRoots=roots));assert len(raw)<1024*1024
    path=tmp_path/'controlled-root-snapshot.json';path.write_bytes(raw);path.chmod(0o600)
    snapshot=FileTrustRootProvider(path).snapshot()
    for entry in roots:
        root=snapshot.get_trust_root(publisher=entry['publisher'],key_id=entry['keyId'])
        assert root is not None and root.public_key==bytes(range(32))
        assert root.revision==entry['revision'] and root.revoked_at is None
    failure=native_profile_runner("SELECT aos_capacity_publication_private.read_signed_body(decode('%s','hex'));"%raw.hex(),False)
    assert 'CAPACITY_SIGNED_BODY_PROFILE_REQUIRED' in failure
    exact=native_profile_runner("SELECT aos_capacity_publication_private.canonical_signed_json(convert_from(decode('%s','hex'),'UTF8')::json,1);"%raw.hex(),False)
    assert 'CAPACITY_SIGNED_BODY_ARRAY' in exact


def test_original_root_snapshot_complete_transport_preserves_safe_file(tmp_path):
    import hashlib,base64
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    roots=[dict(publisher='authority',keyId='key-'+str(i),algorithm='Ed25519',
        publicKey=base64.b64encode(bytes(range(32))).decode(),notBefore='2020-01-01T00:00:00Z',
        notAfter='2030-01-01T00:00:00Z',revokedAt=None,revision='sha256:'+'a'*64) for i in range(1001)]
    roots[0]['keyId']='key with space';roots[1]['keyId']='k'*240
    roots[2]['keyId']='surrogate-\ud800';roots[3]['keyId']='control-\x7f-字😀'
    roots[4].update(notBefore='0001-01-01T00:00:00+23:59',notAfter='2020-01-01T00:00:00+00:00:30.123456')
    roots[5]['revokedAt']='2026-01-01T01:02:03.000001+05:30'
    roots[7]['publicKey']=roots[7]['publicKey'][:-2]+'9='
    roots[8]['notBefore']='2020-01-01T00:00:00,100000Z'
    path=tmp_path/'root-full.json';path.write_text(json.dumps(dict(trustRoots=roots)));path.chmod(0o600)
    frozen=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    assert frozen.root_count==1001 and frozen.authorization=='ROOT_SNAPSHOT_TRANSPORT_ONLY_NO_TRUST_NO_REGISTRATION'
    assert frozen.content_hash=='sha256:'+hashlib.sha256(frozen.canonical_bytes).hexdigest()
    assert frozen.canonical_bytes.isascii() and len(frozen.canonical_bytes)<8*1024*1024
    values=json.loads(frozen.canonical_bytes)['trustRoots'];assert len(values)==1001
    by_key={r['keyId']:r for r in values}
    assert by_key['surrogate-\ud800']['publicKey']==roots[2]['publicKey']
    assert by_key['control-\x7f-字😀']['keyId']==roots[3]['keyId']
    assert by_key[roots[4]['keyId']]['notBefore']==roots[4]['notBefore']
    assert by_key[roots[4]['keyId']]['notAfter']==roots[4]['notAfter']
    assert by_key[roots[5]['keyId']]['revokedAt']==roots[5]['revokedAt']
    assert by_key[roots[7]['keyId']]['publicKey']==base64.b64encode(bytes(range(32))).decode()
    assert by_key[roots[8]['keyId']]['notBefore']=='2020-01-01T00:00:00.100000+00:00'
    path.write_text(json.dumps(dict(trustRoots=list(reversed(roots))),indent=2))
    assert freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))==frozen
    roots[6]['revokedAt']='2026-01-02T00:00:00Z'
    path.write_text(json.dumps(dict(trustRoots=roots)))
    assert freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path)).content_hash!=frozen.content_hash
    roots[6]['revokedAt']=None
    roots[6]['publicKey']=base64.b64encode(b'x'*32).decode()
    path.write_text(json.dumps(dict(trustRoots=roots)))
    assert freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path)).content_hash!=frozen.content_hash


def test_root_snapshot_transport_keeps_expanded_complete_domain(tmp_path):
    import base64
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    public=base64.b64encode(bytes(range(32))).decode()
    roots=[dict(publisher='p'+'\x7f'*238+'q',keyId='k'+str(i).zfill(4)+'\x7f'*234+'z',
        algorithm='Ed25519',publicKey=public,notBefore='2020-01-01T00:00:00Z',
        notAfter='2030-01-01T00:00:00Z',revokedAt=None,revision='sha256:'+'a'*64) for i in range(1200)]
    raw=json.dumps(dict(trustRoots=roots),ensure_ascii=False,separators=(',',':')).encode()
    assert len(raw)<1024*1024
    path=tmp_path/'expanded-root.json';path.write_bytes(raw);path.chmod(0o600)
    frozen=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    assert frozen.root_count==1200 and 2*1024*1024<len(frozen.canonical_bytes)<8*1024*1024
    assert len(json.loads(frozen.canonical_bytes)['trustRoots'])==1200


@pytest.mark.parametrize('fault',['duplicate','symlink','non-regular','non-file-provider'])
def test_root_snapshot_transport_retains_original_safe_file_rejections(tmp_path,fault):
    from aos_api.asset_registry.signature import FileTrustRootProvider,FrozenTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    path=tmp_path/'roots.json';path.write_text('{"trustRoots":[]}');path.chmod(0o600)
    provider=FileTrustRootProvider(path)
    if fault=='duplicate':path.write_text('{"trustRoots":[],"trustRoots":[]}')
    elif fault=='symlink':
        link=tmp_path/'root-link.json';link.symlink_to(path);provider=FileTrustRootProvider(link)
    elif fault=='non-regular':provider=FileTrustRootProvider(tmp_path)
    else:provider=FrozenTrustRootProvider({})
    with pytest.raises(ValueError):freeze_capacity_trust_root_snapshot(provider)


def test_root_snapshot_transport_uses_one_original_frozen_read(tmp_path,monkeypatch):
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    path=tmp_path/'roots.json';path.write_text('{"trustRoots":[]}');path.chmod(0o600)
    original=FileTrustRootProvider.snapshot;calls=[]
    def snapshot_then_file_changes(provider):
        calls.append(provider)
        frozen=original(provider)
        path.write_text('{"trustRoots":[],"trustRoots":[]}')
        return frozen
    monkeypatch.setattr(FileTrustRootProvider,'snapshot',snapshot_then_file_changes)
    frozen=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    assert frozen.root_count==0 and json.loads(frozen.canonical_bytes)==dict(trustRoots=[])
    assert len(calls)==1


def test_root_snapshot_transport_never_promotes_original_file_mode_to_trust(tmp_path):
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    path=tmp_path/'mode-only-root.json';path.write_text('{"trustRoots":[]}');path.chmod(0o666)
    frozen=freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    assert frozen.authorization=='ROOT_SNAPSHOT_TRANSPORT_ONLY_NO_TRUST_NO_REGISTRATION'
    assert not hasattr(frozen,'verified') and not hasattr(frozen,'execution_allowed')



def test_native_complete_root_transport_preserves_opaque_rows(native_profile_runner, tmp_path):
    """PG object functions decode legal file surrogates; array rows stay opaque."""
    import base64
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    roots = [dict(publisher='authority', keyId='key-' + str(i), algorithm='Ed25519',
        publicKey=base64.b64encode(bytes(range(32))).decode(), notBefore='2020-01-01T00:00:00Z',
        notAfter='2030-01-01T00:00:00Z', revokedAt=None, revision='sha256:' + 'a' * 64)
        for i in range(1001)]
    roots[0]['keyId'] = 'surrogate-\ud800'
    roots[1]['keyId'] = 'key with space'
    roots[2]['keyId'] = 'k' * 240
    roots[3]['notAfter'] = '2030-01-01T00:00:00+00:00:30.123456'
    path = tmp_path / 'native-root-full.json'
    path.write_text(json.dumps(dict(trustRoots=roots)))
    frozen = freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    raw = frozen.canonical_bytes
    raw_sql = "decode('%s','hex')" % raw.hex()
    assert raw.startswith(b'{"trustRoots":[') and raw.endswith(b']}')
    # Slice only this known frozen transport framing; this is not a caller-input parser.
    array_raw = raw[len(b'{"trustRoots":'):-1]
    array_sql = "convert_from(decode('%s','hex'),'UTF8')::json" % array_raw.hex()
    actual = native_profile_runner("SELECT 'sha256:'||encode(pg_catalog.sha256(" + raw_sql + "),'hex');")
    assert actual == frozen.content_hash
    assert native_profile_runner("SELECT convert_from(" + raw_sql + ",'UTF8')::json::text;") == raw.decode('ascii')
    row_texts = native_profile_runner("SELECT value::text FROM json_array_elements(" + array_sql +
        ") WITH ORDINALITY ORDER BY ordinality;").splitlines()
    expected = [json.dumps(root, sort_keys=True, separators=(',', ':'), ensure_ascii=True)
        for root in json.loads(raw)['trustRoots']]
    assert len(row_texts) == frozen.root_count == 1001
    assert row_texts == expected  # Every root retained in order; no unusable root silently dropped.
    surrogate = next(value for value in expected if 'surrogate-' in value)
    surrogate_sql = "convert_from(decode('%s','hex'),'UTF8')::json" % surrogate.encode('ascii').hex()
    for expression in [surrogate_sql + "->'keyId'", "json_object_keys(" + surrogate_sql + ")",
            "json_each(" + surrogate_sql + ")", "(" + surrogate_sql + ")::jsonb"]:
        assert 'Unicode low surrogate must follow a high surrogate' in native_profile_runner(
            'SELECT ' + expression + ';', False)
    assert 'Unicode low surrogate must follow a high surrogate' in native_profile_runner(
        "SELECT convert_from(" + raw_sql + ",'UTF8')::json->'trustRoots';", False)
    # An ordinary row remains individually interpretable after lossless full-array retention.
    normal_index = next(i for i, root in enumerate(json.loads(raw)['trustRoots'], 1) if root['keyId'] == 'key-10')
    normal = native_profile_runner("SELECT value::jsonb->>'keyId' FROM json_array_elements(" + array_sql +
        ") WITH ORDINALITY WHERE ordinality=" + str(normal_index) + ';')
    assert normal == 'key-10'



def test_native_root_identifier_original_file_domain(native_profile_runner, tmp_path):
    import base64, random
    from aos_api.asset_registry.signature import FileTrustRootProvider, _is_exact_identifier
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL
    rng = random.Random(631)
    identities = ['key with space', 'k' * 240, '😀' * 240, 'a\ud800z', 'a\udc00z',
        'a\ud800\ud800z', 'a\udc00\udc00z', 'a"\\z', '字😀é', 'a\x7fz']
    identities += ['a' + chr(i) + 'z' for i in range(1, 128)]
    identities += ['a' + ''.join(chr(rng.randrange(1, 0x110000)) for _ in range(20)) + 'z' for _ in range(30)]
    for identity in identities:
        assert _is_exact_identifier(identity)
    roots = [dict(publisher='authority', keyId=key, algorithm='Ed25519',
        publicKey=base64.b64encode(bytes(range(32))).decode(), notBefore='2020-01-01T00:00:00Z',
        notAfter='2030-01-01T00:00:00Z', revokedAt=None, revision='sha256:' + 'a' * 64)
        for key in dict.fromkeys(identities)]
    path = tmp_path / 'identity-domain.json'
    path.write_text(json.dumps(dict(trustRoots=roots)))
    frozen = freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    values = [root['keyId'] for root in json.loads(frozen.canonical_bytes)['trustRoots']]
    rows = []
    for number, identity in enumerate(values):
        literal = json.dumps(identity, ensure_ascii=True)
        rows.append("(%d,convert_from(decode('%s','hex'),'UTF8'))" % (number, literal.encode('ascii').hex()))
    result = native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL +
        'SELECT aos_capacity_publication_private.read_root_identifier_literal(literal)::text '
        'FROM (VALUES ' + ','.join(rows) + ') AS inputs(n,literal) ORDER BY n;').splitlines()
    assert len(result) == frozen.root_count == len(values)
    assert result == ['{' + ','.join(str(ord(ch)) for ch in identity) + '}' for identity in values]


@pytest.mark.parametrize('literal', [
    None, '', 'null', 'true', '[]', '{}', '""', ' "a"', '"a" ', '"a"x',
    '"a""z"', '"a\nz"', '"é"', r'"a\u0061z"', r'"a\u002fz"', r'"a\/z"',
    r'"a\u0008z"', r'"a\u0009z"', r'"a\u000az"', r'"a\u000cz"', r'"a\u000dz"',
    r'"a\u00FFz"', r'"a\x7fz"', r'"a\u0zzzz"', r'"a\u123"', r'"a\uz"',
    r'"a\u0000z"', r'"a\"', '"' + 'k' * 241 + '"', json.dumps('😀' * 241),
    json.dumps('a' + chr(127) + 'z', ensure_ascii=False),
])
def test_native_root_identifier_malformed_or_noncanonical_rejected(native_profile_runner, literal):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL
    argument = 'NULL' if literal is None else "convert_from(decode('%s','hex'),'UTF8')" % literal.encode('utf8').hex()
    assert 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' in native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL +
        'SELECT aos_capacity_publication_private.read_root_identifier_literal(' + argument + ');', False)


@pytest.mark.parametrize('code', [9,10,11,12,13,28,29,30,31,32,133,160,5760,
    8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288])
def test_native_root_identifier_original_strip_edges(native_profile_runner, code):
    from aos_api.asset_registry.signature import _is_exact_identifier
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL
    assert chr(code).isspace()
    for identity in [chr(code) + 'a', 'a' + chr(code)]:
        assert not _is_exact_identifier(identity)
        literal = json.dumps(identity).encode('ascii')
        assert 'CAPACITY_ROOT_IDENTIFIER_REQUIRED' in native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL +
            "SELECT aos_capacity_publication_private.read_root_identifier_literal(convert_from(decode('%s','hex'),'UTF8'));" % literal.hex(), False)


def test_native_root_identifier_catalog_boundary(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL
    result = native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + """
      SELECT p.provolatile,p.prosecdef,p.proconfig::text,
        (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0 AND privilege_type='EXECUTE')
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='aos_capacity_publication_private' AND p.proname='read_root_identifier_literal';
    """)
    assert result == 'i|f|{search_path=pg_catalog}|0'


def test_native_root_identifier_unicode_order_and_acl(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL
    # Numeric codepoint arrays preserve Python identity ordering even for lone surrogates.
    ordered = ['a', '字', '\ud800', '\udc00', '😀']
    assert sorted(ordered) == ordered
    expressions = ["aos_capacity_publication_private.read_root_identifier_literal(convert_from(decode('%s','hex'),'UTF8'))" %
        json.dumps(value).encode('ascii').hex() for value in ordered]
    assert native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + 'SELECT ' +
        ' AND '.join(expressions[i] + '<' + expressions[i+1] for i in range(len(expressions)-1)) + ';') == 't'
    # A canonical surrogate pair counts as one character, as in the original file JSON reader.
    assert native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL +
        "SELECT aos_capacity_publication_private.read_root_identifier_literal(" +
        "convert_from(decode('225c75643833645c756465303022','hex'),'UTF8'))::text;") == '{128512}'
    assert {code for code in range(0x110000) if chr(code).isspace()} == {
        9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,
        8199,8200,8201,8202,8232,8233,8239,8287,12288}
    error = native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + """
        CREATE ROLE capacity_root_profile_reader NOLOGIN;
        GRANT USAGE ON SCHEMA aos_capacity_publication_private TO capacity_root_profile_reader;
        SET LOCAL ROLE capacity_root_profile_reader;
        SELECT aos_capacity_publication_private.read_root_identifier_literal('"authority"');
    """, False)
    assert 'permission denied for function read_root_identifier_literal' in error



def test_native_full_root_snapshot_original_file_complete(native_profile_runner, tmp_path):
    import base64
    from datetime import datetime
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL,
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    roots = [dict(publisher='authority', keyId='key-' + str(i), algorithm='Ed25519',
        publicKey=base64.b64encode(bytes(range(32))).decode(), notBefore='2020-01-01T00:00:00Z',
        notAfter='2030-01-01T00:00:00Z', revokedAt=None, revision='sha256:' + 'a' * 64)
        for i in range(1001)]
    roots[0]['keyId'] = 'surrogate-\ud800'
    roots[1]['publisher'] = 'publisher with space'
    roots[2]['keyId'] = '😀' * 240
    roots[3].update(notBefore='0001-01-01T00:00:00+23:59', notAfter='9999-12-31T23:59:59.999999-23:59')
    roots[4].update(notBefore='2020-01-01T00:00:00.000001+00:00:30.123456',
        revokedAt='2019-01-01T01:02:03.000001-05:30:01.123456')
    roots[5]['keyId'] = 'quote-"-\\-字'
    path = tmp_path / 'full-native-roots.json'
    path.write_text(json.dumps(dict(trustRoots=roots)))
    frozen = freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    statement = "SELECT root_ordinal,publisher_literal,key_id_literal,encode(public_key,'hex'),root_revision," +         "((extract(epoch FROM not_before))*1000000)::bigint," +         "((extract(epoch FROM not_after))*1000000)::bigint," +         "COALESCE(((extract(epoch FROM revoked_at))*1000000)::bigint::text,'null')," +         "encode(canonical_root,'hex') FROM aos_capacity_publication_private.read_root_snapshot(" +         "decode('%s','hex')) ORDER BY root_ordinal;" % frozen.canonical_bytes.hex()
    result = native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL + statement).splitlines()
    def micros(value):
        if value is None: return 'null'
        dt = datetime.fromisoformat(value)
        delta = dt.replace(tzinfo=None) - datetime(1970,1,1) - dt.utcoffset()
        return str((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds)
    expected = []
    for i, root in enumerate(json.loads(frozen.canonical_bytes)['trustRoots'], 1):
        raw = json.dumps(root, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('ascii')
        expected.append('|'.join([str(i), json.dumps(root['publisher']), json.dumps(root['keyId']),
            bytes(range(32)).hex(), root['revision'], micros(root['notBefore']), micros(root['notAfter']),
            micros(root['revokedAt']), raw.hex()]))
    assert len(result) == frozen.root_count == 1001
    assert result == expected


def _root_snapshot_fixture_row(key='key-0'):
    import base64
    return dict(algorithm='Ed25519', publisher='authority', keyId=key,
        publicKey=base64.b64encode(bytes(range(32))).decode(), notBefore='2020-01-01T00:00:00+00:00',
        notAfter='2030-01-01T00:00:00+00:00', revokedAt=None, revision='sha256:'+'a'*64)


def _native_root_snapshot_count(runner, raw, success=True, limit=False):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL,
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    argument = 'NULL' if raw is None else "decode('%s','hex')" % raw.hex()
    select = 'SELECT root_ordinal' if limit else 'SELECT count(*)'
    ddl = CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL
    if raw is not None and len(raw) > 1024*1024:
        # Supply large bodies as stored values, not optimizer-visible giant constants.
        # The temporary input is rolled back with the native fixture transaction.
        ddl += 'CREATE TEMP TABLE root_snapshot_parts(n integer,part text);'
        ddl += 'COPY root_snapshot_parts FROM STDIN;\n'
        ddl += ''.join(str(i) + '\t' + raw[pos:pos+32768].hex() + '\n'
            for i,pos in enumerate(range(0,len(raw),32768)))
        ddl += '\\.\n'
        ddl += 'CREATE TEMP TABLE root_snapshot_input(message bytea NOT NULL);'
        ddl += "INSERT INTO root_snapshot_input SELECT decode(string_agg(part,'' ORDER BY n),'hex') FROM root_snapshot_parts;"
        import hashlib
        ddl += "DO $verify$ BEGIN IF (SELECT encode(pg_catalog.sha256(message),'hex') FROM root_snapshot_input) <> '" + \
            hashlib.sha256(raw).hexdigest() + "' THEN RAISE EXCEPTION 'copied root bytes mismatch'; END IF; END $verify$;"
        source = 'root_snapshot_input CROSS JOIN LATERAL aos_capacity_publication_private.read_root_snapshot(message)'
    else:
        source = 'aos_capacity_publication_private.read_root_snapshot(' + argument + ')'
    return runner(ddl + select + ' FROM ' + source + (' LIMIT 1;' if limit else ';'), success)


@pytest.mark.parametrize('fault', ['missing', 'extra', 'algorithm', 'key-type', 'publisher-empty',
    'identifier-241', 'nul', 'base64-short', 'base64-padbits', 'base64-whitespace', 'revision-uppercase',
    'revision-type', 'naive', 'year-zero', 'year-five-digits', 'day', 'leap-day', 'hour', 'minute',
    'second', 'local-fraction-zero', 'local-fraction-short', 'offset-hour', 'offset-minute', 'offset-second',
    'offset-fraction-zero', 'offset-zero-seconds', 'offset-negative-zero', 'offset-subsecond-utc',
    'equal-window', 'reverse-window', 'revocation-invalid', 'duplicates', 'descending', 'late-invalid',
    'spacing', 'duplicate-field', 'top-extra', 'top-duplicate', 'array-shape', 'root-shape', 'non-ascii',
    'root-field-order', 'escaped-ascii', 'null'])
def test_native_full_root_snapshot_single_fault_rejected(native_profile_runner, fault):
    root = _root_snapshot_fixture_row()
    roots = [root]
    if fault == 'missing': root.pop('publisher')
    elif fault == 'extra': root['verified'] = True
    elif fault == 'algorithm': root['algorithm'] = 'RSA'
    elif fault == 'key-type': root['keyId'] = 12
    elif fault == 'publisher-empty': root['publisher'] = ''
    elif fault == 'identifier-241': root['keyId'] = 'k' * 241
    elif fault == 'nul': root['keyId'] = 'a\x00z'
    elif fault == 'base64-short': root['publicKey'] = 'YQ=='
    elif fault == 'base64-padbits': root['publicKey'] = root['publicKey'][:-2] + '9='
    elif fault == 'base64-whitespace': root['publicKey'] += '\n'
    elif fault == 'revision-uppercase': root['revision'] = 'sha256:'+'A'*64
    elif fault == 'revision-type': root['revision'] = True
    elif fault == 'naive': root['notBefore'] = '2020-01-01T00:00:00'
    elif fault == 'year-zero': root['notBefore'] = '0000-01-01T00:00:00+00:00'
    elif fault == 'year-five-digits': root['notBefore'] = '10000-01-01T00:00:00+00:00'
    elif fault == 'day': root['notBefore'] = '2020-04-31T00:00:00+00:00'
    elif fault == 'leap-day': root['notBefore'] = '2019-02-29T00:00:00+00:00'
    elif fault == 'hour': root['notBefore'] = '2020-01-01T24:00:00+00:00'
    elif fault == 'minute': root['notBefore'] = '2020-01-01T00:60:00+00:00'
    elif fault == 'second': root['notBefore'] = '2020-01-01T00:00:60+00:00'
    elif fault == 'local-fraction-zero': root['notBefore'] = '2020-01-01T00:00:00.000000+00:00'
    elif fault == 'local-fraction-short': root['notBefore'] = '2020-01-01T00:00:00.1+00:00'
    elif fault == 'offset-hour': root['notBefore'] = '2020-01-01T00:00:00+24:00'
    elif fault == 'offset-minute': root['notBefore'] = '2020-01-01T00:00:00+00:60'
    elif fault == 'offset-second': root['notBefore'] = '2020-01-01T00:00:00+00:00:60'
    elif fault == 'offset-fraction-zero': root['notBefore'] = '2020-01-01T00:00:00+00:00:01.000000'
    elif fault == 'offset-zero-seconds': root['notBefore'] = '2020-01-01T00:00:00+00:00:00'
    elif fault == 'offset-negative-zero': root['notBefore'] = '2020-01-01T00:00:00-00:00'
    elif fault == 'offset-subsecond-utc': root['notBefore'] = '2020-01-01T00:00:00+00:00:00.123456'
    elif fault == 'equal-window': root['notBefore'] = root['notAfter']
    elif fault == 'reverse-window': root['notBefore'] = '2040-01-01T00:00:00+00:00'
    elif fault == 'revocation-invalid': root['revokedAt'] = 7
    elif fault == 'duplicates': roots.append(dict(root))
    elif fault == 'descending': roots = [_root_snapshot_fixture_row('z'), root]
    elif fault == 'late-invalid': roots.append(dict(_root_snapshot_fixture_row('z'), algorithm='RSA'))
    elif fault == 'array-shape': roots = root
    elif fault == 'root-shape': roots = [7]
    elif fault == 'non-ascii': root['publisher'] = '字'
    payload = dict(trustRoots=roots)
    if fault == 'top-extra': payload['verified'] = True
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=fault != 'non-ascii').encode('utf8')
    if fault == 'spacing': raw = raw.replace(b':', b': ', 1)
    elif fault == 'duplicate-field': raw = raw.replace(b'"algorithm":"Ed25519"', b'"algorithm":"Ed25519","algorithm":"Ed25519"')
    elif fault == 'top-duplicate': raw = raw[:-1] + b',"trustRoots":[]}'
    elif fault == 'root-field-order': raw = raw.replace(b'"algorithm":"Ed25519","keyId":"key-0"', b'"keyId":"key-0","algorithm":"Ed25519"')
    elif fault == 'escaped-ascii': raw = raw.replace(b'"key-0"', br'"\u006bey-0"')
    elif fault == 'null': raw = None
    assert 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' in _native_root_snapshot_count(native_profile_runner, raw,
        False, limit=fault=='late-invalid')


def test_native_full_root_snapshot_count_size_and_empty(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL,
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    assert _native_root_snapshot_count(native_profile_runner, b'{"trustRoots":[]}') == '0'
    roots = [_root_snapshot_fixture_row('key-%05d' % i) for i in range(10000)]
    raw = json.dumps(dict(trustRoots=roots), sort_keys=True, separators=(',', ':')).encode('ascii')
    assert 2*1024*1024 < len(raw) < 8*1024*1024
    assert _native_root_snapshot_count(native_profile_runner, raw) == '10000'
    roots.append(_root_snapshot_fixture_row('key-10000'))
    raw = json.dumps(dict(trustRoots=roots), sort_keys=True, separators=(',', ':')).encode('ascii')
    assert 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' in _native_root_snapshot_count(native_profile_runner, raw, False)
    assert 'CAPACITY_ROOT_SNAPSHOT_REQUIRED' in native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL +
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL + "SELECT count(*) FROM aos_capacity_publication_private.read_root_snapshot(" +
        "convert_to(repeat('a',8388609),'UTF8'));", False)


def test_native_full_root_snapshot_original_time_normalizations(native_profile_runner, tmp_path):
    from datetime import datetime
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL,
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    times = ['2020-02-29T23:59:59.000001+05:30', '2020-01-01T00:00:00-00:00:30.123456',
        '2020-01-01T00:00:00+23:59:59.999999', '2020-01-01T00:00:00-23:59:59.999999',
        '2020-01-01T00:00:00+00:00:00.123456', '2020-01-01T00:00:00-00:00',
        '2020-01-01T00:00:00+05:30:00.123456', '2020-01-01T00:00:00,100000Z',
        '2020-W01-3T00:00:00Z', '2020-01-01T00:00:00+05', '2020-01-01T00:00:00.000000Z']
    roots = [dict(_root_snapshot_fixture_row('key-%02d' % i), notBefore=value)
        for i,value in enumerate(times)]
    path = tmp_path / 'normalized-root-times.json'
    path.write_text(json.dumps(dict(trustRoots=roots)))
    frozen = freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    normalized = json.loads(frozen.canonical_bytes)['trustRoots']
    assert normalized[4]['notBefore'] == '2020-01-01T00:00:00+00:00'
    actual = native_profile_runner(CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL +
        'SELECT ((extract(epoch FROM not_before))*1000000)::bigint FROM ' +
        "aos_capacity_publication_private.read_root_snapshot(decode('%s','hex')) ORDER BY root_ordinal;" %
        frozen.canonical_bytes.hex()).splitlines()
    expected = []
    for root in normalized:
        dt = datetime.fromisoformat(root['notBefore'])
        delta = dt.replace(tzinfo=None)-datetime(1970,1,1)-dt.utcoffset()
        expected.append(str((delta.days*86400+delta.seconds)*1000000+delta.microseconds))
    assert actual == expected


def test_native_full_root_snapshot_original_expanded_file(native_profile_runner, tmp_path):
    from aos_api.asset_registry.signature import FileTrustRootProvider
    from aos_api.aip_provider_capacity_publication_contracts import freeze_capacity_trust_root_snapshot
    roots = [dict(_root_snapshot_fixture_row('k'+str(i).zfill(4)+'\x7f'*234+'z'),
        publisher='p'+'\x7f'*238+'q') for i in range(1200)]
    raw = json.dumps(dict(trustRoots=roots), ensure_ascii=False, separators=(',', ':')).encode('utf8')
    assert len(raw) < 1024*1024
    path = tmp_path / 'native-expanded-roots.json'
    path.write_bytes(raw)
    frozen = freeze_capacity_trust_root_snapshot(FileTrustRootProvider(path))
    assert 2*1024*1024 < len(frozen.canonical_bytes) < 8*1024*1024
    assert _native_root_snapshot_count(native_profile_runner, frozen.canonical_bytes) == '1200'


def test_native_full_root_snapshot_catalog_and_role_denial(native_profile_runner):
    from aos_api.aip_provider_capacity_publication_store import (CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL,
        CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL)
    ddl = CAPACITY_ROOT_IDENTIFIER_PROFILE_SQL + CAPACITY_ROOT_SNAPSHOT_PROFILE_SQL
    actual = native_profile_runner(ddl + """
      SELECT p.proname,p.provolatile,p.prosecdef,p.proconfig::text,
        (SELECT count(*) FROM aclexplode(p.proacl) WHERE grantee=0 AND privilege_type='EXECUTE')
      FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
      WHERE n.nspname='aos_capacity_publication_private'
        AND p.proname IN ('read_root_time_literal','read_root_snapshot') ORDER BY p.proname;
    """).splitlines()
    assert actual == ['read_root_snapshot|i|f|{search_path=pg_catalog}|0',
        'read_root_time_literal|i|f|{search_path=pg_catalog}|0']
    error = native_profile_runner(ddl + """
        CREATE ROLE capacity_root_snapshot_reader NOLOGIN;
        GRANT USAGE ON SCHEMA aos_capacity_publication_private TO capacity_root_snapshot_reader;
        SET LOCAL ROLE capacity_root_snapshot_reader;
        SELECT count(*) FROM aos_capacity_publication_private.read_root_snapshot(convert_to('{"trustRoots":[]}','UTF8'));
    """, False)
    assert 'permission denied for function read_root_snapshot' in error


def test_native_full_root_snapshot_near_transport_bound_stored_input(native_profile_runner):
    # Pure transport upper domain, not proof of original file/anchor provenance.
    roots = [_root_snapshot_fixture_row('key-%05d-' % i + '\x7f'*85) for i in range(10000)]
    raw = json.dumps(dict(trustRoots=roots), sort_keys=True, separators=(',', ':')).encode('ascii')
    assert 7*1024*1024 < len(raw) < 8*1024*1024
    assert _native_root_snapshot_count(native_profile_runner, raw) == '10000'
