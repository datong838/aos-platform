from datetime import timedelta
from types import SimpleNamespace

import pytest

from aos_api.ecommerce_analyst_growth_plan_sources import require_current_revision
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, DecisionSummaryRevision
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_draft import generation

SCOPE = TenantScope("org-org", "dev-project")


class Connection:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        assert params[:2] == SCOPE.key
        assert "FOR SHARE OF head" in sql
        return SimpleNamespace(fetchone=lambda: self.row)


def example():
    decision, _, _ = generation()
    ref = AnalystExactRef(resourceType="DecisionSummaryRevision", resourceId=decision.decision_id,
                          revision=decision.revision, contentHash=decision.content_hash)
    return decision, ref, dict(payload=decision.model_dump(mode="json", by_alias=True), content_hash=decision.content_hash)


def test_reads_only_exact_current_scoped_decision():
    decision, ref, row = example()
    conn = Connection(row)
    assert require_current_revision(conn, SCOPE, ref) == decision
    assert conn.calls[0][1][2:] == (ref.resource_id, ref.revision)
    assert "revision.revision=head.current_revision" in conn.calls[0][0]


@pytest.mark.parametrize("change", ["missing", "hash", "body", "tenant", "identity", "kind"])
def test_rejects_missing_stale_or_forged_revision(change):
    _, ref, row = example()
    if change == "missing":
        row = None
    elif change == "hash":
        row["content_hash"] = "f" * 64
    elif change == "body":
        row["payload"]["conclusion"] = "伪造"
    elif change == "tenant":
        row["payload"]["tenant"]["orgId"] = "dev-org"
    elif change == "identity":
        row["payload"]["decisionId"] = "wrong"
    else:
        ref = ref.model_copy(update={"resource_type": "Task"})
    with pytest.raises(ValueError):
        require_current_revision(Connection(row), SCOPE, ref)


@pytest.mark.parametrize("change", [None, "revoked", "stale", "empty", "bundle_hash", "brief", "evidence_revoked",
    "evidence_hash", "evidence_missing", "marking", "future", "old", "missing_freshness", "cutoff_old", "zero_ttl"])
def test_source_snapshot_rejects_unusable_dependencies(monkeypatch, change):
    import aos_api.ecommerce_analyst_growth_plan_sources as module
    from test_ecommerce_analyst_authority_contracts import NOW
    decision, ref, _ = example()
    insight = SimpleNamespace(cutoff_at=NOW, evidence_refs=decision.evidence_refs)
    evidence = SimpleNamespace(resource_type="Evidence", resource_id="evidence-1", revision=1, content_hash="b" * 64)
    bundle = SimpleNamespace(tenant=decision.tenant, content_hash="a" * 64, lifecycle="frozen", coverage="complete",
        freshness="fresh", revoked=False, item_refs=[evidence], cutoff_at=NOW,
        brief_ref=SimpleNamespace(resource_id="brief-1", revision=1, content_hash="c" * 64))
    brief = SimpleNamespace(revision=1, content_hash="c" * 64, lifecycle="frozen")
    row = dict(content_hash="b" * 64, freshness_at=NOW, payload={"marking": ["internal"]}, revoked=False)
    if change == "revoked": bundle.revoked = True
    elif change == "stale": bundle.freshness = "stale"
    elif change == "empty": bundle.item_refs = []
    elif change == "bundle_hash": bundle.content_hash = "f" * 64
    elif change == "brief": brief.revision = 2
    elif change == "evidence_revoked": row["revoked"] = True
    elif change == "evidence_hash": row["content_hash"] = "f" * 64
    elif change == "evidence_missing": row = None
    elif change == "marking": row["payload"]["marking"] = ["confidential"]
    elif change == "future": row["freshness_at"] = NOW + timedelta(seconds=1)
    elif change == "old": row["freshness_at"] = NOW - timedelta(days=2)
    elif change == "missing_freshness": row["freshness_at"] = None
    elif change == "cutoff_old": bundle.cutoff_at = NOW - timedelta(days=2)

    def current(conn, scope, requested):
        assert scope == SCOPE
        return decision if requested.resource_type == "DecisionSummaryRevision" else insight

    class Store:
        def get_evidence_bundle(self, scope, identity, revision, *, conn, markings):
            assert scope == SCOPE and identity == "bundle-1" and markings == ["internal"]
            return bundle
        def get_brief(self, scope, identity, *, conn):
            assert scope == SCOPE and identity == "brief-1"
            return brief

    class EvidenceConnection:
        def execute(self, sql, params):
            assert params == (*SCOPE.key, "evidence-1")
            assert "aip_evidence_revoke_event" in sql
            return SimpleNamespace(fetchone=lambda: row)

    monkeypatch.setattr(module, "require_current_revision", current)
    monkeypatch.setattr(module, "AipProductionContractStore", Store)
    args = dict(markings=["internal"], now=NOW, max_source_age=timedelta(days=1) if change != "zero_ttl" else timedelta(0))
    if change is None:
        assert module.require_growth_plan_sources(EvidenceConnection(), SCOPE, ref, **args) == decision
    else:
        with pytest.raises(ValueError):
            module.require_growth_plan_sources(EvidenceConnection(), SCOPE, ref, **args)
