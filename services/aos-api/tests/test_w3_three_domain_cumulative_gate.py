from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from aos_api.ecommerce_w3_cumulative_gate import (
    ISOLATION_CANARY,
    REAL_TENANT,
    W3AxisEvidence,
    W3CumulativeAxis,
    W3CumulativeEvidencePack,
    W3CumulativeGateError,
    W3ReleaseIdentity,
    evaluate_w3_cumulative_gate,
)


def _sha(char: str) -> str:
    return f"sha256:{char * 64}"


def _identity() -> W3ReleaseIdentity:
    return W3ReleaseIdentity(
        git_commit="7138b83",
        app_revision="workshop-w3-14",
        schema_hash=_sha("1"),
        openapi_hash=_sha("2"),
        sdk_hash=_sha("3"),
        web_build_hash=_sha("4"),
        bundle_hash=_sha("5"),
        migration_head="w3_018",
        route_hash=_sha("6"),
        cutoff=datetime(2026, 8, 25, 4, 0, tzinfo=timezone.utc),
    )


def _pack() -> W3CumulativeEvidencePack:
    identity = _identity()
    return W3CumulativeEvidencePack(
        release_identity=identity,
        axes=tuple(
            W3AxisEvidence(
                axis=axis,
                release_identity_id=identity.identity_id,
                status="GREEN",
                evidence_refs=(f"evidence:{axis.value}",),
            )
            for axis in W3CumulativeAxis
        ),
        delivery_receipts={
            "W3-10": "receipt:w3-10",
            "W3-11": "receipt:w3-11",
            "W3-12": "receipt:w3-12",
            "W3-13": "receipt:w3-13",
        },
        authority_owners={
            "public_orchestration": "aip.canonical",
            "content_campaign": "workshop.content_campaign",
            "unified_operations": "workshop.operation_case",
            "analyst": "workshop.analyst",
        },
        positive_tenant=REAL_TENANT,
        isolation_tenant=ISOLATION_CANARY,
        release_applied=False,
        migration_applied=False,
    )


def test_same_release_seven_axis_pack_allows_next_wave_without_release_claim() -> None:
    result = evaluate_w3_cumulative_gate(_pack())

    assert result.status == "CUMULATIVE_CODE_BROWSER_GREEN_NO_RELEASE"
    assert result.axis_count == 7
    assert result.receipt_count == 4
    assert result.next_wave_allowed is True
    assert result.operational_release_green is False


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda pack: replace(pack, axes=pack.axes[:-1]), "seven cumulative axes"),
        (
            lambda pack: replace(
                pack,
                axes=(replace(pack.axes[0], release_identity_id="w3:stale"),)
                + pack.axes[1:],
            ),
            "cross-release",
        ),
        (
            lambda pack: replace(
                pack,
                axes=(replace(pack.axes[0], status="UNKNOWN"),) + pack.axes[1:],
            ),
            "not GREEN",
        ),
        (
            lambda pack: replace(
                pack, delivery_receipts={"W3-10": "receipt:w3-10"}
            ),
            "four exact W3 delivery receipts",
        ),
        (
            lambda pack: replace(pack, positive_tenant=ISOLATION_CANARY),
            "real tenant",
        ),
        (
            lambda pack: replace(pack, external_effect_count=1),
            "must not perform external effects",
        ),
    ],
)
def test_gate_rejects_incomplete_stale_unknown_or_unsafe_packs(
    mutation, message: str
) -> None:
    with pytest.raises(W3CumulativeGateError, match=message):
        evaluate_w3_cumulative_gate(mutation(_pack()))


def test_gate_rejects_second_authority_owner_and_partial_release() -> None:
    duplicate_owner = replace(
        _pack(),
        authority_owners={
            "public_orchestration": "aip.canonical",
            "content_campaign": "workshop.content_campaign",
            "unified_operations": "workshop.operation_case",
            "analyst": "workshop.operation_case",
        },
    )
    with pytest.raises(W3CumulativeGateError, match="canonical mapping"):
        evaluate_w3_cumulative_gate(duplicate_owner)

    partial_release = replace(_pack(), release_applied=True, migration_applied=False)
    with pytest.raises(W3CumulativeGateError, match="partial green"):
        evaluate_w3_cumulative_gate(partial_release)


def test_runtime_green_requires_exact_release_authorization() -> None:
    unauthorized = replace(_pack(), release_applied=True, migration_applied=True)
    with pytest.raises(W3CumulativeGateError, match="authorization ref"):
        evaluate_w3_cumulative_gate(unauthorized)

    authorized = replace(
        unauthorized, release_authorization_ref="release-authorization:exact"
    )
    result = evaluate_w3_cumulative_gate(authorized)
    assert result.status == "CUMULATIVE_RUNTIME_GREEN"
    assert result.operational_release_green is True
