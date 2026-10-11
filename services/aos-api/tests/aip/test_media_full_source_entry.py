"""Media Source entry contract; doubles prove plumbing, never signed authority."""
from contextlib import contextmanager

import pytest

from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractDependencyBlocked,
)
from aos_api.aip_production_contracts import RegisterMediaGateProfileRequest
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")


def request():
    def ref(kind, name):
        return dict(resourceType=kind, resourceId=name, revision=1, contentHash="1" * 64)
    return RegisterMediaGateProfileRequest.model_validate(dict(
        profileId="test-only-full-media", revision=1,
        sourceBundleRef=ref("BundleManifestRevision", "test-only-manifest"),
        signatureRef=ref("BundleSignatureVerification", "test-only-signature"),
        policyRef=ref("MediaGatePolicyRevision", "test-only-policy"),
        gates=[dict(gateId="media."+kind, kind=kind,
                    ruleRef=ref("EvalRuleRevision", "test-only-rule-"+kind),
                    returnStage="review") for kind in ["fact", "brand", "copyright", "platform"]],
    ))


class UnexpectedDatabaseAccess(Exception):
    pass


def test_legacy_stage_success_cannot_authorize_media_signature_and_policy():
    calls = []
    @contextmanager
    def connect(scope):
        calls.append(scope)
        raise UnexpectedDatabaseAccess()
        yield
    store = AipProductionContractStore(
        contract_connect_factory=connect,
        stage_template_source_resolver=lambda *args: True,
    )
    with pytest.raises(ProductionContractDependencyBlocked, match="SIGNED_SOURCE"):
        store.register_media_gate_profile(SCOPE, "test-only", "key", request())
    assert calls == []


@pytest.mark.parametrize("verdict", [False, None, 0, 1, "true", {"valid": True}])
def test_dedicated_resolver_rejects_non_true_before_receipt_or_rule_sql(verdict):
    events = []
    body = request()
    class Connection:
        def execute(self, *args):
            raise UnexpectedDatabaseAccess()
        def commit(self):
            raise UnexpectedDatabaseAccess()
    conn = Connection()
    @contextmanager
    def connect(scope):
        events.append("begin")
        try:
            yield conn
        except Exception:
            events.append("rollback")
            raise
    def resolve(transaction, scope, received):
        assert transaction is conn and scope == SCOPE and received is body
        assert len(received.gates) == 4
        assert received.signature_ref.resource_type == "BundleSignatureVerification"
        assert received.policy_ref.resource_type == "MediaGatePolicyRevision"
        events.append("source")
        return verdict
    store = AipProductionContractStore(contract_connect_factory=connect,
                                       media_gate_source_resolver=resolve)
    with pytest.raises(ProductionContractDependencyBlocked, match="SIGNED_SOURCE"):
        store.register_media_gate_profile(SCOPE, "test-only", "key", body)
    assert events == ["begin", "source", "rollback"]


def test_exact_true_only_reaches_original_receipt_path_after_source(monkeypatch):
    events = []
    conn = object()
    @contextmanager
    def connect(scope):
        yield conn
    def resolve(transaction, scope, body):
        assert transaction is conn and scope == SCOPE
        events.append("source")
        return True
    store = AipProductionContractStore(contract_connect_factory=connect,
                                       media_gate_source_resolver=resolve)
    def replay(*args):
        events.append("original-receipt")
        raise UnexpectedDatabaseAccess("stop plumbing test before actual persistence")
    monkeypatch.setattr(store, "_replay", replay)
    with pytest.raises(UnexpectedDatabaseAccess):
        store.register_media_gate_profile(SCOPE, "test-only", "key", request())
    assert events == ["source", "original-receipt"]


def test_source_error_is_not_silently_downgraded_to_legacy_stage():
    events = []
    @contextmanager
    def connect(scope):
        try:
            yield object()
        finally:
            events.append("transaction-exit")
    def resolve(*args):
        raise RuntimeError("source unavailable")
    def stage(*args):
        events.append("legacy-stage")
        return True
    store = AipProductionContractStore(contract_connect_factory=connect,
                                       media_gate_source_resolver=resolve,
                                       stage_template_source_resolver=stage)
    with pytest.raises(RuntimeError, match="source unavailable"):
        store.register_media_gate_profile(SCOPE, "test-only", "key", request())
    assert events == ["transaction-exit"]
