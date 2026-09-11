from datetime import datetime, timedelta, timezone
import os
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_portrait_sources as module
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.aip_production_contracts import CreateEvalContractRequest, EvalContractRevision
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from test_ecommerce_analyst_method_authority import method, SCOPE


def exact(kind, identity, content_hash, revision=1):
    return AnalystExactRef(resourceType=kind, resourceId=identity, revision=revision, contentHash=content_hash)


def metric():
    body = dict(metricId="order-count", revision=1, name="订单数", unit="count", source="canonical-order-query",
                window="explicit-task-window", aggregation="count", acceptedQuality=["measured"])
    return MetricDefinitionRevision(**body, contentHash=canonical_hash(body))


def eval_body(publication_hash="b" * 64):
    return CreateEvalContractRequest(suiteRef=exact("EvalSuiteRevision", "portrait-suite", "a" * 64).model_dump(mode="json", by_alias=True),
        publicationRef=exact("PublicationEvent", "portrait-publication", publication_hash).model_dump(mode="json", by_alias=True),
        releaseGateRef=exact("ReleaseGateDecision", "portrait-gate", "c" * 64).model_dump(mode="json", by_alias=True),
        artifactSchemaRef=dict(resourceType="Schema", resourceId="portrait-output", revision="1", authority="postgresql"),
        severityThresholds={"critical": 1.0}, gatePolicy={"mode": "all"}, returnMapping={"critical": "draft"}, overridePolicy={"allowed": False})


def setup(monkeypatch):
    method_item, metric_item = method(), metric()
    now = datetime.now(timezone.utc)
    body = eval_body()
    contract = EvalContractRevision(**body.model_dump(mode="python"), tenant=dict(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        contractId="portrait-eval", revision=2, version=2, contentHash=canonical_hash(body.model_dump(mode="json", by_alias=True)),
        lifecycle="frozen", readiness="ready", blockers=[], createdBy="compiler", createdAt=now)
    state = dict(metric=metric_item, contract=contract, latest=1, head=2,
                 gate=dict(status="passed", decision_hash="c" * 64, decided_at=now, expires_at=now + timedelta(days=30)))
    class Connection:
        def execute(self, sql, params):
            assert params[:2] == SCOPE.key
            if "max(revision)" in sql: row = {"revision": state["latest"]}
            elif "aip_eval_contract_head" in sql: row = {"current_revision": state["head"]}
            else: row = state["gate"]
            return SimpleNamespace(fetchone=lambda: row)
    conn = Connection()
    class Metrics:
        def __init__(self, factory): self.factory = factory
        def get_metric_definition(self, scope, identity, revision):
            with self.factory(scope) as bound: assert bound is conn
            return state["metric"]
    class Production:
        def __init__(self, factory): pass
        def get_eval_contract(self, scope, identity, **kwargs):
            assert kwargs["conn"] is conn
            return state["contract"]
    monkeypatch.setattr(module, "AipEvalAuthorityStore", Metrics)
    monkeypatch.setattr(module, "AipProductionContractStore", Production)
    monkeypatch.setattr(module, "require_current_revision", lambda c, scope, ref: method_item)
    kwargs = dict(conn=conn, scope=SCOPE, method_ref=exact("MethodRevision", method_item.method_id, method_item.content_hash),
        metric_refs=[exact("MetricDefinitionRevision", metric_item.metric_id, metric_item.content_hash)],
        eval_ref=exact("EvalContractRevision", contract.contract_id, contract.content_hash, 2), now=now)
    return kwargs, state, method_item


def test_same_connection_returns_only_authority_metadata(monkeypatch):
    kwargs, state, method_item = setup(monkeypatch)
    result = module.read_portrait_authorities(**kwargs)
    assert result == (method_item, [state["metric"]], state["contract"])
    assert "value" not in state["metric"].model_dump()


@pytest.mark.parametrize("drift", ["method_kind", "metric_kind", "duplicate", "missing", "metric_hash", "metric_body", "metric_latest",
    "eval_kind", "eval_head", "eval_hash", "eval_body", "eval_scope", "eval_draft", "eval_blocked", "gate_expired", "gate_future", "gate_hash", "gate_missing", "clock"])
def test_unavailable_or_drifted_authority_is_rejected(monkeypatch, drift):
    kwargs, state, _ = setup(monkeypatch)
    if drift == "method_kind": kwargs["method_ref"] = kwargs["method_ref"].model_copy(update={"resource_type": "SkillTemplate"})
    elif drift == "metric_kind": kwargs["metric_refs"][0] = kwargs["metric_refs"][0].model_copy(update={"resource_type": "MetricObservationRevision"})
    elif drift == "duplicate": kwargs["metric_refs"] *= 2
    elif drift == "missing": kwargs["metric_refs"] = []
    elif drift == "metric_hash": kwargs["metric_refs"][0].content_hash = "d" * 64
    elif drift == "metric_body": state["metric"] = state["metric"].model_copy(update={"unit": "other"})
    elif drift == "metric_latest": state["latest"] = 2
    elif drift == "eval_kind": kwargs["eval_ref"].resource_type = "EvalRunRevision"
    elif drift == "eval_head": state["head"] = 3
    elif drift == "eval_hash": kwargs["eval_ref"].content_hash = "d" * 64
    elif drift == "eval_body": state["contract"] = state["contract"].model_copy(update={"gate_policy": {"mode": "none"}})
    elif drift == "eval_scope": state["contract"] = state["contract"].model_copy(update={"tenant": state["contract"].tenant.model_copy(update={"org_id": "dev-org"})})
    elif drift == "eval_draft": state["contract"] = state["contract"].model_copy(update={"lifecycle": "draft"})
    elif drift == "eval_blocked": state["contract"] = state["contract"].model_copy(update={"readiness": "blocked"})
    elif drift == "gate_expired": kwargs["now"] = state["gate"]["expires_at"]
    elif drift == "gate_future": state["gate"]["decided_at"] += timedelta(seconds=1)
    elif drift == "gate_hash": state["gate"]["decision_hash"] = "d" * 64
    elif drift == "gate_missing": state["gate"] = None
    elif drift == "clock": kwargs["now"] = kwargs["now"].replace(tzinfo=None)
    with pytest.raises(ValueError): module.read_portrait_authorities(**kwargs)


@pytest.mark.parametrize("drift", [None, "missing", "scope", "identity", "revision", "hash"])
def test_metric_owner_reads_scoped_revision_and_rejects_drift(drift):
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore, AipEvalAuthorityError
    from test_ecommerce_analyst_authority_store import Connection, factory
    item = metric()
    row = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, metric_id=item.metric_id, revision=1,
               content_hash=item.content_hash, definition=item.model_dump(mode="json", by_alias=True))
    if drift == "missing": row = None
    elif drift == "scope": row["org_id"] = "dev-org"
    elif drift == "identity": row["metric_id"] = "other"
    elif drift == "revision": row["revision"] = 2
    elif drift == "hash": row["content_hash"] = "d" * 64
    owner = AipEvalAuthorityStore(factory(Connection(rows=[row])))
    if drift:
        with pytest.raises(AipEvalAuthorityError): owner.get_metric_definition(SCOPE, item.metric_id, 1)
    else: assert owner.get_metric_definition(SCOPE, item.metric_id, 1) == item


