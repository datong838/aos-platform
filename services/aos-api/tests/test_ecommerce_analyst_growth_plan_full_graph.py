"""Opt-in full-table integration using a disposable copy of an owned clone.

The graph is synthetic and created through fixture SQL; no Provider is invoked
and this does not validate production provisioning or a real business outcome.
"""
from contextlib import contextmanager
from datetime import timedelta
import os
from pathlib import Path
import sys
import uuid

import pytest

from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef, InsightRevision
from aos_api.ecommerce_analyst_authority_store import EcommerceAnalystAuthorityStore, canonical_hash
from aos_api.ecommerce_analyst_growth_plan_receiver import GrowthPlanDraftReceiver
from aos_api.ecommerce_analyst_growth_plan_draft import growth_plan_prompt
from aos_api.aip_agent_run_executor import AipAgentRunExecutor
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import BuildEvidenceBundleRequest
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_growth_plan_draft import generation
from test_ecommerce_analyst_authority_contracts import insight, NOW

SCOPE = TenantScope("org-org", "dev-project")


@contextmanager
def disposable_database():
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
    from a0v_canonical_ecommerce_first_install import container_database_connect_factory
    raw = container_database_connect_factory(context="colima-aos-extension", container="aos-a0v-recovery-pg", database_name="aos_meta_head")
    with raw() as c:
        params = {k: v for k, v in c.info.get_parameters().items() if k in {"host", "port", "user", "dbname"}}
        params["password"] = c.info.password
    # Administration is through postgres; only the explicit owned clone is used
    # as template. Never terminate other sessions to make CREATE DATABASE work.
    name = "a0v_growth_graph_test_" + uuid.uuid4().hex
    created = False
    try:
        with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(sql.Identifier(name), sql.Identifier("aos_upgrade_check_f1dc452abade")))
            created = True
        @contextmanager
        def connect(scope):
            assert scope == SCOPE
            with psycopg.connect(**dict(params, dbname=name), row_factory=dict_row) as conn:
                assert conn.info.dbname == name
                yield conn
        yield connect
    finally:
        if created:
            with psycopg.connect(**dict(params, dbname="postgres"), autocommit=True) as admin:
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def insert(conn, table, **values):
    from psycopg import sql
    from psycopg.types.json import Jsonb
    values = dict(org_id=SCOPE.org_id, project_id=SCOPE.project_id, **values)
    conn.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, values)), sql.SQL(",").join(sql.Placeholder() for _ in values)),
        tuple(Jsonb(value) if isinstance(value, (dict, list)) else value for value in values.values()))


def exact(kind, identity, content_hash="a" * 64):
    return dict(resourceType=kind, resourceId=identity, revision=1, contentHash=content_hash)


def resource(kind, identity):
    return dict(resourceType=kind, resourceId=identity, revision="1", authority="postgresql")


