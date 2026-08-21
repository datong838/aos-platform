from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace


SCRIPT = (
    Path(__file__).resolve().parents[4]
    / "scripts/aip/inspect_r2_5_catalog_matrix.py"
)
SPEC = importlib.util.spec_from_file_location("inspect_r2_5_catalog_matrix", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Stats:
    runnable_count = 1

    def model_dump(self, **_: object) -> dict[str, int]:
        return {"runnableCount": self.runnable_count}


def _catalog() -> SimpleNamespace:
    rows = []
    for template_id in MODULE.EXPECTED_RUNNABLE_TEMPLATES:
        rows.append(
            SimpleNamespace(
                template=SimpleNamespace(
                    template_id=template_id,
                    display_name=template_id,
                ),
                instance=SimpleNamespace(status=SimpleNamespace(value="active")),
                runtime_readiness=(
                    "runnable"
                    if template_id == "ecommerce.data_advisor"
                    else "blocked"
                ),
                blockers=[] if template_id == "ecommerce.data_advisor" else ["stale"],
                skills=[SimpleNamespace(lifecycle=SimpleNamespace(value="published"))],
            )
        )
    return SimpleNamespace(stats=_Stats(), items=rows)


def test_data_advisor_only_refresh_excludes_multimodal_and_other_colleagues(
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    health = {
        "observationId": "health-text-current",
        "expiresAt": now + timedelta(minutes=15),
    }
    capability_ids: list[str] = []
    skill_ids: list[str] = []

    class _CapabilityService:
        def get(self, _scope, binding_id):
            capability_ids.append(binding_id)
            return SimpleNamespace(
                status="active",
                operational_readiness=MODULE.CapabilityReadiness.AVAILABLE,
                readiness_expires_at=now + timedelta(minutes=10),
            )

    class _SkillService:
        def get_binding(self, _scope, binding_id):
            skill_ids.append(binding_id)
            return SimpleNamespace(
                status="active",
                readiness=MODULE.CapabilityReadiness.AVAILABLE,
                readiness_expires_at=now + timedelta(minutes=10),
            )

    monkeypatch.setattr(MODULE, "_health", lambda _now: health)
    monkeypatch.setattr(MODULE, "AipCapabilityBindingService", _CapabilityService)
    monkeypatch.setattr(MODULE, "AipSkillRegistry", _SkillService)

    result = MODULE.refresh_readiness(now=now, data_advisor_only=True)

    assert capability_ids == [MODULE.CAPABILITY_BINDING_ID]
    assert skill_ids == [MODULE.SKILL_BINDING_ID]
    assert result["mode"] == "data_advisor_only"


def test_data_advisor_only_handoff_can_be_green_while_six_colleagues_are_stale(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        MODULE,
        "_health",
        lambda _now: {
            "observationId": "health-text-current",
            "p50LatencyMs": 611,
            "expiresAt": datetime.now(UTC) + timedelta(minutes=15),
            "v8AgentRunStatus": "succeeded",
            "v8AttemptStatus": "succeeded",
            "canaryAgentRuns": 0,
        },
    )
    monkeypatch.setattr(
        MODULE,
        "refresh_readiness",
        lambda **_kwargs: {"mode": "data_advisor_only"},
    )
    monkeypatch.setattr(
        MODULE,
        "AipEcommerceAgentInstaller",
        lambda: SimpleNamespace(catalog=lambda _principal: _catalog()),
    )

    result = MODULE.inspect(refresh=True, data_advisor_only=True)

    assert result["status"] == "R2_5_DEP_ADP_QUERY_EVIDENCE_GREEN"
    assert result["depAdpQuery"]["dataAdvisorD03Text"] == "GREEN"
    assert result["depAdpQuery"]["sixTextColleagues"] == "RED"

