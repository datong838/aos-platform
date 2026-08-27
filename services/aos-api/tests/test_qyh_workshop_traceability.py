"""QYH read-only evidence fixture and Workshop route traceability regression."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = Path(__file__).parent / "fixtures/business_investigation/qyh_workshop_traceability_v1.json"
WEB_CLIENT = ROOT / "apps/web/src/api/ecommerceWorkshop/client.ts"
WORKSHOP_ROUTER = ROOT / "services/aos-api/aos_api/routers/ecommerce_workshop.py"
WORKSHOP_UI_ROOTS = (
    ROOT / "apps/web/src/components/workshop",
    ROOT / "apps/web/src/shell",
)


@pytest.fixture(scope="module")
def traceability() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_is_tenant_safe_read_only_and_not_runtime_authority(traceability: dict[str, object]) -> None:
    assert traceability["schemaVersion"] == "aos.ecommerce.qyh-workshop-traceability/v1"
    assert traceability["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert traceability["profileCutoff"] == "2026-08-25T12:56:33Z"
    assert traceability["runtimeAuthority"] == "governed-canonical-projections-only"
    assert traceability["sourcePolicy"] == {
        "fixturePurpose": "read-only regression and evidence recomputation",
        "runtimeDatabaseAccess": False,
        "containsPii": False,
        "mayHydrateProduction": False,
    }


def test_all_eight_pages_trace_to_existing_frontend_and_backend_get_contracts(traceability: dict[str, object]) -> None:
    pages = traceability["pages"]
    assert isinstance(pages, list)
    assert len(pages) == 8
    assert len({page["route"] for page in pages}) == 8
    assert pages[0]["route"] == "/workshop/analyst"
    assert pages[0]["role"] == "orchestration-entry"
    assert pages[-1]["route"] == "/workshop/cockpit"
    assert pages[-1]["role"] == "task-receipt-aggregation"

    client_source = WEB_CLIENT.read_text(encoding="utf-8")
    router_source = WORKSHOP_ROUTER.read_text(encoding="utf-8")
    for page in pages:
        assert page["domains"]
        assert len(page["uiFunctions"]) >= 3
        assert all(re.search(r"[\u4e00-\u9fff]", item) for item in page["uiFunctions"])
        assert re.search(r"[\u4e00-\u9fff]", page["failureMode"])
        assert re.search(r"[\u4e00-\u9fff]", page["writeBoundary"])
        assert not re.search(r"\b(?:(?:BI-)?W\d+[-_]\d+|AOS-\d+)\b", " ".join(page["uiFunctions"]))
        for api in page["api"]:
            if api == "/v1/ecommerce-business-investigations":
                continue
            suffix = api.removeprefix("/v1/ecommerce-workshop")
            assert api in client_source, f"frontend client missing {api}"
            assert f'"{suffix}"' in router_source, f"backend router missing {suffix}"


def test_real_analysis_scenarios_are_recomputable_and_keep_non_claims(traceability: dict[str, object]) -> None:
    scenarios = traceability["scenarios"]
    assert isinstance(scenarios, list)
    assert {item["stage"] for item in scenarios} <= {"portrait", "diagnosis", "solution-design"}
    assert len({item["id"] for item in scenarios}) == len(scenarios)
    for scenario in scenarios:
        assert len(scenario["evidencePlanes"]) >= 2
        assert len(set(scenario["evidencePlanes"])) == len(scenario["evidencePlanes"])
        assert len(scenario["nonClaims"]) >= 3
        for field in ("facts", "interpretation", "competingExplanation", "evidenceGap", "decisionImplication"):
            assert scenario[field]

    experience = next(item for item in scenarios if item["id"] == "qyh-experience-bottleneck")
    assert experience["facts"]["pending"] == experience["facts"]["slots"] - experience["facts"]["consumed"]
    assert experience["facts"]["consumptionRate"] == pytest.approx(3 / 164, abs=1e-10)

    money = next(item for item in scenarios if item["id"] == "qyh-order-money-safety")
    assert {"不是确认 GMV", "不是确认收入", "不是利润"} <= set(money["nonClaims"])
    assert money["facts"]["ordersNotDeleted"] <= money["facts"]["ordersTotal"]
    assert money["facts"]["paidNotDeleted"] <= money["facts"]["ordersNotDeleted"]


def test_fixture_cannot_smuggle_database_or_side_effect_material(traceability: dict[str, object]) -> None:
    serialized = json.dumps(traceability, ensure_ascii=False).lower()
    forbidden = ("password", "secretref", "select *", "mysql://", "jdbc:", "insert into", "update ", "delete from")
    assert all(token not in serialized for token in forbidden)


def test_business_pages_do_not_expose_development_plan_ids_as_business_copy() -> None:
    development_id = re.compile(r"\b(?:(?:BI-)?W\d+[-_]\d+|AOS-\d+)\b")
    violations: list[str] = []
    for root in WORKSHOP_UI_ROOTS:
        for source_file in root.rglob("*.tsx"):
            if source_file.name.endswith(".test.tsx"):
                continue
            for line_number, line in enumerate(source_file.read_text(encoding="utf-8").splitlines(), start=1):
                match = development_id.search(line)
                if match:
                    violations.append(f"{source_file.relative_to(ROOT)}:{line_number}:{match.group(0)}")

    assert not violations, "development plan ids leaked into business UI:\n" + "\n".join(violations)
