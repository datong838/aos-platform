from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_growth_plan_receiver as module
from aos_api.ecommerce_analyst_growth_plan_draft import draft_from_completed_generation
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_draft import generation

SCOPE = TenantScope("org-org", "dev-project")


def setup_receiver(monkeypatch):
    decision, attempt, raw = generation()
    decision_ref = AnalystExactRef(resourceType="DecisionSummaryRevision", resourceId=decision.decision_id,
                                  revision=decision.revision, contentHash=decision.content_hash)
    inputs = [SimpleNamespace(resource_type=ref.resource_type, resource_id=ref.resource_id,
                              revision=str(ref.revision), authority="postgresql")
              for ref in [decision_ref, decision.insight_ref, *decision.evidence_refs]]
    run = SimpleNamespace(tenant=decision.tenant, agent_run_id=attempt.agent_run_id, task_run_id="task-run-1",
        request=SimpleNamespace(skill=SimpleNamespace(asset_type="SkillTemplate", asset_id="ecommerce.skill.D03"),
                                model_route=attempt.route_ref, policy=attempt.policy_ref, input_refs=inputs))
    state = dict(attempt=attempt, run=run, published=[], receipt=None, saved=None, source_calls=0,
        artifact=dict(run_id="task-run-1", artifact_type="agent_text_output", content_hash=attempt.output_artifact_ref.content_hash,
            content_ref="sha256://" + attempt.output_artifact_ref.content_hash,
            source=dict(agentRunId=attempt.agent_run_id, attemptId=attempt.attempt_id)))
    class Connection:
        def execute(self, sql, params):
            if "pg_advisory_xact_lock" in sql:
                return None
            assert params == (*SCOPE.key, "artifact-1")
            return SimpleNamespace(fetchone=lambda: state["artifact"])
    connection = Connection()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection
    class Attempts:
        def __init__(self, factory): self.factory = factory
        def get(self, scope, identity):
            assert scope == SCOPE and identity == attempt.attempt_id
            with self.factory(scope) as bound: assert bound is connection
            return state["attempt"]
    class Runs:
        def __init__(self, factory): pass
        def get(self, scope, identity): return state["run"]
    class Owner:
        def __init__(self, factory): self.factory = factory
        def find_plan_publication_receipt(self, scope, key): return state["receipt"]
        def get_plan_exact(self, scope, ref): return state["saved"]
        def publish_plan(self, scope, actor, key, plan, *, expected_version):
            assert scope == SCOPE and expected_version == 0
            with self.factory(scope) as bound: assert bound is connection
            state["published"].append(plan)
            state["saved"] = plan
            state["receipt"] = AnalystExactRef(resourceType="GrowthPlanRevision", resourceId=plan.plan_id, revision=1, contentHash=plan.content_hash)
            return state["receipt"]
    def sources(conn, scope, ref, **kwargs):
        assert conn is connection and scope == SCOPE and ref == decision_ref
        state["source_calls"] += 1
        return decision
    monkeypatch.setattr(module, "AipAgentRunExecutionService", Attempts)
    monkeypatch.setattr(module, "AipAgentRunService", Runs)
    monkeypatch.setattr(module, "EcommerceAnalystAuthorityStore", Owner)
    monkeypatch.setattr(module, "require_growth_plan_sources", sources)
    receiver = module.GrowthPlanDraftReceiver(connect)
    kwargs = dict(attempt_id=attempt.attempt_id, decision_ref=decision_ref, answer=raw,
        budget="100", task_type="analysis", actor="compiler", markings=["internal"],
        now=attempt.completed_at, max_source_age=timedelta(days=1))
    return receiver, state, kwargs


def test_received_draft_uses_owner_once_and_replays_without_new_source_work(monkeypatch):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    first = receiver.receive(SCOPE, **kwargs)
    assert receiver.receive(SCOPE, **kwargs) == first
    assert len(state["published"]) == 1 and state["source_calls"] == 1
    assert state["saved"].lifecycle.value == "draft"


@pytest.mark.parametrize("change", ["unknown", "skill", "input", "route", "artifact_run", "artifact_source", "artifact_missing", "scope"])
def test_invalid_generation_never_reaches_owner(monkeypatch, change):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    if change == "unknown": state["attempt"] = state["attempt"].model_copy(update={"status": "unknown"})
    elif change == "skill": state["run"].request.skill.asset_id = "ecommerce.skill.D02"
    elif change == "input": state["run"].request.input_refs = []
    elif change == "route": state["run"].request.model_route = None
    elif change == "artifact_run": state["artifact"]["run_id"] = "other-run"
    elif change == "artifact_source": state["artifact"]["source"]["attemptId"] = "other-attempt"
    elif change == "artifact_missing": state["artifact"] = None
    else: state["run"].tenant = state["run"].tenant.model_copy(update={"org_id": "dev-org"})
    with pytest.raises(ValueError): receiver.receive(SCOPE, **kwargs)
    assert state["published"] == []


