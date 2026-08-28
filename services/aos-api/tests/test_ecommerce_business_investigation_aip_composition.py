"""Read-only AIP production composition resolution tests."""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_aip_authority import selected_skill_refs
from aos_api.ecommerce_business_investigation_aip_composition import (
    INVESTIGATION_LOGIC_IDS,
    INVESTIGATION_SKILL_IDS,
    PostgresAipProductionCompositionSource,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 28, 10, 30, tzinfo=UTC)


def h(char: str) -> str:
    return char * 64


def context_ref() -> InvestigationExactRef:
    return InvestigationExactRef(
        resourceType="ProductionContextRevision",
        resourceId="context-1",
        revision=1,
        contentHash="sha256:" + h("9"),
    )


def rows() -> dict[str, list[dict]]:
    publications = []
    skills = []
    bindings = []
    selection = selected_skill_refs()
    for index, (logic_id, skill_id) in enumerate(
        zip(INVESTIGATION_LOGIC_IDS, INVESTIGATION_SKILL_IDS), start=1
    ):
        digest = h(str(index))
        selected = selection[skill_id]
        publications.append(
            {
                "publication_id": f"publication-{index}",
                "graph_id": logic_id,
                "graph_revision": 1,
                "graph_hash": digest,
            }
        )
        skills.append(
            {
                "skill_id": skill_id,
                "revision": selected.revision,
                "canonical_logic_id": logic_id,
                "lifecycle": "published",
                "content_hash": selected.content_hash,
                "publication_tenant": {"orgId": "org-org", "projectId": "dev-project"},
                "logic_revision_ref": {
                    "assetType": "LogicRevision",
                    "assetId": logic_id,
                    "revision": 1,
                    "contentHash": digest,
                },
            }
        )
        bindings.append(
            {
                "binding_id": f"binding-{index}",
                "instance_id": "ecommerce.data-advisor.default",
                "skill_id": skill_id,
                "skill_revision": selected.revision,
                "status": "active",
                "version": 7,
                "dependency_snapshot_hash": h("d"),
                "readiness": "available",
                "readiness_reasons": [],
                "last_evaluated_at": NOW,
                "readiness_expires_at": NOW + timedelta(minutes=15),
            }
        )
    return {
        "publications": publications,
        "skills": skills,
        "bindings": bindings,
        "stages": [
            {
                "template_id": "investigation-stages",
                "revision": 3,
                "profile": "ecommerce.business-investigation",
                "stages": [
                    {"stageId": "portrait"},
                    {"stageId": "diagnosis"},
                    {"stageId": "solution-design"},
                ],
                "content_hash": h("4"),
                "lifecycle": "frozen",
            }
        ],
        "plans": [
            {
                "plan_id": "investigation-responsibilities",
                "revision": 2,
                "profile": "ecommerce.business-investigation.readonly",
                "slots": [],
                "content_hash": h("5"),
                "lifecycle": "frozen",
            }
        ],
        "contexts": [
            {
                "context_id": "context-1",
                "revision": 1,
                "task_id": "task-1",
                "profile": "ecommerce.business-investigation",
                "content_hash": h("9"),
                "lifecycle": "frozen",
                "readiness": "ready",
                "blockers": [],
            }
        ],
    }


class Result:
    def __init__(self, value):
        self.value = value

    def fetchall(self):
        return self.value


class Connection:
    def __init__(self, data):
        self.data = data
        self.tenant_params = []

    def execute(self, sql, params):
        if "aip_logic_publication" in sql:
            key = "publications"
        elif "aip_skill_template_revision" in sql:
            key = "skills"
        elif "aip_skill_binding" in sql:
            key = "bindings"
        elif "aip_stage_template_revision" in sql:
            key = "stages"
        elif "aip_responsibility_plan_revision" in sql:
            key = "plans"
        elif "aip_production_context_revision" in sql:
            key = "contexts"
        else:
            raise AssertionError(sql)
        if key != "skills":
            self.tenant_params.append(tuple(params[:2]))
        return Result(self.data[key])


def source(data):
    connection = Connection(data)

    @contextmanager
    def connect(scope):
        assert scope in {SCOPE, TenantScope("dev-org", "dev-project")}
        yield connection

    return PostgresAipProductionCompositionSource(connect), connection


