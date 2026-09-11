from contextlib import contextmanager
from datetime import timedelta
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_diagnosis_receiver as module
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_diagnosis_generation import fixture

SCOPE = TenantScope("org-org", "dev-project")


def setup_receiver(monkeypatch):
    insight, materials, attempt, answer = fixture()
    ref = AnalystExactRef(resourceType="InsightRevision", resourceId=insight.insight_id,
                         revision=insight.revision, contentHash=insight.content_hash)
    inputs = [SimpleNamespace(resource_type=r.resource_type, resource_id=r.resource_id,
                              revision=str(r.revision), authority="postgresql") for r in [ref, *insight.evidence_refs]]
    run = SimpleNamespace(tenant=insight.tenant, agent_run_id=attempt.agent_run_id, task_id="task", task_run_id="task-run",
        request=SimpleNamespace(skill=SimpleNamespace(asset_type="SkillTemplate", asset_id="ecommerce.skill.D02"),
                                model_route=attempt.route_ref, policy=attempt.policy_ref, input_refs=inputs))
    grant = dict(decisionId="grant-1", request=dict(evidenceRef=materials[0]["items"][0]["evidenceRef"],
                                                 purpose="source", requestedLevel="l3", taskId="task"))
    request = module.AnalysisBundleSourceRequest(bundleRef=materials[0]["bundleRef"], grants=[grant])
    state = dict(attempt=attempt, run=run, insight=insight, saved=None, receipt=None, publications=[],
        reads=0, denied=False, artifact=dict(run_id="task-run", source=dict(agentRunId=attempt.agent_run_id, attemptId=attempt.attempt_id)))
    class Connection:
        def execute(self, sql, params):
            if "pg_advisory_xact_lock" in sql: return None
            assert params == (*SCOPE.key, attempt.output_artifact_ref.artifact_id)
            return SimpleNamespace(fetchone=lambda: state["artifact"])
    connection = Connection()
    @contextmanager
    def connect(scope):
        assert scope == SCOPE
        yield connection
    class Attempts:
        def __init__(self, factory): self.factory = factory
        def get(self, scope, identity):
            with self.factory(scope) as conn: assert conn is connection
            return state["attempt"]
    class Runs:
        def __init__(self, factory): pass
        def get(self, scope, identity): return state["run"]
    class Owner:
        def __init__(self, factory): self.factory = factory
        def find_decision_publication_receipt(self, scope, key): return state["receipt"]
        def get_decision_exact(self, scope, ref): return state["saved"]
        def publish_decision(self, scope, actor, key, decision, *, expected_version):
            assert expected_version == 0 and actor == "compiler"
            with self.factory(scope) as conn: assert conn is connection
            state["publications"].append(decision)
            state["saved"] = decision
            state["receipt"] = AnalystExactRef(resourceType="DecisionSummaryRevision", resourceId=decision.decision_id,
                                               revision=1, contentHash=decision.content_hash)
            return state["receipt"]
    def read_text(conn, scope, ref, *, markings):
        assert conn is connection and scope == SCOPE
        if "internal" not in markings: raise ValueError("output forbidden")
        return answer
    def sources(**kwargs):
        assert kwargs["conn"] is connection and kwargs["scope"] == SCOPE and kwargs["task_id"] == "task"
        state["reads"] += 1
        if state["denied"]: raise ValueError("source forbidden")
        return materials[0]
    monkeypatch.setattr(module, "AipAgentRunExecutionService", Attempts)
    monkeypatch.setattr(module, "AipAgentRunService", Runs)
    monkeypatch.setattr(module, "EcommerceAnalystAuthorityStore", Owner)
    monkeypatch.setattr(module, "read_agent_text", read_text)
    monkeypatch.setattr(module, "require_current_revision", lambda *args: state["insight"])
    monkeypatch.setattr(module, "read_analysis_bundle", sources)
    kwargs = dict(attempt_id=attempt.attempt_id, insight_ref=ref, source_requests=[request], actor="compiler",
                  markings=["internal", "secret"], now=attempt.completed_at, max_source_age=timedelta(days=1), max_bytes=10000)
    return module.DiagnosisReceiver(connect), state, kwargs