@pytest.mark.parametrize("field,value", [("budget", "101"), ("task_type", "content"), ("actor", "another")])
def test_replay_drift_rejected(monkeypatch, field, value):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    receiver.receive(SCOPE, **kwargs)
    kwargs[field] = value
    with pytest.raises(ValueError): receiver.receive(SCOPE, **kwargs)
    assert len(state["published"]) == 1


def test_real_owner_persistence_and_replay_in_owned_clone(monkeypatch):
    """Opt-in integration: real Owner/transaction, simulated source/generation.

    Never accepts an arbitrary target DSN, never writes real tenant business data.
    """
    import os
    if os.getenv("AOS_GROWTH_DRAFT_OWNED_CLONE_TEST") != "1":
        pytest.skip("requires explicitly selected owned recovery clone")
    import sys
    import uuid
    from pathlib import Path
    import psycopg
    from psycopg.rows import dict_row
    from psycopg import sql
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from a0v_canonical_ecommerce_first_install import container_database_connect_factory
    factory = container_database_connect_factory(context="colima-aos-extension", container="aos-a0v-recovery-pg", database_name="aos_meta_head")
    with factory() as c:
        params = {key: value for key, value in c.info.get_parameters().items() if key in {"host", "port", "user", "dbname"}}
        params["password"] = c.info.password
    params["dbname"] = "aos_upgrade_check_f1dc452abade"
    schema = "a0v_growth_receiver_test_" + uuid.uuid4().hex
    with psycopg.connect(**params, row_factory=dict_row) as admin:
        assert admin.execute("SELECT current_database() AS name").fetchone()["name"] == params["dbname"]
        admin.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        for table in ["ecommerce_analyst_growth_plan_head", "ecommerce_analyst_growth_plan_revision", "ecommerce_analyst_authority_receipt"]:
            admin.execute(sql.SQL("CREATE TABLE {}.{} (LIKE public.{} INCLUDING ALL)").format(sql.Identifier(schema), sql.Identifier(table), sql.Identifier(table)))
        admin.execute(sql.SQL("CREATE TABLE {}.aip_artifact (org_id text, project_id text, artifact_id text, run_id text, artifact_type text, content_hash text, content_ref text, source jsonb)").format(sql.Identifier(schema)))
        admin.commit()
    try:
        _, state, kwargs = setup_receiver(monkeypatch)
        @contextmanager
        def actual(scope):
            assert scope == SCOPE
            with psycopg.connect(**params, row_factory=dict_row) as conn:
                conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
                yield conn
        class Attempts:
            def __init__(self, factory): pass
            def get(self, scope, identity): return state["attempt"]
        monkeypatch.setattr(module, "AipAgentRunExecutionService", Attempts)
        monkeypatch.setattr(module, "EcommerceAnalystAuthorityStore", EcommerceAnalystAuthorityStore)
        decision, _, _ = generation()
        monkeypatch.setattr(module, "require_growth_plan_sources", lambda *args, **kwargs: decision)
        from psycopg.types.json import Jsonb
        artifact = state["artifact"]
        with actual(SCOPE) as conn:
            conn.execute("INSERT INTO aip_artifact VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (*SCOPE.key, "artifact-1", artifact["run_id"], artifact["artifact_type"], artifact["content_hash"], artifact["content_ref"], Jsonb(artifact["source"])))
        receiver = module.GrowthPlanDraftReceiver(actual)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as workers:
            received = list(workers.map(lambda _: receiver.receive(SCOPE, **kwargs), range(2)))
        first = received[0]
        assert received[1] == first
        assert receiver.receive(SCOPE, **kwargs) == first
        with pytest.raises(ValueError): receiver.receive(SCOPE, **dict(kwargs, budget="101"))
        with actual(SCOPE) as conn:
            for table in ["ecommerce_analyst_growth_plan_head", "ecommerce_analyst_growth_plan_revision", "ecommerce_analyst_authority_receipt"]:
                assert conn.execute(sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(table))).fetchone()["count"] == 1
        saved = EcommerceAnalystAuthorityStore(actual).get_plan_exact(SCOPE, first)
        assert saved.items[0].title == "检查回购间隔" and saved.lifecycle.value == "draft"
        assert saved.generation_artifact_ref.resource_id == "artifact-1"
    finally:
        with psycopg.connect(**params) as admin:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.mark.parametrize("status", ["unknown", "failed", "prepared", "invoking"])
def test_recovery_never_reads_or_retries_incomplete_generation(monkeypatch, status):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    state["attempt"] = state["attempt"].model_copy(update={"status": status})
    kwargs.pop("answer")
    with pytest.raises(ValueError, match="completed retained generation"):
        receiver.recover(SCOPE, **kwargs)
    assert state["source_calls"] == 0 and state["published"] == []
