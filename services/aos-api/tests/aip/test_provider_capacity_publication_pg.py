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
