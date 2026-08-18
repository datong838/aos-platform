"""G04 growth-plan pilot graph and isolated contract-eval authority.

This module deliberately does not construct a Provider client.  Its Eval path
accepts an explicitly injected, read-only dry-run registry and records only
safe structural evidence.  The same immutable graph can later be executed by
the governed AgentRun path using its exact ModelRoute.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_eval_models import EvalReportEvidence
from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_dry_run_models import LogicDryRun
from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    LogicGraphEdge,
    LogicGraphNode,
    LogicGraphSnapshot,
)
from aos_api.aip_logic_runtime_adapters import RuntimeAdapterRegistry
from aos_api.evals_engine import CaseResult, EvalSuite, TestCase

G04_GRAPH_ID = "ecommerce.logic.G04"
G04_EVAL_SUITE_ID = "ecommerce.logic.G04.contract.v1"
G04_OUTPUT_CONTRACT = "RecommendationDraft.DRAFT"

_ALLOWED_INPUT_KEYS = frozenset(
    {"summary", "evidence_refs", "requested_mode", "data_classification"}
)
_SENSITIVE_TEXT = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b1[3-9]\d{9}\b|"
    r"(?:api[_ -]?key|secret|password|token)\s*[:=])",
    re.IGNORECASE,
)


class G04InputGateError(ValueError):
    """Safe, stable failure returned before an adapter can be invoked."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


@dataclass(frozen=True)
class G04ContractEval:
    suite: EvalSuite
    report: EvalReportEvidence
    successful_run: LogicDryRun


def build_g04_graph_request(*, model_id: str) -> CreateLogicGraphRequest:
    """Return the canonical input -> use_llm -> transform G04 graph."""
    exact_model = model_id.strip()
    if not exact_model:
        raise ValueError("model_id is required")
    return CreateLogicGraphRequest(
        id=G04_GRAPH_ID,
        name="G04 商品对比推荐生成",
        description="基于有来源的非敏感经营摘要生成 RecommendationDraft 草稿；禁止外部动作。",
        nodes=[
            LogicGraphNode(
                id="input",
                kind="input",
                label="校验经营摘要",
                position_x=0,
                position_y=0,
                config={
                    "schema": {
                        "type": "object",
                        "required": [
                            "summary",
                            "evidence_refs",
                            "requested_mode",
                            "data_classification",
                        ],
                        "properties": {
                            "summary": {"type": "string"},
                            "evidence_refs": {"type": "array"},
                            "requested_mode": {"type": "string"},
                            "data_classification": {"type": "string"},
                        },
                    }
                },
            ),
            LogicGraphNode(
                id="draft",
                kind="use_llm",
                label="生成商品对比推荐草稿",
                position_x=320,
                position_y=0,
                config={
                    "model": exact_model,
                    "prompt": (
                        "仅生成内部商品对比推荐草稿，不执行发布、触达或工具调用。"
                        "事实必须受 evidence_refs 约束。经营摘要：{{summary}}"
                    ),
                },
            ),
            LogicGraphNode(
                id="contract",
                kind="transform",
                label="收敛输出契约",
                position_x=640,
                position_y=0,
                config={"expression": '"RecommendationDraft.DRAFT"'},
            ),
        ],
        edges=[
            LogicGraphEdge(
                id="input-to-draft",
                source_node_id="input",
                target_node_id="draft",
            ),
            LogicGraphEdge(
                id="draft-to-contract",
                source_node_id="draft",
                target_node_id="contract",
            ),
        ],
        entry_node_ids=["input"],
    )


def build_g04_eval_suite() -> EvalSuite:
    """Six explicit cases: one structural success and five fail-closed gates."""
    safe = {
        "summary": "近七日复购率下降，来源为内部聚合经营指标。",
        "evidence_refs": ["metric://commerce/repeat-rate/7d"],
        "requested_mode": "draft_only",
        "data_classification": "internal_non_sensitive",
    }
    return EvalSuite(
        id=G04_EVAL_SUITE_ID,
        name="G04 商品对比推荐生成契约门 v1（隔离 dry-run，非模型效果证据）",
        gate_threshold=1.0,
        cases=[
            TestCase(id="g04-positive", name="结构与 Usage 合约", inputs=safe),
            TestCase(
                id="g04-structure",
                name="拒绝缺失结构字段",
                inputs={
                    key: value for key, value in safe.items() if key != "summary"
                },
            ),
            TestCase(
                id="g04-fact-boundary",
                name="拒绝无事实来源",
                inputs={**safe, "evidence_refs": []},
            ),
            TestCase(
                id="g04-external-action",
                name="拒绝外部动作",
                inputs={**safe, "requested_mode": "publish_and_send"},
            ),
            TestCase(
                id="g04-sensitive",
                name="拒绝 Secret 或 PII",
                inputs={**safe, "summary": "联系 13800138000 后制定方案"},
            ),
            TestCase(
                id="g04-adapter-failure",
                name="适配器错误失败关闭",
                inputs={**safe, "summary": "__simulate_adapter_error__"},
            ),
        ],
    )


