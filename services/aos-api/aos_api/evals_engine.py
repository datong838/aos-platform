"""W1-12 · Evals 评测门控引擎。

评测集模型 + 4 种评判标准（exact/contains/llm/numeric）+ 门控检查器 + 报告生成。
LLM 评判通过 chat_fn 调用（默认 llm_gateway.chat），不写死模型。

详见 docs/palantier/20_tech/220tech_evals-engine.md。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from pydantic import BaseModel, Field

JudgeKind = str  # "exact" | "contains" | "llm" | "numeric"


class TestCase(BaseModel):
    id: str = Field(default_factory=lambda: "tc-" + uuid.uuid4().hex[:8])
    name: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None
    judge: JudgeKind = "exact"
    tolerance: float = 0.0


class EvalSuite(BaseModel):
    id: str = Field(default_factory=lambda: "es-" + uuid.uuid4().hex[:8])
    name: str
    cases: list[TestCase] = Field(default_factory=list)
    gate_threshold: float = 0.8


class CaseResult(BaseModel):
    case_id: str
    passed: bool
    actual: Any = None
    expected: Any = None
    judge: JudgeKind = "exact"
    detail: str = ""


class EvalReport(BaseModel):
    suite_id: str
    results: list[CaseResult] = Field(default_factory=list)
    pass_rate: float = 0.0
    passed: int = 0
    failed: int = 0
    total: int = 0
    gate_passed: bool = False
    run_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvalsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


TargetFn = Callable[[dict[str, Any]], Any]


class EvalsEngine:
    def __init__(self, chat_fn: Callable[..., dict[str, Any]] | None = None) -> None:
        if chat_fn is None:
            from .llm_gateway import chat as _default_chat
            chat_fn = _default_chat
        self._chat_fn = chat_fn
        self._suites: dict[str, EvalSuite] = {}
        self._reports: dict[str, list[EvalReport]] = {}

    def create_suite(self, suite: EvalSuite) -> EvalSuite:
        self._suites[suite.id] = suite
        return suite

    def get_suite(self, suite_id: str) -> EvalSuite | None:
        return self._suites.get(suite_id)

    def list_suites(self) -> list[EvalSuite]:
        return list(self._suites.values())

    def run(
        self, suite_id: str, target_fn: TargetFn, debug: bool = False
    ) -> EvalReport:
        suite = self._suites.get(suite_id)
        if suite is None:
            raise EvalsError("NOT_FOUND", f"评测集 {suite_id} 不存在")
        results: list[CaseResult] = []
        for case in suite.cases:
            actual = target_fn(case.inputs)
            passed, detail = self._judge(case, actual)
            results.append(CaseResult(
                case_id=case.id,
                passed=passed,
                actual=actual,
                expected=case.expected,
                judge=case.judge,
                detail=detail,
            ))
        passed_count = sum(1 for r in results if r.passed)
        total = len(results)
        pass_rate = passed_count / total if total > 0 else 0.0
        report = EvalReport(
            suite_id=suite_id,
            results=results,
            pass_rate=round(pass_rate, 4),
            passed=passed_count,
            failed=total - passed_count,
            total=total,
            gate_passed=pass_rate >= suite.gate_threshold,
        )
        self._reports.setdefault(suite_id, []).append(report)
        return report

    def _judge(self, case: TestCase, actual: Any) -> tuple[bool, str]:
        if case.judge == "exact":
            ok = actual == case.expected
            return ok, "精确匹配" if ok else f"期望 {case.expected!r} 实际 {actual!r}"
        if case.judge == "contains":
            ok = str(case.expected) in str(actual)
            return ok, "包含匹配" if ok else f"期望包含 {case.expected!r}"
        if case.judge == "numeric":
            try:
                diff = abs(float(actual) - float(case.expected))
                ok = diff <= case.tolerance
                return ok, f"差值 {diff:.4f} ≤ 容差 {case.tolerance}" if ok else f"差值 {diff:.4f} > 容差 {case.tolerance}"
            except (TypeError, ValueError) as exc:
                return False, f"数值转换失败：{exc}"
        if case.judge == "llm":
            prompt = (
                f"请判断以下回答是否正确。\n"
                f"问题输入：{case.inputs}\n"
                f"期望输出：{case.expected}\n"
                f"实际输出：{actual}\n"
                f"请只回答 yes 或 no。"
            )
            try:
                resp = self._chat_fn(prompt)
                answer_text = resp.get("answer", "") if isinstance(resp, dict) else str(resp)
                ok = "yes" in answer_text.lower().strip()[:10]
                return ok, f"LLM 评判：{answer_text[:80]}"
            except Exception as exc:
                return False, f"LLM 评判失败：{exc}"
        return False, f"未知评判标准：{case.judge}"

    def gate_check(self, suite_id: str, target_fn: TargetFn) -> dict[str, Any]:
        report = self.run(suite_id, target_fn)
        return {
            "suite_id": suite_id,
            "gate_passed": report.gate_passed,
            "pass_rate": report.pass_rate,
            "threshold": self._suites[suite_id].gate_threshold,
            "passed": report.passed,
            "failed": report.failed,
            "total": report.total,
        }

    def get_report(self, suite_id: str) -> EvalReport | None:
        reports = self._reports.get(suite_id)
        if not reports:
            return None
        return reports[-1]

    def history(self, suite_id: str) -> list[EvalReport]:
        return list(self._reports.get(suite_id, []))


_engine = EvalsEngine()


def get_engine() -> EvalsEngine:
    return _engine
