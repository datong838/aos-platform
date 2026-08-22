from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_content_team import (
    ContentTextPlanRequest,
    LOGIC_CROSSWALK,
    RESPONSIBILITIES,
    STAGE_ORDER,
    build_content_team_catalog,
    build_content_text_plan,
)


HASH = "b" * 64


def _ref(kind: str, identifier: str) -> str:
    return f"{kind}:{identifier}@1#{HASH}"


def _request(**updates):
    payload = {
        "productRef": _ref("Product", "niushop-20"),
        "factPackRef": _ref("FactPack", "product-20"),
        "briefRef": _ref("TaskBriefRevision", "content-20"),
        "evidenceBundleRef": _ref("EvidenceBundleRevision", "content-20"),
        "sourceDraftRef": _ref("Artifact", "content-draft-20"),
        "evalReportRef": _ref("EvalReportRevision", "content-draft-20"),
        "lineageRef": _ref("Lineage", "content-draft-20"),
        "c02PilotRef": _ref("AgentRun", "ecommerce-content-officer-C02-real-pilot-v1"),
    }
    payload.update(updates)
    return ContentTextPlanRequest.model_validate(payload)


def test_content_director_is_profile_not_new_agent_or_capability():
    catalog = build_content_team_catalog()

    assert len(RESPONSIBILITIES) == 10
    assert RESPONSIBILITIES[0].key == "coordinator"
    assert RESPONSIBILITIES[0].executes_tools is False
    assert catalog["agentRole"] == "ecommerce.content_officer"
    assert catalog["coordinatorIsProfile"] is True
    assert catalog["sharedCapabilityCountDelta"] == 0
    assert catalog["digitalCoworkerCountDelta"] == 0


def test_all_c01_c08_have_one_crosswalk_and_audit_precedes_platform():
    assert tuple(LOGIC_CROSSWALK) == tuple(f"C{index:02d}" for index in range(1, 9))
    assert STAGE_ORDER == (
        "strategy", "copy_script_title", "audit", "platform", "lead_handoff", "review"
    )
    assert STAGE_ORDER.index("audit") < STAGE_ORDER.index("platform")
    assert LOGIC_CROSSWALK["C03"][0] == "copy_script"


def test_strict_request_rejects_non_exact_and_extra_fields():
    with pytest.raises(ValidationError, match="exact revision/hash ref required"):
        _request(productRef="niushop:1:20")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _request(tenant={"orgId": "org-org", "projectId": "dev-project"})


def test_text_plan_is_deterministic_draft_only_and_traceable():
    request = _request()
    first = build_content_text_plan(request)
    second = build_content_text_plan(request)

    assert first == second
    assert first["status"] == "draft_ready"
    assert [item["stage"] for item in first["steps"]] == list(STAGE_ORDER)
    assert all(item["sideEffect"] is False for item in first["steps"])
    assert first["providerCalls"] == 0
    assert first["platformWrites"] == 0
    assert first["mediaJobs"] == 0
    assert first["avatarSessions"] == 0
    assert first["memoryPromotions"] == 0
    assert first["c02PilotRef"] == request.c02_pilot_ref
    assert len(first["planHash"]) == 64


def test_missing_draft_eval_lineage_fail_closed():
    result = build_content_text_plan(
        _request(sourceDraftRef=None, evalReportRef=None, lineageRef=None)
    )

    assert result["status"] == "blocked"
    assert result["blockerCodes"] == (
        "CONTENT_SOURCE_DRAFT_REQUIRED",
        "CONTENT_EVAL_REPORT_REQUIRED",
        "CONTENT_LINEAGE_REQUIRED",
    )


def test_current_harness_authority_is_unknown_and_publish_never_runs():
    harness_context = {
        "contentDraftRef": _ref("Artifact", "draft-20"),
        "factPackRef": _ref("FactPack", "product-20"),
        "platformRuleRef": _ref("PlatformRuleRevision", "douyin"),
        "summary": "真实商品平台适配草稿",
        "capabilityStates": {"copy.generate": "available", "platform.adapt": "available"},
    }
    unknown = build_content_text_plan(
        _request(harnessIds=["DY-01"], harnessContexts={"DY-01": harness_context})
    )
    publish = build_content_text_plan(
        _request(
            harnessIds=["DY-01"],
            harnessContexts={"DY-01": harness_context},
            requestedAction="publish",
        )
    )

    assert unknown["status"] == "blocked"
    assert unknown["harnessDecisions"][0]["status"] == "unknown"
    assert "HARNESS_RULE_AUTHORITY_UNVERIFIED" in unknown["blockerCodes"]
    assert publish["status"] == "blocked"
    assert "CONTENT_PLATFORM_WRITE_DEFERRED_G5_G6" in publish["blockerCodes"]
    assert publish["platformWrites"] == 0
