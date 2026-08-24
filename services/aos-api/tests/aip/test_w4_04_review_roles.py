"""W4-04 explicit ReviewIssue command role gates."""
from __future__ import annotations

import pytest

from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.routers.aip_production_contracts import _require_review_role


def _principal(*roles: str) -> Principal:
    return Principal(
        subject="pytest:w4-04",
        org_id="org-org",
        project_id="dev-project",
        roles=list(roles),
    )


def test_review_create_and_control_roles_are_explicit_and_separate() -> None:
    _require_review_role(_principal("evaluator"))
    _require_review_role(_principal("reviewer"), control=True)

    with pytest.raises(ApiError) as create_denied:
        _require_review_role(_principal("viewer"))
    assert create_denied.value.code == "AIP_REVIEW_ROLE_REQUIRED"
    assert create_denied.value.status_code == 403

    with pytest.raises(ApiError) as control_denied:
        _require_review_role(_principal("aip_executor"), control=True)
    assert control_denied.value.code == "AIP_REVIEW_ROLE_REQUIRED"
    assert control_denied.value.status_code == 403
