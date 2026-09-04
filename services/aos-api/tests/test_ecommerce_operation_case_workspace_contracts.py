from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aos_api.ecommerce_operation_case_workspace_contracts import (
    OperationCaseWorkspaceEnvelope,
)


NOW = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)


def _body() -> dict[str, object]:
    return {
        "tenant": {"orgId": "org-org", "projectId": "dev-project"},
        "status": "ready",
        "evaluatedAt": NOW,
        "dataCutoff": NOW,
        "sources": [
            {"sourceId": source_id, "status": "ready", "count": count, "blocker": None}
            for source_id, count in [
                ("orders", 1), ("inventory", 1), ("shipments", 0),
                ("aftersaleEvents", 0), ("payments", 0), ("operationCases", 0),
            ]
        ],
        "cases": [],
        "candidates": [],
        "availableRefs": [],
        "ledger": {
            "sourceTotal": 2, "assigned": 2, "unassigned": 0, "candidates": 0,
            "openCases": 0, "pausedCases": 0, "closedCases": 0,
        },
        "externalEffectAllowed": False,
    }


def test_workspace_contract_reconciles_source_and_assignment_ledgers() -> None:
    body = OperationCaseWorkspaceEnvelope.model_validate(_body())
    assert body.ledger.source_total == body.ledger.assigned + body.ledger.unassigned
    drift = _body()
    drift["ledger"] = {**drift["ledger"], "sourceTotal": 3}  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        OperationCaseWorkspaceEnvelope.model_validate(drift)


def test_workspace_contract_requires_canonical_sources_and_false_external_effect() -> None:
    missing = _body()
    missing["sources"] = missing["sources"][:-1]  # type: ignore[index]
    with pytest.raises(ValidationError):
        OperationCaseWorkspaceEnvelope.model_validate(missing)
    unsafe = _body()
    unsafe["externalEffectAllowed"] = True
    with pytest.raises(ValidationError):
        OperationCaseWorkspaceEnvelope.model_validate(unsafe)

