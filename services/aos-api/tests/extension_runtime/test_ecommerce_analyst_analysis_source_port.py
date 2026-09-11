from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

import aos_api.ecommerce_analyst_analysis_source_port as module
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


NOW = datetime(2026, 9, 11, 8, tzinfo=UTC)
SCOPE = TenantScope("org-org", "dev-project")


def _request():
    return {
        "bundleRef": {
            "resourceType": "EvidenceBundleRevision",
            "resourceId": "bundle-1",
            "revision": 1,
            "contentHash": "b" * 64,
        },
        "grants": [
            {
                "decisionId": "disclosure-1",
                "request": {
                    "evidenceRef": {
                        "resourceType": "Evidence",
                        "resourceId": "evidence-1",
                        "revision": 1,
                        "contentHash": "a" * 64,
                    },
                    "purpose": "source",
                    "requestedLevel": "l3",
                    "taskId": "task-1",
                },
            }
        ],
    }


def test_host_port_binds_scope_and_narrow_transaction(monkeypatch):
    connection = object()
    transaction = HostTransaction(connection)
    calls = []
    expected = {"bundleRef": _request()["bundleRef"], "items": []}

    def read_analysis_bundle(**kwargs):
        calls.append(kwargs)
        return expected

    monkeypatch.setattr(module, "read_analysis_bundle", read_analysis_bundle)
    port = module.BoundEcommerceGrowthAnalysisSourcePort(transaction, SCOPE)
    result = port.read(
        task_id="task-1",
        actor="analyst-1",
        request=_request(),
        markings=("internal", "secret"),
        now=NOW,
        max_source_age_seconds=86_400,
        max_bytes=10_000,
    )

    assert result is expected
    assert len(calls) == 1
    assert calls[0]["conn"] is transaction
    assert calls[0]["scope"] is SCOPE
    assert calls[0]["task_id"] == "task-1"
    assert calls[0]["actor"] == "analyst-1"
    assert calls[0]["request"].bundle_ref.resource_id == "bundle-1"
    assert calls[0]["markings"] == ("internal", "secret")
    assert calls[0]["now"] == NOW
    assert calls[0]["max_source_age"] == timedelta(days=1)
    assert calls[0]["max_bytes"] == 10_000


@pytest.mark.parametrize("transaction,scope", [(object(), SCOPE), (HostTransaction(object()), object())])
def test_host_port_rejects_raw_connection_or_untrusted_scope(transaction, scope):
    with pytest.raises(TypeError, match="host transaction and tenant scope are required"):
        module.BoundEcommerceGrowthAnalysisSourcePort(transaction, scope)


@pytest.mark.parametrize(
    "change",
    [
        {"task_id": ""},
        {"actor": " "},
        {"request": []},
        {"markings": ["internal"]},
        {"markings": ("internal", "internal")},
        {"now": datetime(2026, 9, 11, 8)},
        {"max_source_age_seconds": 0},
        {"max_source_age_seconds": True},
        {"max_bytes": 0},
        {"max_bytes": 2_097_153},
    ],
)
def test_host_port_rejects_invalid_boundary_before_owner_read(monkeypatch, change):
    calls = []
    monkeypatch.setattr(module, "read_analysis_bundle", lambda **kwargs: calls.append(kwargs))
    port = module.BoundEcommerceGrowthAnalysisSourcePort(HostTransaction(object()), SCOPE)
    kwargs = dict(
        task_id="task-1",
        actor="analyst-1",
        request=_request(),
        markings=("internal",),
        now=NOW,
        max_source_age_seconds=86_400,
        max_bytes=10_000,
    )
    kwargs.update(change)
    with pytest.raises(ValueError, match="invalid analysis source read boundary"):
        port.read(**kwargs)
    assert calls == []