def test_once_saved_diagnosis_recovers_without_new_source_authority(monkeypatch):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    ref = receiver.recover(SCOPE, **kwargs)
    state["denied"] = True
    assert receiver.recover(SCOPE, **dict(kwargs, source_requests=[], now=kwargs["now"] + timedelta(days=3))) == ref
    assert len(state["publications"]) == 1 and state["reads"] == 1
    with pytest.raises(ValueError, match="output forbidden"):
        receiver.recover(SCOPE, **dict(kwargs, markings=["public"]))


@pytest.mark.parametrize("drift", ["unknown", "actor", "tenant", "id", "receipt", "usage", "skill", "route", "input", "artifact", "provenance", "denied", "stale", "future", "missing", "duplicate", "inventory", "request", "oversize"])
def test_unproven_diagnosis_is_not_published(monkeypatch, drift):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    attempt = state["attempt"]
    if drift == "unknown": state["attempt"] = attempt.model_copy(update={"status": "unknown"})
    elif drift == "actor": kwargs["actor"] = "other"
    elif drift == "tenant": state["attempt"] = attempt.model_copy(update={"tenant": attempt.tenant.model_copy(update={"org_id": "dev-org"})})
    elif drift == "id": state["attempt"] = attempt.model_copy(update={"attempt_id": "other"})
    elif drift == "receipt": state["attempt"] = attempt.model_copy(update={"provider_receipt_id": None})
    elif drift == "usage": state["attempt"] = attempt.model_copy(update={"usage_receipt_ids": []})
    elif drift == "skill": state["run"].request.skill.asset_id = "ecommerce.skill.D03"
    elif drift == "route": state["run"].request.model_route = None
    elif drift == "input": state["run"].request.input_refs = []
    elif drift == "artifact": state["artifact"] = None
    elif drift == "provenance": state["artifact"]["source"]["attemptId"] = "other"
    elif drift == "denied": state["denied"] = True
    elif drift == "stale": kwargs["now"] += timedelta(days=3)
    elif drift == "future": kwargs["now"] -= timedelta(seconds=1)
    elif drift == "missing": kwargs["source_requests"] = []
    elif drift == "duplicate": kwargs["source_requests"] *= 2
    elif drift == "inventory": kwargs["source_requests"][0].bundle_ref.resource_id = "other"
    elif drift == "request": state["attempt"] = attempt.model_copy(update={"request_hash": "c" * 64})
    elif drift == "oversize": kwargs["max_bytes"] = 1
    with pytest.raises(ValueError): receiver.recover(SCOPE, **kwargs)
    assert state["publications"] == []


@pytest.mark.parametrize("drift", ["actor", "insight", "saved_artifact", "saved_id"])
def test_replay_drift_is_rejected(monkeypatch, drift):
    receiver, state, kwargs = setup_receiver(monkeypatch)
    receiver.recover(SCOPE, **kwargs)
    if drift == "actor": kwargs["actor"] = "other"
    elif drift == "insight": kwargs["insight_ref"] = kwargs["insight_ref"].model_copy(update={"content_hash": "d" * 64})
    elif drift == "saved_artifact": state["saved"] = state["saved"].model_copy(update={"generation_artifact_ref": None})
    elif drift == "saved_id": state["saved"] = state["saved"].model_copy(update={"decision_id": "other"})
    with pytest.raises(ValueError): receiver.recover(SCOPE, **kwargs)
    assert len(state["publications"]) == 1


@pytest.mark.parametrize("drift", [None, "body", "identity", "revision", "tenant", "kind", "hash"])
def test_decision_exact_owner_checks_identity_and_body(drift):
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, AnalystAuthorityStoreError
    from aos_api.ecommerce_analyst_diagnosis_generation import decision_from_completed_generation
    from test_ecommerce_analyst_authority_store import Connection, factory
    source, materials, attempt, answer = fixture()
    item = decision_from_completed_generation(insight=source, materials=materials, attempt=attempt, answer=answer, actor="compiler")
    ref = AnalystExactRef(resourceType="DecisionSummaryRevision", resourceId=item.decision_id, revision=1, contentHash=item.content_hash)
    payload = item.model_dump(mode="json", by_alias=True)
    if drift == "body": payload["conclusion"] = "changed"
    elif drift == "identity": payload["decisionId"] = "other"
    elif drift == "revision": payload.update(revision=2, version=2, priorRef=ref.model_dump(mode="json", by_alias=True))
    elif drift == "tenant": payload["tenant"]["orgId"] = "dev-org"
    elif drift == "kind": ref = ref.model_copy(update={"resource_type": "GrowthPlanRevision"})
    elif drift == "hash": payload["contentHash"] = "d" * 64
    conn = Connection(rows=[dict(payload=payload, content_hash=item.content_hash)])
    owner = EcommerceAnalystAuthorityStore(factory(conn))
    if drift:
        with pytest.raises(AnalystAuthorityStoreError): owner.get_decision_exact(SCOPE, ref)
    else:
        assert owner.get_decision_exact(SCOPE, ref) == item
        assert conn.calls[0][1] == (*SCOPE.key, item.decision_id, 1)


