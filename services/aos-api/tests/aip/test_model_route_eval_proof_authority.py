import base64
from datetime import timedelta

import pytest

from aos_api.aip_model_route_eval_proof_authority import (
    RouteEvalProofAuthorityRejected,
    revalidate_route_eval_proof_signers,
)
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_finalization_proof import finalization_fixture


SCOPE = TenantScope("org-org", "dev-project")


def fixture():
    proof, manifest, *_ = finalization_fixture()
    return proof, manifest


def test_complete_route_proof_signers_are_current_and_return_only_stable_identities():
    proof, manifest = fixture()
    result = revalidate_route_eval_proof_signers(
        scope=SCOPE,
        proof=proof,
        manifest_bytes=manifest,
        checked_at=proof.finalized_at + timedelta(seconds=1),
        revoked_identity_ids=frozenset(),
    )
    assert result.execution_id == proof.execution_id
    assert result.manifest_hash == proof.manifest_hash
    assert result.identity_ids == tuple(sorted({
        item.signed_certificate.certificate.identity_id for item in proof.calls
    }))
    assert result.issuer_keys == tuple(sorted({
        (
            item.signed_certificate.certificate.issuer_id,
            item.signed_certificate.certificate.issuer_key_id,
        )
        for item in proof.calls
    }))
    assert not hasattr(result, "manifest_bytes")


@pytest.mark.parametrize(
    "fault",
    ["scope", "manifest", "naive", "before", "mutable", "invalid_member", "revoked", "expired"],
)
def test_route_proof_signer_currentness_fails_closed(fault):
    proof, manifest = fixture()
    scope = SCOPE
    checked_at = proof.finalized_at + timedelta(seconds=1)
    revoked = frozenset()
    if fault == "scope":
        scope = TenantScope("dev-org", "dev-project")
    elif fault == "manifest":
        manifest += b"\n"
    elif fault == "naive":
        checked_at = checked_at.replace(tzinfo=None)
    elif fault == "before":
        checked_at = proof.finalized_at - timedelta(microseconds=1)
    elif fault == "mutable":
        revoked = set()
    elif fault == "invalid_member":
        revoked = frozenset([b"not-an-identity"])
    elif fault == "revoked":
        revoked = frozenset([proof.calls[0].signed_certificate.certificate.identity_id])
    else:
        checked_at = min(
            item.signed_certificate.certificate.valid_until for item in proof.calls
        )
    with pytest.raises(RouteEvalProofAuthorityRejected, match="current Route proof signer"):
        revalidate_route_eval_proof_signers(
            scope=scope,
            proof=proof,
            manifest_bytes=manifest,
            checked_at=checked_at,
            revoked_identity_ids=revoked,
        )


def test_route_proof_signer_rejects_cryptographic_signature_drift():
    proof, manifest = fixture()
    first, second = proof.calls
    signed = first.signed_certificate.model_copy(
        update={"signature_base64": base64.b64encode(bytes(64)).decode("ascii")}
    )
    first = first.model_copy(
        update={
            "signed_certificate": signed,
            "certificate_hash": canonical_hash(
                signed.model_dump(mode="json", by_alias=True)
            ),
        }
    )
    # A nested signature cannot be changed independently of the signed-case
    # certificate hash.  Keep the malformed copied object to prove the public
    # boundary revalidates the complete proof before any signer conclusion.
    drifted = proof.model_copy(update={"calls": (first, second)})
    with pytest.raises(RouteEvalProofAuthorityRejected, match="current Route proof signer"):
        revalidate_route_eval_proof_signers(
            scope=SCOPE,
            proof=drifted,
            manifest_bytes=manifest,
            checked_at=proof.finalized_at + timedelta(seconds=1),
            revoked_identity_ids=frozenset(),
        )