def seed_authorities(connect):
    """Synthetic Eval gate/publication graph, real Owner readiness checks."""
    from test_ecommerce_analyst_growth_plan_full_graph import insert
    from test_ecommerce_analyst_method_authority import apply_migrations
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    from aos_api.aip_production_contract_store import AipProductionContractStore
    apply_migrations(connect)
    method_item, metric_item = method(), metric()
    method_ref = EcommerceAnalystAuthorityStore(connect).publish_method(SCOPE, "compiler", "portrait-method", method_item, expected_version=0)
    AipEvalAuthorityStore(connect).create_metric_definition(SCOPE, metric_item, actor="compiler")
    now = datetime.now(timezone.utc)
    with connect(SCOPE) as conn:
        insert(conn, "aip_eval_suite_revision", suite_id="portrait-suite", revision=1, content_hash="a" * 64,
               target_ref={}, dataset_ref={}, judge_ref={}, cases=[{"synthetic": True}], gate_threshold=1.0, actor="compiler")
        insert(conn, "aip_eval_run", run_id="portrait-eval-run", suite_id="portrait-suite", suite_revision=1, suite_hash="a" * 64,
               target_ref={}, dataset_ref={}, judge_ref={}, status="succeeded", idempotency_key="portrait-eval-run", created_by="compiler", started_at=now, finished_at=now)
        insert(conn, "aip_release_gate_decision", decision_id="portrait-gate", target_ref={}, suite_ref={}, eval_run_id="portrait-eval-run",
               eval_report_ref={}, status="passed", decision_hash="c" * 64, decided_by="compiler", decided_at=now, expires_at=now + timedelta(days=30))
        insert(conn, "aip_publication_event", event_id="portrait-publication", publication_id="portrait-publication-family", target_ref={},
               event_type="published", release_gate_decision_id="portrait-gate", reason_hash="e" * 64, actor="compiler", occurred_at=now)
        row = conn.execute("SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND event_id=%s", (*SCOPE.key, "portrait-publication")).fetchone()
        publication_hash = canonical_hash(AipProductionContractStore._publication_snapshot(row))
    owner = AipProductionContractStore(connect)
    draft = owner.create_eval_contract(SCOPE, "compiler", "portrait-eval-contract", eval_body(publication_hash))
    assert draft.readiness.value == "ready"
    frozen = owner.freeze_eval_contract(SCOPE, "compiler", draft.contract_id, draft.version, "portrait-eval-freeze")
    return dict(scope=SCOPE, method_ref=method_ref, metric_refs=[exact("MetricDefinitionRevision", metric_item.metric_id, metric_item.content_hash)],
                eval_ref=exact("EvalContractRevision", frozen.contract_id, frozen.content_hash, frozen.revision), now=now)


@pytest.mark.skipif(os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1", reason="explicit disposable database required")
@pytest.mark.parametrize("change", ["revoke_publication", "new_metric", "expired_gate"])
def test_real_authorities_revalidate_publication_metric_and_expiry(change):
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    with disposable_database() as connect:
        kwargs = seed_authorities(connect)
        with connect(SCOPE) as conn:
            method_item, metrics, contract = module.read_portrait_authorities(conn=conn, **kwargs)
            assert method_item.algorithm == "descriptive_snapshot_v1" and metrics[0].metric_id == "order-count"
            assert contract.lifecycle.value == "frozen"
        if change == "revoke_publication":
            with connect(SCOPE) as conn:
                insert(conn, "aip_publication_event", event_id="portrait-publication-revoked", publication_id="portrait-publication-family", target_ref={},
                    event_type="revoked", release_gate_decision_id="portrait-gate", reason_hash="f" * 64, actor="compiler", occurred_at=kwargs["now"] + timedelta(seconds=1))
        elif change == "new_metric":
            item = metric().model_copy(update={"revision": 2, "window": "changed-window"})
            item = item.model_copy(update={"content_hash": canonical_hash(item.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
            AipEvalAuthorityStore(connect).create_metric_definition(SCOPE, item, actor="compiler")
        else: kwargs["now"] += timedelta(days=30)
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError): module.read_portrait_authorities(conn=conn, **kwargs)