def seed_graph(connect, *, retain_text=False):
    decision, attempt, answer = generation()
    with connect(SCOPE) as conn:
        assert not conn.execute("SELECT 1 FROM aip_agent_run WHERE org_id=%s AND project_id=%s AND agent_run_id=%s", (*SCOPE.key, attempt.agent_run_id)).fetchone()
        insert(conn, "aip_task", task_id="a0v-full-task", task_type="analysis", title="Synthetic full graph", status="executing", idempotency_key="a0v-full-task", request_hash="a" * 64, created_by="pytest")
        insert(conn, "aip_plan_revision", plan_revision_id="a0v-full-plan", task_id="a0v-full-task", revision=1, content_hash="a" * 64, steps=[], idempotency_key="a0v-full-plan", request_hash="a" * 64, created_by="pytest")
        insert(conn, "aip_task_run", run_id="a0v-full-task-run", task_id="a0v-full-task", plan_revision_id="a0v-full-plan", status="running", idempotency_key="a0v-full-task-run", request_hash="a" * 64, created_by="pytest")
        template = conn.execute("SELECT template_id,revision FROM aip_agent_template_revision ORDER BY template_id,revision LIMIT 1").fetchone()
        assert template, "owned clone has no template for synthetic FK fixture"
        insert(conn, "aip_agent_instance", instance_id="a0v-full-instance", template_id=template["template_id"], template_revision=template["revision"], status="active", overlay={}, created_by="pytest")
        insert(conn, "aip_skill_binding", binding_id="a0v-full-binding", instance_id="a0v-full-instance", skill_id="ecommerce.skill.D03", skill_revision=2, capability_refs=[], budget_policy_ref={}, status="active")
        insert(conn, "aip_task_brief_head", brief_id="a0v-full-brief", task_id="a0v-full-task", current_revision=1)
        insert(conn, "aip_task_brief_revision", brief_id="a0v-full-brief", task_id="a0v-full-task", revision=1, brief_type="analysis", schema_ref=resource("Schema", "a0v-full-schema"), spec={}, content_hash="c" * 64, lifecycle="frozen", created_by="pytest")
        payload = {"facts": ["repeat_rate"], "marking": ["internal"]}
        insert(conn, "aip_evidence", evidence_id="a0v-full-evidence", run_id="a0v-full-task-run", evidence_type="analysis", subject_ref=resource("Task", "a0v-full-task"), source_type="synthetic-integration", source_ref="a0v-full-source", observed_at=NOW, freshness_at=NOW, content_hash=canonical_hash(payload), payload=payload, created_by="pytest")
    bundle = AipProductionContractStore(connect).build_evidence_bundle(SCOPE, "pytest", "a0v-full-bundle", BuildEvidenceBundleRequest(
        briefRef=exact("TaskBriefRevision", "a0v-full-brief", "c" * 64), cutoffAt=NOW,
        itemRefs=[exact("Evidence", "a0v-full-evidence", canonical_hash(payload))], requiredFactIds=["repeat_rate"], marking=["internal"]))
    bundle_ref = AnalystExactRef.model_validate(exact("EvidenceBundleRevision", bundle.bundle_id, bundle.content_hash))
    source = InsightRevision.model_validate(insight()).model_copy(update={"evidence_refs": [bundle_ref]})
    source = source.model_copy(update={"content_hash": canonical_hash(source.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    owner = EcommerceAnalystAuthorityStore(connect)
    insight_ref = owner.publish_insight(SCOPE, source.created_by, "a0v-full-insight", source, expected_version=0)
    decision = decision.model_copy(update={"insight_ref": insight_ref, "evidence_refs": [bundle_ref]})
    decision = decision.model_copy(update={"content_hash": canonical_hash(decision.model_dump(mode="json", by_alias=True, exclude={"content_hash"}))})
    decision_ref = owner.publish_decision(SCOPE, decision.created_by, "a0v-full-decision", decision, expected_version=0)
    query, system = growth_plan_prompt(decision, budget="100", task_type="analysis")
    request = ExecuteAgentRunRequest(expectedAgentRunVersion=attempt.agent_run_version, attemptId=attempt.attempt_id, attemptNo=attempt.attempt_no,
        budgetRef=attempt.budget_ref, capacityReservationRef=attempt.capacity_reservation_ref, query=query, systemPrompt=system, dataClassification="internal")
    attempt = attempt.model_copy(update={"request_hash": AipAgentRunExecutor._request_hash(attempt.agent_run_id, request)})
    with connect(SCOPE) as conn:
        asset = lambda kind, identity: dict(assetType=kind, assetId=identity, revision=1, contentHash="a" * 64)
        insert(conn, "aip_agent_run", agent_run_id=attempt.agent_run_id, task_id="a0v-full-task", task_run_id="a0v-full-task-run",
            plan_ref=resource("PlanRevision", "a0v-full-plan"), instance_id="a0v-full-instance", instance_version=1,
            skill_binding_id="a0v-full-binding", skill_ref=asset("SkillTemplate", "ecommerce.skill.D03"), logic_ref=asset("LogicRevision", "D03"),
            model_route_ref=attempt.route_ref.model_dump(mode="json", by_alias=True), policy_ref=attempt.policy_ref.model_dump(mode="json", by_alias=True),
            input_refs=[resource(ref.resource_type, ref.resource_id) for ref in [decision_ref, insight_ref, bundle_ref]], status="succeeded", version=3,
            task_ref=resource("Task", "a0v-full-task"), task_run_ref=resource("TaskRun", "a0v-full-task-run"), instance_ref=asset("AgentInstance", "a0v-full-instance"), instance_snapshot={})
        fields = attempt.model_dump(mode="python", exclude={"tenant"})
        fields["invoking_at"] = NOW
        for name, value in list(fields.items()):
            if hasattr(value, "value"): fields[name] = value.value
        for name in ["route_ref", "policy_ref", "model_ref", "provider_ref", "price_snapshot_ref", "budget_ref", "capacity_reservation_ref", "output_artifact_ref"]:
            fields[name] = getattr(attempt, name).model_dump(mode="json", by_alias=True)
        insert(conn, "aip_agent_run_execution_attempt", **fields, idempotency_key="a0v-full-attempt")
        insert(conn, "aip_artifact", artifact_id=attempt.output_artifact_ref.artifact_id, run_id="a0v-full-task-run", artifact_type="agent_text_output",
            content_hash=attempt.output_artifact_ref.content_hash, content_ref="sha256://" + attempt.output_artifact_ref.content_hash,
            source=dict(agentRunId=attempt.agent_run_id, attemptId=attempt.attempt_id), marking=["internal"], created_by="pytest")
        if retain_text:
            from aos_api.aip_agent_text_output import write_agent_text
            write_agent_text(conn, SCOPE, attempt.output_artifact_ref.artifact_id, answer, attempt.output_artifact_ref.content_hash, ["internal"])
    return dict(attempt_id=attempt.attempt_id, decision_ref=decision_ref, answer=answer, budget="100", task_type="analysis", actor="compiler", markings=["internal"], now=NOW, max_source_age=timedelta(days=1))


def test_complete_database_graph_and_rejected_answer():
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("requires explicit disposable full-graph database test")
    with disposable_database() as connect:
        kwargs = seed_graph(connect)
        receiver = GrowthPlanDraftReceiver(connect)
        with pytest.raises(ValueError): receiver.receive(SCOPE, **dict(kwargs, answer=kwargs["answer"] + " "))
        class InjectedCommitFailure(RuntimeError):
            pass
        class BeforeCommitFailure:
            def __init__(self, conn): self.conn = conn
            def __getattr__(self, name): return getattr(self.conn, name)
            def commit(self): raise InjectedCommitFailure("synthetic failure before commit")
        @contextmanager
        def failing_connect(scope):
            with connect(scope) as conn:
                yield BeforeCommitFailure(conn)
        with pytest.raises(InjectedCommitFailure):
            GrowthPlanDraftReceiver(failing_connect).receive(SCOPE, **kwargs)
        identity = canonical_hash({"tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id}, "attemptId": kwargs["attempt_id"]})
        with connect(SCOPE) as conn:
            for table in ["ecommerce_analyst_growth_plan_head", "ecommerce_analyst_growth_plan_revision"]:
                assert conn.execute(f"SELECT count(*) AS n FROM {table} WHERE org_id=%s AND project_id=%s AND plan_id=%s", (*SCOPE.key, "growth-draft-" + identity[:40])).fetchone()["n"] == 0
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_authority_receipt WHERE org_id=%s AND project_id=%s AND idempotency_key=%s", (*SCOPE.key, "growth-draft-receive:" + identity)).fetchone()["n"] == 0
        first = receiver.receive(SCOPE, **kwargs)
        assert receiver.receive(SCOPE, **kwargs) == first
        saved = EcommerceAnalystAuthorityStore(connect).get_plan_exact(SCOPE, first)
        assert saved.items[0].title == "检查回购间隔" and saved.lifecycle.value == "draft"
        assert saved.generation_artifact_ref.resource_id == "artifact-1"
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_growth_plan_revision WHERE org_id=%s AND project_id=%s AND plan_id=%s", (*SCOPE.key, first.resource_id)).fetchone()["n"] == 1


@pytest.mark.parametrize("blocker", ["revoked", "expired", "marking"])
def test_complete_database_graph_rejects_unusable_source(blocker):
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("requires explicit disposable full-graph database test")
    from aos_api.aip_production_contracts import RevokeEvidenceRequest
    from aos_api.aip_production_contract_store import ProductionContractNotFound
    with disposable_database() as connect:
        kwargs = seed_graph(connect)
        if blocker == "revoked":
            with connect(SCOPE) as conn:
                evidence_hash = conn.execute("SELECT content_hash FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s", (*SCOPE.key, "a0v-full-evidence")).fetchone()["content_hash"]
            AipProductionContractStore(connect).revoke_evidence(SCOPE, "pytest", "a0v-full-evidence", "a0v-full-revoke", RevokeEvidenceRequest(expectedRevision=1, expectedContentHash=evidence_hash, reason="synthetic integration revocation"))
        elif blocker == "expired":
            kwargs["now"] = NOW + timedelta(days=2)
        else:
            kwargs["markings"] = ["public"]
        with pytest.raises((ValueError, ProductionContractNotFound)):
            GrowthPlanDraftReceiver(connect).receive(SCOPE, **kwargs)
        identity = canonical_hash({"tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id}, "attemptId": kwargs["attempt_id"]})
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM ecommerce_analyst_growth_plan_head WHERE org_id=%s AND project_id=%s AND plan_id=%s", (*SCOPE.key, "growth-draft-" + identity[:40])).fetchone()["n"] == 0


@pytest.mark.parametrize("retained", [False, True])
def test_recovery_from_new_instance_requires_retained_original_text(retained):
    if os.getenv("AOS_GROWTH_DRAFT_FULL_GRAPH_TEST") != "1":
        pytest.skip("requires explicit disposable full-graph database test")
    import importlib.util
    from types import SimpleNamespace
    with disposable_database() as connect:
        path = Path(__file__).resolve().parents[1] / "alembic/versions/a0v_012_agent_text_output.py"
        spec = importlib.util.spec_from_file_location("recovery_text_migration", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        with connect(SCOPE) as conn:
            migration.op = SimpleNamespace(execute=conn.execute)
            migration.upgrade()
        kwargs = seed_graph(connect, retain_text=retained)
        del kwargs["answer"]
        if not retained:
            with pytest.raises(ValueError): GrowthPlanDraftReceiver(connect).recover(SCOPE, **kwargs)
        else:
            first = GrowthPlanDraftReceiver(connect).recover(SCOPE, **kwargs)
            assert GrowthPlanDraftReceiver(connect).recover(SCOPE, **kwargs) == first
            saved = EcommerceAnalystAuthorityStore(connect).get_plan_exact(SCOPE, first)
            assert saved.items[0].title == "检查回购间隔"
            assert saved.generation_artifact_ref.resource_id == "artifact-1"
