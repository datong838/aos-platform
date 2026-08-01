"""Focused safety and scheduler tests for canonical AIP Logic dry-runs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_logic_dry_run_executor import (
    LogicDryRunExecutor,
    LogicDryRunPreflightError,
)
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest, LogicTokenUsage
from aos_api.aip_logic_graph_models import (
    LogicGraphSnapshot,
    ValidateLogicGraphRequest,
    compute_logic_graph_hash,
    compute_logic_graph_payload_hash,
)
from aos_api.aip_logic_runtime_adapters import (
    ExecuteAdapterResult,
    LLMAdapterResult,
    RuntimeAdapterRegistry,
    ToolAdapterResult,
)
from pydantic import ValidationError


def _snapshot(nodes, edges, entries) -> LogicGraphSnapshot:
    content = ValidateLogicGraphRequest(
        name="dry-run", nodes=nodes, edges=edges, entry_node_ids=entries
    )
    now = datetime.now(UTC)
    return LogicGraphSnapshot(
        id="graph-1",
        name=content.name,
        description="",
        status="draft",
        schema_version=1,
        revision=3,
        graph_hash=compute_logic_graph_hash(content),
        nodes=content.nodes,
        edges=content.edges,
        entry_node_ids=content.entry_node_ids,
        created_at=now,
        updated_at=now,
    )


def test_request_requires_strict_explicit_true_and_rejects_legacy_alias() -> None:
    base = {"expected_revision": 1, "expected_graph_hash": "a" * 64}
    for body in (
        {**base, "dry_run": False},
        {**base, "dry_run": 1},
        {**base, "dryRun": True},
        base,
    ):
        with pytest.raises(ValidationError):
            LogicDryRunRequest.model_validate(body)
    assert LogicDryRunRequest.model_validate({**base, "dry_run": True}).dry_run is True


def test_json_depth_counts_root_as_one() -> None:
    allowed = {}
    for _ in range(15):
        allowed = {"child": allowed}
    LogicDryRunRequest(
        expected_revision=1, dry_run=True, expected_graph_hash="a" * 64, inputs=allowed
    )
    too_deep = {"child": allowed}
    with pytest.raises(ValidationError, match="depth"):
        LogicDryRunRequest(
            expected_revision=1,
            dry_run=True,
            expected_graph_hash="a" * 64,
            inputs=too_deep,
        )


def test_branch_is_deterministic_and_unselected_path_is_skipped() -> None:
    graph = _snapshot(
        [
            {"id": "in", "kind": "input", "label": "input"},
            {
                "id": "b",
                "kind": "branch",
                "label": "branch",
                "config": {
                    "paths": [
                        {"id": "high", "condition": "score >= 5"},
                        {"id": "fallback", "default": True},
                    ]
                },
            },
            {
                "id": "yes",
                "kind": "transform",
                "label": "yes",
                "config": {"expression": "score * 2"},
            },
            {
                "id": "no",
                "kind": "transform",
                "label": "no",
                "config": {"expression": "0"},
            },
        ],
        [
            {"id": "i-b", "source_node_id": "in", "target_node_id": "b"},
            {
                "id": "b-y",
                "source_node_id": "b",
                "source_port": "high",
                "branch_path": "high",
                "target_node_id": "yes",
            },
            {
                "id": "b-n",
                "source_node_id": "b",
                "source_port": "fallback",
                "branch_path": "fallback",
                "target_node_id": "no",
            },
        ],
        ["in"],
    )
    result = LogicDryRunExecutor().execute(graph, {"score": 7})
    by_id = {node.node_id: node for node in result.node_results}
    assert result.status == "succeeded"
    assert by_id["b"].selected_branch_path == "high"
    assert by_id["yes"].status == "executed"
    assert by_id["no"].status == "skipped"
    assert by_id["no"].error.reason == "branch_not_selected"


def test_unknown_config_fails_and_active_successor_is_canceled_fail_fast() -> None:
    graph = _snapshot(
        [
            {"id": "in", "kind": "input", "label": "input", "config": {"legacy": True}},
            {
                "id": "next",
                "kind": "transform",
                "label": "next",
                "config": {"expression": "1"},
            },
        ],
        [{"id": "e", "source_node_id": "in", "target_node_id": "next"}],
        ["in"],
    )
    with pytest.raises(LogicDryRunPreflightError, match="canonical contract"):
        LogicDryRunExecutor().execute(graph, {})


def test_llm_usage_is_real_and_raw_answer_is_not_returned() -> None:
    adapters = RuntimeAdapterRegistry()
    adapters.register_llm(
        "approved",
        lambda _prompt, _context: LLMAdapterResult(
            output="secret raw answer",
            usage=LogicTokenUsage(
                model="approved", input_tokens=2, output_tokens=3, total_tokens=5
            ),
        ),
        adapter_name="fake-safe",
    )
    graph = _snapshot(
        [
            {
                "id": "llm",
                "kind": "use_llm",
                "label": "llm",
                "config": {"prompt": "hello", "model": "approved"},
            }
        ],
        [],
        ["llm"],
    )
    result = LogicDryRunExecutor(adapters).execute(graph, {})
    assert result.total_tokens == 5
    assert result.node_results[0].output["response_length"] == len("secret raw answer")
    assert "secret raw answer" not in str(result.model_dump())
    assert "cot" not in str(result.model_dump()).lower()


def test_tool_requires_read_only_dry_run_safe_registration() -> None:
    adapters = RuntimeAdapterRegistry()
    adapters.register_tool(
        "write",
        lambda _args, _context: ToolAdapterResult(output={"ok": True}),
        adapter_name="fake",
        read_only=False,
        dry_run_safe=True,
    )
    graph = _snapshot(
        [
            {
                "id": "tool",
                "kind": "use_tool",
                "label": "tool",
                "config": {"tool": "write"},
            }
        ],
        [],
        ["tool"],
    )
    result = LogicDryRunExecutor(adapters).execute(graph, {})
    assert result.status == "failed"
    assert result.error.code == "TOOL_NOT_DRY_RUN_SAFE"


def test_oversized_tool_output_fails_instead_of_truncating_success() -> None:
    adapters = RuntimeAdapterRegistry()
    adapters.register_tool(
        "large",
        lambda _args, _context: ToolAdapterResult(output={"value": "x" * 140_000}),
        adapter_name="fake",
        read_only=True,
        dry_run_safe=True,
    )
    graph = _snapshot(
        [
            {
                "id": "tool",
                "kind": "use_tool",
                "label": "tool",
                "config": {"tool": "large"},
            }
        ],
        [],
        ["tool"],
    )
    result = LogicDryRunExecutor(adapters).execute(graph, {})
    assert result.status == "failed"
    assert result.error.code in {"TOOL_ADAPTER_FAILED", "NODE_OUTPUT_INVALID"}
    assert result.node_results[0].truncated is False


def test_adapter_timeout_is_cooperative_and_machine_readable() -> None:
    clock = [0.0]
    adapters = RuntimeAdapterRegistry(monotonic=lambda: clock[0])

    def timed_out(_prompt, context):
        clock[0] = 11.0
        context.checkpoint()

    adapters.register_llm("approved", timed_out, adapter_name="cooperative")
    graph = _snapshot(
        [
            {
                "id": "llm",
                "kind": "use_llm",
                "label": "llm",
                "config": {"prompt": "hello", "model": "approved"},
            }
        ],
        [],
        ["llm"],
    )
    result = LogicDryRunExecutor(adapters).execute(graph, {})
    assert result.status == "failed"
    assert result.error.code == "ADAPTER_TIMEOUT"


def test_total_result_budget_fails_instead_of_truncating_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "aos_api.aip_logic_dry_run_executor.MAX_TOTAL_RESULT_BYTES", 200
    )
    graph = _snapshot([{"id": "n", "kind": "input", "label": "n"}], [], ["n"])
    result = LogicDryRunExecutor().execute(graph, {"value": "x" * 100})
    assert result.status == "failed"
    assert result.error.code == "TOTAL_RESULT_LIMIT"


def test_preflight_rejects_archived_and_non_root_entry() -> None:
    archived = _snapshot(
        [{"id": "n", "kind": "input", "label": "n"}], [], ["n"]
    ).model_copy(update={"status": "archived"})
    with pytest.raises(LogicDryRunPreflightError) as archived_error:
        LogicDryRunExecutor.preflight(archived)
    assert archived_error.value.code == "LOGIC_GRAPH_ARCHIVED"
    graph = _snapshot(
        [
            {"id": "a", "kind": "input", "label": "a"},
            {"id": "b", "kind": "input", "label": "b"},
        ],
        [{"id": "a-b", "source_node_id": "a", "target_node_id": "b"}],
        ["b"],
    )
    with pytest.raises(LogicDryRunPreflightError) as entry_error:
        LogicDryRunExecutor.preflight(graph)
    assert entry_error.value.code == "ENTRY_NODE_HAS_INCOMING_EDGE"


def test_preflight_rejects_empty_graph_before_a_run_can_be_created() -> None:
    with pytest.raises(LogicDryRunPreflightError) as exc:
        LogicDryRunExecutor.preflight(_snapshot([], [], []))
    assert exc.value.code == "LOGIC_GRAPH_EMPTY"


def test_guarded_unexpected_failure_has_complete_terminal_node_evidence(
    monkeypatch,
) -> None:
    graph = _snapshot(
        [
            {"id": "first", "kind": "input", "label": "first"},
            {
                "id": "next",
                "kind": "transform",
                "label": "next",
                "config": {"expression": "1"},
            },
            {"id": "orphan", "kind": "input", "label": "orphan"},
        ],
        [{"id": "first-next", "source_node_id": "first", "target_node_id": "next"}],
        ["first"],
    )

    def explode(*_args, **_kwargs):
        raise RuntimeError("unexpected")

    executor = LogicDryRunExecutor()
    monkeypatch.setattr(executor, "execute", explode)
    result = executor.execute_guarded(
        graph, {}, run_id="guarded", started_at=datetime.now(UTC)
    )
    assert [node.node_id for node in result.node_results] == [
        "first",
        "next",
        "orphan",
    ]
    assert [node.status for node in result.node_results] == [
        "failed",
        "canceled",
        "skipped",
    ]
    assert result.error.node_id == "first"
    assert result.node_results[0].error.code == "INTERNAL_EXECUTION_ERROR"
    assert result.node_results[0].error.node_id == "first"
    assert result.node_results[1].error.reason == "fail_fast"
    assert result.node_results[2].error.reason == "not_reachable"


def test_published_snapshot_is_revalidated_without_rewriting_its_checksum() -> None:
    draft = _snapshot([{"id": "n", "kind": "input", "label": "n"}], [], ["n"])
    payload = {
        "name": draft.name,
        "description": draft.description,
        "status": "published",
        "schema_version": draft.schema_version,
        "nodes": [node.model_dump(mode="json") for node in draft.nodes],
        "edges": [],
        "entry_node_ids": ["n"],
    }
    published = draft.model_copy(
        update={
            "status": "published",
            "graph_hash": compute_logic_graph_payload_hash(payload),
        }
    )
    assert LogicDryRunExecutor().execute(published, {}).status == "succeeded"


def test_failed_upstream_skips_handoff_instead_of_submitting_intent() -> None:
    graph = _snapshot(
        [
            {
                "id": "bad",
                "kind": "transform",
                "label": "bad",
                "config": {"expression": "missing.value"},
            },
            {"id": "ok", "kind": "input", "label": "ok"},
            {
                "id": "h",
                "kind": "handoff",
                "label": "h",
                "config": {"decision": "review", "handoff_to": "draft_inbox"},
            },
        ],
        [
            {"id": "bad-h", "source_node_id": "bad", "target_node_id": "h"},
            {"id": "ok-h", "source_node_id": "ok", "target_node_id": "h"},
        ],
        ["bad", "ok"],
    )
    result = LogicDryRunExecutor().execute(graph, {})
    assert result.status == "failed"
    handoff = next(node for node in result.node_results if node.node_id == "h")
    assert handoff.status == "skipped"
    assert handoff.error.reason == "upstream_failed"


def test_all_ten_canonical_kinds_have_explicit_success_behavior() -> None:
    adapters = RuntimeAdapterRegistry()
    adapters.register_llm(
        "m",
        lambda _prompt, _ctx: LLMAdapterResult(
            output="answer",
            usage=LogicTokenUsage(
                model="m", input_tokens=1, output_tokens=1, total_tokens=2
            ),
        ),
        adapter_name="llm-safe",
    )
    adapters.register_tool(
        "t",
        lambda _args, _ctx: ToolAdapterResult(output={"tool": "ok"}),
        adapter_name="tool-safe",
        read_only=True,
        dry_run_safe=True,
    )
    adapters.register_execute(
        "sandbox",
        lambda _request, _ctx: ExecuteAdapterResult(preview={"ready": True}),
        adapter_name="sandbox-safe",
    )
    cases = [
        ("input", {}, {"x": 1}),
        ("create_variable", {"name": "made", "expression": "1"}, {}),
        ("get_property", {"source": "inputs", "property": "x"}, {"x": 1}),
        ("use_llm", {"prompt": "hello", "model": "m"}, {}),
        ("use_tool", {"tool": "t"}, {}),
        ("transform", {"expression": "1 + 2"}, {}),
        (
            "apply_action",
            {
                "action": "Order.flag",
                "edits": [{"object_id": "o-1", "field": "flag", "value": True}],
            },
            {},
        ),
        ("execute", {"target": "sandbox", "request": {"id": "x"}}, {}),
        ("branch", {"paths": [{"id": "default", "default": True}]}, {}),
    ]
    for kind, config, inputs in cases:
        graph = _snapshot(
            [{"id": "n", "kind": kind, "label": kind, "config": config}], [], ["n"]
        )
        result = LogicDryRunExecutor(adapters).execute(graph, inputs)
        assert result.status == "succeeded", kind
        assert result.node_results[0].status == "executed", kind
    handoff = _snapshot(
        [
            {"id": "a", "kind": "input", "label": "a"},
            {"id": "b", "kind": "input", "label": "b"},
            {
                "id": "h",
                "kind": "handoff",
                "label": "h",
                "config": {"decision": "review", "handoff_to": "draft_inbox"},
            },
        ],
        [
            {"id": "a-h", "source_node_id": "a", "target_node_id": "h"},
            {"id": "b-h", "source_node_id": "b", "target_node_id": "h"},
        ],
        ["a", "b"],
    )
    result = LogicDryRunExecutor(adapters).execute(handoff, {})
    assert result.status == "succeeded"
    assert result.node_results[-1].output["submitted"] is False


@pytest.mark.parametrize(
    "kind,config",
    [
        ("create_variable", {"name": "x", "expr": "1"}),
        ("transform", {"expr": "1"}),
        ("use_tool", {"tool_id": "t"}),
        ("apply_action", {"action_ref": "a", "edits": []}),
        ("execute", {"query": "q"}),
    ],
)
def test_legacy_config_aliases_are_not_accepted(kind: str, config: dict) -> None:
    graph = _snapshot(
        [{"id": "n", "kind": kind, "label": kind, "config": config}], [], ["n"]
    )
    with pytest.raises(LogicDryRunPreflightError) as exc:
        LogicDryRunExecutor().execute(graph, {})
    assert exc.value.code == "NODE_CONFIG_INVALID"
