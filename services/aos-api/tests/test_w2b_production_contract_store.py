from __future__ import annotations

import pytest

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractConflict,
    ProductionContractDependencyBlocked,
    ProductionContractIdempotencyConflict,
)
from aos_api.aip_production_contracts import (
    AssigneeKind,
    AssigneeRef,
    ContractReadiness,
    CreateEvalContractRequest,
    CreateResponsibilityPlanRequest,
    ExactRevisionRef,
    ReviseEvalContractRequest,
    ReviseResponsibilityPlanRequest,
    ResponsibilitySlot,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("dev-org", "dev-project")
OTHER_SCOPE = TenantScope("other-org", "dev-project")
HASH = "a" * 64


def _exact(resource_type: str, resource_id: str, content_hash: str = HASH) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=resource_type,
        resource_id=resource_id,
        revision=1,
        content_hash=content_hash,
    )


def _schema(identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type="Schema",
        resource_id=identifier,
        revision="1",
        authority="aip",
    )


def _eval_request(content_hash: str = HASH, *, warning: float | None = None) -> CreateEvalContractRequest:
    thresholds = {"critical": 1.0}
    if warning is not None:
        thresholds["warning"] = warning
    return CreateEvalContractRequest(
        suite_ref=_exact("EvalSuiteRevision", "suite-w2b", content_hash),
        artifact_schema_ref=_schema("artifact-w2b"),
        severity_thresholds=thresholds,
        gate_policy={"mode": "all"},
        return_mapping={"critical": "draft"},
        override_policy={"allowed": False},
    )


def _responsibility_request(profile: str = "ecommerce-standard") -> CreateResponsibilityPlanRequest:
    return CreateResponsibilityPlanRequest(
        profile=profile,
        template_ref=_exact("ResponsibilityTemplateRevision", "ecommerce-standard"),
        slots=[
            ResponsibilitySlot(
                slot_id="content.review",
                responsibility_type="independent_review",
                required_capability_ids=["capability.content.review"],
                input_schema_ref=_schema("content.review.input"),
                output_schema_ref=_schema("content.review.output"),
                return_stage="draft",
                assignee=AssigneeRef(
                    kind=AssigneeKind.AGENT_INSTANCE,
                    resource_id="agent-content-w2b",
                    version=1,
                ),
            )
        ],
    )


