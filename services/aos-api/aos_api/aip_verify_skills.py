"""AIP Verify Skills — 验证技能定义.

来源：Claude Blog — Verification Loops in Claude Code with skills
设计：每个验证技能只检查一个维度（单一职责），可链式组合。
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aos_api.aip_task_model import ActResult, VerifyResult


class VerifySkill(BaseModel):
    """验证技能 — 单一职责，可组合。

    遵循 Claude Blog 的 Verification Loop 设计：
    - 四种触发模式: standalone | embedded | chained | pr
    - 严重性分级: critical | high | medium | low
    - 自动修复优先
    """
    id: str = ""
    name: str = ""
    description: str = ""
    trigger: str = "embedded"  # standalone | embedded | chained | pr
    severity: str = "medium"  # critical | high | medium | low
    max_retries: int = 3
    auto_fix: str | None = None  # 自动修复策略名


class VerifySkillRegistry:
    """验证技能注册表 — 管理所有验证技能。

    Phase 1 只实现基本框架和默认验证技能。
    Phase 4 将完善所有数字同事的验证技能。
    """

    def __init__(self) -> None:
        self._skills: dict[str, list[VerifySkill]] = {}

    def register(self, action_type: str, skill: VerifySkill) -> None:
        if action_type not in self._skills:
            self._skills[action_type] = []
        self._skills[action_type].append(skill)

    def get_skills(self, action_type: str) -> list[VerifySkill]:
        return self._skills.get(action_type, [])

    def verify(
        self,
        action_type: str,
        act_result: ActResult,
        context: dict[str, Any] | None = None,
    ) -> VerifyResult:
        """执行验证技能链。

        Chained 模式：逐个执行验证技能，全部通过才返回 passed=True。
        失败时根据 severity 决定是否重试或停止。
        """
        skills = self.get_skills(action_type)
        issues: list[str] = []

        for skill in skills:
            issue = self._run_skill(skill, act_result, context)
            if issue:
                issues.append(f"[{skill.name}] {issue}")
                if skill.severity == "critical":
                    return VerifyResult(
                        passed=False,
                        should_retry=False,
                        is_fatal=True,
                        issues=issues,
                    )

        if issues:
            return VerifyResult(
                passed=False,
                should_retry=True,
                is_fatal=False,
                issues=issues,
            )

        return VerifyResult(passed=True)

    def _run_skill(
        self,
        skill: VerifySkill,
        act_result: ActResult,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """执行单个验证技能，返回问题描述（None 表示通过）。"""
        ctx = context or {}

        # ── 基本验证（Phase 1）──
        if skill.id == "verify-output-not-empty":
            if not act_result.output or not act_result.output.strip():
                return "输出为空"
            return None

        if skill.id == "verify-output-length":
            max_len = ctx.get("max_length", 500)
            if len(act_result.output) > max_len:
                return f"输出长度 {len(act_result.output)} 超过限制 {max_len}"
            return None

        if skill.id == "verify-no-error":
            if not act_result.success or act_result.error:
                return f"执行失败: {act_result.error or '未知错误'}"
            return None

        if skill.id == "verify-has-artifact":
            if not act_result.artifacts:
                return "没有产出 Artifact"
            return None

        # 默认：通过
        return None


# ── 默认验证技能 ──

def _init_default_skills() -> VerifySkillRegistry:
    """初始化默认验证技能。"""
    reg = VerifySkillRegistry()

    # LLM 调用的通用验证
    reg.register("llm_call", VerifySkill(
        id="verify-output-not-empty",
        name="输出非空检查",
        severity="high",
        auto_fix="regenerate",
    ))
    reg.register("llm_call", VerifySkill(
        id="verify-no-error",
        name="执行无错误检查",
        severity="critical",
    ))
    reg.register("llm_call", VerifySkill(
        id="verify-output-length",
        name="输出长度检查",
        severity="medium",
    ))

    # 工具调用的通用验证
    reg.register("tool_call", VerifySkill(
        id="verify-output-not-empty",
        name="工具输出非空",
        severity="high",
    ))
    reg.register("tool_call", VerifySkill(
        id="verify-has-artifact",
        name="工具产出检查",
        severity="medium",
    ))

    # 写回操作的验证
    reg.register("action_writeback", VerifySkill(
        id="verify-no-error",
        name="写回无错误",
        severity="critical",
    ))

    return reg


# ── Singleton ──

_registry: VerifySkillRegistry | None = None


def get_verify_registry() -> VerifySkillRegistry:
    global _registry
    if _registry is None:
        _registry = _init_default_skills()
    return _registry