def validate_g04_inputs(inputs: dict[str, Any]) -> None:
    if set(inputs) != _ALLOWED_INPUT_KEYS:
        raise G04InputGateError(
            "G04_INPUT_STRUCTURE_INVALID", "G04 input fields do not match the contract"
        )
    summary = inputs.get("summary")
    evidence_refs = inputs.get("evidence_refs")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 4_000:
        raise G04InputGateError(
            "G04_INPUT_STRUCTURE_INVALID", "G04 summary is missing or invalid"
        )
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or any(
            not isinstance(ref, str) or not ref.strip() or len(ref) > 500
            for ref in evidence_refs
        )
    ):
        raise G04InputGateError(
            "G04_FACT_EVIDENCE_REQUIRED", "G04 facts require non-empty evidence refs"
        )
    if inputs.get("requested_mode") != "draft_only":
        raise G04InputGateError(
            "G04_EXTERNAL_ACTION_DENIED", "G04 only permits draft-only output"
        )
    if inputs.get("data_classification") != "internal_non_sensitive":
        raise G04InputGateError(
            "G04_DATA_CLASSIFICATION_DENIED",
            "G04 only permits approved non-sensitive input",
        )
    if _SENSITIVE_TEXT.search(summary):
        raise G04InputGateError(
            "G04_SENSITIVE_INPUT_DENIED", "G04 input contains secret or PII patterns"
        )


def evaluate_g04_contract(
    graph: LogicGraphSnapshot,
    registry: RuntimeAdapterRegistry,
    *,
    now: datetime | None = None,
) -> G04ContractEval:
    """Evaluate G04 without a Provider call and return persistence-ready evidence."""
    if graph.id != G04_GRAPH_ID:
        raise ValueError("G04 eval target must be the canonical G04 graph")
    suite = build_g04_eval_suite()
    executor = LogicDryRunExecutor(registry)
    results: list[CaseResult] = []
    successful_run: LogicDryRun | None = None
    for case in suite.cases:
        if case.id == "g04-adapter-failure":
            validate_g04_inputs(case.inputs)
            run = executor.execute(
                graph, case.inputs, run_id="logic-run-g04-eval-adapter-failure"
            )
            actual = {
                "status": run.status,
                "error_code": run.error.code if run.error else None,
                "production_written": run.production_written,
            }
            passed = (
                run.status == "failed"
                and run.error is not None
                and run.error.code in {"LLM_ADAPTER_FAILED", "ADAPTER_TIMEOUT"}
                and run.production_written is False
            )
        elif case.id == "g04-positive":
            validate_g04_inputs(case.inputs)
            run = executor.execute(
                graph, case.inputs, run_id="logic-run-g04-eval-positive"
            )
            terminal = run.node_results[-1]
            llm_node = next(item for item in run.node_results if item.node_id == "draft")
            actual = {
                "status": run.status,
                "output_contract": terminal.output,
                "usage_present": llm_node.usage is not None,
                "production_written": run.production_written,
            }
            passed = actual == {
                "status": "succeeded",
                "output_contract": G04_OUTPUT_CONTRACT,
                "usage_present": True,
                "production_written": False,
            }
            if passed:
                successful_run = run
        else:
            expected_code = {
                "g04-structure": "G04_INPUT_STRUCTURE_INVALID",
                "g04-fact-boundary": "G04_FACT_EVIDENCE_REQUIRED",
                "g04-external-action": "G04_EXTERNAL_ACTION_DENIED",
                "g04-sensitive": "G04_SENSITIVE_INPUT_DENIED",
            }[case.id]
            try:
                validate_g04_inputs(case.inputs)
            except G04InputGateError as exc:
                actual = {"blocked": True, "code": exc.code}
                passed = exc.code == expected_code
            else:
                actual = {"blocked": False, "code": None}
                passed = False
        results.append(
            CaseResult(
                case_id=case.id,
                passed=passed,
                actual=actual,
                expected="contract gate passed",
                judge="exact",
                detail="isolated contract evidence; not Provider quality evidence",
            )
        )
    if successful_run is None:
        raise RuntimeError("G04 positive contract case did not produce a successful run")
    passed_count = sum(result.passed for result in results)
    report = EvalReportEvidence(
        report_id="ecommerce.logic.G04.contract.v1.report",
        suite_id=suite.id,
        target_type="logic_graph",
        target_id=graph.id,
        target_revision=graph.revision,
        target_hash=graph.graph_hash,
        results=results,
        pass_rate=round(passed_count / len(results), 4),
        passed=passed_count,
        failed=len(results) - passed_count,
        total=len(results),
        gate_passed=passed_count == len(results),
        run_at=(now or datetime.now(UTC)).isoformat(),
    )
    return G04ContractEval(suite=suite, report=report, successful_run=successful_run)