def _seed_dependencies() -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES('other-org','隔离组织') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES"
            "('other-org','dev-project','隔离工作区') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            """INSERT INTO aip_eval_suite_revision
            (org_id,project_id,suite_id,revision,content_hash,target_ref,dataset_ref,
             judge_ref,cases,gate_threshold,actor)
            VALUES(%s,%s,'suite-w2b',1,%s,'{}','{}','{}','[{}]',1.0,'test')
            ON CONFLICT DO NOTHING""",
            (*SCOPE.key, HASH),
        )
        conn.execute(
            """INSERT INTO aip_agent_template_revision
            (template_id,revision,display_name,role_key,lifecycle,source_ref,
             source_license,manifest,content_hash,created_by)
            VALUES('template-content-w2b',1,'内容官','content_officer','published',
             '{}','internal','{}',%s,'test') ON CONFLICT DO NOTHING""",
            ("b" * 64,),
        )
        conn.execute(
            """INSERT INTO aip_agent_instance
            (org_id,project_id,instance_id,template_id,template_revision,status,
             overlay,version,created_by)
            VALUES(%s,%s,'agent-content-w2b','template-content-w2b',1,
             'provisioning','{}',1,'test') ON CONFLICT DO NOTHING""",
            SCOPE.key,
        )
        conn.commit()


def test_eval_contract_create_replay_list_and_tenant_isolation() -> None:
    _seed_dependencies()
    store = AipProductionContractStore()
    before_count = store.list_eval_contracts(SCOPE).count
    created = store.create_eval_contract(SCOPE, "test", "eval-create", _eval_request())
    replay = store.create_eval_contract(SCOPE, "test", "eval-create", _eval_request())
    assert replay.contract_id == created.contract_id
    assert created.readiness is ContractReadiness.BLOCKED
    assert {item.code for item in created.blockers} == {
        "EVAL_PUBLICATION_MISSING",
        "EVAL_GATE_MISSING",
    }
    assert store.list_eval_contracts(SCOPE).count == before_count + 1
    assert store.list_eval_contracts(OTHER_SCOPE).count == 0
    with pytest.raises(ProductionContractIdempotencyConflict):
        store.create_eval_contract(
            SCOPE,
            "test",
            "eval-create",
            _eval_request("c" * 64),
        )


def test_eval_contract_rejects_cross_tenant_or_drifted_suite() -> None:
    _seed_dependencies()
    store = AipProductionContractStore()
    with pytest.raises(ProductionContractDependencyBlocked, match="EVAL_SUITE"):
        store.create_eval_contract(OTHER_SCOPE, "test", "eval-other", _eval_request())
    with pytest.raises(ProductionContractDependencyBlocked, match="EVAL_SUITE_DRIFTED"):
        store.create_eval_contract(
            SCOPE,
            "test",
            "eval-drift",
            _eval_request("d" * 64),
        )


def test_responsibility_plan_fails_closed_without_template_authority() -> None:
    _seed_dependencies()
    store = AipProductionContractStore()
    with pytest.raises(
        ProductionContractDependencyBlocked,
        match="RESPONSIBILITY_TEMPLATE_AUTHORITY_UNAVAILABLE",
    ):
        store.create_responsibility_plan(
            SCOPE,
            "test",
            "plan-no-authority",
            _responsibility_request(),
        )


def test_responsibility_plan_draft_reports_inactive_binding_blockers() -> None:
    _seed_dependencies()
    store = AipProductionContractStore(
        responsibility_template_resolver=lambda _scope, _ref: True
    )
    before_count = store.list_responsibility_plans(SCOPE).count
    created = store.create_responsibility_plan(
        SCOPE,
        "test",
        "plan-create",
        _responsibility_request(),
    )
    assert created.readiness is ContractReadiness.BLOCKED
    assert created.coverage.value == "blocked"
    assert created.uncovered_slots == ["content.review"]
    assert {item.code for item in created.blockers} == {
        "SKILL_BINDING_NOT_ACTIVE",
        "CAPABILITY_BINDING_NOT_ACTIVE",
    }
    assert store.list_responsibility_plans(SCOPE).count == before_count + 1


def test_eval_revise_uses_cas_and_blocked_freeze_does_not_advance_head() -> None:
    _seed_dependencies()
    store = AipProductionContractStore()
    created = store.create_eval_contract(SCOPE, "test", "eval-cas-create", _eval_request())
    revised = store.revise_eval_contract(
        SCOPE,
        "test",
        created.contract_id,
        "eval-cas-revise",
        ReviseEvalContractRequest(
            **_eval_request(warning=0.7).model_dump(),
            expected_version=1,
        ),
    )
    assert (revised.revision, revised.version) == (2, 2)
    with pytest.raises(ProductionContractConflict, match="stale"):
        store.revise_eval_contract(
            SCOPE,
            "test",
            created.contract_id,
            "eval-cas-stale",
            ReviseEvalContractRequest(
                **_eval_request().model_dump(),
                expected_version=1,
            ),
        )
    with pytest.raises(ProductionContractDependencyBlocked, match="EVAL_CONTRACT_NOT_READY"):
        store.freeze_eval_contract(
            SCOPE,
            "test",
            created.contract_id,
            2,
            "eval-freeze-blocked",
        )
    latest = store.get_eval_contract(SCOPE, created.contract_id)
    assert (latest.revision, latest.version, latest.lifecycle.value) == (2, 2, "draft")


def test_responsibility_revise_and_blocked_freeze_do_not_mutate_history() -> None:
    _seed_dependencies()
    store = AipProductionContractStore(
        responsibility_template_resolver=lambda _scope, _ref: True
    )
    created = store.create_responsibility_plan(
        SCOPE, "test", "plan-cas-create", _responsibility_request()
    )
    revised = store.revise_responsibility_plan(
        SCOPE,
        "test",
        created.plan_id,
        "plan-cas-revise",
        ReviseResponsibilityPlanRequest(
            **_responsibility_request("ecommerce-standard-v2").model_dump(),
            expected_version=1,
        ),
    )
    assert (revised.revision, revised.version) == (2, 2)
    with pytest.raises(ProductionContractDependencyBlocked, match="RESPONSIBILITY_PLAN_NOT_READY"):
        store.freeze_responsibility_plan(
            SCOPE,
            "test",
            created.plan_id,
            2,
            "plan-freeze-blocked",
        )
    latest = store.get_responsibility_plan(SCOPE, created.plan_id)
    assert (latest.revision, latest.version, latest.lifecycle.value) == (2, 2, "draft")


def test_w2b_revision_tables_are_force_rls_and_database_immutable() -> None:
    _seed_dependencies()
    store = AipProductionContractStore()
    created = store.create_eval_contract(SCOPE, "test", "eval-immutable", _eval_request())
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class
            WHERE relname IN ('aip_eval_contract_revision','aip_responsibility_plan_revision')
            ORDER BY relname"""
        ).fetchall()
        assert [(row["relname"], row["relrowsecurity"], row["relforcerowsecurity"]) for row in rows] == [
            ("aip_eval_contract_revision", True, True),
            ("aip_responsibility_plan_revision", True, True),
        ]
        with pytest.raises(Exception, match="AIP4_APPEND_ONLY"):
            with conn.transaction():
                conn.execute(
                    """UPDATE aip_eval_contract_revision SET created_by='mutated'
                    WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=1""",
                    (*SCOPE.key, created.contract_id),
                )
        unchanged = conn.execute(
            """SELECT created_by FROM aip_eval_contract_revision
            WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=1""",
            (*SCOPE.key, created.contract_id),
        ).fetchone()
        assert unchanged["created_by"] == "test"


def test_eval_ready_contract_freezes_as_an_append_only_revision() -> None:
    _seed_dependencies()

    class ReadyStore(AipProductionContractStore):
        def _eval_blockers(self, conn, scope, row):  # type: ignore[no-untyped-def]
            return []

    store = ReadyStore()
    created = store.create_eval_contract(SCOPE, "test", "eval-ready", _eval_request())
    frozen = store.freeze_eval_contract(
        SCOPE, "test", created.contract_id, 1, "eval-ready-freeze"
    )
    assert (frozen.revision, frozen.version, frozen.lifecycle.value) == (2, 2, "frozen")
    assert frozen.content_hash == created.content_hash
    with connect(SCOPE) as conn:
        history = conn.execute(
            """SELECT revision,lifecycle,content_hash FROM aip_eval_contract_revision
            WHERE org_id=%s AND project_id=%s AND contract_id=%s ORDER BY revision""",
            (*SCOPE.key, created.contract_id),
        ).fetchall()
    assert [(row["revision"], row["lifecycle"]) for row in history] == [
        (1, "draft"),
        (2, "frozen"),
    ]
    assert len({row["content_hash"] for row in history}) == 1
