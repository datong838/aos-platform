from __future__ import annotations

import pytest
from pydantic import ValidationError

from aos_api.aip_task_models import CreateTaskRequest


def _goal() -> dict[str, object]:
    return {
        "workshopAssignment": {
            "roleKey": "shopping_advisor",
            "colleagueName": "导购顾问",
            "status": "requested",
        },
        "origin": "workshop.task-cockpit",
    }


def test_workshop_business_task_accepts_chinese_business_title_and_requested_colleague() -> None:
    request = CreateTaskRequest(
        type="ecommerce.workshop.business_task",
        title="复盘栖月汇微商城的订单与商品规模",
        goal=_goal(),
    )

    assert request.goal["workshopAssignment"] == _goal()["workshopAssignment"]


@pytest.mark.parametrize("title", ["review orders", "R3-03 完成前端代码开发", "AOS-000459 技术方案同步"])
def test_workshop_business_task_rejects_non_business_title(title: str) -> None:
    with pytest.raises(ValidationError):
        CreateTaskRequest(type="ecommerce.workshop.business_task", title=title, goal=_goal())


@pytest.mark.parametrize(
    "assignment",
    [
        None,
        {"roleKey": "shopping_advisor", "colleagueName": "数据参谋", "status": "requested"},
        {"roleKey": "shopping_advisor", "colleagueName": "导购顾问", "status": "running"},
    ],
)
def test_workshop_business_task_rejects_missing_or_forged_assignment(assignment: object) -> None:
    goal = {} if assignment is None else {"workshopAssignment": assignment}
    with pytest.raises(ValidationError):
        CreateTaskRequest(type="ecommerce.workshop.business_task", title="核对微商城商品库存", goal=goal)


def test_other_task_types_remain_compatible() -> None:
    request = CreateTaskRequest(type="generic", title="W2-C ordinary compatibility")
    assert request.title == "W2-C ordinary compatibility"