def test_complete_exact_composition_is_ready() -> None:
    resolver, connection = source(rows())
    actual = resolver.read(
        SCOPE,
        "initial_store_analysis",
        observed_at=NOW,
        production_context_ref=context_ref(),
    )
    assert actual.ready is True
    assert actual.blockers == []
    assert len(actual.logic_refs) == len(actual.skill_refs) == 3
    assert len(actual.skill_binding_refs) == 3
    assert actual.stage_template_ref is not None
    assert actual.responsibility_plan_ref is not None
    assert actual.production_context_ref == context_ref()
    assert connection.tenant_params and set(connection.tenant_params) == {SCOPE.key}


def test_explicit_skill_ref_is_selected_without_using_latest_revision() -> None:
    data = rows()
    duplicate = deepcopy(data["skills"][-1])
    duplicate["revision"] = 9
    duplicate["content_hash"] = h("e")
    data["skills"].append(duplicate)
    resolver, _ = source(data)
    actual = resolver.read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert actual.ready is False
    assert "AIP_SKILL_SELECTION_REF_MISSING_OR_DRIFTED" not in actual.blockers
    d03 = next(ref for ref in actual.skill_refs if ref.resource_id == "ecommerce.skill.D03")
    assert d03.revision == 4


def test_declared_skill_ref_drift_does_not_fall_back_to_another_revision() -> None:
    data = rows()
    data["skills"][-1]["content_hash"] = h("e")
    resolver, _ = source(data)
    actual = resolver.read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert "AIP_SKILL_SELECTION_REF_MISSING_OR_DRIFTED" in actual.blockers
    assert all(ref.resource_id != "ecommerce.skill.D03" for ref in actual.skill_refs)


def test_binding_missing_ambiguous_and_stale_are_distinct() -> None:
    missing = rows()
    missing["bindings"] = missing["bindings"][:-1]
    actual = source(missing)[0].read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert "AIP_SKILL_BINDING_MISSING" in actual.blockers

    ambiguous = rows()
    ambiguous["bindings"].append(deepcopy(ambiguous["bindings"][0]))
    ambiguous["bindings"][-1]["binding_id"] = "binding-duplicate"
    actual = source(ambiguous)[0].read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert "AIP_SKILL_BINDING_AMBIGUOUS" in actual.blockers

    stale = rows()
    stale["bindings"][0]["readiness_expires_at"] = NOW
    actual = source(stale)[0].read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert "AIP_SKILL_BINDING_READINESS_STALE" in actual.blockers


def test_stage_plan_and_context_lifecycles_fail_closed() -> None:
    data = rows()
    data["stages"][0]["stages"] = [{"stageId": "content.review"}]
    data["plans"][0]["lifecycle"] = "draft"
    actual = source(data)[0].read(SCOPE, "initial_store_analysis", observed_at=NOW)
    assert "AIP_INVESTIGATION_STAGE_TEMPLATE_MISSING" in actual.blockers
    assert "AIP_INVESTIGATION_RESPONSIBILITY_PLAN_NOT_FROZEN" in actual.blockers
    assert "AIP_PRODUCTION_CONTEXT_REQUIRES_RUN" in actual.blockers


def test_context_exact_ref_drift_and_not_ready_are_rejected() -> None:
    data = rows()
    drifted = context_ref().model_copy(update={"content_hash": "sha256:" + h("8")})
    actual = source(data)[0].read(
        SCOPE,
        "initial_store_analysis",
        observed_at=NOW,
        production_context_ref=drifted,
    )
    assert "AIP_PRODUCTION_CONTEXT_REF_DRIFTED" in actual.blockers

    data["contexts"][0]["readiness"] = "blocked"
    actual = source(data)[0].read(
        SCOPE,
        "initial_store_analysis",
        observed_at=NOW,
        production_context_ref=context_ref(),
    )
    assert "AIP_PRODUCTION_CONTEXT_NOT_READY" in actual.blockers


def test_publication_tenant_cannot_cross_into_isolation_canary() -> None:
    resolver, connection = source(rows())
    canary = TenantScope("dev-org", "dev-project")
    actual = resolver.read(canary, "initial_store_analysis", observed_at=NOW)
    assert actual.ready is False
    assert "AIP_SKILL_PUBLICATION_MISSING" in actual.blockers
    assert set(connection.tenant_params) == {canary.key}