def seed_diagnosis_graph(connect, *, taor_ready=False):
    """Synthetic provenance graph with real table constraints and source Owners.

    Does not exercise provisioning, Provider execution, or tenant business data.
    """
    import importlib.util
    from datetime import datetime, timezone
    from pathlib import Path
    from test_ecommerce_analyst_growth_plan_full_graph import insert, resource
    from test_aip_taor_lease_adapter import running_run
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, ResolveEvidenceDisclosureRequest
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
    from aos_api.ecommerce_analyst_diagnosis_generation import diagnosis_prompt
    from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
    from aos_api.aip_agent_run_executor import AipAgentRunExecutor
    from aos_api.aip_agent_text_output import write_agent_text
    source, _, attempt, answer = fixture()
    now = datetime.now(timezone.utc)
    migration_path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_012_agent_text_output.py"
    spec = importlib.util.spec_from_file_location("diagnosis_text_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with connect(SCOPE) as conn:
        migration.op = SimpleNamespace(execute=conn.execute)
        migration.upgrade()
    tasks = AipTaskStore(connect_factory=connect)
    if taor_ready:
        from aos_api.aip_contracts import PlanStep, ResourceRef
        from aos_api.aip_task_models import CreateTaskRequest, CreatePlanRevisionRequest, CreateTaskRunRequest
        from aos_api.ecommerce_analyst_diagnosis_worker import diagnosis_stage_attempt_id
        task = tasks.create_task(SCOPE, "compiler", "diagnosis-task", CreateTaskRequest(type="analysis", title="Synthetic diagnosis worker"))
        steps = [PlanStep(step_key=key, title=key) for key in ("portrait", "diagnosis", "solution-design")]
        steps[1].assignee_refs = [ResourceRef(resource_type="AgentInstance", resource_id="diagnosis-instance", revision="1", authority="aip-assignee-directory")]
        plan = tasks.create_plan(SCOPE, "compiler", task.id, "diagnosis-plan", CreatePlanRevisionRequest(expected_task_version=task.version, steps=steps))
        task = tasks.get_task(SCOPE, task.id)
        tasks.approve_plan(SCOPE, "compiler", task.id, plan.revision, task.version, plan.content_hash)
        task = tasks.get_task(SCOPE, task.id)
        run = tasks.create_run(SCOPE, "compiler", task.id, "diagnosis-run", CreateTaskRunRequest(plan_revision_id=plan.id, expected_task_version=task.version))
        snapshot = tasks.timeline(SCOPE, run.id)
        tasks.start_run(SCOPE, run.id, expected_run_version=run.version, expected_task_version=snapshot.task.version,
                        actor="compiler", idempotency_key="diagnosis-start", reason="synthetic stage handoff")
        attempt = attempt.model_copy(update={"attempt_id": diagnosis_stage_attempt_id(SCOPE, tasks.timeline(SCOPE, run.id))})
    else:
        run = running_run(tasks)
    payload = {"facts": ["repeat_rate"], "values": {"repeat_rate": 0.2}, "marking": ["internal"]}
    with connect(SCOPE) as conn:
        insert(conn, "aip_task_brief_head", brief_id="diagnosis-brief", task_id=run.task_id, current_revision=1)
        insert(conn, "aip_task_brief_revision", brief_id="diagnosis-brief", task_id=run.task_id, revision=1,
               brief_type="analysis", schema_ref=resource("Schema", "fixture"), spec={}, content_hash="c" * 64, lifecycle="frozen", created_by="compiler")
        insert(conn, "aip_evidence", evidence_id="diagnosis-evidence", run_id=run.id, evidence_type="query", subject_ref={},
               source_type="database", source_ref="synthetic-diagnosis-fixture", observed_at=now, freshness_at=now,
               content_hash=canonical_hash(payload), payload=payload, created_by="compiler")
    production = AipProductionContractStore(connect)
    evidence = dict(resourceType="Evidence", resourceId="diagnosis-evidence", revision=1, contentHash=canonical_hash(payload))
    bundle = production.build_evidence_bundle(SCOPE, "compiler", "diagnosis-bundle", BuildEvidenceBundleRequest(
        briefRef=dict(resourceType="TaskBriefRevision", resourceId="diagnosis-brief", revision=1, contentHash="c" * 64),
        cutoffAt=now, itemRefs=[evidence], requiredFactIds=["repeat_rate"], marking=["internal"]))
    bundle_ref = AnalystExactRef(resourceType="EvidenceBundleRevision", resourceId=bundle.bundle_id, revision=1, contentHash=bundle.content_hash)
    body = ResolveEvidenceDisclosureRequest(evidenceRef=evidence, purpose="source", requestedLevel="l3", taskId=run.task_id)
    grant = production.resolve_evidence_disclosure(SCOPE, "compiler", "diagnosis-grant", body, markings=["internal", "secret"])
    assert grant.status.value == "allowed"
    source_request = module.AnalysisBundleSourceRequest(bundleRef=bundle_ref, grants=[dict(decisionId=grant.decision_id, request=body)])
    source = source.model_copy(update={"evidence_refs": [bundle_ref], "cutoff_at": now, "created_at": now})
    source = source.model_copy(update={"content_hash": canonical_hash(source.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    insight_ref = EcommerceAnalystAuthorityStore(connect).publish_insight(SCOPE, source.created_by, "diagnosis-insight", source, expected_version=0)
    with connect(SCOPE) as conn:
        material = module.read_analysis_bundle(conn=conn, scope=SCOPE, task_id=run.task_id, actor="compiler", request=source_request,
            markings=["internal", "secret"], now=now, max_source_age=timedelta(days=1), max_bytes=10000)
    query, system = diagnosis_prompt(source, [material])
    attempt = attempt.model_copy(update={"prepared_at": now, "completed_at": now})
    request = ExecuteAgentRunRequest(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id, attemptNo=attempt.attempt_no,
        budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref, query=query, systemPrompt=system, dataClassification="internal")
    attempt = attempt.model_copy(update={"request_hash": AipAgentRunExecutor._request_hash(attempt.agent_run_id, request)})
    with connect(SCOPE) as conn:
        template = conn.execute("SELECT template_id,revision FROM aip_agent_template_revision ORDER BY template_id,revision LIMIT 1").fetchone()
        assert template
        insert(conn, "aip_agent_instance", instance_id="diagnosis-instance", template_id=template["template_id"], template_revision=template["revision"],
               status="active", overlay={}, created_by="compiler")
        insert(conn, "aip_skill_binding", binding_id="diagnosis-binding", instance_id="diagnosis-instance", skill_id="ecommerce.skill.D02",
               skill_revision=2, capability_refs=[], budget_policy_ref={}, status="active")
        asset = lambda kind, identity: dict(assetType=kind, assetId=identity, revision=1, contentHash="a" * 64)
        insert(conn, "aip_agent_run", agent_run_id=attempt.agent_run_id, task_id=run.task_id, task_run_id=run.id,
            plan_ref=resource("PlanRevision", run.plan_revision_id), instance_id="diagnosis-instance", instance_version=1,
            skill_binding_id="diagnosis-binding", skill_ref=dict(asset("SkillTemplate", "ecommerce.skill.D02"), revision=2), logic_ref=asset("LogicRevision", "D02"),
            model_route_ref=attempt.route_ref.model_dump(mode="json", by_alias=True), policy_ref=attempt.policy_ref.model_dump(mode="json", by_alias=True),
            input_refs=[resource(ref.resource_type, ref.resource_id) for ref in [insight_ref, bundle_ref]], status="succeeded", version=3,
            task_ref=resource("Task", run.task_id), task_run_ref=resource("TaskRun", run.id), instance_ref=asset("AgentInstance", "diagnosis-instance"), instance_snapshot={})
        fields = attempt.model_dump(mode="python", exclude={"tenant"})
        fields["invoking_at"] = now
        for name, value in list(fields.items()):
            if hasattr(value, "value"): fields[name] = value.value
        for name in ["route_ref", "policy_ref", "model_ref", "provider_ref", "price_snapshot_ref", "budget_ref", "capacity_reservation_ref", "output_artifact_ref"]:
            fields[name] = getattr(attempt, name).model_dump(mode="json", by_alias=True)
        insert(conn, "aip_agent_run_execution_attempt", **fields, idempotency_key="diagnosis-attempt")
        insert(conn, "aip_artifact", artifact_id=attempt.output_artifact_ref.artifact_id, run_id=run.id, artifact_type="agent_text_output",
            content_hash=attempt.output_artifact_ref.content_hash, content_ref="sha256://" + attempt.output_artifact_ref.content_hash,
            source=dict(agentRunId=attempt.agent_run_id, attemptId=attempt.attempt_id), marking=["internal"], created_by="compiler")
        write_agent_text(conn, SCOPE, attempt.output_artifact_ref.artifact_id, answer, attempt.output_artifact_ref.content_hash, ["internal"])
    return dict(attempt_id=attempt.attempt_id, insight_ref=insight_ref, source_requests=[source_request], actor="compiler",
                markings=["internal", "secret"], now=now, max_source_age=timedelta(days=1), max_bytes=10000)


@pytest.mark.parametrize("case", ["rollback_concurrent_replay", "revoked", "output_marking", "missing_grant"])
def test_full_database_receiver_boundaries(case):
    import os
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("explicit disposable full database test required")
    from concurrent.futures import ThreadPoolExecutor
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database
    from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
    from aos_api.aip_production_contract_store import AipProductionContractStore
    from aos_api.aip_production_contracts import RevokeEvidenceRequest
    with disposable_database() as connect:
        kwargs = seed_diagnosis_graph(connect)
        receiver = module.DiagnosisReceiver(connect)
        evidence = kwargs["source_requests"][0].grants[0].request.evidence_ref
        def revoke():
            AipProductionContractStore(connect).revoke_evidence(SCOPE, "compiler", evidence.resource_id, "diagnosis-revoke",
                RevokeEvidenceRequest(expectedContentHash=evidence.content_hash, reason="synthetic withdrawal"))
        identity = canonical_hash({"tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id}, "attemptId": kwargs["attempt_id"]})
        def assert_count(expected):
            with connect(SCOPE) as conn:
                for table in ["ecommerce_analyst_decision_head", "ecommerce_analyst_decision_revision"]:
                    assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s AND decision_id=%s",
                                        (*SCOPE.key, "diagnosis-" + identity[:40])).fetchone()["n"] == expected
                assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
                                    (*SCOPE.key, "diagnosis-receive:" + identity)).fetchone()["n"] == expected
        if case == "rollback_concurrent_replay":
            class CommitFailure(RuntimeError): pass
            class FailCommit:
                def __init__(self, conn): self.conn = conn
                def __getattr__(self, name): return getattr(self.conn, name)
                def commit(self): raise CommitFailure("injected before commit")
            @contextmanager
            def failing(scope):
                with connect(scope) as conn: yield FailCommit(conn)
            with pytest.raises(CommitFailure): module.DiagnosisReceiver(failing).recover(SCOPE, **kwargs)
            assert_count(0)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: receiver.recover(SCOPE, **kwargs), range(2)))
            assert results[0] == results[1]
            assert_count(1)
            saved = EcommerceAnalystAuthorityStore(connect).get_decision_exact(SCOPE, results[0])
            assert saved.insight_ref == kwargs["insight_ref"] and saved.generation_artifact_ref.resource_id == "artifact-1"
            revoke()
            assert receiver.recover(SCOPE, **dict(kwargs, source_requests=[])) == results[0]
            with pytest.raises(ValueError): receiver.recover(SCOPE, **dict(kwargs, markings=["public"]))
            assert_count(1)
        else:
            if case == "revoked": revoke()
            elif case == "output_marking": kwargs["markings"] = ["public"]
            else: kwargs["source_requests"][0].grants[0].decision_id = "nonexistent-grant"
            with pytest.raises((ValueError, RuntimeError)): receiver.recover(SCOPE, **kwargs)
            assert_count(0)
