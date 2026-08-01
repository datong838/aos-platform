"""Cross-field truth gates for canonical AIP Logic dry-run contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from aos_api.aip_logic_dry_run_models import (
    LogicDryRun,
    LogicNodeCounts,
    LogicNodeResult,
    LogicProposedEdit,
    LogicRunError,
    LogicRunSummary,
    LogicTokenUsage,
)
from pydantic import ValidationError

NOW = datetime.now(UTC)


def _error(node_id: str = "node") -> LogicRunError:
    return LogicRunError(code="FAILED", message="failed", node_id=node_id)


def _node(**updates) -> LogicNodeResult:
    values = {
        "node_id": "node",
        "kind": "input",
        "status": "executed",
        "started_at": NOW,
        "finished_at": NOW,
        "elapsed_ms": 0,
        "summary": "done",
        "output": {},
    }
    values.update(updates)
    return LogicNodeResult(**values)


def _run(**updates) -> LogicDryRun:
    values = {
        "run_id": "run",
        "graph_id": "graph",
        "status": "succeeded",
        "evaluated_revision": 1,
        "graph_hash": "a" * 64,
        "started_at": NOW,
        "finished_at": NOW,
        "elapsed_ms": 0,
        "node_results": [_node()],
    }
    values.update(updates)
    return LogicDryRun(**values)


@pytest.mark.parametrize(
    "updates",
    [
        {"error": _error()},
        {"status": "failed"},
        {
            "status": "skipped",
            "started_at": None,
            "finished_at": None,
            "elapsed_ms": None,
            "error": LogicRunError(code="SKIPPED", message="skipped", node_id="node"),
        },
        {"error": _error("other")},
        {"finished_at": NOW - timedelta(seconds=1)},
        {
            "proposed_edits": [
                LogicProposedEdit(
                    action="a",
                    object_id="o",
                    field="f",
                    value=True,
                    source_node_id="other",
                )
            ]
        },
    ],
)
def test_node_result_rejects_cross_field_contradictions(updates) -> None:
    with pytest.raises(ValidationError):
        _node(**updates)


def test_dry_run_rejects_status_error_node_token_edit_and_time_contradictions() -> None:
    failed = _node(status="failed", output=None, error=_error())
    usage = LogicTokenUsage(model="m", input_tokens=1, output_tokens=2, total_tokens=3)
    invalid_runs = [
        {"node_results": [failed]},
        {"status": "failed", "error": _error(), "node_results": [_node()]},
        {
            "status": "failed",
            "error": _error("missing"),
            "node_results": [failed],
        },
        {"node_results": [_node(), _node()]},
        {"node_results": [_node(usage=usage)], "total_tokens": 2},
        {"total_tokens": 1},
        {
            "proposed_edits": [
                LogicProposedEdit(
                    action="a",
                    object_id="o",
                    field="f",
                    value=True,
                    source_node_id="missing",
                )
            ]
        },
        {"finished_at": NOW - timedelta(seconds=1)},
    ]
    for updates in invalid_runs:
        with pytest.raises(ValidationError):
            _run(**updates)


def test_summary_rejects_status_count_error_and_time_contradictions() -> None:
    base = {
        "run_id": "run",
        "graph_id": "graph",
        "status": "succeeded",
        "evaluated_revision": 1,
        "graph_hash": "a" * 64,
        "started_at": NOW,
        "finished_at": NOW,
        "elapsed_ms": 0,
        "node_counts": LogicNodeCounts(executed=1),
    }
    invalid = [
        {"node_counts": LogicNodeCounts(failed=1)},
        {"error_code": "FAILED"},
        {
            "status": "failed",
            "node_counts": LogicNodeCounts(executed=1),
            "error_code": "FAILED",
        },
        {
            "status": "failed",
            "node_counts": LogicNodeCounts(failed=1),
            "error_code": None,
        },
        {"finished_at": NOW - timedelta(seconds=1)},
    ]
    for updates in invalid:
        with pytest.raises(ValidationError):
            LogicRunSummary(**{**base, **updates})
