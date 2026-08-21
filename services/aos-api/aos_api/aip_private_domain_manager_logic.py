"""Canonical P01/P03/P04/P05 private-domain Logic contracts for R07.

P02 is deliberately excluded because it already has immutable Graph, Eval,
Publication, Binding and real-pilot history.  The contracts in this module
accept only CustomerLite and policy references, produce drafts only, and run
through an injected read-only dry-run adapter registry.  They cannot contact a
customer, execute a tool, apply an Action, or write production state.
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


@dataclass(frozen=True)
class PrivateDomainManagerLogicDefinition:
    logic_id: str
    name: str
    description: str
    output_contract: str
    requested_mode: str
    prompt: str

    @property
    def graph_id(self) -> str:
        return f"ecommerce.logic.{self.logic_id}"

    @property
    def eval_suite_id(self) -> str:
        return f"{self.graph_id}.contract.v1"


_DEFINITIONS = {
    "P01": PrivateDomainManagerLogicDefinition(
        logic_id="P01",
        name="客户身份沉淀",
        description=(
            "基于 CustomerLite 与已授权策略引用生成客户身份沉淀草稿；"
            "禁止读取原始 PII、直接触达或生产写入。"
        ),
        output_contract="CustomerIdentityDraft.DRAFT",
        requested_mode="identity_draft_only",
        prompt="仅生成客户身份沉淀草稿，不扩充原始 PII，不执行触达或写入。",
    ),
    "P03": PrivateDomainManagerLogicDefinition(
        logic_id="P03",
        name="跟进与触达排期",
        description=(
            "基于 CustomerLite、同意、ContactPolicy、频控和退订状态生成排期草稿；"
            "禁止直接发送消息或创建生产任务。"
        ),
        output_contract="FollowupSchedule.DRAFT",
        requested_mode="schedule_draft_only",
        prompt="仅生成受同意、退订和频控约束的跟进排期草稿，不发送消息。",
    ),
    "P04": PrivateDomainManagerLogicDefinition(
        logic_id="P04",
        name="沉默客户与复购机会",
        description=(
            "基于 CustomerLite 与有来源的聚合行为生成复购机会草稿；"
            "禁止自动生成并发送营销内容。"
        ),
        output_contract="ReengagementOpportunity.DRAFT",
        requested_mode="opportunity_draft_only",
        prompt="仅生成沉默客户与复购机会草稿，不生成可直接发送的生产触达。",
    ),
    "P05": PrivateDomainManagerLogicDefinition(
        logic_id="P05",
        name="关系反馈",
        description=(
            "基于 CustomerLite 与有来源的关系效果摘要生成反馈草稿；"
            "禁止自动更新画像、记忆或客户状态。"
        ),
        output_contract="RelationshipFeedback.DRAFT",
        requested_mode="feedback_draft_only",
        prompt="仅生成关系反馈与改进建议草稿，不更新画像、记忆或客户状态。",
    ),
}

PRIVATE_DOMAIN_MANAGER_LOGIC_IDS = tuple(_DEFINITIONS)

_INPUT_KEYS = frozenset(
    {
        "summary",
        "evidence_refs",
        "requested_mode",
        "data_classification",
        "customer_lite_ref",
        "consent_ref",
        "consent_state",
        "contact_policy_ref",
        "frequency_cap_ref",
        "frequency_state",
        "unsubscribe_state",
    }
)
_REFERENCE_PREFIXES = {
    "customer_lite_ref": "object://CustomerLite/",
    "consent_ref": "consent://",
    "contact_policy_ref": "policy://contact/",
    "frequency_cap_ref": "policy://frequency/",
}
_UNSAFE_INPUT = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\b1[3-9]\d{9}\b|"
    r"(?:api[_ -]?key|secret|password|token)\s*[:=]|"
    r"ignore\s+(?:all\s+)?previous|reveal\s+(?:the\s+)?system\s+prompt|"
    r"jailbreak|忽略(?:以上|之前)|泄露系统提示词)",
    re.IGNORECASE,
)


class PrivateDomainManagerInputGateError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.safe_message = message
        super().__init__(message)


@dataclass(frozen=True)
class PrivateDomainManagerContractEval:
    suite: EvalSuite
    report: EvalReportEvidence
    successful_run: LogicDryRun


def private_domain_manager_definition(
    logic_id: str,
) -> PrivateDomainManagerLogicDefinition:
    try:
        return _DEFINITIONS[logic_id.strip().upper()]
    except KeyError as exc:
        raise ValueError(f"unsupported private-domain logic: {logic_id}") from exc


def _input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": sorted(_INPUT_KEYS),
        "properties": {
            "summary": {"type": "string"},
            "evidence_refs": {"type": "array"},
            "requested_mode": {"type": "string"},
            "data_classification": {"type": "string"},
            "customer_lite_ref": {"type": "string"},
            "consent_ref": {"type": "string"},
            "consent_state": {"type": "string"},
            "contact_policy_ref": {"type": "string"},
            "frequency_cap_ref": {"type": "string"},
            "frequency_state": {"type": "string"},
            "unsubscribe_state": {"type": "string"},
        },
    }


def build_private_domain_manager_graph_request(
    logic_id: str, *, model_id: str
) -> CreateLogicGraphRequest:
    definition = private_domain_manager_definition(logic_id)
    exact_model = model_id.strip()
    if not exact_model:
        raise ValueError("model_id is required")
    return CreateLogicGraphRequest(
        id=definition.graph_id,
        name=f"{definition.logic_id} {definition.name}",
        description=definition.description,
        nodes=[
            LogicGraphNode(
                id="input",
                kind="input",
                label="校验 CustomerLite 与触达治理边界",
                position_x=0,
                position_y=0,
                config={"schema": _input_schema()},
            ),
            LogicGraphNode(
                id="draft",
                kind="use_llm",
                label=definition.name,
                position_x=320,
                position_y=0,
                config={
                    "model": exact_model,
                    "prompt": (
                        f"{definition.prompt}事实必须受 evidence_refs 约束；"
                        "只允许使用 customer_lite_ref 指向的最小披露对象。"
                        "非敏感摘要：{{summary}}"
                    ),
                },
            ),
            LogicGraphNode(
                id="contract",
                kind="transform",
                label="收敛 Draft 输出契约",
                position_x=640,
                position_y=0,
                config={"expression": f'"{definition.output_contract}"'},
            ),
        ],
        edges=[
            LogicGraphEdge(
                id="input-to-draft", source_node_id="input", target_node_id="draft"
            ),
            LogicGraphEdge(
                id="draft-to-contract",
                source_node_id="draft",
                target_node_id="contract",
            ),
        ],
        entry_node_ids=["input"],
    )


def _safe_inputs(definition: PrivateDomainManagerLogicDefinition) -> dict[str, Any]:
    return {
        "summary": "近七日聚合关系指标来自已登记的租户快照，截止时间明确。",
        "evidence_refs": ["metric://commerce/customer-lite/relationship/7d"],
        "requested_mode": definition.requested_mode,
        "data_classification": "internal_non_sensitive",
        "customer_lite_ref": "object://CustomerLite/niushop:1:5",
        "consent_ref": "consent://customer-lite/niushop:1:5/revision-3",
        "consent_state": "granted",
        "contact_policy_ref": "policy://contact/private-domain/revision-1",
        "frequency_cap_ref": "policy://frequency/private-domain/revision-1",
        "frequency_state": "within_cap",
        "unsubscribe_state": "subscribed",
    }


def build_private_domain_manager_eval_suite(logic_id: str) -> EvalSuite:
    definition = private_domain_manager_definition(logic_id)
    safe = _safe_inputs(definition)
    prefix = definition.logic_id.lower()
    return EvalSuite(
        id=definition.eval_suite_id,
        name=f"{definition.logic_id} {definition.name}治理契约门 v1（隔离 dry-run）",
        gate_threshold=1.0,
        cases=[
            TestCase(id=f"{prefix}-positive", name="结构与 Draft 输出契约", inputs=safe),
            TestCase(
                id=f"{prefix}-missing",
                name="拒绝缺失结构字段",
                inputs={key: value for key, value in safe.items() if key != "summary"},
            ),
            TestCase(
                id=f"{prefix}-fact-boundary",
                name="拒绝无事实来源",
                inputs={**safe, "evidence_refs": []},
            ),
            TestCase(
                id=f"{prefix}-unsafe-input",
                name="拒绝原始 PII、Secret 或提示词注入",
                inputs={**safe, "summary": "客户手机号 13800138000"},
            ),
            TestCase(
                id=f"{prefix}-consent-denied",
                name="拒绝未同意",
                inputs={**safe, "consent_state": "denied"},
            ),
            TestCase(
                id=f"{prefix}-unsubscribed",
                name="拒绝已退订",
                inputs={**safe, "unsubscribe_state": "unsubscribed"},
            ),
            TestCase(
                id=f"{prefix}-frequency-exceeded",
                name="拒绝超出频控",
                inputs={**safe, "frequency_state": "exceeded"},
            ),
            TestCase(
                id=f"{prefix}-unauthorized",
                name="拒绝越权触达模式",
                inputs={**safe, "requested_mode": "send_now"},
            ),
            TestCase(
                id=f"{prefix}-adapter-failure",
                name="适配器错误失败关闭",
                inputs={**safe, "summary": "__simulate_adapter_error__"},
            ),
        ],
    )


def validate_private_domain_manager_inputs(
    logic_id: str, inputs: dict[str, Any]
) -> None:
    definition = private_domain_manager_definition(logic_id)
    if set(inputs) != set(_INPUT_KEYS):
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_INPUT_STRUCTURE_INVALID",
            f"{definition.logic_id} input fields do not match the contract",
        )
    summary = inputs.get("summary")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 4_000:
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_INPUT_STRUCTURE_INVALID",
            f"{definition.logic_id} summary is missing or invalid",
        )
    evidence_refs = inputs.get("evidence_refs")
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or any(
            not isinstance(ref, str) or not ref.strip() or len(ref) > 500
            for ref in evidence_refs
        )
    ):
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_FACT_EVIDENCE_REQUIRED",
            f"{definition.logic_id} facts require non-empty evidence refs",
        )
    for field, prefix in _REFERENCE_PREFIXES.items():
        value = inputs.get(field)
        if (
            not isinstance(value, str)
            or not value.startswith(prefix)
            or len(value) > 500
        ):
            raise PrivateDomainManagerInputGateError(
                f"{definition.logic_id}_POLICY_REFERENCE_INVALID",
                f"{definition.logic_id} requires an opaque {field} reference",
            )
    if inputs.get("requested_mode") != definition.requested_mode:
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_EXTERNAL_ACTION_DENIED",
            f"{definition.logic_id} only permits its approved draft mode",
        )
    if inputs.get("data_classification") != "internal_non_sensitive":
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_DATA_CLASSIFICATION_DENIED",
            f"{definition.logic_id} only permits approved non-sensitive input",
        )
    if inputs.get("consent_state") != "granted":
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_CONSENT_REQUIRED",
            f"{definition.logic_id} requires an exact granted consent reference",
        )
    if inputs.get("unsubscribe_state") != "subscribed":
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_UNSUBSCRIBED",
            f"{definition.logic_id} refuses unsubscribed or unknown contacts",
        )
    if inputs.get("frequency_state") != "within_cap":
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_FREQUENCY_CAP_EXCEEDED",
            f"{definition.logic_id} refuses contacts outside the frequency cap",
        )
    if _UNSAFE_INPUT.search(summary) or any(
        _UNSAFE_INPUT.search(ref) for ref in evidence_refs
    ):
        raise PrivateDomainManagerInputGateError(
            f"{definition.logic_id}_UNSAFE_INPUT_DENIED",
            f"{definition.logic_id} input contains PII, secret, or prompt injection",
        )


def evaluate_private_domain_manager_contract(
    logic_id: str,
    graph: LogicGraphSnapshot,
    registry: RuntimeAdapterRegistry,
    *,
    now: datetime | None = None,
) -> PrivateDomainManagerContractEval:
    definition = private_domain_manager_definition(logic_id)
    if graph.id != definition.graph_id:
        raise ValueError("eval target must match the canonical private-domain graph")
    suite = build_private_domain_manager_eval_suite(logic_id)
    executor = LogicDryRunExecutor(registry)
    results: list[CaseResult] = []
    successful_run: LogicDryRun | None = None
    expected_codes = {
        "missing": f"{definition.logic_id}_INPUT_STRUCTURE_INVALID",
        "fact-boundary": f"{definition.logic_id}_FACT_EVIDENCE_REQUIRED",
        "unsafe-input": f"{definition.logic_id}_UNSAFE_INPUT_DENIED",
        "consent-denied": f"{definition.logic_id}_CONSENT_REQUIRED",
        "unsubscribed": f"{definition.logic_id}_UNSUBSCRIBED",
        "frequency-exceeded": f"{definition.logic_id}_FREQUENCY_CAP_EXCEEDED",
        "unauthorized": f"{definition.logic_id}_EXTERNAL_ACTION_DENIED",
    }
    for case in suite.cases:
        suffix = case.id.removeprefix(f"{definition.logic_id.lower()}-")
        if suffix == "adapter-failure":
            validate_private_domain_manager_inputs(logic_id, case.inputs)
            run = executor.execute(
                graph,
                case.inputs,
                run_id=(
                    f"logic-run-{definition.logic_id.lower()}-eval-adapter-failure"
                ),
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
        elif suffix == "positive":
            validate_private_domain_manager_inputs(logic_id, case.inputs)
            run = executor.execute(
                graph,
                case.inputs,
                run_id=f"logic-run-{definition.logic_id.lower()}-eval-positive",
            )
            llm_node = next(
                item for item in run.node_results if item.node_id == "draft"
            )
            actual = {
                "status": run.status,
                "output_contract": run.node_results[-1].output,
                "usage_present": llm_node.usage is not None,
                "production_written": run.production_written,
            }
            passed = actual == {
                "status": "succeeded",
                "output_contract": definition.output_contract,
                "usage_present": True,
                "production_written": False,
            }
            if passed:
                successful_run = run
        else:
            try:
                validate_private_domain_manager_inputs(logic_id, case.inputs)
            except PrivateDomainManagerInputGateError as exc:
                actual = {"blocked": True, "code": exc.code}
                passed = exc.code == expected_codes[suffix]
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
        raise RuntimeError(f"{definition.logic_id} positive contract case did not succeed")
    passed_count = sum(result.passed for result in results)
    report = EvalReportEvidence(
        report_id=f"{definition.eval_suite_id}.report",
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
    return PrivateDomainManagerContractEval(
        suite=suite, report=report, successful_run=successful_run
    )


__all__ = [
    "PRIVATE_DOMAIN_MANAGER_LOGIC_IDS",
    "PrivateDomainManagerContractEval",
    "PrivateDomainManagerInputGateError",
    "PrivateDomainManagerLogicDefinition",
    "build_private_domain_manager_eval_suite",
    "build_private_domain_manager_graph_request",
    "evaluate_private_domain_manager_contract",
    "private_domain_manager_definition",
    "validate_private_domain_manager_inputs",
]
